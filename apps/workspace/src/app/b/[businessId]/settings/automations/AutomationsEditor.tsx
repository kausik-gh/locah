'use client'

import { useState, useTransition } from 'react'
import { LocalTime } from '@/components/LocalTime'
import { saveAutomation } from './actions'

export type Step = { key: string; when: string; does: string; marketing: boolean; on: boolean; offset_hours: number }
export type Automation = {
  key: string
  label: string
  module: string
  module_label: string
  anchor: string
  stops_when: string
  enabled: boolean
  quiet_hours: boolean
  /** Low stock only: also put a draft requisition on the Buying desk. */
  draft_requisition?: boolean | null
  channel?: string
  last_run_at?: string | null
  next_run_at?: string | null
  counts?: { done?: number; skipped?: number; failed?: number }
  steps: Step[]
}
export type SentMessage = {
  id: string; what: string; to: string; status: string; status_label: string; error: string | null
  category: string | null; test_number: boolean; created_at: string | null; status_at: string | null
}
export type Activity = {
  id: string
  ladder_label: string
  step_when: string
  step_does: string
  status: string
  outcome: string | null
  due_at: string
  executed_at: string | null
}

/** One automation: the whole thing on/off, each step on/off, in owner words. */
export function AutomationCard({ businessId, automation }: { businessId: string; automation: Automation }) {
  const [enabled, setEnabled] = useState(automation.enabled)
  const [steps, setSteps] = useState(() => Object.fromEntries(automation.steps.map((s) => [s.key, s.on])))
  const [draft, setDraft] = useState(Boolean(automation.draft_requisition))
  const [pending, start] = useTransition()
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState<string | null>(null)

  const save = (change: Parameters<typeof saveAutomation>[2], done: string, undo: () => void) => {
    setError(null)
    setSaved(null)
    start(async () => {
      const r = await saveAutomation(businessId, automation.key, change)
      if (r.ok) setSaved(done)
      else {
        undo()
        setError(r.message)
      }
    })
  }

  const toggleAll = () => {
    const next = !enabled
    setEnabled(next)
    save({ enabled: next }, next ? 'Switched on.' : 'Switched off. Anything scheduled was stopped.', () =>
      setEnabled(!next),
    )
  }

  const toggleStep = (key: string) => {
    const next = { ...steps, [key]: !steps[key] }
    setSteps(next)
    const offsets = Object.fromEntries(automation.steps.map((s) => [s.key, s.offset_hours]))
    save(
      { config: { disabled_steps: Object.keys(next).filter((k) => !next[k]), offset_hours: offsets } },
      next[key] ? 'Step switched on.' : 'Step switched off.',
      () => setSteps(steps),
    )
  }

  const toggleDraft = () => {
    const next = !draft
    setDraft(next)
    save({ config: { draft_requisition: next } },
      next ? 'Low stock will also draft a requisition for you to review.' : 'No more draft requisitions.',
      () => setDraft(!next))
  }

  const titleId = `auto-${automation.key.replace(/\W/g, '-')}`
  return (
    <section className={`bos-card bos-auto${enabled ? '' : ' is-off'}`} aria-labelledby={titleId}>
      <div className="bos-card__head">
        <div>
          <h2 id={titleId}>{automation.label}</h2>
          <p className="bos-auto__meta">
            Part of {automation.module_label} · counts from {automation.anchor}
            {automation.channel ? <> · {automation.channel}</> : null}
          </p>
          <p className="bos-auto__meta">
            Last ran {automation.last_run_at ? <LocalTime value={automation.last_run_at} /> : 'not yet'}
            {automation.next_run_at ? <> · next <LocalTime value={automation.next_run_at} /></> : null}
            {automation.counts && (automation.counts.done || automation.counts.skipped || automation.counts.failed)
              ? ` · last 30 days: ${automation.counts.done ?? 0} done, ${automation.counts.skipped ?? 0} not needed${automation.counts.failed ? `, ${automation.counts.failed} failed` : ''}`
              : null}
          </p>
        </div>
        <label className="bos-toggle">
          <input type="checkbox" checked={enabled} onChange={toggleAll} disabled={pending} />
          <span className="bos-toggle__track" aria-hidden />
          <span>{enabled ? 'On' : 'Off'}</span>
          <span className="sr-only"> — {automation.label}</span>
        </label>
      </div>

      <ol className="bos-steps">
        {automation.steps.map((s) => (
          <li key={s.key} className={steps[s.key] && enabled ? '' : 'is-off'}>
            <div>
              <strong>{s.when}</strong>
              <p>
                {s.does}
                {s.marketing ? <span className="bos-tag">needs marketing consent</span> : null}
              </p>
            </div>
            {automation.steps.length > 1 ? (
              <label className="bos-toggle">
                <input
                  type="checkbox"
                  checked={steps[s.key]}
                  onChange={() => toggleStep(s.key)}
                  disabled={pending || !enabled}
                />
                <span className="bos-toggle__track" aria-hidden />
                <span className="sr-only">
                  {s.when}: {steps[s.key] ? 'on' : 'off'}
                </span>
              </label>
            ) : null}
          </li>
        ))}
      </ol>

      {automation.draft_requisition !== null && automation.draft_requisition !== undefined ? (
        <label className="bos-toggle">
          <input type="checkbox" checked={draft} onChange={toggleDraft} disabled={pending || !enabled} />
          <span className="bos-toggle__track" aria-hidden />
          <span>Also put a draft requisition on the Buying desk (you review it; nothing is ordered)</span>
        </label>
      ) : null}

      <p className="bos-auto__foot">
        Stops when {automation.stops_when}.
        {automation.quiet_hours ? ' Messages wait until 8 am if they fall between 9 pm and 8 am.' : ''}
      </p>
      <p className={`bos-status${error ? ' bos-error' : ''}`} role="status" aria-live="polite">
        {pending ? 'Saving…' : error ?? saved ?? ''}
      </p>
    </section>
  )
}

