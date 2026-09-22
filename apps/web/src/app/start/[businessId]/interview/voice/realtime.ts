/**
 * The xAI realtime transport: microphone in, Locah's voice out, tool calls across.
 *
 * Deliberately knows nothing about businesses. It moves audio and events, and it
 * hands every spoken utterance to a callback that posts it to the ordinary
 * interview endpoint — the same one the typed form posts to. What Locah says
 * next is whatever that endpoint returns; this file never decides it.
 *
 * Verified against the live API rather than assumed: the socket authenticates
 * with a short-lived client secret passed as a WebSocket subprotocol (a browser
 * cannot set an Authorization header), the session reports model
 * `grok-voice-think-fast-2.0` and voice `xai_ara`, and turn detection is off
 * until `session.update` asks for it.
 */

export type VoiceState =
  | 'idle'
  | 'requesting-mic'
  | 'connecting'
  | 'listening'
  | 'user-speaking'
  | 'thinking'
  | 'speaking'
  | 'reconnecting'
  | 'ended'
  | 'failed'

export type VoiceTranscriptLine = {
  role: 'user' | 'assistant'
  text: string
  at: number
  /** Stable realtime item id, used to replace live captions instead of duplicating them. */
  id?: string
  final?: boolean
}

export type RealtimeSession = {
  client_secret: string
  expires_at: number | null
  url: string
  model: string
  voice: string
  session: Record<string, unknown>
}

export type VoiceCallbacks = {
  onState: (state: VoiceState) => void
  onTranscript: (line: VoiceTranscriptLine) => void
  /** Returns what Locah decided, which becomes the tool result the model speaks. */
  onTurn: (transcript: string) => Promise<{ say: string; sufficient: boolean }>
  onError: (message: string) => void
  onMetric: (name: string, ms: number) => void
}

// The realtime stream is 24 kHz mono PCM16 in both directions.
const SAMPLE_RATE = 24000

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

export class VoiceConnection {
  private ws: WebSocket | null = null
  private mic: MediaStream | null = null
  private captureCtx: AudioContext | null = null
  private playbackCtx: AudioContext | null = null
  private node: ScriptProcessorNode | null = null
  private queue: AudioBufferSourceNode[] = []
  private playHead = 0
  private muted = false
  private closedByUs = false
  private speechStartedAt = 0
  private speechStoppedAt = 0
  private toolStartedAt = 0
  private toolResultAt = 0
  private firstAudioAfterTool = false
  private activeResponse = false
  private activeAssistantItemId: string | null = null
  private assistantPlaybackStartedAt = 0
  private finalTranscriptItems = new Set<string>()

  constructor(private readonly cb: VoiceCallbacks) {}

  get isMuted(): boolean {
    return this.muted
  }

