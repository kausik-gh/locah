'use client'

import { useState, useTransition } from 'react'
import { saveCap } from './actions'

export type Meter = { resource: string; label: string; period: string; used: number; cap: number | null; counting: boolean }

const fmt = (n: number) => n.toLocaleString('en-IN')

/** One meter: this month's use against the owner's limit, and the limit editor. */
export function UsageMeter({ businessId, meter }: { businessId: string; meter: Meter }) {
  const [cap, setCap] = useState<number | null>(meter.cap)
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(meter.cap === null ? '' : String(meter.cap))
  const [pending, start] = useTransition()
  const [error, setError] = useState<string | null>(null)

  const pct = cap ? Math.min(100, Math.round((meter.used * 100) / cap)) : 0
  const tone = cap === null ? '' : pct >= 100 ? ' is-full' : pct >= 80 ? ' is-near' : ''
  const id = `meter-${meter.resource}`

  const submit = (value: number | null) => {
    setError(null)
    start(async () => {
      const r = await saveCap(businessId, meter.resource, value)
      if (r.ok) {
        setCap(value)
        setEditing(false)
      } else setError(r.message)
    })
  }

  return (
    <section className={`bos-card bos-meter${tone}`} aria-labelledby={id}>
      <div className="bos-card__head">
        <h3 id={id}>{meter.label}</h3>
        {!editing ? (
          <button type="button" className="btn-quiet" onClick={() => setEditing(true)}>
            {cap === null ? 'Set a limit' : 'Change limit'}
          </button>
        ) : null}
      </div>
      <p className="bos-meter__nums">
        <strong>{fmt(meter.used)}</strong>
        {cap !== null ? <span> of {fmt(cap)} this month</span> : <span> used this month · no limit</span>}
      </p>
      {cap !== null ? (
        <div
          className="bos-meter__bar"
          role="meter"
          aria-valuemin={0}
          aria-valuemax={cap}
          aria-valuenow={Math.min(meter.used, cap)}
          aria-label={`${meter.label}: ${pct}% of the limit used`}
        >
          <span style={{ width: `${pct}%` }} />
        </div>
      ) : null}
      {editing ? (
        <form
          className="bos-meter__form"
          onSubmit={(e) => {
            e.preventDefault()
            const n = draft.trim() === '' ? null : Number(draft.replace(/,/g, ''))
            if (n !== null && (!Number.isInteger(n) || n < 0)) {
              setError('Enter a whole number, or leave it empty for no limit.')
              return
            }
            submit(n)
          }}
        >
          <label>
            <span className="bos-label">Monthly limit</span>
            <input
              inputMode="numeric"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="No limit"
              aria-describedby={`${id}-help`}
            />
          </label>
          <p id={`${id}-help`} className="bos-hint" style={{ margin: 0 }}>
            Leave empty for no limit.
          </p>
          <div className="bos-meter__actions">
            <button type="submit" disabled={pending}>{pending ? 'Saving…' : 'Save limit'}</button>
            <button type="button" className="btn-quiet" onClick={() => setEditing(false)} disabled={pending}>
              Cancel
            </button>
          </div>
        </form>
      ) : null}
      {error ? <p className="bos-status bos-error" role="alert">{error}</p> : null}
    </section>
  )
}
