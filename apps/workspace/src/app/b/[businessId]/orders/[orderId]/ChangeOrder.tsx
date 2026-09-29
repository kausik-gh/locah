'use client'

import { useRouter } from 'next/navigation'
import { useState, useTransition } from 'react'
import { ItemPicker, type CatalogueItem, type PickedLine } from '../ItemPicker'
import { changeOrder, type Changed } from '../phone-actions'

type Line = { id: string; title: string; quantity: number }
type Draft = { line_id?: string; offering_id?: string; variant_id?: string; options?: Record<string, unknown>; title: string; quantity: string }

const rupees = (v: number) =>
  new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', minimumFractionDigits: Number.isInteger(v) ? 0 : 2, maximumFractionDigits: 2 }).format(v)

/**
 * Change this order (FR-OR-18): quantities, lines taken off, items added. The
 * server works the new total, stock, tax and the money difference out before
 * anything is saved; saving needs the customer's agreement and is kept in the
 * order's history.
 */
export function ChangeOrder({ businessId, orderId, version, lines, items }: {
  businessId: string
  orderId: string
  version: number
  lines: Line[]
  items: CatalogueItem[]
}) {
  const router = useRouter()
  const [open, setOpen] = useState(false)
  const [draft, setDraft] = useState<Draft[]>(lines.map((l) => ({ line_id: l.id, title: l.title, quantity: String(l.quantity) })))
  const [result, setResult] = useState<Changed | null>(null)
  const [agreed, setAgreed] = useState(false)
  const [reason, setReason] = useState('')
  const [msg, setMsg] = useState<{ text: string; bad: boolean } | null>(null)
  const [pending, start] = useTransition()

  const body = () => ({
    lines: draft.map((d) => d.line_id
      ? { line_id: d.line_id, quantity: Number(d.quantity) }
      : { offering_id: d.offering_id, variant_id: d.variant_id, options: d.options, quantity: Number(d.quantity) }),
    reason: reason.trim() || null,
    customer_agreed: agreed,
    version,
  })
  const edit = (next: Draft[]) => {
    setDraft(next)
    setResult(null)
    setMsg(null)
  }
  const see = () => start(async () => {
    const r = await changeOrder(businessId, orderId, body(), true)
    if (!r.ok) return setMsg({ text: r.message, bad: true })
    setResult(r.data ?? null)
  })
  const save = () => start(async () => {
    const r = await changeOrder(businessId, orderId, body(), false)
    if (!r.ok) return setMsg({ text: r.message, bad: true })
    setMsg({ text: 'Order changed.', bad: false })
    setOpen(false)
    router.refresh()
  })

  if (!open) {
    return (
      <p><button type="button" className="btn-ghost" onClick={() => setOpen(true)}>Change order</button>
        {msg ? <span className="bos-status" role="status"> {msg.text}</span> : null}</p>
    )
  }
  return (
    <section className="bos-card bos-change" aria-labelledby="change-h">
      <h2 id="change-h">Change order</h2>
      {draft.map((d, i) => (
        <div key={i} className="bos-change__row">
          <span>{d.title}{d.line_id ? '' : ' (new)'}</span>
          <input aria-label={`How many ${d.title}`} inputMode="numeric" value={d.quantity}
            onChange={(e) => edit(draft.map((x, j) => (j === i ? { ...x, quantity: e.target.value } : x)))} />
          <button type="button" className="btn-quiet" onClick={() => edit(draft.filter((_, j) => j !== i))}>Remove</button>
        </div>
      ))}
      <h3 className="bos-rate__sub">Add an item</h3>
      <ItemPicker businessId={businessId} items={items} onAdd={(l: PickedLine) => edit([...draft, {
        offering_id: l.offering_id, variant_id: l.variant_id, options: l.options, title: l.label, quantity: String(l.quantity) }])} />
      <p style={{ marginTop: '.8rem' }}><button type="button" onClick={see} disabled={pending}>{pending ? 'Working it out…' : 'See the new total'}</button></p>
      {result ? (
        <div className="bos-change__result" role="status" aria-live="polite">
          <p><strong>{rupees(result.before_total)} → {rupees(result.total)}</strong>{result.changes.length ? ` · ${result.changes.join('; ')}` : ''}</p>
          <p>
            {result.paid ? `${rupees(result.paid)} already paid. ` : ''}
            {result.to_collect ? `${rupees(result.to_collect)} still to collect.` : ''}
            {result.refund_due ? `${rupees(result.refund_due)} to refund — it will show in Payments.` : ''}
          </p>
          <label className="bos-toggle">
            <input type="checkbox" checked={agreed} onChange={(e) => setAgreed(e.target.checked)} />
            <span className="bos-toggle__track" aria-hidden />
            <span>The customer agreed to this change</span>
          </label>
          <label style={{ display: 'block', marginTop: '.6rem' }}>
            <span className="bos-label">Why — optional</span>
            <input name="change-reason" value={reason} maxLength={300} onChange={(e) => setReason(e.target.value)} placeholder="Customer called to add one more" />
          </label>
          <p style={{ marginTop: '.6rem' }}><button type="button" onClick={save} disabled={pending || !agreed}>Save the change</button></p>
        </div>
      ) : null}
      <p className={`bos-status${msg?.bad ? ' bos-error' : ''}`} role="status" aria-live="polite">{msg?.text ?? ''}</p>
      <button type="button" className="btn-quiet" onClick={() => { setOpen(false); edit(lines.map((l) => ({ line_id: l.id, title: l.title, quantity: String(l.quantity) }))) }}>Keep the order as it is</button>
    </section>
  )
}
