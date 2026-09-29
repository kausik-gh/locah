'use client'

import { useRouter } from 'next/navigation'
import { useState, useTransition } from 'react'
import { createPlan, enrol, finaliseDay } from './member-actions'

export type PlanLite = {
  id: string
  name: string
  plan_kind: string
  kind_label: string
  price_amount: number
  duration_days: number | null
  sessions_included: number | null
  grace_days: number
  status: string
  billing_timing: string
  delivery: Record<string, unknown> | null
}
type Customer = { id: string; display_name: string; phone: string | null }
type Product = { id: string; title: string; price_amount: number | null }

const KINDS: [string, string][] = [
  ['access', 'Membership (gym, yoga, club access)'],
  ['session_pack', 'Session pack (10 PT sessions, 8 classes)'],
  ['recurring_delivery', 'Subscription (milk, tiffin, water cans)'],
  ['fee_plan', 'Fee plan (course fees in instalments)'],
  ['service_contract', 'Service contract (AMC)'],
  ['member_dues', 'Member dues (club, association)'],
]
const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

function Status({ error, done }: { error: string | null; done: string | null }) {
  return (
    <p className={`bos-status ${error ? 'bos-error' : ''}`} role="status">
      {error || done || ''}
    </p>
  )
}

/** A new plan, with only the rules its kind needs. */
export function PlanForm({ businessId, defaultKind, products }: { businessId: string; defaultKind: string; products: Product[] }) {
  const [kind, setKind] = useState(defaultKind)
  const [pending, start] = useTransition()
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState<string | null>(null)
  const [days, setDays] = useState<number[]>([0, 1, 2, 3, 4, 5, 6])
  const [rows, setRows] = useState([{ label: 'Admission', amount: '', due_after_days: '0' }])
  const router = useRouter()

  return (
    <form
      className="bos-money__form"
      style={{ marginTop: '.8rem' }}
      onSubmit={(e) => {
        e.preventDefault()
        const f = new FormData(e.currentTarget)
        const num = (k: string) => (f.get(k) ? Number(f.get(k)) : undefined)
        const body: Record<string, unknown> = {
          name: String(f.get('name')),
          plan_kind: kind,
          price_amount: num('price_amount') ?? 0,
          duration_days: num('duration_days'),
          status: 'active',
          visibility: String(f.get('visibility') || 'public'),
          grace_days: num('grace_days') ?? 0,
          grace_allows_entry: f.get('grace_allows_entry') === 'on',
          freeze_allowed: f.get('freeze_allowed') === 'on',
          max_freeze_days: num('max_freeze_days'),
        }
        if (kind === 'session_pack') Object.assign(body, { sessions_included: num('sessions_included'), consume_on: String(f.get('consume_on')) })
        if (kind === 'service_contract') body.visits_included = num('visits_included')
        if (kind === 'recurring_delivery') {
          body.billing_timing = String(f.get('billing_timing'))
          body.delivery = { offering_id: String(f.get('offering_id')), quantity: num('quantity') ?? 1, days, slot: String(f.get('slot') || ''), window: String(f.get('window') || ''), cutoff: String(f.get('cutoff') || '21:00'), mode: String(f.get('mode') || 'delivery') }
          if (body.billing_timing === 'postpaid') body.duration_days = undefined
        }
        if (kind === 'fee_plan')
          body.instalment_template = rows.filter((r) => r.amount).map((r) => ({ label: r.label, amount: Number(r.amount), due_after_days: Number(r.due_after_days || 0) }))
        setError(null)
        setDone(null)
        start(async () => {
          const r = await createPlan(businessId, body)
          if (!r.ok) setError(r.message)
          else {
            setDone('Plan saved.')
            router.push(`/b/${businessId}/memberships?kind=${kind}`)
          }
        })
      }}
    >
      <label className="bos-money__wide">
        <span>Kind</span>
        <select value={kind} onChange={(e) => setKind(e.target.value)}>
          {KINDS.map(([k, label]) => (
            <option key={k} value={k}>
              {label}
            </option>
          ))}
        </select>
      </label>
      <label>
        <span>Name</span>
        <input name="name" required maxLength={120} placeholder={kind === 'recurring_delivery' ? 'Morning milk' : 'Monthly'} />
      </label>
      <label>
        <span>{kind === 'fee_plan' ? 'Course fee (for the record)' : 'Price per period (₹)'}</span>
        <input name="price_amount" type="number" min="0" step="1" defaultValue={kind === 'fee_plan' ? 0 : undefined} />
      </label>
      <label>
        <span>{kind === 'fee_plan' ? 'Term length (days)' : kind === 'recurring_delivery' ? 'Paid period (days; prepaid)' : 'Length (days)'}</span>
        <input name="duration_days" type="number" min="1" max="3650" defaultValue={kind === 'member_dues' || kind === 'service_contract' ? 365 : 30} />
      </label>
      {kind !== 'fee_plan' && kind !== 'recurring_delivery' ? (
        <label>
          <span>Grace after it ends (days)</span>
          <input name="grace_days" type="number" min="0" max="90" defaultValue={kind === 'access' ? 3 : 0} />
        </label>
      ) : null}
      {kind === 'access' ? (
        <>
          <label className="bos-toggle">
            <input type="checkbox" name="grace_allows_entry" />
            <span className="bos-toggle__track" aria-hidden="true" />
            <span>Let members in during grace (amber at the desk)</span>
          </label>
          <label className="bos-toggle">
            <input type="checkbox" name="freeze_allowed" defaultChecked />
            <span className="bos-toggle__track" aria-hidden="true" />
            <span>Allow freezes</span>
          </label>
          <label>
            <span>Most freeze days per member</span>
            <input name="max_freeze_days" type="number" min="1" max="365" defaultValue={15} />
          </label>
        </>
      ) : null}
      {kind === 'session_pack' ? (
        <>
          <label>
            <span>Sessions in the pack</span>
            <input name="sessions_included" type="number" min="1" max="1000" required defaultValue={10} />
          </label>
          <label>
            <span>A session counts when</span>
            <select name="consume_on" defaultValue="completed">
              <option value="completed">the class or session is done</option>
              <option value="booked">it is booked</option>
              <option value="checkin">they check in</option>
            </select>
          </label>
        </>
      ) : null}
      {kind === 'service_contract' ? (
        <label>
          <span>Preventive visits covered</span>
          <input name="visits_included" type="number" min="1" max="365" defaultValue={2} />
        </label>
      ) : null}
      {kind === 'recurring_delivery' ? (
        <>
          <label>
            <span>What is delivered</span>
            <select name="offering_id" required>
              {products.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.title}
                  {p.price_amount ? ` · ₹${p.price_amount}` : ''}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>Usual quantity</span>
            <input name="quantity" type="number" min="1" max="1000" defaultValue={1} />
          </label>
          <label>
            <span>Billing</span>
            <select name="billing_timing" defaultValue="prepaid">
              <option value="prepaid">Prepaid for the period</option>
              <option value="postpaid">Postpaid — month-end bill on the khata</option>
            </select>
          </label>
          <label>
            <span>Slot</span>
            <input name="slot" maxLength={30} placeholder="Morning / Lunch" />
          </label>
          <label>
            <span>Delivery window</span>
            <input name="window" maxLength={30} placeholder="06:00-08:00" />
          </label>
          <label>
            <span>Cutoff (the day before)</span>
            <input name="cutoff" type="time" defaultValue="21:00" />
          </label>
          <label>
            <span>How</span>
            <select name="mode" defaultValue="delivery">
              <option value="delivery">Delivered</option>
              <option value="pickup">Picked up</option>
            </select>
          </label>
          <fieldset className="bos-money__wide bos-choices" style={{ border: 0, padding: 0 }}>
            <legend className="bos-hint">Delivery days</legend>
            {DAYS.map((d, i) => (
              <label key={d} className={`bos-choice ${days.includes(i) ? 'is-on' : ''}`}>
                <input type="checkbox" checked={days.includes(i)} onChange={(e) => setDays(e.target.checked ? [...days, i].sort() : days.filter((x) => x !== i))} />
                {d}
              </label>
            ))}
          </fieldset>
        </>
      ) : null}
      {kind === 'fee_plan' ? (
        <fieldset className="bos-money__wide" style={{ border: 0, padding: 0, display: 'grid', gap: '.5rem' }}>
          <legend className="bos-hint">Instalments (days after enrolment)</legend>
          {rows.map((r, i) => (
            <div key={i} className="bos-money__row">
              <input aria-label="Instalment name" value={r.label} onChange={(e) => setRows(rows.map((x, j) => (j === i ? { ...x, label: e.target.value } : x)))} />
              <input aria-label="Amount" type="number" min="1" placeholder="₹" value={r.amount} onChange={(e) => setRows(rows.map((x, j) => (j === i ? { ...x, amount: e.target.value } : x)))} />
              <input aria-label="Days after enrolment" type="number" min="0" value={r.due_after_days} onChange={(e) => setRows(rows.map((x, j) => (j === i ? { ...x, due_after_days: e.target.value } : x)))} />
            </div>
          ))}
          <button type="button" className="btn-ghost" onClick={() => setRows([...rows, { label: `Instalment ${rows.length + 1}`, amount: '', due_after_days: String(30 * rows.length) }])}>
            Add an instalment
          </button>
        </fieldset>
      ) : null}
      <button type="submit" disabled={pending}>
        {pending ? 'Saving…' : 'Save plan'}
      </button>
      <Status error={error} done={done} />
    </form>
  )
}

