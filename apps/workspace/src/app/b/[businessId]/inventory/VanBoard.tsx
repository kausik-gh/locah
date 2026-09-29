'use client'

import { useState, useTransition } from 'react'
import { useRouter } from 'next/navigation'
import { addVan, receiveTransfer, requestTransfer, sendTransfer } from './field-actions'
import type { Good, Place, TransferCard } from './TransferBoard'

export type VanLine = {
  offering_id: string
  title: string
  on_hand: number
  available: number
  on_hand_text: string
  available_text: string
}
export type VanCard = {
  location_id: string
  name: string
  lines: VanLine[]
  inbound: TransferCard[]
  outbound: TransferCard[]
}

const key = () => (typeof crypto !== 'undefined' && crypto.randomUUID ? crypto.randomUUID() : `key-${Date.now()}`)

export function VanBoard({
  businessId, vans, places, goods,
}: {
  businessId: string
  vans: VanCard[]
  places: Place[]
  goods: Good[]
}) {
  const router = useRouter()
  const [pending, start] = useTransition()
  const [msg, setMsg] = useState<string | null>(null)
  const [bad, setBad] = useState(false)
  const stores = places.filter((p) => p.stock_role !== 'van')
  const tracked = goods.filter((g) => g.track_inventory)

  const run = (fn: () => Promise<{ ok: boolean; message?: string }>, done: string) => {
    setMsg(null)
    start(async () => {
      const r = await fn()
      setBad(!r.ok)
      setMsg(r.ok ? done : (r.message || 'That did not save.'))
      if (r.ok) router.refresh()
    })
  }

  const move = (source: string, destination: string, offering: string, quantity: number, sendNow: boolean) => {
    run(async () => {
      const asked = await requestTransfer(businessId, {
        source_location_id: source, destination_location_id: destination,
        idempotency_key: key(), lines: [{ offering_id: offering, quantity }],
      })
      if (!asked.ok || !sendNow) return asked
      const id = (asked.data as { id?: string } | undefined)?.id
      if (!id) return { ok: false, message: 'The transfer was not created.' }
      return sendTransfer(businessId, id, key())
    }, sendNow ? 'On the way.' : 'Requested.')
  }

  return (
    <div className="bos-field">
      <form className="bos-field__request" onSubmit={(e) => {
        e.preventDefault()
        const name = String(new FormData(e.currentTarget).get('name') || '').trim()
        if (!name) return
        run(() => addVan(businessId, name), 'Van added.')
      }}>
        <h2>Add a van</h2>
        <label>Name
          <input name="name" required maxLength={120} placeholder="Service van" />
        </label>
        <button type="submit" className="btn" disabled={pending}>Add</button>
      </form>
      {msg ? <p className={bad ? 'bos-field__msg is-bad' : 'bos-field__msg'} role="status">{msg}</p> : null}
      {vans.length === 0 ? <p className="bos-empty">No van yet. A van is a stock location that carries parts.</p> : null}
      <div className="bos-van-board">
        {vans.map((van) => (
          <article key={van.location_id}>
            <header>
              <h2>{van.name}</h2>
              <span>{van.lines.reduce((n, ln) => n + ln.available, 0)} free</span>
            </header>
            {van.lines.length === 0 ? <p className="bos-empty">Nothing on this van.</p> : (
              <ul className="bos-van-board__stock">
                {van.lines.map((ln) => (
                  <li key={`${ln.offering_id}`}>
                    <strong>{ln.title}</strong>
                    <span>{ln.available_text} free</span>
                    {ln.on_hand !== ln.available ? <small>{ln.on_hand_text} on hand</small> : null}
                  </li>
                ))}
              </ul>
            )}
            {van.inbound.length > 0 ? (
              <section>
                <h3>Coming in</h3>
                <ul>
                  {van.inbound.map((t) => (
                    <li key={t.id}>
                      From {t.source_name}
                      {t.lines.map((ln) => <span key={ln.offering_id}> · {ln.title} {ln.quantity_text}</span>)}
                      <button type="button" disabled={pending} onClick={() => run(
                        () => receiveTransfer(businessId, t.id, key()), 'Received onto the van.',
                      )}>Receive</button>
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}
            {van.outbound.length > 0 ? (
              <section>
                <h3>Going back</h3>
                <ul>
                  {van.outbound.map((t) => (
                    <li key={t.id}>To {t.destination_name} · in transit</li>
                  ))}
                </ul>
              </section>
            ) : null}
            <form className="bos-field__request" onSubmit={(e) => {
              e.preventDefault()
              const form = new FormData(e.currentTarget)
              const offering = String(form.get('offering') || '')
              const quantity = Number(form.get('quantity') || 0)
              const store = String(form.get('store') || '')
              const direction = String(form.get('direction') || 'to-van')
              const source = direction === 'to-van' ? store : van.location_id
              const destination = direction === 'to-van' ? van.location_id : store
              move(source, destination, offering, quantity, form.get('send') === 'on')
            }}>
              <h3>Restock or return</h3>
              <label>Direction
                <select name="direction" defaultValue="to-van">
                  <option value="to-van">Central → this van</option>
                  <option value="to-store">This van → central</option>
                </select>
              </label>
              <label>Store
                <select name="store" required>
                  {stores.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
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
                <input name="send" type="checkbox" defaultChecked /> Send now
              </label>
              <button type="submit" className="btn" disabled={pending || stores.length === 0 || tracked.length === 0}>Move</button>
            </form>
          </article>
        ))}
      </div>
    </div>
  )
}
