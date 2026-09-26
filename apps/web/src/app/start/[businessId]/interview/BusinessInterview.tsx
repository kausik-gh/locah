'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import type { BusinessInterviewData, InterviewCommand } from '@platform/contracts'
import { ClipIcon, MicIcon, SendIcon, StopIcon } from '@/components/onboarding/icons'
import {
  finishInterviewUpload,
  interviewAction,
  reloadInterview,
  startInterviewUpload,
} from './actions'
import { ROLE_LABELS, ROLE_ORDER, roleFromText, type MediaRole } from './attachment'
import { BuildOverlay, ConfirmSheet } from './ConfirmSheet'
import { Progress, UnderstandingPanel, type Correct } from './UnderstandingPanel'
import { useVoice } from './voice/useVoice'

type Change = Omit<InterviewCommand, 'revision' | 'request_id'>
/** An image that is uploaded and waiting only for the owner to say what it is. */
type Staged = { assetId: string; filename: string }

const VOICE_LABEL = {
  off: 'Talk to LOCAH',
  connecting: 'Connecting…',
  listening: 'Listening…',
  understanding: 'Understanding…',
  speaking: 'LOCAH is speaking…',
  failed: 'Voice stopped',
} as const

/**
 * Talk to LOCAH — the one conversation behind Create Business.
 *
 * Typing and talking post the same command and read back the same state, so
 * the owner can talk, type, talk again and attach a photo without losing
 * anything. Build is offered as soon as there is something honest to build
 * and never withdrawn; pressing it shows the understanding once, whole, then
 * builds. The side panel is typed understanding with structured corrections.
 */
