/**
 * The Gemini Live transport: microphone in, Locah's voice out, one tool across.
 *
 * Same contract as the xAI transport in `realtime.ts`: it moves audio and
 * events and knows nothing about businesses. Every spoken utterance reaches
 * Locah through `onTurn`, which posts it to the ordinary interview endpoint the
 * typed form uses, and what Locah decided comes back as the tool result the
 * model speaks. The model supplies ears, a voice and turn-taking — not truth.
 *
 * Protocol facts this relies on, checked against the Live API docs:
 *   - input is raw little-endian PCM16 at 16 kHz (`audio/pcm;rate=16000`);
 *   - output is PCM16 at 24 kHz;
 *   - the server's own activity detection sets `serverContent.interrupted`
 *     when the owner talks over Locah, and the client must stop playback and
 *     drop what is queued;
 *   - the ephemeral token carries the whole setup (instructions, tool, voice),
 *     so this file sends only the model name and cannot change them.
 */

import type { VoiceCallbacks, VoiceState } from './realtime'

export type GeminiLiveSession = {
  provider: 'gemini'
  token: string
  expires_at: number | null
  url: string
  model: string
  voice: string
  setup: Record<string, unknown>
}

const INPUT_RATE = 16000
const OUTPUT_RATE = 24000

type FunctionCall = { id?: string; name?: string; args?: Record<string, unknown> }

function encodeBase64(bytes: Uint8Array): string {
  let binary = ''
  for (let i = 0; i < bytes.length; i += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000))
  }
  return btoa(binary)
}

function decodeBase64(value: string): Uint8Array {
  const binary = atob(value)
  const bytes = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i)
  return bytes
}

export class GeminiLiveConnection {
  private ws: WebSocket | null = null
  private mic: MediaStream | null = null
  private captureCtx: AudioContext | null = null
  private playbackCtx: AudioContext | null = null
  private node: ScriptProcessorNode | null = null
  private queue: AudioBufferSourceNode[] = []
  private playHead = 0
  private muted = false
  private closedByUs = false
  private ready = false
  private handledCalls = new Set<string>()
  private cancelledCalls = new Set<string>()
  private userText = ''
  private assistantText = ''
  private turn = 0
  private toolResultAt = 0
  private speechEndedAt = 0

  constructor(private readonly cb: VoiceCallbacks) {}

  get isMuted(): boolean {
    return this.muted
  }

  async start(session: GeminiLiveSession, stream?: MediaStream): Promise<void> {
    this.closedByUs = false
    this.cb.onState('requesting-mic')
    try {
      this.mic =
        stream ??
        (await navigator.mediaDevices.getUserMedia({
          audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
        }))
    } catch {
      this.cb.onState('failed')
      this.cb.onError('Locah needs your microphone to talk. Allow it in your browser, or carry on in chat.')
      return
    }

    this.cb.onState('connecting')
    const openedAt = performance.now()
    await new Promise<void>((resolve) => {
      const ws = new WebSocket(`${session.url}?access_token=${encodeURIComponent(session.token)}`)
      this.ws = ws
      ws.onopen = () => {
        this.cb.onMetric('time_to_connect_ms', Math.round(performance.now() - openedAt))
        ws.send(JSON.stringify({ setup: session.setup }))
      }
      ws.onmessage = async (event) => {
        const raw = typeof event.data === 'string' ? event.data : await (event.data as Blob).text()
        let message: Record<string, any>
        try {
          message = JSON.parse(raw)
        } catch {
          return
        }
        if (message.setupComplete !== undefined && !this.ready) {
          this.ready = true
          this.cb.onMetric('time_to_ready_ms', Math.round(performance.now() - openedAt))
          this.startCapture()
          this.cb.onState('listening')
          resolve()
          return
        }
        await this.handle(message)
      }
      ws.onerror = () => {
        if (!this.closedByUs) this.cb.onError('The voice connection had a problem.')
      }
      ws.onclose = (event) => {
        this.stopCapture()
        this.stopPlayback()
        if (!this.closedByUs) {
          this.cb.onState('failed')
          const quota = /quota|exhaust|limit/i.test(event.reason || '')
          this.cb.onError(
            quota
              ? 'Voice is busy right now. Your answers are saved — carry on in chat.'
              : 'The voice connection dropped. Your answers are saved — carry on in chat.'
          )
        }
        resolve()
      }
    })
  }

