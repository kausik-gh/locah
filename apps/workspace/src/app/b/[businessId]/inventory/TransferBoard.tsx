'use client'

import { useState, useTransition } from 'react'
import { useRouter } from 'next/navigation'
import { approveTransfer, receiveTransfer, requestTransfer, sendTransfer } from './field-actions'

export type TransferLine = { offering_id: string; title: string; quantity: number; quantity_text: string }
export type TransferCard = {
  id: string
  status: 'requested' | 'approved' | 'in_transit' | 'received' | 'cancelled'
  requires_approval: boolean
  source_name: string | null
  destination_name: string | null
  source_location_id: string
  destination_location_id: string
  note: string | null
  lines: TransferLine[]
}
export type Place = { id: string; name: string; stock_role?: string }
export type Good = { id: string; title: string; track_inventory: boolean }

const key = () => (typeof crypto !== 'undefined' && crypto.randomUUID ? crypto.randomUUID() : `key-${Date.now()}`)

export function TransferBoard({
  businessId, places, goods, transfers,
}: {
  businessId: string
  places: Place[]
  goods: Good[]
  transfers: TransferCard[]
}) {
  const router = useRouter()
  const [pending, start] = useTransition()
  const [msg, setMsg] = useState<string | null>(null)
  const [bad, setBad] = useState(false)
  const tracked = goods.filter((g) => g.track_inventory)
  const columns: { status: TransferCard['status'][]; title: string; hint: string }[] = [
    { status: ['requested', 'approved'], title: 'Requested', hint: 'Waiting to leave. Stock is still at the source until it is sent.' },
    { status: ['in_transit'], title: 'In transit', hint: 'Not available at the source or the destination.' },
    { status: ['received'], title: 'Received', hint: 'The destination has the quantity.' },
  ]

  const run = (fn: () => Promise<{ ok: boolean; message?: string }>, done: string) => {
    setMsg(null)
    start(async () => {
      const r = await fn()
      setBad(!r.ok)
      setMsg(r.ok ? done : (r.message || 'That did not save.'))
      if (r.ok) router.refresh()
    })
  }

  return (
    <div className="bos-field">
      <form className="bos-field__request" onSubmit={(e) => {
        e.preventDefault()
        const form = new FormData(e.currentTarget)
        const source = String(form.get('source') || '')
        const destination = String(form.get('destination') || '')
        const offering = String(form.get('offering') || '')
        const quantity = Number(form.get('quantity') || 0)
        run(() => requestTransfer(businessId, {
          source_location_id: source,
          destination_location_id: destination,
          requires_approval: form.get('approval') === 'on',
          note: String(form.get('note') || '') || null,
          idempotency_key: key(),
          lines: [{ offering_id: offering, quantity }],
        }), 'Transfer requested.')
      }}>
        <h2>Move stock</h2>
        <label>From
          <select name="source" required defaultValue={places[0]?.id ?? ''}>
            {places.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        </label>
        <label>To
          <select name="destination" required defaultValue={places[1]?.id ?? places[0]?.id ?? ''}>
            {places.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        </label>
        <label>Item
          <select name="offering" required>
            {tracked.map((g) => <option key={g.id} value={g.id}>{g.title}</option>)}
          </select>
        </label>
        <label>Qty
          <input name="quantity" type="number" min={1} required defaultValue={1} />
        </label>
        <label className="bos-field__check">
          <input name="approval" type="checkbox" /> Needs approval
        </label>
        <label>Note
          <input name="note" maxLength={300} placeholder="Optional" />
        </label>
        <button type="submit" className="btn" disabled={pending || tracked.length === 0 || places.length < 2}>Request</button>
      </form>
      {msg ? <p className={bad ? 'bos-field__msg is-bad' : 'bos-field__msg'} role="status">{msg}</p> : null}
      <div className="bos-transfer-board">
        {columns.map((col) => {
          const cards = transfers.filter((t) => col.status.includes(t.status))
          return (
            <section key={col.title} aria-label={col.title}>
              <header>
                <h2>{col.title}</h2>
                <span>{cards.length}</span>
              </header>
              <p>{col.hint}</p>
              {cards.length === 0 ? <p className="bos-empty">Nothing here.</p> : null}
              <ul>
                {cards.map((t) => (
                  <li key={t.id}>
                    <strong>{t.source_name} → {t.destination_name}</strong>
                    {t.status === 'approved' ? <em>Approved</em> : null}
                    <ul>
                      {t.lines.map((ln) => <li key={ln.offering_id}>{ln.title} · {ln.quantity_text}</li>)}
                    </ul>
                    {t.note ? <small>{t.note}</small> : null}
                    <div className="bos-field__actions">
                      {t.status === 'requested' && t.requires_approval ? (
                        <button type="button" disabled={pending} onClick={() => run(
                          () => approveTransfer(businessId, t.id, key()), 'Approved. It can leave now.',
                        )}>Approve</button>
                      ) : null}
                      {(t.status === 'requested' && !t.requires_approval) || t.status === 'approved' ? (
                        <button type="button" disabled={pending} onClick={() => run(
                          () => sendTransfer(businessId, t.id, key()), 'Sent. It is in transit.',
                        )}>Send</button>
                      ) : null}
                      {t.status === 'in_transit' ? (
                        <button type="button" disabled={pending} onClick={() => run(
                          () => receiveTransfer(businessId, t.id, key()), 'Received.',
                        )}>Receive</button>
                      ) : null}
                    </div>
                  </li>
                ))}
              </ul>
            </section>
          )
        })}
      </div>
    </div>
  )
}
