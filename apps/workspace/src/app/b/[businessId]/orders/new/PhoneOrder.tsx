'use client'

import Link from 'next/link'
import { useEffect, useState, useTransition } from 'react'
import { sendPaymentLink } from '@/lib/collect-actions'
import { ItemPicker, type CatalogueItem, type PickedLine } from '../ItemPicker'
import { placePhoneOrder, pricePhoneOrder, type Placed, type Priced } from '../phone-actions'

const rupees = (v: number) =>
  new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', minimumFractionDigits: Number.isInteger(v) ? 0 : 2, maximumFractionDigits: 2 }).format(v)
const hour = (t: string) => {
  const [h, m] = t.split(':').map(Number)
  return `${h % 12 || 12}${m ? `:${String(m).padStart(2, '0')}` : ''} ${h < 12 ? 'am' : 'pm'}`
}

/**
 * Take a phone order (FR-OR-13): the caller's name and number, what they want,
 * pickup or delivery, the day for a made-to-order item — priced by the server
 * exactly as the website prices it, and placed through the same order path.
 */
export function PhoneOrder({ businessId, items, modes }: { businessId: string; items: CatalogueItem[]; modes: string[] }) {
  const [name, setName] = useState('')
  const [phone, setPhone] = useState('')
  const [basket, setBasket] = useState<PickedLine[]>([])
  const [mode, setMode] = useState(modes.includes('pickup') ? 'pickup' : modes[0] ?? 'pickup')
  const [address, setAddress] = useState({ line1: '', city: '', postal_code: '' })
  const [dueDate, setDueDate] = useState('')
  const [dueTime, setDueTime] = useState('')
  const [priced, setPriced] = useState<Priced | null>(null)
  const [priceError, setPriceError] = useState<string | null>(null)
  const [placed, setPlaced] = useState<Placed | null>(null)
  const [msg, setMsg] = useState<{ text: string; bad: boolean } | null>(null)
  const [pending, start] = useTransition()

  const delivery = mode === 'delivery'
  const body = () => ({
    items: basket.map(({ offering_id, variant_id, quantity, options }) => ({ offering_id, variant_id, quantity, options })),
    fulfilment_mode: mode,
    ...(delivery && address.line1 && address.city ? { delivery_address: address } : {}),
    ...(dueDate ? { due: { date: dueDate, time: dueTime } } : {}),
  })

  useEffect(() => {
    if (!basket.length) {
      setPriced(null)
      return
    }
    const t = setTimeout(async () => {
      const r = await pricePhoneOrder(businessId, body())
      if (!r.ok) return setPriceError(r.message)
      setPriceError(null)
      const p = r.data ?? null
      setPriced(p)
      if (p?.preorder.needed && !dueDate) {
        const first = p.preorder.dates.find((d) => !d.full)
        if (first) {
          setDueDate(first.date)
          setDueTime(first.times[0] ?? '')
        }
      }
    }, 250)
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [basket, mode, address.line1, address.city, address.postal_code, dueDate, dueTime])

  const place = () => {
    setMsg(null)
    if (!name.trim()) return setMsg({ text: 'Enter the caller’s name.', bad: true })
    if (phone.replace(/\D/g, '').length < 10) return setMsg({ text: 'Enter their phone number.', bad: true })
    if (!basket.length) return setMsg({ text: 'Add what they want.', bad: true })
    start(async () => {
      const r = await placePhoneOrder(businessId, { ...body(), customer: { name: name.trim(), phone }, payment_method: 'cod' })
      if (!r.ok) return setMsg({ text: r.message, bad: true })
      setPlaced(r.data ?? null)
    })
  }
  const sendLink = () => {
    if (!placed?.advance) return
    start(async () => {
      const r = await sendPaymentLink(businessId, placed.advance!.request_id, placed.advance!.url)
      setMsg(r.ok ? { text: 'Advance link sent on WhatsApp.', bad: false } : { text: r.message, bad: true })
    })
  }

  if (placed) {
    return (
      <section className="bos-card" aria-labelledby="placed-h">
        <h2 id="placed-h">Order {placed.confirmation.order_number} placed</h2>
        <p>{rupees(placed.confirmation.grand_total)} for {name}. It is in Orders like every other order.</p>
        {placed.advance ? (
          <div className="bos-phone__advance">
            <p><strong>Advance {rupees(placed.advance.amount)}</strong> — send them the link, or read it out:</p>
            <p className="bos-hint"><code>{placed.advance.url}</code></p>
            <button type="button" onClick={sendLink} disabled={pending}>Send the link on WhatsApp</button>
          </div>
        ) : null}
        <p style={{ display: 'flex', gap: '.6rem', flexWrap: 'wrap', marginTop: '.8rem' }}>
          <Link className="btn" href={`/b/${businessId}/orders/${placed.order.id}`}>Open the order</Link>
          <button type="button" className="btn-ghost" onClick={() => { setPlaced(null); setBasket([]); setName(''); setPhone(''); setDueDate(''); setMsg(null) }}>
            Take another order
          </button>
        </p>
        <p className={`bos-status${msg?.bad ? ' bos-error' : ''}`} role="status" aria-live="polite">{msg?.text ?? ''}</p>
      </section>
    )
  }

  const pre = priced?.preorder
  const day = pre?.dates.find((d) => d.date === dueDate)
  return (
    <div className="bos-works bos-phone">
      <section className="bos-card" aria-labelledby="caller-h">
        <h2 id="caller-h">Who is calling</h2>
        <div className="bos-form-grid">
          <label><span className="bos-label">Name</span><input name="caller-name" value={name} onChange={(e) => setName(e.target.value)} maxLength={120} /></label>
          <label><span className="bos-label">Phone</span><input name="caller-phone" inputMode="tel" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="98400 12345" /></label>
        </div>
      </section>

      <section className="bos-card" aria-labelledby="what-h">
        <h2 id="what-h">What they want</h2>
        <ItemPicker businessId={businessId} items={items} onAdd={(l) => setBasket((b) => [...b, l])} />
        {basket.length ? (
          <ul className="bos-phone__basket">
            {basket.map((l, i) => (
              <li key={i}>
                <span>{l.quantity} × {l.label}</span>
                <button type="button" className="btn-quiet" onClick={() => setBasket((b) => b.filter((_, j) => j !== i))}>Remove</button>
              </li>
            ))}
          </ul>
        ) : null}
      </section>

      <section className="bos-card" aria-labelledby="how-h">
        <h2 id="how-h">Pickup or delivery</h2>
        <fieldset className="bos-choices" style={{ border: 0, padding: 0, margin: 0 }}>
          <legend className="sr-only">Pickup or delivery</legend>
          {modes.map((m) => (
            <label key={m} className="bos-choice">
              <input type="radio" name="mode" checked={mode === m} onChange={() => setMode(m)} />
              {m === 'delivery' ? 'Delivery' : 'Pickup'}
            </label>
          ))}
        </fieldset>
        {delivery ? (
          <div className="bos-form-grid" style={{ marginTop: '.6rem' }}>
            <label><span className="bos-label">Address</span><input name="addr-line1" value={address.line1} onChange={(e) => setAddress({ ...address, line1: e.target.value })} /></label>
            <label><span className="bos-label">City</span><input name="addr-city" value={address.city} onChange={(e) => setAddress({ ...address, city: e.target.value })} /></label>
            <label><span className="bos-label">PIN code</span><input name="addr-pin" inputMode="numeric" value={address.postal_code} onChange={(e) => setAddress({ ...address, postal_code: e.target.value })} /></label>
          </div>
        ) : null}
        {pre && (pre.needed || pre.offered) ? (
          <div className="bos-form-grid" style={{ marginTop: '.6rem' }}>
            <label>
              <span className="bos-label">Day wanted{pre.needed ? '' : ' — optional'}</span>
              <select name="due-date" value={dueDate} onChange={(e) => { setDueDate(e.target.value); setDueTime(pre.dates.find((d) => d.date === e.target.value)?.times[0] ?? '') }}>
                {pre.needed ? null : <option value="">As soon as possible</option>}
                {pre.dates.map((d) => <option key={d.date} value={d.date} disabled={d.full}>{d.label}{d.full ? ' — full' : ''}</option>)}
              </select>
            </label>
            {day ? (
              <label>
                <span className="bos-label">Ready at</span>
                <select name="due-time" value={dueTime} onChange={(e) => setDueTime(e.target.value)}>
                  {day.times.map((t) => <option key={t} value={t}>{hour(t)}</option>)}
                </select>
              </label>
            ) : null}
          </div>
        ) : null}
      </section>

      <section className="bos-card" aria-labelledby="total-h">
        <h2 id="total-h">Total</h2>
        {priceError ? <p className="bos-error">{priceError}</p> : null}
        {priced ? (
          <>
            <ul className="bos-phone__lines">
              {priced.lines.map((l, i) => <li key={i}><span>{l.quantity} × {l.title}</span><strong>{rupees(l.line_total)}</strong></li>)}
              {priced.delivery?.charge ? <li><span>Delivery</span><strong>{rupees(priced.delivery.charge)}</strong></li> : null}
              {priced.tax_amount ? <li className="bos-hint"><span>GST{priced.tax_included ? ' (included)' : ''}</span><span>{rupees(priced.tax_amount)}</span></li> : null}
              <li className="is-total"><span>Total</span><strong>{rupees(priced.total)}</strong></li>
            </ul>
            {delivery && priced.delivery && !priced.delivery.serviceable ? <p className="bos-error">That address is outside your delivery areas.</p> : null}
            {priced.problems.map((p) => <p key={p.offering_id} className="bos-error">{p.message}</p>)}
            {priced.due_error ? <p className="bos-error">{priced.due_error}</p> : null}
            {pre?.advance ? <p>Advance to ask: <strong>{rupees(pre.advance)}</strong> — a payment link is made when you place it.</p> : null}
            <p className="bos-hint">Paid at {delivery ? 'delivery' : 'pickup'}{pre?.advance ? ', after the advance' : ''}.</p>
          </>
        ) : (
          <p className="bos-hint">Add items to see the total.</p>
        )}
        <button type="button" onClick={place} disabled={pending || !basket.length}>{pending ? 'Placing…' : 'Place the order'}</button>
        <p className={`bos-status${msg?.bad ? ' bos-error' : ''}`} role="status" aria-live="polite">{msg?.text ?? ''}</p>
      </section>
    </div>
  )
}
