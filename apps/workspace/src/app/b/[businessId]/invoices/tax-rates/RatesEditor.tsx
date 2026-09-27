'use client'

import { useRouter } from 'next/navigation'
import { useState, useTransition } from 'react'
import { addRate, removeRate } from '../invoice-actions'
import { day } from '../types'

export type RateData = {
  today: string
  rates: { id: string; offering_id: string | null; offering_title: string | null; hsn_sac: string | null; rate: number; effective_from: string; effective_to: string | null; note: string | null }[]
  items: { id: string; title: string; hsn_sac: string | null; status: string; typed_rate: number | null; rate_today: number | null }[]
}

export function RatesEditor({ businessId, data }: { businessId: string; data: RateData }) {
  const router = useRouter()
  const [pending, start] = useTransition()
  const [msg, setMsg] = useState<{ text: string; bad?: boolean } | null>(null)
  const [target, setTarget] = useState<'hsn' | 'item'>('hsn')
  const [hsn, setHsn] = useState('')
  const [item, setItem] = useState('')
  const [rate, setRate] = useState('')
  const [from, setFrom] = useState(data.today)
  const [note, setNote] = useState('')
  const missing = data.items.filter((i) => i.rate_today === null)

  const add = (e: React.FormEvent) => {
    e.preventDefault()
    start(async () => {
      setMsg(null)
      const r = await addRate(businessId, {
        hsn_sac: target === 'hsn' ? hsn : undefined, offering_id: target === 'item' ? item : undefined,
        rate: Number(rate), effective_from: from, note: note || undefined,
      })
      setMsg({ text: r.ok ? 'Rate added' : r.message ?? 'That did not save', bad: !r.ok })
      if (r.ok) { setRate(''); setNote(''); router.refresh() }
    })
  }
  const remove = (id: string) => start(async () => {
    const r = await removeRate(businessId, id)
    setMsg({ text: r.ok ? 'Removed — bills already issued keep their rate' : r.message ?? 'That did not work', bad: !r.ok })
    if (r.ok) router.refresh()
  })

  const byHsn = data.rates.filter((r) => r.hsn_sac)
  const byItem = data.rates.filter((r) => r.offering_id)
  return (
    <div className="bos-works">
      {missing.length ? (
        <section className="bos-card bos-inv-needs" aria-label="Items without a rate">
          <h2>{missing.length} {missing.length === 1 ? 'item has' : 'items have'} no GST rate yet</h2>
          <p className="bos-hint">A tax invoice is not issued for an item without a rate. Add a rate for its HSN/SAC code below, or set one on the item.</p>
          <ul className="bos-inv-chiplist">{missing.slice(0, 12).map((i) => <li key={i.id}>{i.title}{i.hsn_sac ? ` · ${i.hsn_sac}` : ' · no HSN/SAC'}</li>)}</ul>
        </section>
      ) : null}

      <section className="bos-card" aria-labelledby="add-h">
        <h2 id="add-h">Add a rate</h2>
        <form className="bos-inv-form" onSubmit={add}>
          <div className="bos-choices">
            <label className="bos-choice"><input type="radio" checked={target === 'hsn'} onChange={() => setTarget('hsn')} /> For an HSN / SAC code</label>
            <label className="bos-choice"><input type="radio" checked={target === 'item'} onChange={() => setTarget('item')} /> For one item</label>
          </div>
          <div className="bos-form-grid">
            {target === 'hsn' ? (
              <label><span className="bos-label">HSN / SAC code</span>
                <input inputMode="numeric" value={hsn} onChange={(e) => setHsn(e.target.value.replace(/\D/g, '').slice(0, 8))} required placeholder="e.g. 1006" />
                <span className="bos-fieldhelp">A shorter code covers every longer code that starts with it.</span></label>
            ) : (
              <label><span className="bos-label">Item</span>
                <select value={item} onChange={(e) => setItem(e.target.value)} required>
                  <option value="">Choose</option>
                  {data.items.map((i) => <option key={i.id} value={i.id}>{i.title}</option>)}
                </select></label>
            )}
            <label><span className="bos-label">GST %</span><input inputMode="decimal" value={rate} onChange={(e) => setRate(e.target.value)} required /></label>
            <label><span className="bos-label">Applies from</span><input type="date" value={from} onChange={(e) => setFrom(e.target.value)} required /></label>
            <label><span className="bos-label">Note — optional</span><input value={note} onChange={(e) => setNote(e.target.value)} maxLength={300} placeholder="e.g. notification reference" /></label>
          </div>
          <p className="bos-fieldhelp">A new rate ends the previous one the day before it starts. Bills already issued keep the rate they were issued with.</p>
          <button type="submit" disabled={pending}>Add rate</button>
          {msg ? <p className={`bos-status${msg.bad ? ' bos-error' : ''}`} role="status">{msg.text}</p> : null}
        </form>
      </section>

      <RateTable title="By HSN / SAC code" rows={byHsn} label={(r) => r.hsn_sac ?? ''} onRemove={remove} pending={pending} today={data.today} />
      <RateTable title="For single items" rows={byItem} label={(r) => r.offering_title ?? 'Item'} onRemove={remove} pending={pending} today={data.today} />

      <section className="bos-card" aria-labelledby="items-h">
        <h2 id="items-h">What each item charges today</h2>
        <p className="bos-hint">Order of precedence: a dated rate for the item, then the longest matching HSN/SAC code, then the rate typed on the item.</p>
        <div className="ws-tablewrap">
          <table>
            <thead><tr><th>Item</th><th>HSN / SAC</th><th data-num>Rate on the item</th><th data-num>Charged today</th></tr></thead>
            <tbody>
              {data.items.map((i) => (
                <tr key={i.id}>
                  <td>{i.title}</td>
                  <td>{i.hsn_sac ?? '—'}</td>
                  <td data-num>{i.typed_rate === null ? '—' : `${i.typed_rate}%`}</td>
                  <td data-num>{i.rate_today === null ? <span className="bos-inv-warn">Not set</span> : `${i.rate_today}%`}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}

function RateTable({ title, rows, label, onRemove, pending, today }: {
  title: string
  rows: RateData['rates']
  label: (r: RateData['rates'][number]) => string
  onRemove: (id: string) => void
  pending: boolean
  today: string
}) {
  if (!rows.length) return null
  return (
    <section className="bos-card">
      <h2>{title}</h2>
      <ul className="bos-inv-rates">
        {rows.map((r) => {
          const current = r.effective_from <= today && (!r.effective_to || r.effective_to >= today)
          return (
            <li key={r.id} className={current ? 'is-current' : ''}>
              <strong>{label(r)}</strong>
              <span className="bos-inv-rates__rate">{r.rate}%</span>
              <span>{day(r.effective_from)} → {r.effective_to ? day(r.effective_to) : 'onwards'}{r.note ? ` · ${r.note}` : ''}</span>
              <span className={`bos-state${current ? ' is-ready' : ' is-off'}`}>{current ? 'In force' : r.effective_from > today ? 'Upcoming' : 'Ended'}</span>
              <button type="button" className="btn-quiet" disabled={pending} onClick={() => onRemove(r.id)}>Remove</button>
            </li>
          )
        })}
      </ul>
    </section>
  )
}