  private startCapture(): void {
    if (!this.mic) return
    const ctx = new AudioContext({ sampleRate: INPUT_RATE })
    this.captureCtx = ctx
    const source = ctx.createMediaStreamSource(this.mic)
    // 1024 frames at 16 kHz is 64 ms: small enough that the end of a sentence
    // reaches the server promptly, large enough not to flood the socket.
    const node = ctx.createScriptProcessor(1024, 1, 1)
    this.node = node
    node.onaudioprocess = (event) => {
      if (this.muted || !this.ready || !this.ws || this.ws.readyState !== WebSocket.OPEN) return
      const input = event.inputBuffer.getChannelData(0)
      const pcm = new Int16Array(input.length)
      for (let i = 0; i < input.length; i += 1) {
        const clamped = Math.max(-1, Math.min(1, input[i]))
        pcm[i] = clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff
      }
      this.ws.send(
        JSON.stringify({
          realtimeInput: {
            audio: { data: encodeBase64(new Uint8Array(pcm.buffer)), mimeType: `audio/pcm;rate=${INPUT_RATE}` },
          },
        })
      )
    }
    source.connect(node)
    node.connect(ctx.destination)
  }

  private stopCapture(): void {
    this.node?.disconnect()
    this.node = null
    void this.captureCtx?.close().catch(() => {})
    this.captureCtx = null
    this.mic?.getTracks().forEach((track) => track.stop())
    this.mic = null
  }

  /** Cut Locah off mid-word. The owner started talking; they come first. */
  private stopPlayback(): void {
    this.queue.forEach((source) => {
      try {
        source.stop()
      } catch {
        /* already finished */
      }
    })
    this.queue = []
    this.playHead = 0
  }

  private play(bytes: Uint8Array): void {
    if (!this.playbackCtx) this.playbackCtx = new AudioContext({ sampleRate: OUTPUT_RATE })
    const ctx = this.playbackCtx
    const pcm = new Int16Array(bytes.buffer, bytes.byteOffset, Math.floor(bytes.byteLength / 2))
    const buffer = ctx.createBuffer(1, pcm.length, OUTPUT_RATE)
    const channel = buffer.getChannelData(0)
    for (let i = 0; i < pcm.length; i += 1) channel[i] = pcm[i] / 0x8000
    const source = ctx.createBufferSource()
    source.buffer = buffer
    source.connect(ctx.destination)
    const startAt = Math.max(ctx.currentTime, this.playHead)
    source.start(startAt)
    this.playHead = startAt + buffer.duration
    this.queue.push(source)
    source.onended = () => {
      this.queue = this.queue.filter((item) => item !== source)
      if (this.queue.length === 0 && this.ws?.readyState === WebSocket.OPEN) this.setState('listening')
    }
  }

  private state: VoiceState = 'idle'
  private setState(next: VoiceState): void {
    if (this.state === next) return
    this.state = next
    this.cb.onState(next)
  }

  private send(payload: Record<string, unknown>): void {
    if (this.ws?.readyState === WebSocket.OPEN) this.ws.send(JSON.stringify(payload))
  }

