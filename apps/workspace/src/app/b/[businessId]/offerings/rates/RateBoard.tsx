'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useState, useTransition } from 'react'
import { inr } from '../types'
import { addRate, enterRate } from './rate-actions'

export type Rate = {
  id: string
  key: string
  label: string
  unit: string
  unit_label: string
  value: number | null
  effective_from: string | null
  history: { value: number; effective_from: string; note: string | null }[]
  items: { id: string; title: string; status: string; price_amount: number | null; basis: string | null }[]
}

const UNITS: [string, string][] = [
  ['g', 'per gram'],
  ['kg', 'per kg'],
  ['carat', 'per carat'],
  ['piece', 'per piece'],
  ['ml', 'per ml'],
  ['l', 'per litre'],
]
const ZONE = 'Asia/Kolkata'

function dayKey(iso: string | Date) {
  return new Date(iso).toLocaleDateString('en-CA', { timeZone: ZONE })
}

function whenWords(iso: string) {
  const time = new Date(iso).toLocaleTimeString('en-IN', { timeZone: ZONE, hour: 'numeric', minute: '2-digit' })
  if (dayKey(iso) === dayKey(new Date())) return `today, ${time}`
  return new Date(iso).toLocaleDateString('en-IN', { timeZone: ZONE, day: 'numeric', month: 'short' }) + `, ${time}`
}

function rupees(v: number) {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    minimumFractionDigits: Number.isInteger(v) ? 0 : 2,
    maximumFractionDigits: 2,
  }).format(v)
}

export function RateBoard({ businessId, rates }: { businessId: string; rates: Rate[] }) {
  return (
    <div className="bos-works bos-rates">
      {rates.length === 0 ? (
        <div className="bos-empty">
          No rates yet. Add the rate you price by — for example 22K gold per gram — then price items from it in
          Products & services.
        </div>
      ) : (
        rates.map((r) => <RateCard key={r.id} businessId={businessId} rate={r} />)
      )}
      <AddRate businessId={businessId} />
    </div>
  )
}

