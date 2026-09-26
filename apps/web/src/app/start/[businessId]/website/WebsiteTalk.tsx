'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import type { BusinessInterviewData } from '@platform/contracts'
import { MicIcon, SendIcon, StopIcon } from '@/components/onboarding/icons'
import { interviewAction, reloadInterview } from '../interview/actions'
import { useVoice } from '../interview/voice/useVoice'

const SUGGESTIONS = ['Make it warmer', 'Don’t show prices', 'Put delivery higher', 'Change the headline to …']
const VOICE_LABEL = {
  off: 'Talk to LOCAH',
  connecting: 'Connecting…',
  listening: 'Listening…',
  understanding: 'Understanding…',
  speaking: 'LOCAH is speaking…',
  failed: 'Voice stopped',
} as const

/**
 * The same conversation, after the website exists.
 *
 * Every message goes to the one interview command; after building, LOCAH
 * reads it for website edits ("make it warmer", "don't show prices", "we also
 * sell prawns") and changes structured state, never page source. `onChanged`
 * reloads the preview beside it.
 */
export function WebsiteTalk({
  initial,
  onChanged,
}: {
  initial: BusinessInterviewData
  onChanged: () => void
}) {
  const [data, setData] = useState(initial)
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const latest = useRef(initial)
  const chain = useRef<Promise<unknown>>(Promise.resolve())
  const log = useRef<HTMLDivElement>(null)
  const id = data.blueprint.business_id
  latest.current = data
  // Only what was said since the website was built, plus the moment it was.
  const built = data.blueprint.completion_state.first_preview_at
  const messages = data.blueprint.messages.filter((m) => !built || m.at >= built).slice(-12)

  useEffect(() => {
    log.current?.scrollTo({ top: log.current.scrollHeight, behavior: 'smooth' })
  }, [messages.length, busy])

  const post = useCallback(
    async (message: string, via: 'text' | 'voice' = 'text') => {
      const current = latest.current.blueprint
      const res = await interviewAction(id, {
        action: 'turn',
        text: message,
        via,
        revision: current.revision,
        request_id: crypto.randomUUID(),
      })
      if (!res.ok) {
        if (res.stale) {
          const again = await reloadInterview(id)
          if (again.ok) {
            latest.current = again.data
            setData(again.data)
          }
        }
        throw new Error(res.error)
      }
      latest.current = res.data
      setData(res.data)
      onChanged()
      return res.data
    },
    [id, onChanged]
  )

  async function send(message: string) {
    if (!message.trim() || busy) return
    setBusy(true)
    setError('')
    try {
      await post(message.trim())
      setText('')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'That didn’t go through — try again.')
    } finally {
      setBusy(false)
    }
  }

  const voice = useVoice({
    businessId: id,
    onTurn: (transcript) => {
      const run = async () => {
        try {
          const next = await post(transcript, 'voice')
          const reply = next.blueprint.messages.filter((m) => m.role === 'assistant').slice(-1)[0]?.text
          return { say: reply || 'Done.', sufficient: true }
        } catch {
          return { say: 'I couldn’t change that just now — could you say it again?', sufficient: true }
        }
      }
      const turn = chain.current.then(run, run)
      chain.current = turn.catch(() => undefined)
      return turn
    },
  })

  return (
    <aside className="wt" aria-label="Talk to LOCAH about your website">
      <div className="wt-head">
        <p className="wt-eyebrow">Talk to LOCAH</p>
        <p className="wt-sub">Say what to change — it updates the website beside you.</p>
      </div>
      <div className="wt-log" role="log" aria-live="polite" ref={log}>
        {messages.length === 0 ? (
          <p className="wt-empty">
            Try “make it warmer”, “don’t show prices” or “we also sell prawns”. Your own edits in the
            Workspace always win.
          </p>
        ) : (
          messages.map((m, i) => (
            <div key={`${m.at}-${i}`} className={`wt-msg wt-msg--${m.role}`}>
              <p>{m.text}</p>
            </div>
          ))
        )}
        {busy ? <p className="wt-working">Updating your website…</p> : null}
      </div>
      <div className="wt-chips" aria-label="Suggestions">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            type="button"
            disabled={busy}
            onClick={() => (s.endsWith('…') ? setText(s.replace(' …', ' ')) : void send(s))}
          >
            {s}
          </button>
        ))}
      </div>
      {error ? (
        <p className="wt-error" role="alert">
          {error}
        </p>
      ) : null}
      {voice.live || voice.phase === 'failed' ? (
        <div className="wt-voice" data-phase={voice.phase}>
          <span className="ti-voice__orb" aria-hidden="true" />
          <p role="status">
            <strong>{VOICE_LABEL[voice.phase]}</strong>
            <span>{voice.phase === 'speaking' ? voice.said : voice.heard}</span>
          </p>
          <button type="button" className="wt-stop" onClick={voice.stop} aria-label="Stop talking">
            <StopIcon />
          </button>
        </div>
      ) : (
        <form
          className="wt-compose"
          onSubmit={(e) => {
            e.preventDefault()
            void send(text)
          }}
        >
          <label className="lc-sr" htmlFor="wt-input">
            What should change?
          </label>
          <input
            id="wt-input"
            value={text}
            disabled={busy}
            placeholder="What should change?"
            onChange={(e) => setText(e.target.value)}
          />
          {data.voice.available ? (
            <button type="button" className="wt-icon" aria-label="Talk to LOCAH" onClick={() => void voice.start()}>
              <MicIcon />
            </button>
          ) : null}
          <button type="submit" className="wt-send" disabled={busy || !text.trim()} aria-label="Send">
            <SendIcon />
          </button>
        </form>
      )}
    </aside>
  )
}
