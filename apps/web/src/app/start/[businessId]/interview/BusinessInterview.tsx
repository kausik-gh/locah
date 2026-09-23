'use client'

import Link from 'next/link'
import { useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import type {
  BusinessInterviewData,
  InterviewCommand,
  InterviewFactKey,
  InterviewModule,
} from '@platform/contracts'
import {
  finishInterviewUpload,
  interviewAction,
  reloadInterview,
  startInterviewUpload,
} from './actions'
import { ROLE_LABELS, ROLE_ORDER, roleFromText, type MediaRole } from './attachment'
import { UnderstandingPanel } from './UnderstandingPanel'
import { VoicePanel } from './voice/VoicePanel'

const LABELS: Record<InterviewFactKey, string> = {
  description: 'Your business',
  classification: 'Kind of business',
  operating_model: 'How you work',
  locations: 'Where to find you',
  offerings: 'What you sell or do',
  customer_actions: 'What visitors should do',
  operational_characteristics: 'How it works',
  brand: 'Your brand',
  tone: 'Your voice',
  colours: 'Your colours',
  opening_hours: 'Opening hours',
  phone: 'Phone',
  email: 'Email',
  website_priorities: 'What matters most',
}
type Change = Omit<InterviewCommand, 'revision' | 'request_id'>
/** An image that is uploaded and waiting only for the owner to say what it is. */
type Staged = { assetId: string; filename: string }

/** One tool the owner can switch on. Choosing is always the owner's. */
function ToolCard({
  module,
  busy,
  compact = false,
  onChoose,
}: {
  module: InterviewModule
  busy: boolean
  compact?: boolean
  onChoose: (choice: 'approved' | 'declined') => void
}) {
  const extra = module.dependencies.filter((id) => !id.startsWith('core-'))
  const said = module.evidence?.find((e) => e.kind === 'owner_said')
  return (
    <article className={`bi-tool${compact ? ' bi-tool--compact' : ''}`}>
      <h4>{module.label}</h4>
      {module.strength && !compact ? (
        <span className="bi-tag bi-tag--tool">
          {module.strength === 'dependency'
            ? `Needed for ${module.needed_by?.join(', ') || 'another tool'}`
            : module.strength === 'useful'
              ? 'Useful'
              : 'Strong fit'}
        </span>
      ) : null}
      <p className={module.reason.startsWith('Because you said') ? 'bi-tool__why' : undefined}>
        {module.reason}
      </p>
      {said && !compact && !module.reason.includes(said.text) ? (
        <p className="bi-evidence">You said: “{said.text}”</p>
      ) : null}
      {module.configuration_needed && !compact ? (
        <p className="ob-help">To set up: {module.configuration_needed}</p>
      ) : null}
      {!compact ? <p className="ob-help">{module.availability_reason}</p> : null}
      {extra.length > 0 && !compact ? (
        <p className="ob-help">May also need: {extra.join(', ')}.</p>
      ) : null}
      <div className="bi-choices">
        <button
          className="lc-btn"
          disabled={busy}
          aria-pressed={module.choice === 'approved'}
          onClick={() => onChoose('approved')}
        >
          {module.choice === 'approved' ? '✓ Using this' : 'Use this'}
        </button>
        <button
          className="lc-btn"
          disabled={busy}
          aria-pressed={module.choice === 'declined'}
          onClick={() => onChoose('declined')}
        >
          Not now
        </button>
      </div>
    </article>
  )
}

export function BusinessInterview({ initial }: { initial: BusinessInterviewData }) {
  const [data, setData] = useState(initial)
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [field, setField] = useState<InterviewFactKey | ''>('')
  const [lastAnswer, setLastAnswer] = useState('')
  // The owner's own words, shown the instant they send them. Replaced by server
  // state on the next response — never a fabricated assistant reply.
  const [sending, setSending] = useState('')
  const [staged, setStaged] = useState<Staged | null>(null)
  const [mode, setMode] = useState<'chat' | 'voice'>('chat')
  const [uploading, setUploading] = useState(false)
  const input = useRef<HTMLTextAreaElement>(null)
  const busyRef = useRef(false)
  // Spoken turns can overlap: the owner keeps talking while the last sentence
  // is still being saved. They run one after another, and each reads the
  // revision the previous one produced — not the one from the last render.
  const latest = useRef(initial)
  const voiceChain = useRef<Promise<unknown>>(Promise.resolve())
  const stream = useRef<HTMLDivElement>(null)
  const router = useRouter()
  const bp = data.blueprint
  latest.current = data
  const pendingChoices = bp.recommended_modules.some((m) => m.choice === 'pending')
  const logoState = data.understanding.logo.state
  const requested = (role: 'hero' | 'logo') =>
    bp.media_generation_requests.some((r) => r.role === role)
  // Recommended tools are shown once, with the owner's own words as the reason;
  // everything else they could use is listed after, grouped by who it serves.
  const recommendedIds = new Set(bp.recommended_modules.map((m) => m.module_id))
  const others = data.available_modules.filter((m) => !recommendedIds.has(m.module_id))
  const forCustomers = others.filter((m) => (m.group ?? 'customer') === 'customer')
  const forRunning = others.filter((m) => m.group === 'operations')
  const choose = (moduleId: string, choice: 'approved' | 'declined') =>
    void send({ action: 'choices', choices: { [moduleId]: choice } })

  useEffect(() => {
    stream.current?.scrollTo({ top: stream.current.scrollHeight, behavior: 'smooth' })
  }, [bp.messages.length, sending])

  // A logo is drawn in the background while the owner carries on. Look again
  // every few seconds until it arrives or fails — never for more than 3 minutes.
  useEffect(() => {
    if (logoState !== 'queued' && logoState !== 'requested') return
    let tries = 0
    const timer = window.setInterval(async () => {
      tries += 1
      if (tries > 36) window.clearInterval(timer)
      if (busyRef.current) return
      const res = await reloadInterview(bp.business_id)
      if (!res.ok || busyRef.current) return
      if (res.data.blueprint.revision < latest.current.blueprint.revision) return
      latest.current = res.data
      setData(res.data)
    }, 5000)
    return () => window.clearInterval(timer)
  }, [logoState, bp.business_id])

  async function send(change: Change) {
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
          const latest = await reloadInterview(bp.business_id)
          if (latest.ok) setData(latest.data)
        }
        return false
      }
      latest.current = res.data
      setData(res.data)
      if (change.action === 'turn') {
        setLastAnswer(change.text || '')
        setText('')
        setField('')
      }
      if (change.action === 'build') router.push(`/start/${bp.business_id}/website`)
      return true
    } catch {
      setError('Could not save that change. Your previous answers are safe. Please retry.')
      return false
    } finally {
      setBusy(false)
      busyRef.current = false
      setSending('')
    }
  }

  /**
   * A spoken turn, handled by exactly the same command a typed one uses.
   *
   * Locah's reply is whatever the interview decided — the realtime model is
   * told what to say, it does not choose. That is what keeps one Blueprint
   * authoritative across both ways of talking to it.
   */
  function speakTurn(transcript: string): Promise<{ say: string; sufficient: boolean }> {
    const run = async () => {
      const current = latest.current.blueprint
      const res = await interviewAction(current.business_id, {
        action: 'turn',
        text: transcript,
        revision: current.revision,
        request_id: crypto.randomUUID(),
      })
      if (!res.ok) {
        if (res.stale) {
          const reloaded = await reloadInterview(current.business_id)
          if (reloaded.ok) {
            latest.current = reloaded.data
            setData(reloaded.data)
          }
        }
        return {
          say: 'I could not save that just now — could you say it once more?',
          sufficient: false,
        }
      }
      latest.current = res.data
      setData(res.data)
      const next = res.data.blueprint
      const reply = next.messages.filter((m) => m.role === 'assistant').slice(-1)[0]?.text
      return {
        say: reply || 'Tell me a little more about your business.',
        sufficient: next.completion_state.sufficient,
      }
    }
    const turn = voiceChain.current.then(run, run)
    voiceChain.current = turn.catch(() => undefined)
    return turn
  }

  /** Upload now so the transfer overlaps with typing; ask what it is only if the words do not say. */
  async function attach(file: File) {
    setUploading(true)
    setError('')
    try {
      if (file.size > 10 * 1024 * 1024) throw new Error('Choose an image smaller than 10 MB.')
      const guess = roleFromText(text)
      const start = await startInterviewUpload(
        bp.business_id,
        guess ?? 'business',
        file.type,
        file.size,
        file.name
      )
      if (!start.ok) throw new Error(start.error)
      // Supabase's signed-upload endpoint expects the same multipart body its
      // `uploadToSignedUrl` client emits for a browser File. A raw File plus a
      // manually-set Content-Type passes preflight but the upload itself is
      // rejected by the hosted storage service.
      const uploadBody = new FormData()
      uploadBody.append('cacheControl', '3600')
      uploadBody.append('', file)
      const uploaded = await fetch(start.uploadUrl, {
        method: 'PUT',
        headers: { 'x-upsert': 'false' },
        body: uploadBody,
      })
      if (!uploaded.ok) throw new Error('The image did not upload. Please try again.')
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
    const ok = await send({
      action: 'media',
      media: { asset_id: assetId, role, label: filename, source: 'USER_UPLOAD' },
    })
    if (ok) setStaged(null)
  }

  const waiting = busy && Boolean(sending)

  return (
    <div className="bi">
      <header className="bi-heading">
        <div>
          <p className="bi-eyebrow">A LITTLE CONVERSATION. YOUR NEXT CHAPTER.</p>
          <h1>{bp.identity.display_name?.value}</h1>
          <p>Tell us what makes your business yours. You can leave and come back any time.</p>
        </div>
        <span className="bi-saved" role="status">
          {busy ? 'Saving…' : 'Progress saved'}
        </span>
      </header>
      <div className="bi-layout">
        <section className="bi-conversation" aria-label="Business interview">
          <div className="bi-modes" role="tablist" aria-label="How to answer">
            <button
              role="tab"
              type="button"
              aria-selected={mode === 'chat'}
              onClick={() => setMode('chat')}
            >
              Chat with Locah
            </button>
            <button
              role="tab"
              type="button"
              aria-selected={mode === 'voice'}
              disabled={!data.voice.available}
              title={data.voice.reason}
              onClick={() => setMode('voice')}
            >
              {data.voice.available ? 'Talk to Locah' : 'Talk to Locah · not available yet'}
            </button>
          </div>
          {mode === 'voice' ? (
            <VoicePanel
              businessId={bp.business_id}
              data={data}
              onTurn={speakTurn}
              onSwitchToChat={() => setMode('chat')}
            />
          ) : null}
          {mode === 'chat' ? (
            <>
              <div
                className="bi-messages"
                role="log"
                aria-live="polite"
                aria-relevant="additions"
                ref={stream}
              >
                {bp.messages.map((message, i) => (
                  <div
                    className={`bi-message bi-message--${message.role}`}
                    key={`${message.at}-${i}`}
                  >
                    <span>{message.role === 'assistant' ? 'LOCAH' : 'YOU'}</span>
                    <p>{message.text}</p>
                  </div>
                ))}
                {waiting && (
                  <>
                    <div className="bi-message bi-message--user bi-message--pending">
                      <span>YOU</span>
                      <p>{sending}</p>
                    </div>
                    <div
                      className="bi-message bi-message--assistant bi-thinking"
                      aria-label="Locah is reading your answer"
                    >
                      <span>LOCAH</span>
                      <p>
                        <i />
                        <i />
                        <i />
                      </p>
                    </div>
                  </>
                )}
              </div>
              {error && (
                <p className="ob-error" role="alert">
                  {error}
                </p>
              )}

              {staged && (
                <div className="bi-staged" role="group" aria-label="What is this image?">
                  <p>
                    <strong>{staged.filename}</strong> is ready. What is it?
                  </p>
                  <div className="bi-choices">
                    {ROLE_ORDER.map((role) => (
                      <button
                        key={role}
                        className="lc-btn"
                        type="button"
                        disabled={busy}
                        onClick={() => void saveAttachment(staged.assetId, staged.filename, role)}
                      >
                        {ROLE_LABELS[role]}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <form
                className="bi-compose"
                onSubmit={(e) => {
                  e.preventDefault()
                  void send({ action: 'turn', text, ...(field ? { field } : {}) })
                }}
              >
                <label htmlFor="interview-message">
                  {field ? `Update: ${LABELS[field]}` : 'Your reply'}
                </label>
                <textarea
                  ref={input}
                  id="interview-message"
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey) && text.trim()) {
                      e.preventDefault()
                      void send({ action: 'turn', text, ...(field ? { field } : {}) })
                    }
                  }}
                  maxLength={4000}
                  required
                  rows={3}
                  disabled={busy}
                  placeholder="In your own words… you can attach a photo or logo too."
                />
                <div className="bi-compose-actions">
                  <button className="lc-btn lc-btn--primary" disabled={busy || !text.trim()}>
                    {busy ? 'Saving…' : 'Send reply →'}
                  </button>
                  <label className="bi-clip">
                    {uploading ? 'Uploading…' : '📎 Attach image'}
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
                  {field && (
                    <button className="lc-btn" type="button" onClick={() => setField('')}>
                      Cancel correction
                    </button>
                  )}
                </div>
                <p className="ob-help bi-hint">
                  Say what a picture is as you attach it — “this is our logo”, “photos of our shop”
                  — and it goes to the right place.
                </p>
              </form>
            </>
          ) : null}

          {lastAnswer && bp.last_turn?.fallback_reason && bp.remaining_questions[0] && (
            <div className="bi-fallback">
              <p>
                AI couldn’t organise your answer. You can save it directly as “
                {LABELS[bp.remaining_questions[0].field]}”, then review it.
              </p>
              <button
                className="lc-btn"
                disabled={busy}
                onClick={() =>
                  void send({
                    action: 'turn',
                    field: bp.remaining_questions[0].field,
                    text: lastAnswer,
                  })
                }
              >
                Save as answer
              </button>
            </div>
          )}

          {bp.media_assets.length > 0 && (
            <ul className="bi-attached">
              {bp.media_assets.map((asset) => (
                <li key={asset.asset_id}>
                  ✓ {asset.label || 'Image'} — {ROLE_LABELS[asset.role]}
                </li>
              ))}
            </ul>
          )}
          {data.image_generation.available && bp.completion_state.status !== 'built' && (
            <details className="bi-artwork">
              <summary>No logo or cover photo? Locah can draw them · optional</summary>
              <p className="ob-help">{data.image_generation.reason}</p>
              <div className="bi-choices">
                {!bp.media_assets.some((m) => m.role === 'logo') ? (
                  <button
                    className="lc-btn"
                    disabled={busy || requested('logo')}
                    onClick={() => void send({ action: 'image', image_role: 'logo' })}
                  >
                    {requested('logo') ? '✓ Logo will be drawn' : 'Make me a simple logo'}
                  </button>
                ) : null}
                {!bp.media_assets.some((m) => m.role === 'hero') ? (
                  <button
                    className="lc-btn"
                    disabled={busy || requested('hero')}
                    onClick={() => void send({ action: 'image', image_role: 'hero' })}
                  >
                    {requested('hero') ? '✓ Cover artwork will be drawn' : 'Draw cover artwork'}
                  </button>
                ) : null}
              </div>
              <p className="ob-help">Drawn after you build, so it never slows your first preview.</p>
            </details>
          )}
        </section>

        <UnderstandingPanel
          data={data}
          busy={busy}
          thinking={waiting}
          onDraft={(draft) => send({ action: 'draft', draft })}
          onConfirm={() => void send({ action: 'confirm' })}
          onCorrect={(target, label, value, key) => {
            setMode('chat')
            if (key) {
              setField(key)
              setText(value)
            } else {
              setField('')
              setText(`About ${label.toLowerCase()}: `)
            }
            input.current?.focus()
          }}
        />
      </div>
      {bp.completion_state.sufficient && (
        <section className="bi-finish" aria-label="Review and build">
          <h2>A few choices. Then it’s yours.</h2>
          {bp.unsupported_requests.map((gap) => (
            <p className="bi-gap" key={gap.normalized_intent}>
              <strong>You asked: {gap.original_request}</strong>
              <br />
              {gap.why_unsupported}
            </p>
          ))}
          {bp.recommended_modules.length > 0 && (
            <section aria-label="Recommended for you">
              <h3>Recommended from what you told us</h3>
              <p>
                Each one says why. Nothing turns on unless you choose it, and you can change your
                mind later.
              </p>
              <div className="bi-tool-grid">
                {bp.recommended_modules.map((module) => (
                  <ToolCard
                    key={module.module_id}
                    module={module}
                    busy={busy}
                    onChoose={(choice) => choose(module.module_id, choice)}
                  />
                ))}
              </div>
              {pendingChoices ? (
                <button
                  className="bi-text-button"
                  disabled={busy}
                  onClick={() =>
                    void send({
                      action: 'choices',
                      choices: Object.fromEntries(
                        bp.recommended_modules
                          .filter((m) => m.choice === 'pending')
                          .map((m) => [m.module_id, 'declined'])
                      ),
                    })
                  }
                >
                  Skip these for now
                </button>
              ) : null}
            </section>
          )}
          {others.length > 0 && (
            <details className="bi-more-tools">
              <summary>
                Also available for your business · {others.length}{' '}
                {others.length === 1 ? 'tool' : 'tools'}
              </summary>
              <p className="ob-help">
                Included in your access, switched off until you choose them.
              </p>
              {[
                { title: 'For your customers', rows: forCustomers },
                { title: 'For running your business', rows: forRunning },
              ]
                .filter((g) => g.rows.length > 0)
                .map((g) => (
                  <section key={g.title} aria-label={g.title}>
                    <h4 className="bi-tool-group">{g.title}</h4>
                    <div className="bi-tool-grid">
                      {g.rows.map((module) => (
                        <ToolCard
                          key={module.module_id}
                          module={module}
                          busy={busy}
                          compact
                          onChoose={(choice) => choose(module.module_id, choice)}
                        />
                      ))}
                    </div>
                  </section>
                ))}
            </details>
          )}
          <details>
            <summary>Choose your starting design · optional</summary>
            <div className="bi-template-grid">
              {data.templates
                .filter((t) => t.available)
                .map((template) => (
                  <button
                    key={template.id}
                    className="bi-template"
                    disabled={busy}
                    aria-pressed={bp.template_preferences.template_id === template.id}
                    onClick={() => void send({ action: 'template', template_id: template.id })}
                  >
                    <span className="bi-swatches" aria-hidden="true">
                      <i style={{ background: template.primary_color }} />
                      <i style={{ background: template.accent_color }} />
                    </span>
                    <strong>{template.name}</strong>
                    <span>{template.look.join(' · ')}</span>
                    <small>{template.description}</small>
                  </button>
                ))}
            </div>
          </details>
          <div className="bi-build">
            <p>
              Your first preview appears immediately. Personalization runs in the background.
              <br />
              Nothing is published until you choose to publish.
            </p>
            {bp.completion_state.status === 'built' ? (
              <Link className="lc-btn lc-btn--primary" href={`/start/${bp.business_id}/website`}>
                Open your website
              </Link>
            ) : (
              <button
                className="lc-btn lc-btn--primary lc-btn--lg"
                disabled={busy || !bp.completion_state.confirmed || pendingChoices}
                onClick={() => void send({ action: 'build' })}
              >
                Build my website →
              </button>
            )}
            {!bp.completion_state.confirmed && <small>Confirm your details above first.</small>}
            {pendingChoices && <small>Choose your tools, or continue without them.</small>}
          </div>
        </section>
      )}
    </div>
  )
}
