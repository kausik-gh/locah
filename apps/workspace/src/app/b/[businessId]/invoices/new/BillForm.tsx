'use client'

import { useRouter } from 'next/navigation'
import { useMemo, useState, useTransition } from 'react'
import { createBill, updateDraft } from '../invoice-actions'
import { rupees, type Bill, type Setup } from '../types'

export type CatalogueItem = {
  id: string
  title: string
  price_amount: number | null
  hsn_sac: string | null
  tax_rate: number | null
  status: string
  kind_label?: string
}
export type CustomerLite = { id: string; display_name: string; phone: string | null; email: string | null }

type Line = { key: string; offering_id: string; title: string; quantity: string; unit_price: string; discount: string; hsn_sac: string; rate: string }

const blank = (): Line => ({ key: Math.random().toString(36).slice(2), offering_id: '', title: '', quantity: '1', unit_price: '', discount: '', hsn_sac: '', rate: '' })

/**
 * A bill raised by hand. Catalogue lines take their price and rate from the
 * catalogue and the tax rates page; a free line (a service fee, a site visit)
 * carries its own HSN/SAC and rate. Place of supply defaults from the buyer's
 * GSTIN; the owner can change it.
 */
export function BillForm({ businessId, setup, items, customers, draft }: {
  businessId: string
  setup: Setup
  items: CatalogueItem[]
  customers: CustomerLite[]
  draft: Bill | null
}) {
  const router = useRouter()
  const [pending, start] = useTransition()
  const [error, setError] = useState<string | null>(null)
  const registers = setup.registers.filter((r) => r.status === 'active')
  const [registerId, setRegisterId] = useState(draft?.register_id ?? registers[0]?.id ?? '')
  const register = registers.find((r) => r.id === registerId)
  const registration = setup.registrations.find((r) => r.id === register?.registration_id)
  const regular = registration?.scheme === 'regular'
  const [contactId, setContactId] = useState('')
  const [business, setBusiness] = useState(Boolean(draft?.buyer?.gstin))
  const [buyer, setBuyer] = useState({
    name: draft?.buyer?.name ?? '', phone: draft?.buyer?.phone ?? '', gstin: draft?.buyer?.gstin ?? '',
    address: draft?.buyer?.address ?? '', state_code: draft?.buyer?.state_code ?? '',
  })
  const gstinState = /^\d{2}/.test(buyer.gstin) ? buyer.gstin.slice(0, 2) : ''
  const [pos, setPos] = useState(draft?.place_of_supply ?? '')
  const effectivePos = pos || (business ? gstinState || buyer.state_code : '') || registration?.state_code || ''
  const [reverse, setReverse] = useState(draft?.reverse_charge ?? false)
  const [lines, setLines] = useState<Line[]>(() =>
    draft?.lines?.length
      ? draft.lines.map((l) => ({
          key: l.id, offering_id: l.offering_id ?? '', title: l.title, quantity: String(l.quantity),
          unit_price: String(l.unit_price), discount: l.discount ? String(l.discount) : '', hsn_sac: l.hsn_sac ?? '',
          rate: l.tax_rate === null ? '' : String(l.tax_rate),
        }))
      : [blank()],
  )
  const [due, setDue] = useState(draft?.due_date ?? '')
  const [notes, setNotes] = useState(draft?.notes ?? '')
  const byId = useMemo(() => new Map(items.map((i) => [i.id, i])), [items])

  const set = (i: number, patch: Partial<Line>) => setLines((ls) => ls.map((l, j) => (j === i ? { ...l, ...patch } : l)))
  const pick = (i: number, id: string) => {
    const it = byId.get(id)
    set(i, it ? { offering_id: id, title: it.title, unit_price: it.price_amount === null ? '' : String(it.price_amount), hsn_sac: it.hsn_sac ?? '', rate: '' }
      : { offering_id: '', title: '' })
  }
  const pickCustomer = (id: string) => {
    setContactId(id)
    const c = customers.find((x) => x.id === id)
    if (c) setBuyer((bb) => ({ ...bb, name: c.display_name, phone: c.phone ?? '' }))
  }
  const rough = lines.reduce((s, l) => s + Number(l.quantity || 0) * Number(l.unit_price || 0) - Number(l.discount || 0), 0)

  const submit = (issue: boolean) =>
    start(async () => {
      setError(null)
      const body: Record<string, unknown> = {
        register_id: registerId || undefined,
        customer_contact_id: contactId || undefined,
        buyer: {
          name: buyer.name || undefined, phone: buyer.phone || undefined,
          ...(business ? { gstin: buyer.gstin || undefined, address: buyer.address || undefined, state_code: gstinState || buyer.state_code || undefined } : {}),
        },
        place_of_supply: regular || registration?.scheme === 'composition' ? effectivePos || undefined : undefined,
        reverse_charge: regular && business && reverse,
        due_date: due || undefined,
        notes: notes || undefined,
        issue,
        lines: lines.filter((l) => l.offering_id || l.title.trim()).map((l) => ({
          offering_id: l.offering_id || undefined,
          title: l.offering_id ? undefined : l.title.trim(),
          quantity: Number(l.quantity || 0),
          unit_price: l.unit_price === '' ? undefined : Number(l.unit_price),
          discount: l.discount ? Number(l.discount) : undefined,
          hsn_sac: l.offering_id ? undefined : l.hsn_sac || undefined,
          rate: l.offering_id || !regular || l.rate === '' ? undefined : Number(l.rate),
        })),
      }
      const r = draft ? await updateDraft(businessId, draft.id, body) : await createBill(businessId, body)
      if (!r.ok || !r.data) return setError(r.ok ? 'Nothing came back' : r.message)
      router.push(`/b/${businessId}/invoices/${r.data.id}`)
    })

  return (
    <div className="bos-works bos-inv-new">
      {registers.length > 1 ? (
        <section className="bos-card">
          <h2>Billed from</h2>
          <label style={{ maxWidth: 360, display: 'block' }}>
            <span className="bos-label">Register</span>
            <select value={registerId} onChange={(e) => setRegisterId(e.target.value)}>
              {registers.map((r) => <option key={r.id} value={r.id}>{r.name} · {r.location_name} ({r.code})</option>)}
            </select>
          </label>
        </section>
      ) : null}

      <section className="bos-card" aria-labelledby="buyer-h">
        <h2 id="buyer-h">Customer</h2>
        <div className="bos-form-grid">
          {customers.length ? (
            <label>
              <span className="bos-label">From your customers — optional</span>
              <select value={contactId} onChange={(e) => pickCustomer(e.target.value)}>
                <option value="">Someone new or walk-in</option>
                {customers.map((c) => <option key={c.id} value={c.id}>{c.display_name}{c.phone ? ` · ${c.phone}` : ''}</option>)}
              </select>
            </label>
          ) : null}
          <label><span className="bos-label">Name{business ? '' : ' — optional'}</span><input value={buyer.name} onChange={(e) => setBuyer({ ...buyer, name: e.target.value })} maxLength={200} /></label>
          <label><span className="bos-label">Phone — optional</span><input value={buyer.phone} onChange={(e) => setBuyer({ ...buyer, phone: e.target.value })} inputMode="tel" maxLength={20} /></label>
        </div>
        {registration?.scheme !== 'unregistered' ? (
          <label className="bos-toggle" style={{ marginTop: '.8rem' }}>
            <input type="checkbox" checked={business} onChange={(e) => setBusiness(e.target.checked)} />
            <span className="bos-toggle__track" aria-hidden />
            <span>A registered business (has a GSTIN)</span>
          </label>
        ) : null}
        {business ? (
          <div className="bos-form-grid" style={{ marginTop: '.8rem' }}>
            <label><span className="bos-label">Buyer GSTIN</span><input value={buyer.gstin} onChange={(e) => setBuyer({ ...buyer, gstin: e.target.value.toUpperCase().replace(/\s/g, '') })} maxLength={15} placeholder="15 characters" /></label>
            <label className="bos-form-wide"><span className="bos-label">Billing address — optional</span><input value={buyer.address} onChange={(e) => setBuyer({ ...buyer, address: e.target.value })} maxLength={500} /></label>
          </div>
        ) : null}
        {registration && registration.scheme !== 'unregistered' ? (
          <div className="bos-form-grid" style={{ marginTop: '.8rem' }}>
            <label>
              <span className="bos-label">Place of supply</span>
              <select value={effectivePos} onChange={(e) => setPos(e.target.value)}>
                {setup.states.map((s) => <option key={s.code} value={s.code}>{s.name} ({s.code})</option>)}
              </select>
              <span className="bos-fieldhelp">
                {effectivePos && effectivePos === registration.state_code ? 'Same state as you: CGST + SGST.' : 'Another state: IGST.'}{' '}
                Usually where the goods are delivered. Unsure? Confirm with your CA.
              </span>
            </label>
            {regular && business ? (
              <label className="bos-toggle" style={{ alignSelf: 'center' }}>
                <input type="checkbox" checked={reverse} onChange={(e) => setReverse(e.target.checked)} />
                <span className="bos-toggle__track" aria-hidden />
                <span>Reverse charge applies (confirm with your CA)</span>
              </label>
            ) : null}
          </div>
        ) : null}
      </section>

      <section className="bos-card" aria-labelledby="lines-h">
        <h2 id="lines-h">What was sold</h2>
        <p className="bos-hint">
          Prices are {setup.profile?.prices_include_tax ? 'including' : 'before'} GST, as set in Tax &amp; invoicing.
          {regular ? ' Items take their GST rate from your tax rates; a line you type yourself needs its own.' : ' No GST is charged on your bills.'}
        </p>
        <ul className="bos-inv-lines">
          {lines.map((l, i) => (
            <li key={l.key}>
              <label className="bos-inv-lines__item">
                <span className="bos-label">Item</span>
                <select value={l.offering_id} onChange={(e) => pick(i, e.target.value)}>
                  <option value="">Type a line yourself</option>
                  {items.map((it) => <option key={it.id} value={it.id}>{it.title}{it.price_amount !== null ? ` · ${rupees(it.price_amount)}` : ''}</option>)}
                </select>
              </label>
              {!l.offering_id ? (
                <label className="bos-inv-lines__title"><span className="bos-label">Description</span><input value={l.title} onChange={(e) => set(i, { title: e.target.value })} maxLength={300} /></label>
              ) : null}
              <label><span className="bos-label">Qty</span><input inputMode="decimal" value={l.quantity} onChange={(e) => set(i, { quantity: e.target.value })} /></label>
              <label><span className="bos-label">Price</span><input inputMode="decimal" value={l.unit_price} onChange={(e) => set(i, { unit_price: e.target.value })} /></label>
              <label><span className="bos-label">Discount</span><input inputMode="decimal" value={l.discount} onChange={(e) => set(i, { discount: e.target.value })} placeholder="0" /></label>
              {!l.offering_id && regular ? (
                <>
                  <label><span className="bos-label">HSN/SAC</span><input inputMode="numeric" value={l.hsn_sac} onChange={(e) => set(i, { hsn_sac: e.target.value.replace(/\D/g, '') })} maxLength={8} /></label>
                  <label><span className="bos-label">GST %</span><input inputMode="decimal" value={l.rate} onChange={(e) => set(i, { rate: e.target.value })} /></label>
                </>
              ) : null}
              {lines.length > 1 ? <button type="button" className="btn-quiet" onClick={() => setLines(lines.filter((_, j) => j !== i))}>Remove</button> : null}
            </li>
          ))}
        </ul>
        <button type="button" className="btn-ghost" onClick={() => setLines([...lines, blank()])}>Add a line</button>
      </section>

      <section className="bos-card" aria-labelledby="more-h">
        <h2 id="more-h">Terms</h2>
        <div className="bos-form-grid">
          <label><span className="bos-label">Due date — optional</span><input type="date" value={due} onChange={(e) => setDue(e.target.value)} /></label>
          <label className="bos-form-wide"><span className="bos-label">Note on the bill — optional</span><textarea rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={2000} /></label>
        </div>
      </section>

      <div className="bos-savebar">
        <span className="bos-inv-rough">About {rupees(rough)} {setup.profile?.prices_include_tax || !regular ? '' : '+ GST'}</span>
        <button type="button" onClick={() => submit(true)} disabled={pending}>{pending ? 'Working…' : 'Issue bill'}</button>
        <button type="button" className="btn-ghost" onClick={() => submit(false)} disabled={pending}>Save draft</button>
        <p className={`bos-status${error ? ' bos-error' : ''}`} role="status" aria-live="polite">{error ?? ''}</p>
      </div>
    </div>
  )
}
