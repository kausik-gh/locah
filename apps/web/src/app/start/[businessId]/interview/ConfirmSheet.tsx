'use client'

import { useEffect, useRef, useState } from 'react'
import type { BusinessInterviewData } from '@platform/contracts'
import { CheckIcon } from '@/components/onboarding/icons'

/** "How people join / order / book" — the heading follows what customers actually do. */
function actionHeading(ids: string[]): string {
  const first = ids[0] || ''
  if (first.startsWith('order')) return 'How people order'
  if (first === 'book_trial' || first === 'join' || first === 'subscribe') return 'How people join'
  if (first.startsWith('book') || first === 'check_dates') return 'How people book'
  if (first === 'request_quote' || first === 'enquire') return 'How buyers reach you'
  return 'How people reach you'
}

/**
 * The confirmation moment: "LOCAH understands me" — not a settings form.
 *
 * Everything here is the typed understanding the owner already saw forming
 * beside the conversation, said back once, whole. Pressing Build is the
 * confirmation. Recommended tools are secondary and never block the website:
 * "Looks good" records the owner's approval (approval is not activation),
 * "Review later" changes nothing.
 */
export function ConfirmSheet({
  data,
  busy,
  onBuild,
  onChange,
  onKeepTalking,
  onKeepTools,
  onName,
  onClose,
}: {
  data: BusinessInterviewData
  busy: boolean
  onBuild: () => void
  onChange: () => void
  onKeepTalking: () => void
  onKeepTools: () => Promise<boolean>
  onName: (name: string) => Promise<boolean>
  onClose: () => void
}) {
  const u = data.understanding
  const bp = data.blueprint
  const [name, setName] = useState('')
  const [toolsLater, setToolsLater] = useState(false)
  const dialog = useRef<HTMLDivElement>(null)
  const pendingName = u.business.name_pending || !u.business.name
  const kindLine = [u.business.category, u.business.place].filter(Boolean).join(' · ')
  const tools = u.tools.slice(0, 3)
  const approved = tools.length > 0 && tools.every((t) => t.choice === 'approved')
  const works = u.buying.map((b) => b.text)

  useEffect(() => {
    dialog.current?.focus()
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className="cs-scrim" role="presentation" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="cs" role="dialog" aria-modal="true" aria-labelledby="cs-title" tabIndex={-1} ref={dialog}>
        <p className="cs-eyebrow">Here&rsquo;s what I&rsquo;ll build from</p>
        {pendingName ? (
          <form
            className="cs-name"
            onSubmit={async (e) => {
              e.preventDefault()
              if (name.trim()) await onName(name.trim())
            }}
          >
            <label htmlFor="cs-name" id="cs-title">
              What&rsquo;s the business called?
            </label>
            <div>
              <input id="cs-name" value={name} maxLength={120} autoFocus onChange={(e) => setName(e.target.value)} />
              <button className="lc-btn lc-btn--sm" disabled={busy || !name.trim()}>
                Save
              </button>
            </div>
          </form>
        ) : (
          <h2 className="cs-title" id="cs-title">
            {u.business.name}
          </h2>
        )}
        {kindLine ? <p className="cs-kind">{kindLine}</p> : null}
        {u.read_back ? <p className="cs-readback">{u.read_back}</p> : null}

        <div className="cs-grid">
          {u.offer.groups.length ? (
            <section>
              <h3>What you offer</h3>
              <ul>
                {u.offer.groups.slice(0, 6).map((g) => (
                  <li key={g.name}>{g.name}</li>
                ))}
              </ul>
            </section>
          ) : null}
          {u.actions.length ? (
            <section>
              <h3>{actionHeading(u.actions.map((a) => a.id))}</h3>
              <ul>
                {u.actions.map((a) => (
                  <li key={a.id}>{a.label}</li>
                ))}
              </ul>
            </section>
          ) : null}
          {works.length ? (
            <section>
              <h3>How the business works</h3>
              <ul>
                {works.map((w) => (
                  <li key={w}>{w}</li>
                ))}
              </ul>
            </section>
          ) : null}
          {u.direction?.words?.length ? (
            <section>
              <h3>Website direction</h3>
              <ul>
                {u.direction.words.map((w) => (
                  <li key={w}>{w}</li>
                ))}
              </ul>
            </section>
          ) : null}
        </div>

        {tools.length ? (
          <section className="cs-tools" aria-label="Recommended for you">
            <h3>Recommended for you</h3>
            <ul>
              {tools.map((t) => (
                <li key={t.id}>
                  <strong>
                    {t.choice === 'approved' ? <CheckIcon size={14} /> : null}
                    {t.label}
                  </strong>
                  {t.why ? <span>{t.why}</span> : null}
                </li>
              ))}
            </ul>
            {approved ? (
              <p className="cs-note">Kept. You&rsquo;ll set them up in your Workspace — they don&rsquo;t hold up your website.</p>
            ) : toolsLater ? (
              <p className="cs-note">No problem — they&rsquo;ll be waiting in your Workspace.</p>
            ) : (
              <div className="cs-tools__actions">
                <button type="button" className="lc-btn lc-btn--sm lc-btn--ghost" disabled={busy} onClick={() => void onKeepTools()}>
                  Looks good
                </button>
                <button type="button" className="cs-link" onClick={() => setToolsLater(true)}>
                  Review later
                </button>
              </div>
            )}
          </section>
        ) : null}

        <div className="cs-actions">
          <button
            type="button"
            className="lc-btn lc-btn--primary lc-btn--lg cs-build"
            disabled={busy || pendingName}
            onClick={onBuild}
          >
            Build my website
          </button>
          <button type="button" className="lc-btn lc-btn--ghost" disabled={busy} onClick={onChange}>
            Change something
          </button>
          <button type="button" className="cs-link" disabled={busy} onClick={onKeepTalking}>
            Keep talking
          </button>
        </div>
        {bp.unsupported_requests.length ? (
          <p className="cs-note">
            Not in this first version: {bp.unsupported_requests.map((g) => g.original_request).join('; ')}.
          </p>
        ) : null}
      </div>
    </div>
  )
}

export const BUILD_STEPS = [
  'Understanding your business',
  'Planning your website',
  'Building your pages',
  'Preparing your first version',
] as const

/**
 * The build, as it actually happens. Step one is already true when the owner
 * presses Build; planning and the pages are written by the one build request,
 * so they complete when it returns — never on a timer; the last step is the
 * website page loading.
 */
export function BuildOverlay({ stage, error, onRetry }: { stage: number; error: string; onRetry: () => void }) {
  return (
    <div className="bo" role="dialog" aria-modal="true" aria-label="Building your website">
      <div className="bo-inner">
        <p className="bo-eyebrow">Your website</p>
        <h2>{error ? 'That didn’t go through' : 'Making it yours'}</h2>
        <ol className="bo-steps">
          {BUILD_STEPS.map((label, i) => {
            const state = i < stage ? 'done' : i === stage && !error ? 'active' : 'todo'
            return (
              <li key={label} data-state={state}>
                <span className="bo-mark" aria-hidden="true">
                  {state === 'done' ? <CheckIcon size={14} /> : null}
                </span>
                {label}
                {state === 'active' ? '…' : ''}
              </li>
            )
          })}
        </ol>
        {error ? (
          <div className="bo-error">
            <p role="alert">{error}</p>
            <button type="button" className="lc-btn lc-btn--primary" onClick={onRetry}>
              Try again
            </button>
          </div>
        ) : null}
      </div>
    </div>
  )
}