function RateCard({ businessId, rate: r }: { businessId: string; rate: Rate }) {
  const router = useRouter()
  const [value, setValue] = useState('')
  const [note, setNote] = useState('')
  const [pending, start] = useTransition()
  const [msg, setMsg] = useState<{ text: string; bad: boolean } | null>(null)
  const today = r.effective_from !== null && dayKey(r.effective_from) === dayKey(new Date())
  const unit = r.unit_label === 'g' ? 'gram' : r.unit_label

  const save = () => {
    setMsg(null)
    const n = Number(value.replace(/[,₹\s]/g, ''))
    if (!value.trim() || !Number.isFinite(n) || n <= 0) return setMsg({ text: `Enter today's rate per ${unit}.`, bad: true })
    start(async () => {
      const res = await enterRate(businessId, r.id, n, note.trim() || null)
      if (!res.ok) return setMsg({ text: res.message, bad: true })
      const count = res.data?.repriced.length ?? 0
      setMsg({ text: `Saved. ${count === 1 ? '1 item' : `${count} items`} now priced at ${rupees(n)} per ${unit}.`, bad: false })
      setValue('')
      setNote('')
      router.refresh()
    })
  }

  return (
    <section className="bos-card bos-rate" aria-labelledby={`rate-${r.id}`}>
      <div className="bos-rate__head">
        <h2 id={`rate-${r.id}`}>{r.label}</h2>
        <p className="bos-rate__now">
          {r.value !== null ? (
            <>
              <strong>{rupees(r.value)}</strong> per {unit}
            </>
          ) : (
            <strong>No rate yet</strong>
          )}
        </p>
        <span className={`bos-state${today ? ' is-ready' : ' is-warn'}`}>
          {r.effective_from ? (today ? 'Entered today' : 'Not entered today') : 'Not entered'}
        </span>
      </div>
      {r.effective_from ? <p className="bos-hint">Last entered {whenWords(r.effective_from)}.</p> : null}
      <div className="bos-form-grid bos-rate__form">
        <label>
          <span className="bos-label">Today&apos;s rate (₹ per {unit})</span>
          <input name={`rate-${r.key}`} inputMode="decimal" value={value} onChange={(e) => setValue(e.target.value)}
            placeholder={r.value !== null ? String(r.value) : ''} />
        </label>
        <label>
          <span className="bos-label">Note — optional</span>
          <input value={note} onChange={(e) => setNote(e.target.value)} maxLength={200} placeholder="Morning rate" />
        </label>
        <div className="bos-rate__save">
          <button type="button" onClick={save} disabled={pending}>{pending ? 'Saving…' : 'Save rate'}</button>
        </div>
      </div>
      <p className={`bos-status${msg?.bad ? ' bos-error' : ''}`} role="status" aria-live="polite">{msg?.text ?? ''}</p>

      <h3 className="bos-rate__sub">Priced from this rate</h3>
      {r.items.length === 0 ? (
        <p className="bos-hint">
          No items yet. Open an item in <Link href={`/b/${businessId}/offerings`}>Products & services</Link> and choose
          &ldquo;From a rate&rdquo; under Price.
        </p>
      ) : (
        <ul className="bos-catalogue">
          {r.items.map((i) => (
            <li key={i.id} className={i.status === 'archived' ? 'is-muted' : ''}>
              <Link href={`/b/${businessId}/offerings/${i.id}`} className="bos-catalogue__main">
                <strong>{i.title}</strong>
                <span>{i.price_amount !== null ? inr(i.price_amount) : 'No price until the rate is entered'}</span>
                {i.basis ? <span className="bos-rate__basis">{i.basis}</span> : null}
              </Link>
            </li>
          ))}
        </ul>
      )}
      {r.history.length ? (
        <details className="bos-rate__history">
          <summary>Rates entered</summary>
          <ul>
            {r.history.map((h) => (
              <li key={h.effective_from}>
                <span>{whenWords(h.effective_from)}</span>
                <strong>{rupees(h.value)}</strong>
                {h.note ? <span className="bos-hint">{h.note}</span> : null}
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </section>
  )
}

function AddRate({ businessId }: { businessId: string }) {
  const router = useRouter()
  const [label, setLabel] = useState('')
  const [unit, setUnit] = useState('g')
  const [value, setValue] = useState('')
  const [pending, start] = useTransition()
  const [msg, setMsg] = useState<{ text: string; bad: boolean } | null>(null)
  const add = () => {
    setMsg(null)
    if (!label.trim()) return setMsg({ text: 'Name the rate, for example 22K gold.', bad: true })
    const n = value.trim() ? Number(value.replace(/[,₹\s]/g, '')) : null
    if (n !== null && (!Number.isFinite(n) || n <= 0)) return setMsg({ text: 'Enter the rate as a number.', bad: true })
    start(async () => {
      const res = await addRate(businessId, { label: label.trim(), unit, value: n })
      if (!res.ok) return setMsg({ text: res.message, bad: true })
      setMsg({ text: `Added ${label.trim()}.`, bad: false })
      setLabel('')
      setValue('')
      router.refresh()
    })
  }
  return (
    <section className="bos-card" aria-labelledby="add-rate-h">
      <h2 id="add-rate-h">Add a rate</h2>
      <div className="bos-form-grid">
        <label>
          <span className="bos-label">Name</span>
          <input name="new-rate-label" value={label} onChange={(e) => setLabel(e.target.value)} maxLength={60} placeholder="22K gold" />
        </label>
        <label>
          <span className="bos-label">Rate is</span>
          <select name="new-rate-unit" value={unit} onChange={(e) => setUnit(e.target.value)}>
            {UNITS.map(([k, l]) => (
              <option key={k} value={k}>{l}</option>
            ))}
          </select>
        </label>
        <label>
          <span className="bos-label">Today&apos;s rate (₹) — optional</span>
          <input name="new-rate-value" inputMode="decimal" value={value} onChange={(e) => setValue(e.target.value)} />
        </label>
      </div>
      <button type="button" className="btn-ghost" onClick={add} disabled={pending}>{pending ? 'Adding…' : 'Add rate'}</button>
      <p className={`bos-status${msg?.bad ? ' bos-error' : ''}`} role="status" aria-live="polite">{msg?.text ?? ''}</p>
    </section>
  )
}
