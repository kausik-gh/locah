'use client'

import { useState } from 'react'
import type {
  BusinessInterviewData,
  DraftCommand,
  DraftField,
  DraftText,
  InterviewFactKey,
  InterviewModule,
} from '@platform/contracts'

/**
 * What Locah has understood, the website it is drafting, what is still worth
 * knowing and the tools that fit — rebuilt by the server on every turn.
 *
 * Business truth and website wording are shown apart on purpose: the first is
 * what the owner told Locah, the second is Locah's suggestion until the owner
 * edits or keeps it. Nothing here switches a tool on.
 */

/** Truth the owner can correct directly; everything else is corrected by saying so. */
const FACT_OF: Record<string, InterviewFactKey> = {
  'contact.location': 'locations',
  'contact.phone': 'phone',
  'offerings.main': 'offerings',
  'operations.hours': 'opening_hours',
  'business.identity': 'description',
}

const DRAFT_LABELS: Record<Exclude<DraftField, 'offering'>, string> = {
  hero_headline: 'Headline',
  hero_subheadline: 'Tagline',
  about: 'About',
  cta_label: 'Main button',
}
/** The server's limits for each line (`_apply_draft`). */
const DRAFT_LIMITS: Record<DraftField, number> = {
  hero_headline: 90,
  hero_subheadline: 220,
  about: 800,
  cta_label: 32,
  offering: 240,
}

function provenanceLabel(text: DraftText): { label: string; tone: 'ai' | 'owner' } {
  if (text.provenance === 'ai_suggestion') return { label: 'Suggested by Locah', tone: 'ai' }
  if (text.provenance === 'owner_claim') return { label: 'Your words', tone: 'owner' }
  return { label: 'Confirmed', tone: 'owner' }
}

function strengthLabel(module: InterviewModule): string {
  if (module.strength === 'dependency') {
    return module.needed_by?.length ? `Needed for ${module.needed_by.join(', ')}` : 'Needed'
  }
  return module.strength === 'useful' ? 'Useful' : 'Strong fit'
}

/** One piece of website wording, with edit / keep / rewrite / remove. */
function DraftLine({
  label,
  value,
  busy,
  multiline,
  limit,
  onCommand,
}: {
  label: string
  value: DraftText | null
  busy: boolean
  /** Longer wording: a paragraph, set as body text. Short lines read as headings. */
  multiline?: boolean
  limit: number
  onCommand: (op: DraftCommand['op'], text?: string) => Promise<boolean>
}) {
  const [editing, setEditing] = useState(false)
  const [text, setText] = useState('')
  if (!value && !editing) return null
  const tag = value ? provenanceLabel(value) : null
  return (
    <div className="bi-draft-line">
      <div className="bi-draft-line__head">
        <span className="bi-draft-line__label">{label}</span>
        {tag ? <span className={`bi-tag bi-tag--${tag.tone}`}>{tag.label}</span> : null}
      </div>
      {editing ? (
        <form
          onSubmit={async (e) => {
            e.preventDefault()
            if (await onCommand('edit', text)) setEditing(false)
          }}
        >
          <textarea
            aria-label={`Edit ${label.toLowerCase()}`}
            value={text}
            rows={limit > 240 ? 5 : 2}
            maxLength={limit}
            onChange={(e) => setText(e.target.value)}
            disabled={busy}
            autoFocus
          />
          <div className="bi-draft-line__actions">
            <button className="lc-btn" disabled={busy || !text.trim()}>
              Save
            </button>
            <button type="button" className="bi-text-button" onClick={() => setEditing(false)}>
              Cancel
            </button>
          </div>
        </form>
      ) : (
        <>
          <p className={`bi-draft-line__text${multiline ? '' : ' bi-draft-line__text--short'}`}>
            {value?.text}
          </p>
          <div className="bi-draft-line__actions">
            <button
              type="button"
              className="bi-text-button"
              disabled={busy}
              onClick={() => {
                setText(value?.text ?? '')
                setEditing(true)
              }}
            >
              Edit
            </button>
            {value?.provenance === 'ai_suggestion' ? (
              <button
                type="button"
                className="bi-text-button"
                disabled={busy}
                onClick={() => void onCommand('approve')}
              >
                Keep
              </button>
            ) : null}
            <button
              type="button"
              className="bi-text-button"
              disabled={busy}
              onClick={() => void onCommand('regenerate')}
            >
              Rewrite
            </button>
            <button
              type="button"
              className="bi-text-button"
              disabled={busy}
              onClick={() => void onCommand('dismiss')}
            >
              Remove
            </button>
          </div>
        </>
      )}
    </div>
  )
}

function Skeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div className="bi-skeleton" aria-hidden="true">
      {Array.from({ length: lines }, (_, i) => (
        <i key={i} style={{ width: `${92 - i * 17}%` }} />
      ))}
    </div>
  )
}

export function UnderstandingPanel({
  data,
  busy,
  thinking,
  onDraft,
  onCorrect,
  onConfirm,
}: {
  data: BusinessInterviewData
  busy: boolean
  /** A turn is being read right now: the panel is about to change. */
  thinking: boolean
  onDraft: (command: DraftCommand) => Promise<boolean>
  onCorrect: (target: string, label: string, value: string, field?: InterviewFactKey) => void
  onConfirm: () => void
}) {
  const [open, setOpen] = useState(false)
  const bp = data.blueprint
  const u = data.understanding
  const wd = bp.website_draft
  const hasDraft = Boolean(
    wd.hero_headline || wd.hero_subheadline || wd.about || wd.cta_label || wd.offerings.length
  )
  const tools = bp.recommended_modules
  const ready = bp.completion_state.sufficient

  return (
    <aside className="bi-summary bi-panel" aria-label="What Locah understood" aria-busy={thinking}>
      <button
        type="button"
        className="bi-panel__toggle"
        aria-expanded={open}
        aria-controls="bi-panel-body"
        onClick={() => setOpen((v) => !v)}
      >
        <span>{ready ? 'Ready for your review' : 'What Locah understood'}</span>
        <small>
          {u.items.length} {u.items.length === 1 ? 'detail' : 'details'}
          {hasDraft ? ' · website draft' : ''}
        </small>
      </button>

      <div className="bi-panel__body" id="bi-panel-body" data-open={open}>
        <section className="bi-panel__section" aria-labelledby="bi-understood">
          <p className="bi-eyebrow" id="bi-understood">
            WHAT I UNDERSTAND
            {thinking ? <span className="bi-updating"> · updating</span> : null}
          </p>
          {u.kind ? (
            <h2 className="bi-kind">{u.kind}</h2>
          ) : thinking ? (
            <Skeleton lines={1} />
          ) : (
            <h2 className="bi-kind bi-kind--empty">Tell Locah about your business.</h2>
          )}
          {u.traits.length > 0 && (
            <ul className="bi-traits" aria-label="How you work">
              {u.traits.map((trait) => (
                <li key={trait}>{trait}</li>
              ))}
            </ul>
          )}
          {u.customer_steps.length > 1 && (
            <>
              <p className="bi-panel__label">What a customer does</p>
              <ol className="bi-steps">
                {u.customer_steps.map((step) => (
                  <li key={step}>{step}</li>
                ))}
              </ol>
            </>
          )}
          {(['from_you', 'confirmed'] as const).map((status) => {
            const rows = u.items.filter((item) => item.status === status)
            if (!rows.length) return null
            return (
              <div className="bi-truth" key={status}>
                <p className="bi-panel__label bi-truth__status">
                  <span className={`bi-tag ${status === 'confirmed' ? 'bi-tag--owner' : 'bi-tag--check'}`}>
                    {status === 'confirmed' ? 'Confirmed' : 'Needs confirmation'}
                  </span>
                  {status === 'from_you' ? 'From what you said' : null}
                </p>
                <dl>
                  {rows.map((item) => (
                    <div key={item.target}>
                      <dt>{item.label}</dt>
                      <dd>{item.value}</dd>
                      <button
                        type="button"
                        className="bi-text-button"
                        disabled={busy}
                        aria-label={`Change ${item.label.toLowerCase()}`}
                        onClick={() => onCorrect(item.target, item.label, item.value, FACT_OF[item.target])}
                      >
                        Change
                      </button>
                    </div>
                  ))}
                </dl>
              </div>
            )
          })}
          <div className="bi-logo" aria-live="polite">
            <span className="bi-panel__label">Logo</span>
            {u.logo.state === 'ready' ? (
              u.logo.url ? (
                // eslint-disable-next-line @next/next/no-img-element -- signed storage URL
                <img src={u.logo.url} alt={`${bp.identity.display_name?.value ?? 'Business'} logo`} />
              ) : (
                <span>Ready</span>
              )
            ) : u.logo.state === 'queued' || u.logo.state === 'requested' ? (
              <span className="bi-logo__pending">
                <i aria-hidden="true" /> Drawing your logo…
              </span>
            ) : u.logo.state === 'failed' || u.logo.state === 'unavailable' ? (
              <span className="bi-logo__failed">
                {u.logo.reason || 'Locah couldn’t draw a logo this time.'}
              </span>
            ) : (
              <span className="bi-muted">Not added yet — upload one, or ask Locah to make one.</span>
            )}
          </div>
        </section>

        <section className="bi-panel__section" aria-labelledby="bi-draft">
          <p className="bi-eyebrow" id="bi-draft">
            WEBSITE DRAFT
          </p>
          {hasDraft ? (
            <>
              {(Object.keys(DRAFT_LABELS) as (keyof typeof DRAFT_LABELS)[]).map((key) => (
                <DraftLine
                  key={key}
                  label={DRAFT_LABELS[key]}
                  value={wd[key]}
                  busy={busy}
                  multiline={key === 'about' || key === 'hero_subheadline'}
                  limit={DRAFT_LIMITS[key]}
                  onCommand={(op, text) => onDraft({ field: key, op, text })}
                />
              ))}
              {wd.offerings.length > 0 && (
                <div className="bi-draft-offerings">
                  <p className="bi-panel__label">What you sell</p>
                  {wd.offerings.map((offering) =>
                    offering.description ? (
                      <DraftLine
                        key={offering.name}
                        label={offering.name}
                        value={offering.description}
                        busy={busy}
                        multiline
                        limit={DRAFT_LIMITS.offering}
                        onCommand={(op, text) =>
                          onDraft({ field: 'offering', op, text, offering_name: offering.name })
                        }
                      />
                    ) : (
                      <div className="bi-draft-line" key={offering.name}>
                        <span className="bi-draft-line__label">{offering.name}</span>
                        <div className="bi-draft-line__actions">
                          <button
                            type="button"
                            className="bi-text-button"
                            disabled={busy}
                            onClick={() =>
                              void onDraft({ field: 'offering', op: 'regenerate', offering_name: offering.name })
                            }
                          >
                            Write a line for this
                          </button>
                        </div>
                      </div>
                    )
                  )}
                </div>
              )}
              {wd.owner_claims.length > 0 && (
                <div className="bi-claims">
                  <p className="bi-panel__label">Lines you asked for</p>
                  <ul>
                    {wd.owner_claims.map((claim) => (
                      <li key={claim.claim}>“{claim.claim}”</li>
                    ))}
                  </ul>
                </div>
              )}
              {thinking ? <Skeleton lines={2} /> : null}
            </>
          ) : thinking ? (
            <Skeleton />
          ) : (
            <p className="bi-muted">
              As you talk, Locah writes your homepage here — headline, About and what you sell. You
              can edit every word.
            </p>
          )}
        </section>

        {u.still_worth_knowing.length > 0 && !ready && (
          <section className="bi-panel__section" aria-labelledby="bi-still">
            <p className="bi-eyebrow" id="bi-still">
              STILL WORTH KNOWING
            </p>
            <ul className="bi-still">
              {u.still_worth_knowing.map((item) => (
                <li key={item.id}>
                  {item.label}
                  {item.essential ? <span className="bi-tag bi-tag--check">Needed</span> : null}
                </li>
              ))}
            </ul>
          </section>
        )}

        {tools.length > 0 && (
          <section className="bi-panel__section" aria-labelledby="bi-tools">
            <p className="bi-eyebrow" id="bi-tools">
              RECOMMENDED TOOLS
            </p>
            <ul className="bi-panel-tools">
              {tools.map((module) => {
                const said = module.evidence?.find((e) => e.kind === 'owner_said')
                return (
                  <li key={module.module_id} data-strength={module.strength ?? 'strong'}>
                    <div className="bi-panel-tools__head">
                      <strong>{module.label}</strong>
                      <span className="bi-tag bi-tag--tool">{strengthLabel(module)}</span>
                    </div>
                    <p>{module.reason}</p>
                    {said && !module.reason.includes(said.text) ? (
                      <p className="bi-evidence">You said: “{said.text}”</p>
                    ) : null}
                  </li>
                )
              })}
            </ul>
            <p className="bi-muted">Nothing switches on until you choose it when you build.</p>
          </section>
        )}

        <section className="bi-panel__section bi-panel__ready">
          <p className="bi-progress" role="status">
            {ready ? 'Enough for a strong first website. Everything else can wait.' : u.readiness.reason}
          </p>
          {ready && (
            <button
              className="lc-btn"
              disabled={busy || bp.completion_state.confirmed}
              onClick={onConfirm}
            >
              {bp.completion_state.confirmed ? '✓ Details confirmed' : 'These details are correct'}
            </button>
          )}
        </section>
      </div>
    </aside>
  )
}
