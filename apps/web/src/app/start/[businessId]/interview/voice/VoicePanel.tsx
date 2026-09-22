'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import type { BusinessInterviewData } from '@platform/contracts'
import { startVoiceSession } from '../actions'
import { VoiceConnection, type RealtimeSession, type VoiceState, type VoiceTranscriptLine } from './realtime'

const LABEL: Record<VoiceState, string> = {
  idle: 'Ready when you are',
  'requesting-mic': 'Waiting for your microphone',
  connecting: 'Connecting',
  listening: 'Listening',
  'user-speaking': 'Listening',
  thinking: 'Thinking',
  speaking: 'Speaking',
  reconnecting: 'Reconnecting',
  ended: 'Ended',
  failed: 'Voice stopped',
}

/**
 * Talking to Locah.
 *
 * The panel owns the microphone and the socket and nothing else. Every spoken
 * utterance goes to the same interview command the typed form sends, and what
 * comes back is both what Locah says next and what the summary beside it shows
 * — so there is exactly one Blueprint whichever way the owner is talking to it.
 *
 * The transcript here is a record of what was heard, not state. If voice drops,
 * nothing is lost, because nothing was ever being held here.
 */
export function VoicePanel({
  businessId,
  data,
  onTurn,
  onSwitchToChat,
}: {
  businessId: string
  data: BusinessInterviewData
  onTurn: (transcript: string) => Promise<{ say: string; sufficient: boolean }>
  onSwitchToChat: () => void
}) {
  const [state, setState] = useState<VoiceState>('idle')
  const [lines, setLines] = useState<VoiceTranscriptLine[]>([])
  const [error, setError] = useState('')
  const [muted, setMuted] = useState(false)
  const connection = useRef<VoiceConnection | null>(null)
  const stream = useRef<HTMLDivElement>(null)
  const turnRef = useRef(onTurn)
  turnRef.current = onTurn

  useEffect(() => {
    stream.current?.scrollTo({ top: stream.current.scrollHeight, behavior: 'smooth' })
  }, [lines.length])

  // The socket must not outlive the panel; a live microphone after someone
  // navigates away is the kind of bug people never forgive.
  useEffect(() => () => connection.current?.stop(), [])

  const begin = useCallback(async () => {
    setError('')
    setState('connecting')
    const minted = await startVoiceSession(businessId)
    if (!minted.ok) {
      setState('failed')
      setError(minted.error)
      return
    }
    const conn = new VoiceConnection({
      onState: setState,
      onTranscript: (line) => setLines((prev) => [...prev.slice(-40), line]),
      onTurn: (transcript) => turnRef.current(transcript),
      onError: setError,
      onMetric: (name, ms) => {
        if (process.env.NODE_ENV !== 'production') console.info(`[voice] ${name}=${ms}`)
      },
    })
    connection.current = conn
    await conn.start(minted.session as RealtimeSession)
  }, [businessId])

  const end = useCallback(() => {
    connection.current?.stop()
    connection.current = null
    setState('ended')
  }, [])

  const live = state !== 'idle' && state !== 'ended' && state !== 'failed'
  const sufficient = data.blueprint.completion_state.sufficient

  return (
    <div className="vp">
      <div className="vp-stage" data-state={state}>
        <span className="vp-orb" aria-hidden="true" />
        <p className="vp-state" role="status">
          {LABEL[state]}
        </p>
        {!live && !sufficient ? (
          <p className="vp-prompt">
            {state === 'failed'
              ? 'You can try again, or carry on by typing — nothing is lost either way.'
              : 'Tell Locah about your business out loud. You can interrupt at any time.'}
          </p>
        ) : null}
        {sufficient && live ? (
          <p className="vp-prompt">That’s enough to build with. Review what Locah understood below.</p>
        ) : null}
      </div>

      {error ? (
        <p className="ob-error" role="alert">
          {error}
        </p>
      ) : null}

      <div className="vp-controls">
        {!live ? (
          <button className="lc-btn lc-btn--primary lc-btn--lg" onClick={() => void begin()}>
            {state === 'ended' || state === 'failed' ? 'Start talking again' : 'Start talking'}
          </button>
        ) : (
          <>
            <button
              className="lc-btn"
              aria-pressed={muted}
              onClick={() => {
                const next = !muted
                setMuted(next)
                connection.current?.setMuted(next)
              }}
            >
              {muted ? 'Unmute' : 'Mute'}
            </button>
            <button className="lc-btn" onClick={end}>
              End
            </button>
          </>
        )}
        <button className="bi-text-button" onClick={onSwitchToChat}>
          Switch to typing
        </button>
      </div>

      {lines.length > 0 ? (
        <div className="vp-transcript" ref={stream} role="log" aria-live="polite">
          <p className="bi-eyebrow">WHAT LOCAH HEARD</p>
          {lines.map((line, i) => (
            <p className={`vp-line vp-line--${line.role}`} key={`${line.at}-${i}`}>
              <span>{line.role === 'assistant' ? 'LOCAH' : 'YOU'}</span> {line.text}
            </p>
          ))}
          <p className="ob-help vp-note">
            Heard something wrong? Switch to typing and correct it — the details Locah keeps are
            beside this, not in what was said.
          </p>
        </div>
      ) : null}
    </div>
  )
}