  async start(session: RealtimeSession): Promise<void> {
    this.closedByUs = false
    this.cb.onState('requesting-mic')
    try {
      this.mic = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
      })
    } catch {
      this.cb.onState('failed')
      this.cb.onError(
        'Locah needs your microphone to talk. Allow it in your browser, or carry on in chat.'
      )
      return
    }

    this.cb.onState('connecting')
    const openedAt = performance.now()
    await new Promise<void>((resolve) => {
      // The secret travels as a subprotocol because browsers cannot set headers
      // on a WebSocket. It is short-lived and single-use; the account key never
      // leaves the server.
      const ws = new WebSocket(session.url, [`xai-client-secret.${session.client_secret}`])
      this.ws = ws
      ws.onopen = () => {
        this.cb.onMetric('time_to_connect_ms', Math.round(performance.now() - openedAt))
        ws.send(JSON.stringify({ type: 'session.update', session: session.session }))
        this.startCapture()
        this.cb.onState('listening')
        resolve()
      }
      ws.onmessage = (event) => void this.handle(JSON.parse(String(event.data)))
      ws.onerror = () => {
        if (!this.closedByUs) this.cb.onError('The voice connection had a problem.')
      }
      ws.onclose = () => {
        this.stopCapture()
        if (!this.closedByUs) {
          this.cb.onState('failed')
          this.cb.onError(
            'The voice connection dropped. Your answers are saved — carry on in chat.'
          )
        }
        resolve()
      }
    })
  }

  private startCapture(): void {
    if (!this.mic) return
    const ctx = new AudioContext({ sampleRate: SAMPLE_RATE })
    this.captureCtx = ctx
    const source = ctx.createMediaStreamSource(this.mic)
    // ScriptProcessor is deprecated but is the one path that works without
    // shipping a separate worklet file; the buffer is small enough that the
    // main-thread cost is not audible.
    const node = ctx.createScriptProcessor(2048, 1, 1)
    this.node = node
    node.onaudioprocess = (event) => {
      if (this.muted || !this.ws || this.ws.readyState !== WebSocket.OPEN) return
      const input = event.inputBuffer.getChannelData(0)
      const pcm = new Int16Array(input.length)
      for (let i = 0; i < input.length; i += 1) {
        const clamped = Math.max(-1, Math.min(1, input[i]))
        pcm[i] = clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff
      }
      this.ws.send(
        JSON.stringify({
          type: 'input_audio_buffer.append',
          audio: encodeBase64(new Uint8Array(pcm.buffer)),
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

  /** Cut playback dead. Used when the owner talks over Locah. */
  private stopPlayback(): boolean {
    const hadPlayback = this.queue.length > 0
    this.queue.forEach((source) => {
      try {
        source.stop()
      } catch {
        /* already finished */
      }
    })
    this.queue = []
    this.playHead = 0
    return hadPlayback
  }

  private play(bytes: Uint8Array): void {
    if (!this.playbackCtx) this.playbackCtx = new AudioContext({ sampleRate: SAMPLE_RATE })
    const ctx = this.playbackCtx
    const pcm = new Int16Array(bytes.buffer, bytes.byteOffset, bytes.byteLength / 2)
    const buffer = ctx.createBuffer(1, pcm.length, SAMPLE_RATE)
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
      if (this.queue.length === 0 && !this.activeResponse) {
        this.activeAssistantItemId = null
        this.assistantPlaybackStartedAt = 0
      }
    }
  }

  private send(payload: Record<string, unknown>): void {
    if (this.ws?.readyState === WebSocket.OPEN) this.ws.send(JSON.stringify(payload))
  }

  private async handle(event: Record<string, any>): Promise<void> {
    switch (event.type) {
      case 'input_audio_buffer.speech_started': {
        // Barge-in: the owner started talking, so Locah stops immediately and
        // the audio already queued is dropped rather than played out. Only
        // cancel when a response exists: cancelling the first user turn is a
        // protocol error and used to show a false failure in the UI.
        this.speechStartedAt = performance.now()
        this.speechStoppedAt = 0
        const interruptionStartedAt = performance.now()
        const interruptedPlayback = this.stopPlayback()
        if (this.activeResponse) this.send({ type: 'response.cancel' })
        if (interruptedPlayback && this.activeAssistantItemId) {
          const playedMs = this.assistantPlaybackStartedAt
            ? Math.max(0, Math.round(performance.now() - this.assistantPlaybackStartedAt))
            : 0
          this.send({
            type: 'conversation.item.truncate',
            item_id: this.activeAssistantItemId,
            content_index: 0,
            audio_end_ms: playedMs,
          })
          this.cb.onMetric(
            'interruption_latency_ms',
            Math.round(performance.now() - interruptionStartedAt)
          )
        }
        this.cb.onState('user-speaking')
        break
      }

      case 'input_audio_buffer.speech_stopped':
        this.speechStoppedAt = performance.now()
        this.cb.onState('thinking')
        break

      case 'conversation.item.input_audio_transcription.updated': {
        const text = String(event.transcript || '').trim()
        if (text) {
          this.cb.onTranscript({
            role: 'user',
            text,
            at: Date.now(),
            id: String(event.item_id || `speech-${this.speechStartedAt}`),
            final: false,
          })
        }
        break
      }

      case 'conversation.item.input_audio_transcription.completed':
      case 'conversation.item.input_audio_transcription.done': {
        const text = String(event.transcript || '').trim()
        const id = String(event.item_id || `speech-${this.speechStartedAt}`)
        if (text && !this.finalTranscriptItems.has(id)) {
          // Despite its name, xAI currently emits cumulative `completed`
          // events while speech is still arriving. Treat them as captions
          // until VAD has ended the turn; the event after `speech_stopped` is
          // the authoritative transcript and latency boundary.
          const final = this.speechStoppedAt > 0
          this.cb.onTranscript({ role: 'user', text, at: Date.now(), id, final })
          if (final) {
            this.finalTranscriptItems.add(id)
            this.cb.onMetric(
              'speech_end_to_final_transcript_ms',
              Math.round(performance.now() - this.speechStoppedAt)
            )
          }
        }
        break
      }

      // xAI names these `response.output_audio*`, not the `response.audio*` the
      // OpenAI-shaped docs suggest. Verified against the live socket: listening
      // for the wrong name is silent failure — the session looks healthy and
      // Locah simply never speaks. Both spellings are accepted so a rename
      // upstream cannot mute the product again.
      case 'response.output_audio.delta':
      case 'response.audio.delta':
        if (typeof event.delta === 'string') {
          if (!this.assistantPlaybackStartedAt) this.assistantPlaybackStartedAt = performance.now()
          if (this.toolResultAt && !this.firstAudioAfterTool) {
            this.firstAudioAfterTool = true
            this.cb.onMetric(
              'tool_result_to_first_audio_ms',
              Math.round(performance.now() - this.toolResultAt)
            )
          }
          this.cb.onState('speaking')
          this.play(decodeBase64(event.delta))
        }
        break

      case 'response.output_audio_transcript.done':
      case 'response.audio_transcript.done':
      case 'response.text.done': {
        const text = String(event.transcript || event.text || '').trim()
        if (text) this.cb.onTranscript({ role: 'assistant', text, at: Date.now() })
        break
      }

      case 'response.function_call_arguments.done': {
        // The one place the model reaches into Locah. It gets back whatever the
        // interview endpoint decided, and nothing else.
        this.toolStartedAt = performance.now()
        let transcript = ''
        try {
          transcript = String(JSON.parse(event.arguments || '{}').transcript || '')
        } catch {
          transcript = ''
        }
        let result = { say: 'Sorry, could you say that once more?', sufficient: false }
        if (transcript.trim()) {
          try {
            result = await this.cb.onTurn(transcript)
          } catch {
            result = {
              say: 'I could not save that just now. Could you say it again?',
              sufficient: false,
            }
          }
        }
        this.cb.onMetric(
          'transcript_to_interview_result_ms',
          Math.round(performance.now() - this.toolStartedAt)
        )
        this.send({
          type: 'conversation.item.create',
          item: {
            type: 'function_call_output',
            call_id: event.call_id,
            output: JSON.stringify(result),
          },
        })
        this.toolResultAt = performance.now()
        this.firstAudioAfterTool = false
        this.send({ type: 'response.create' })
        break
      }

      case 'response.created':
        this.activeResponse = true
        this.activeAssistantItemId = null
        this.assistantPlaybackStartedAt = 0
        break

      case 'response.output_item.added':
        if (event.item?.type === 'message' && event.item?.id) {
          this.activeAssistantItemId = String(event.item.id)
        }
        break

      case 'response.done':
        this.activeResponse = false
        if (this.ws?.readyState === WebSocket.OPEN) this.cb.onState('listening')
        break

      case 'error':
        this.cb.onError('Locah had trouble hearing you. You can carry on in chat.')
        break

      default:
        break
    }
  }

  setMuted(muted: boolean): void {
    this.muted = muted
    if (muted) this.stopPlayback()
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
    this.cb.onState('ended')
  }
}
