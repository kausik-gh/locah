'use client'

import { useRouter } from 'next/navigation'
import { useState, useTransition } from 'react'
import { openAccount } from './khata-actions'

/**
 * Open a khata by hand — a customer carried over from the notebook with what
 * they already owe, or a supplier you buy from on credit.
 */
export function OpenAccount({ businessId, party: initial }: { businessId: string; party: 'customer' | 'supplier' }) {
  const router = useRouter()
  const [open, setOpen] = useState(false)
  const [pending, start] = useTransition()
  const [error, setError] = useState<string | null>(null)
  const [party, setParty] = useState(initial)
  const [f, setF] = useState({ name: '', phone: '', gstin: '', opening: '', limit: '', days: '' })
  const set = (k: keyof typeof f, v: string) => setF((x) => ({ ...x, [k]: v }))

  const submit = () =>
    start(async () => {
      setError(null)
      const r = await openAccount(businessId, {
        party_type: party, display_name: f.name.trim(), phone: f.phone.trim() || undefined,
        gstin: f.gstin.trim() || undefined, opening_balance: f.opening ? Number(f.opening) : undefined,
        credit_limit: f.limit ? Number(f.limit) : undefined, credit_days: f.days ? Number(f.days) : undefined,
      })
      if (!r.ok || !r.data) return setError(r.ok ? 'Nothing came back' : r.message)
      router.push(`/b/${businessId}/khata/${r.data.id}`)
    })

  if (!open) {
    return (
      <div className="bos-inv-buttons" style={{ margin: '0 0 1rem' }}>
        <button type="button" onClick={() => setOpen(true)} aria-expanded={false}>Open an account</button>
      </div>
    )
  }
  return (
    <section className="bos-card" aria-labelledby="open-h" style={{ marginBottom: '1.2rem' }}>
      <h2 id="open-h">Open an account</h2>
      <div className="bos-choices" role="radiogroup" aria-label="Whose account" style={{ margin: '.4rem 0 .8rem' }}>
        {(['customer', 'supplier'] as const).map((p) => (
          <label key={p} className="bos-choice">
            <input type="radio" name="party" checked={party === p} onChange={() => setParty(p)} />
            <span>{p === 'customer' ? 'A customer who buys on credit' : 'A supplier you buy from on credit'}</span>
          </label>
        ))}
      </div>
      <div className="bos-form-grid">
        <label><span className="bos-label">Name</span><input value={f.name} onChange={(e) => set('name', e.target.value)} maxLength={160} /></label>
        <label><span className="bos-label">Phone{party === 'customer' ? '' : ' — optional'}</span><input value={f.phone} onChange={(e) => set('phone', e.target.value)} inputMode="tel" maxLength={20} placeholder="+91…" /></label>
        <label><span className="bos-label">GSTIN — optional</span><input value={f.gstin} onChange={(e) => set('gstin', e.target.value.toUpperCase().replace(/\s/g, ''))} maxLength={15} /></label>
        <label><span className="bos-label">{party === 'customer' ? 'Already owes you (₹) — optional' : 'You already owe them (₹) — optional'}</span>
          <input inputMode="decimal" value={f.opening} onChange={(e) => set('opening', e.target.value.replace(/[^\d.]/g, ''))} />
          <span className="bos-fieldhelp">Carried over from your notebook.</span></label>
        {party === 'customer' ? (
          <label><span className="bos-label">Credit limit (₹) — optional</span>
            <input inputMode="decimal" value={f.limit} onChange={(e) => set('limit', e.target.value.replace(/[^\d.]/g, ''))} />
            <span className="bos-fieldhelp">Above this, the counter asks for a manager&apos;s PIN.</span></label>
        ) : null}
        <label><span className="bos-label">Days to pay — optional</span>
          <input inputMode="numeric" value={f.days} onChange={(e) => set('days', e.target.value.replace(/\D/g, ''))} placeholder="e.g. 30" /></label>
      </div>
      <div className="bos-inv-buttons">
        <button type="button" disabled={pending || !f.name.trim()} onClick={submit}>{pending ? 'Opening…' : 'Open account'}</button>
        <button type="button" className="btn-ghost" onClick={() => setOpen(false)}>Cancel</button>
        <p className={`bos-status${error ? ' bos-error' : ''}`} role="status" aria-live="polite">{error ?? ''}</p>
      </div>
    </section>
  )
}