const STATUS: Record<string, { label: string; tone: string }> = {
  done: { label: 'Done', tone: 'good' },
  pending: { label: 'Scheduled', tone: 'info' },
  // A step waiting for 8 am says so in its outcome ("Waiting for 8 am (quiet hours)").
  processing: { label: 'Running', tone: 'info' },
  skipped: { label: 'Not needed', tone: 'neutral' },
  cancelled: { label: 'Stopped', tone: 'neutral' },
  failed: { label: 'Failed', tone: 'bad' },
}

const MSG_TONE: Record<string, string> = {
  queued: 'info', sent: 'info', delivered: 'good', read: 'good', failed: 'bad', blocked: 'warn',
}

/** Messages automations sent, with WhatsApp's own delivery state - never assumed. */
export function AutomatedMessages({ items }: { items: SentMessage[] }) {
  if (items.length === 0) {
    return <div className="bos-empty">No automatic messages yet. Confirmations, reminders and updates are listed here with what WhatsApp reported.</div>
  }
  return (
    <ul className="bos-log">
      {items.map((m) => {
        const tone = MSG_TONE[m.status] ?? 'neutral'
        return (
          <li key={m.id}>
            <span className={`bos-log__dot is-${tone}`} aria-hidden />
            <div>
              <p className="bos-log__what">
                <strong>{m.what}</strong> · WhatsApp to {m.to}
                {m.test_number ? <span className="bos-tag bos-tag--warn" style={{ marginLeft: '0.4rem' }}>TEST / SANDBOX</span> : null}
              </p>
              {m.error ? <p className="bos-log__outcome">{m.error}</p> : null}
            </div>
            <div className="bos-log__when">
              <span className={`bos-log__status is-${tone}`}>{m.status_label}</span>
              <LocalTime value={m.status_at ?? m.created_at} />
            </div>
          </li>
        )
      })}
    </ul>
  )
}

/** The activity log: every step, what it did or why it did not run. */
export function AutomationActivity({ items }: { items: Activity[] }) {
  if (items.length === 0) {
    return <div className="bos-empty">Nothing has run yet. Each step will be listed here as it happens.</div>
  }
  return (
    <ul className="bos-log">
      {items.map((a) => {
        const st = STATUS[a.status] ?? { label: a.status, tone: 'neutral' }
        return (
          <li key={a.id}>
            <span className={`bos-log__dot is-${st.tone}`} aria-hidden />
            <div>
              <p className="bos-log__what">
                <strong>{a.ladder_label}</strong> · {a.step_when}
              </p>
              <p className="bos-log__outcome">{a.outcome ?? a.step_does}</p>
            </div>
            <div className="bos-log__when">
              <span className={`bos-log__status is-${st.tone}`}>{st.label}</span>
              <LocalTime value={a.executed_at ?? a.due_at} />
            </div>
          </li>
        )
      })}
    </ul>
  )
}
