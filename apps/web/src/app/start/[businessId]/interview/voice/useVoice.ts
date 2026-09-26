'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { startVoiceSession } from '../actions'
import { GeminiLiveConnection, type GeminiLiveSession } from './gemini-live'
import { VoiceConnection, type RealtimeSession, type VoiceCallbacks, type VoiceState } from './realtime'
import { ReplayVoiceConnection, type ReplaySession } from './replay'

type Connection = VoiceConnection | GeminiLiveConnection | ReplayVoiceConnection

/** What the owner sees: four words, not a protocol. */
export type VoicePhase = 'off' | 'connecting' | 'listening' | 'understanding' | 'speaking' | 'failed'

const PHASE: Record<VoiceState, VoicePhase> = {
  idle: 'off',
  'requesting-mic': 'connecting',
  connecting: 'connecting',
  listening: 'listening',
  'user-speaking': 'listening',
  thinking: 'understanding',
  speaking: 'speaking',
  reconnecting: 'connecting',
  ended: 'off',
  failed: 'failed',
}

/**
 * Talking to LOCAH, as a hook the composer uses.
 *
 * It owns the microphone and the socket and nothing else. Every spoken
 * utterance is handed to `onTurn` — the same interview command a typed reply
 * uses — and what comes back is what LOCAH says. So there is one
 * conversation: talk, type, talk again, and nothing is lost, because nothing
 * was ever held here.
 */
export function useVoice({
  businessId,
  onTurn,
}: {
  businessId: string
  onTurn: (transcript: string) => Promise<{ say: string; sufficient: boolean }>
}) {
  const [phase, setPhase] = useState<VoicePhase>('off')
  const [heard, setHeard] = useState('')
  const [said, setSaid] = useState('')
  const [error, setError] = useState('')
  const connection = useRef<Connection | null>(null)
  const turnRef = useRef(onTurn)
  turnRef.current = onTurn

  // A live microphone after the owner leaves the page is never acceptable.
  useEffect(() => () => connection.current?.stop(), [])

  const start = useCallback(async () => {
    setError('')
    setHeard('')
    setSaid('')
    setPhase('connecting')
    const minted = await startVoiceSession(businessId)
    if (!minted.ok) {
      setPhase('failed')
      setError(minted.error)
      return
    }
    const callbacks: VoiceCallbacks = {
      onState: (state) => setPhase(PHASE[state]),
      onTranscript: (line) => (line.role === 'user' ? setHeard(line.text) : setSaid(line.text)),
      onTurn: (transcript) => turnRef.current(transcript),
      onError: (message) => setError(message),
      onMetric: (name, ms) => {
        if (process.env.NODE_ENV !== 'production') console.info(`[voice] ${name}=${ms}`)
      },
    }
    const session = minted.session as { provider?: string }
    try {
      if (session.provider === 'replay') {
        const conn = new ReplayVoiceConnection(callbacks)
        connection.current = conn
        await conn.start(session as ReplaySession)
      } else if (session.provider === 'gemini') {
        const conn = new GeminiLiveConnection(callbacks)
        connection.current = conn
        await conn.start(session as GeminiLiveSession)
      } else {
        const conn = new VoiceConnection(callbacks)
        connection.current = conn
        await conn.start(session as RealtimeSession)
      }
    } catch (e) {
      setPhase('failed')
      setError(e instanceof Error ? e.message : 'Voice stopped.')
    }
  }, [businessId])

  const stop = useCallback(() => {
    connection.current?.stop()
    connection.current = null
    setPhase('off')
  }, [])

  return { phase, heard, said, error, start, stop, live: phase !== 'off' && phase !== 'failed' }
}