  private async handle(message: Record<string, any>): Promise<void> {
    const content = message.serverContent
    if (content) {
      if (content.interrupted) {
        // Barge-in: drop everything already queued, never replay it.
        this.stopPlayback()
        this.finishAssistantLine()
        this.setState('user-speaking')
      }
      const heard = content.inputTranscription?.text
      if (typeof heard === 'string' && heard) {
        this.userText += heard
        this.cb.onTranscript({ role: 'user', text: this.userText.trim(), at: Date.now(), id: `u${this.turn}` })
        this.setState('user-speaking')
        this.speechEndedAt = performance.now()
      }
      const parts = content.modelTurn?.parts
      if (Array.isArray(parts)) {
        for (const part of parts) {
          const data = part?.inlineData?.data
          if (typeof data === 'string' && data) {
            if (this.toolResultAt) {
              this.cb.onMetric('tool_result_to_first_audio_ms', Math.round(performance.now() - this.toolResultAt))
              this.toolResultAt = 0
            } else if (this.speechEndedAt) {
              this.cb.onMetric('speech_to_first_audio_ms', Math.round(performance.now() - this.speechEndedAt))
              this.speechEndedAt = 0
            }
            this.setState('speaking')
            this.play(decodeBase64(data))
          }
        }
      }
      const said = content.outputTranscription?.text
      if (typeof said === 'string' && said) {
        this.assistantText += said
        this.cb.onTranscript({
          role: 'assistant',
          text: this.assistantText.trim(),
          at: Date.now(),
          id: `a${this.turn}`,
        })
      }
      if (content.turnComplete) {
        this.finishUserLine()
        this.finishAssistantLine()
        this.turn += 1
        if (this.queue.length === 0) this.setState('listening')
      }
    }

    if (message.toolCall) {
      const calls: FunctionCall[] = Array.isArray(message.toolCall.functionCalls)
        ? message.toolCall.functionCalls
        : []
      for (const call of calls) await this.answer(call)
    }

    if (message.toolCallCancellation) {
      const ids: unknown[] = Array.isArray(message.toolCallCancellation.ids) ? message.toolCallCancellation.ids : []
      ids.forEach((id) => this.cancelledCalls.add(String(id)))
    }

    if (message.goAway) {
      this.cb.onError('This voice session is about to end. Your answers are saved — start again or carry on in chat.')
    }
  }

  /** The one place the model reaches into Locah. It gets back what Locah decided. */
  private async answer(call: FunctionCall): Promise<void> {
    const id = String(call.id || '')
    if (!id || this.handledCalls.has(id)) return
    this.handledCalls.add(id)
    const transcript = String(call.args?.transcript || '').trim()
    this.finishUserLine(transcript)
    this.setState('thinking')
    const started = performance.now()
    let result = { say: 'Sorry, could you say that once more?', sufficient: false }
    if (transcript) {
      try {
        result = await this.cb.onTurn(transcript)
      } catch {
        result = { say: 'I could not save that just now. Could you say it again?', sufficient: false }
      }
    }
    this.cb.onMetric('tool_latency_ms', Math.round(performance.now() - started))
    if (this.cancelledCalls.has(id)) return
    this.toolResultAt = performance.now()
    this.send({
      toolResponse: {
        functionResponses: [{ id, name: call.name || 'process_business_interview_turn', response: result }],
      },
    })
  }

  private finishUserLine(authoritative?: string): void {
    const text = (this.userText || authoritative || '').trim()
    if (text) this.cb.onTranscript({ role: 'user', text, at: Date.now(), id: `u${this.turn}`, final: true })
    this.userText = ''
  }

  private finishAssistantLine(): void {
    const text = this.assistantText.trim()
    if (text) this.cb.onTranscript({ role: 'assistant', text, at: Date.now(), id: `a${this.turn}`, final: true })
    this.assistantText = ''
  }

  setMuted(muted: boolean): void {
    this.muted = muted
    if (muted) {
      this.stopPlayback()
      // Tell the server the stream paused so it does not wait on silence.
      this.send({ realtimeInput: { audioStreamEnd: true } })
    }
  }

  stop(): void {
    this.closedByUs = true
    this.stopPlayback()
    this.stopCapture()
    void this.playbackCtx?.close().catch(() => {})
    this.playbackCtx = null
    try {
      this.ws?.close()
    } catch {
      /* already closed */
    }
    this.ws = null
    this.setState('ended')
  }
}