export function BusinessInterview({ initial }: { initial: BusinessInterviewData }) {
  const [data, setData] = useState(initial)
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [sending, setSending] = useState('')
  const [staged, setStaged] = useState<Staged | null>(null)
  const [uploading, setUploading] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const [sheet, setSheet] = useState(false) // mobile "What I understand"
  const [build, setBuild] = useState<{ stage: number; error: string } | null>(null)
  const latest = useRef(initial)
  const busyRef = useRef(false)
  const voiceChain = useRef<Promise<unknown>>(Promise.resolve())
  const stream = useRef<HTMLDivElement>(null)
  const input = useRef<HTMLTextAreaElement>(null)
  const panel = useRef<HTMLDivElement>(null)
  const router = useRouter()
  const params = useSearchParams()
  const bp = data.blueprint
  const u = data.understanding
  latest.current = data
  const buildable = Boolean(data.build_available)
  const built = bp.completion_state.status === 'built'

  const apply = useCallback((next: BusinessInterviewData) => {
    latest.current = next
    setData(next)
  }, [])

  async function send(change: Change): Promise<boolean> {
    setBusy(true)
    busyRef.current = true
    setError('')
    if (change.action === 'turn' && change.text) setSending(change.text)
    try {
      const res = await interviewAction(bp.business_id, {
        ...change,
        revision: latest.current.blueprint.revision,
        request_id: crypto.randomUUID(),
      })
      if (!res.ok) {
        setError(res.error)
        if (res.stale) {
          const again = await reloadInterview(bp.business_id)
          if (again.ok) apply(again.data)
        }
        return false
      }
      apply(res.data)
      if (change.action === 'turn') setText('')
      return true
    } catch {
      setError('That didn’t save. Your earlier answers are safe — please try again.')
      return false
    } finally {
      setBusy(false)
      busyRef.current = false
      setSending('')
    }
  }

  /**
   * A spoken turn: exactly the command a typed one uses. What LOCAH says next
   * is whatever the interview decided — the voice model is told what to say.
   */
  const speakTurn = useCallback(
    (transcript: string): Promise<{ say: string; sufficient: boolean }> => {
      const run = async () => {
        const current = latest.current.blueprint
        const res = await interviewAction(current.business_id, {
          action: 'turn',
          text: transcript,
          via: 'voice',
          revision: current.revision,
          request_id: crypto.randomUUID(),
        })
        if (!res.ok) {
          if (res.stale) {
            const again = await reloadInterview(current.business_id)
            if (again.ok) apply(again.data)
          }
          return { say: 'I couldn’t save that just now — could you say it once more?', sufficient: false }
        }
        apply(res.data)
        const reply = res.data.blueprint.messages.filter((m) => m.role === 'assistant').slice(-1)[0]?.text
        return {
          say: reply || 'Tell me a little more about your business.',
          sufficient: Boolean(res.data.blueprint.completion_state.ready_at),
        }
      }
      const turn = voiceChain.current.then(run, run)
      voiceChain.current = turn.catch(() => undefined)
      return turn
    },
    [apply]
  )

  const voice = useVoice({ businessId: bp.business_id, onTurn: speakTurn })

  // "Talk to LOCAH" on the first screen lands here ready to listen.
  const autoTalk = useRef(false)
  useEffect(() => {
    if (autoTalk.current) return
    autoTalk.current = true
    if (params.get('talk') === '1' && data.voice.available) void voice.start()
    const retry = params.get('retry')
    if (retry) setText(retry)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // The owner said "build it": show them what will be built.
  useEffect(() => {
    if (bp.confirm_requested && buildable && !built) setConfirming(true)
  }, [bp.confirm_requested, buildable, built])

  useEffect(() => {
    stream.current?.scrollTo({ top: stream.current.scrollHeight, behavior: 'smooth' })
  }, [bp.messages.length, sending, voice.heard, voice.phase])

  const correct: Correct = (slot, values, fieldText) =>
    send({ action: 'correct', slot, values, ...(fieldText ? { text: fieldText } : {}) })

  async function startBuild() {
    setConfirming(false)
    setBuild({ stage: 1, error: '' })
    const ok = await send({ action: 'build' })
    if (!ok) {
      setBuild({ stage: 1, error: 'Your website wasn’t built. Nothing was lost — try again.' })
      return
    }
    setBuild({ stage: 3, error: '' })
    router.push(`/start/${bp.business_id}/website`)
  }

  /** Upload now so it overlaps with typing; ask what it is only if the words don't say. */
  async function attach(file: File) {
    setUploading(true)
    setError('')
    try {
      if (file.size > 10 * 1024 * 1024) throw new Error('Choose an image smaller than 10 MB.')
      const guess = roleFromText(text)
      const start = await startInterviewUpload(bp.business_id, guess ?? 'business', file.type, file.size, file.name)
      if (!start.ok) throw new Error(start.error)
      // Supabase's signed upload expects the multipart body its own client sends.
      const body = new FormData()
      body.append('cacheControl', '3600')
      body.append('', file)
      const uploaded = await fetch(start.uploadUrl, { method: 'PUT', headers: { 'x-upsert': 'false' }, body })
      if (!uploaded.ok) throw new Error('The image didn’t upload. Please try again.')
      const complete = await finishInterviewUpload(bp.business_id, start.assetId)
      if (!complete.ok) throw new Error(complete.error)
      if (guess) await saveAttachment(start.assetId, file.name, guess)
      else setStaged({ assetId: start.assetId, filename: file.name })
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Image upload failed.')
    } finally {
      setUploading(false)
    }
  }

  async function saveAttachment(assetId: string, filename: string, role: MediaRole) {
    const ok = await send({ action: 'media', media: { asset_id: assetId, role, label: filename, source: 'USER_UPLOAD' } })
    if (ok) setStaged(null)
  }

  const submit = () => {
    if (text.trim() && !busy) void send({ action: 'turn', text: text.trim() })
  }
  const waiting = busy && Boolean(sending)
  const lastAssistant = bp.messages.map((m) => m.role).lastIndexOf('assistant')
  const checkpointAt = bp.checkpoint_turn != null ? bp.checkpoint_turn * 2 : -1
  const showCheckpoint = buildable && !built && checkpointAt === lastAssistant && !bp.refining && !waiting
  const title = u.business.name || 'Your business'
  const kindLine = [u.business.category, u.business.place].filter(Boolean).join(' · ')

  return (
    <div className="ti">
      <header className="ti-bar">
        <div className="ti-bar__who">
          <p className="ti-bar__name">{title}</p>
          {kindLine ? <p className="ti-bar__kind">{kindLine}</p> : null}
        </div>
        <Progress data={data} compact />
        <button type="button" className="ti-bar__panel" onClick={() => setSheet(true)}>
          What I understand
        </button>
        {buildable && !built ? (
          <button type="button" className="lc-btn lc-btn--primary ti-bar__build" disabled={busy} onClick={() => setConfirming(true)}>
            Build my website
          </button>
        ) : built ? (
          <a className="lc-btn lc-btn--primary ti-bar__build" href={`/start/${bp.business_id}/website`}>
            Open your website
          </a>
        ) : null}
      </header>

      <div className="ti-layout">
        <section className="ti-chat" aria-label="Conversation with LOCAH">
          <div className="ti-log" role="log" aria-live="polite" aria-relevant="additions" ref={stream}>
            {bp.messages.map((m, i) => (
              <div key={`${m.at}-${i}`} className={`ti-msg ti-msg--${m.role}`}>
                {m.role === 'assistant' ? (
                  <span className="ti-msg__who" aria-hidden="true">
                    <i />
                    LOCAH
                  </span>
                ) : null}
                <p>{m.text}</p>
                {m.role === 'user' && m.via === 'voice' ? (
                  <span className="ti-msg__via">
                    <MicIcon size={12} /> spoken
                  </span>
                ) : null}
                {i === checkpointAt && showCheckpoint ? (
                  <div className="ti-checkpoint">
                    <button type="button" className="lc-btn lc-btn--primary" disabled={busy} onClick={() => setConfirming(true)}>
                      Build my website
                    </button>
                    <button type="button" className="lc-btn lc-btn--ghost" disabled={busy} onClick={() => void send({ action: 'refine' })}>
                      Keep refining
                    </button>
                  </div>
                ) : null}
              </div>
            ))}
            {waiting ? (
              <>
                <div className="ti-msg ti-msg--user ti-msg--pending">
                  <p>{sending}</p>
                </div>
                <div className="ti-msg ti-msg--assistant ti-thinking" aria-label="LOCAH is reading your answer">
                  <span className="ti-msg__who" aria-hidden="true">
                    <i />
                    LOCAH
                  </span>
                  <p>
                    <b />
                    <b />
                    <b />
                  </p>
                </div>
              </>
            ) : null}
            {voice.live && voice.heard && voice.phase === 'listening' ? (
              <div className="ti-msg ti-msg--user ti-msg--pending">
                <p>{voice.heard}</p>
              </div>
            ) : null}
          </div>

          {error ? (
            <p className="ti-error" role="alert">
              {error}
            </p>
          ) : null}

          {staged ? (
            <div className="ti-staged" role="group" aria-label="What is this image?">
              <p>
                <strong>{staged.filename}</strong> is ready. What is it?
              </p>
              <div>
                {ROLE_ORDER.map((role) => (
                  <button
                    key={role}
                    type="button"
                    className="lc-btn lc-btn--sm lc-btn--ghost"
                    disabled={busy}
                    onClick={() => void saveAttachment(staged.assetId, staged.filename, role)}
                  >
                    {ROLE_LABELS[role]}
                  </button>
                ))}
              </div>
            </div>
          ) : null}

          {buildable && !built ? (
            <button type="button" className="ti-float-build lc-btn lc-btn--primary" disabled={busy} onClick={() => setConfirming(true)}>
              Build my website
            </button>
          ) : null}

          {voice.live || voice.phase === 'failed' ? (
            <div className="ti-voice" data-phase={voice.phase}>
              <span className="ti-voice__orb" aria-hidden="true" />
              <div className="ti-voice__text">
                <p className="ti-voice__state" role="status">
                  {VOICE_LABEL[voice.phase]}
                </p>
                <p className="ti-voice__line">
                  {voice.phase === 'failed'
                    ? voice.error || 'Voice stopped. Nothing is lost — try again or type.'
                    : voice.phase === 'speaking'
                      ? voice.said
                      : voice.heard || 'Say it the way you’d tell a friend.'}
                </p>
              </div>
              <div className="ti-voice__actions">
                {voice.phase === 'failed' ? (
                  <button type="button" className="lc-btn lc-btn--sm" onClick={() => void voice.start()}>
                    Retry
                  </button>
                ) : (
                  <button type="button" className="ti-voice__stop" onClick={voice.stop} aria-label="Stop talking">
                    <StopIcon />
                  </button>
                )}
                <button
                  type="button"
                  className="ti-link"
                  onClick={() => {
                    voice.stop()
                    input.current?.focus()
                  }}
                >
                  Type instead
                </button>
              </div>
            </div>
          ) : (
            <form
              className="ti-compose"
              onSubmit={(e) => {
                e.preventDefault()
                submit()
              }}
            >
              <label className="lc-sr" htmlFor="ti-input">
                Your reply
              </label>
              <textarea
                id="ti-input"
                ref={input}
                value={text}
                rows={1}
                maxLength={4000}
                disabled={busy}
                placeholder={built ? 'Tell LOCAH what to change…' : 'Reply in your own words…'}
                onChange={(e) => {
                  setText(e.target.value)
                  e.target.style.height = 'auto'
                  e.target.style.height = `${Math.min(e.target.scrollHeight, 180)}px`
                }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    submit()
                  }
                }}
              />
              <div className="ti-compose__tools">
                <label className="ti-icon" title="Attach a photo or logo">
                  <ClipIcon />
                  <span className="lc-sr">{uploading ? 'Uploading…' : 'Attach a photo or logo'}</span>
                  <input
                    type="file"
                    accept="image/jpeg,image/png,image/webp,image/gif"
                    disabled={busy || uploading}
                    onChange={(e) => {
                      const file = e.target.files?.[0]
                      if (file) void attach(file)
                      e.target.value = ''
                    }}
                  />
                </label>
                {data.voice.available ? (
                  <button type="button" className="ti-icon ti-icon--mic" disabled={busy} onClick={() => void voice.start()}>
                    <MicIcon />
                    <span>Talk</span>
                  </button>
                ) : null}
                <button type="submit" className="ti-send" disabled={busy || !text.trim()} aria-label="Send">
                  <SendIcon />
                </button>
              </div>
            </form>
          )}
        </section>

        <aside className={`ti-panel${sheet ? ' ti-panel--open' : ''}`} aria-label="What LOCAH understands" ref={panel}>
          <div className="ti-panel__grab">
            <span>What I understand</span>
            <button type="button" onClick={() => setSheet(false)} aria-label="Close">
              ×
            </button>
          </div>
          <UnderstandingPanel
            data={data}
            busy={busy}
            thinking={waiting}
            onCorrect={correct}
            onAsk={(prefill) => {
              setSheet(false)
              setText(prefill)
              input.current?.focus()
            }}
          />
        </aside>
        {sheet ? <div className="ti-sheet-scrim" onClick={() => setSheet(false)} aria-hidden="true" /> : null}
      </div>

      {confirming ? (
        <ConfirmSheet
          data={data}
          busy={busy}
          onBuild={() => void startBuild()}
          onChange={() => {
            setConfirming(false)
            setSheet(true)
            panel.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
          }}
          onKeepTalking={() => {
            setConfirming(false)
            void send({ action: 'refine' })
          }}
          onKeepTools={() => send({ action: 'keep_tools' })}
          onName={(name) => correct('name', [], name)}
          onClose={() => setConfirming(false)}
        />
      ) : null}
      {build ? <BuildOverlay stage={build.stage} error={build.error} onRetry={() => void startBuild()} /> : null}
    </div>
  )
}