/** Enrol someone on a plan; the first charge follows (collect it on their page). */
export function EnrolForm({ businessId, plans, customers, kind }: { businessId: string; plans: PlanLite[]; customers: Customer[]; kind: string }) {
  const [pending, start] = useTransition()
  const [error, setError] = useState<string | null>(null)
  const router = useRouter()
  return (
    <form
      className="bos-money__form"
      onSubmit={(e) => {
        e.preventDefault()
        const f = new FormData(e.currentTarget)
        const body: Record<string, unknown> = {
          plan_id: String(f.get('plan_id')),
          customer_contact_id: String(f.get('customer_contact_id')),
          payment_method: 'pay_at_business',
          idempotency_key: crypto.randomUUID(),
        }
        if (f.get('starts_on')) body.starts_at = new Date(`${f.get('starts_on')}T00:00:00+05:30`).toISOString()
        if (f.get('payer_contact_id')) body.payer_contact_id = String(f.get('payer_contact_id'))
        if (kind === 'recurring_delivery' && f.get('quantity')) body.delivery = { quantity: Number(f.get('quantity')), address: f.get('address') ? { line1: String(f.get('address')) } : undefined }
        setError(null)
        start(async () => {
          const r = await enrol(businessId, body)
          if (!r.ok) setError(r.message)
          else if (r.data) router.push(`/b/${businessId}/memberships/${r.data.id}`)
        })
      }}
    >
      <label>
        <span>Plan</span>
        <select name="plan_id" required>
          {plans.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
      </label>
      <label>
        <span>{kind === 'fee_plan' ? 'Student' : 'Customer'}</span>
        <select name="customer_contact_id" required>
          {customers.map((c) => (
            <option key={c.id} value={c.id}>
              {c.display_name}
              {c.phone ? ` · ${c.phone}` : ''}
            </option>
          ))}
        </select>
      </label>
      {kind === 'fee_plan' ? (
        <label>
          <span>Who pays (parent or guardian)</span>
          <select name="payer_contact_id" defaultValue="">
            <option value="">The student</option>
            {customers.map((c) => (
              <option key={c.id} value={c.id}>
                {c.display_name}
              </option>
            ))}
          </select>
        </label>
      ) : null}
      {kind === 'recurring_delivery' ? (
        <>
          <label>
            <span>Quantity each day</span>
            <input name="quantity" type="number" min="1" max="1000" defaultValue={1} />
          </label>
          <label className="bos-money__wide">
            <span>Delivery address</span>
            <input name="address" maxLength={200} />
          </label>
        </>
      ) : null}
      <label>
        <span>Starts on</span>
        <input name="starts_on" type="date" />
      </label>
      <button type="submit" disabled={pending}>
        {pending ? 'Adding…' : 'Add'}
      </button>
      <Status error={error} done={null} />
    </form>
  )
}

/** Make tomorrow's orders now instead of waiting for the cutoff. */
export function FinaliseDay({ businessId, onDate }: { businessId: string; onDate: string }) {
  const [pending, start] = useTransition()
  const [msg, setMsg] = useState<string | null>(null)
  return (
    <span className="bos-money__row">
      <button
        type="button"
        className="btn-ghost"
        disabled={pending}
        onClick={() =>
          start(async () => {
            const r = await finaliseDay(businessId, onDate)
            setMsg(r.ok && r.data ? `${r.data.orders} orders made` : r.ok ? 'Done' : r.message)
          })
        }
      >
        Make tomorrow&apos;s orders now
      </button>
      {msg ? <span className="bos-status">{msg}</span> : null}
    </span>
  )
}
