/**
 * What every voice transport shares (Gemini Live, and the replay used in local
 * acceptance runs). A transport moves audio and events and hands each spoken
 * utterance to `onTurn` — the ordinary interview command — and never decides
 * what Locah says.
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
  /** Stable item id, used to replace live captions instead of duplicating them. */
  id?: string
  final?: boolean
}

export type VoiceCallbacks = {
  onState: (state: VoiceState) => void
  onTranscript: (line: VoiceTranscriptLine) => void
  /** Returns what Locah decided, which becomes the tool result the model speaks. */
  onTurn: (transcript: string) => Promise<{ say: string; sufficient: boolean }>
  onError: (message: string) => void
  onMetric: (name: string, ms: number) => void
}
