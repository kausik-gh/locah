'use client'

import { useRouter } from 'next/navigation'
import { useState, useTransition } from 'react'
import { saveCounter, setPin, verifyUpi } from './counter-actions'

export type CounterSetup = {
  settings: {
    upi_vpa: string | null
    upi_payee_name?: string | null
    return_window_days: number
    discount_caps: Record<string, number>
    block_size?: number
    weighed_label: { prefix: string; item_digits: number; value: 'weight' | 'price'; value_digits: number; value_decimals: number } | null
    receipt_footer: string | null
    configured?: boolean
  }
  registers: { id: string; name: string; location_name: string; open_shift: unknown }[]
  approvers: { identity_id: string; name: string }[]
  me: string
}
export type ToVerify = { id: string; document_id: string; number: string; amount: number; method: string; reference: string | null; received_on: string }

const ROLES: [string, string][] = [['cashier', 'Cashier'], ['manager', 'Manager']]
const money = (v: number) => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', minimumFractionDigits: 2 }).format(v)

export function CounterSettings({ businessId, setup, canConfigure, canApprove, toVerify }: {
  businessId: string; setup: CounterSetup; canConfigure: boolean; canApprove: boolean; toVerify: ToVerify[] | null
}) {
  const router = useRouter()
  const [pending, start] = useTransition()
  const [msg, setMsg] = useState<{ where: string; text: string; bad?: boolean } | null>(null)
  const s = setup.settings
  const [vpa, setVpa] = useState(s.upi_vpa ?? '')
  const [payee, setPayee] = useState(s.upi_payee_name ?? '')
  const [windowDays, setWindowDays] = useState(String(s.return_window_days))
  const [caps, setCaps] = useState<Record<string, string>>(Object.fromEntries(ROLES.map(([k]) => [k, String(s.discount_caps?.[k] ?? 0)])))
  const [block, setBlock] = useState(String(s.block_size ?? 50))
  const [footer, setFooter] = useState(s.receipt_footer ?? '')
  const [scale, setScale] = useState(Boolean(s.weighed_label))
  const [fmt, setFmt] = useState(s.weighed_label ?? { prefix: '21', item_digits: 5, value: 'weight' as const, value_digits: 5, value_decimals: 3 })
  const [pin, setPinValue] = useState('')
  const hasPin = setup.approvers.some((a) => a.identity_id === setup.me)
  const run = (where: string, fn: () => Promise<{ ok: boolean; message?: string }>, ok: string) =>
    start(async () => {
      setMsg(null)
      const r = await fn()
      setMsg({ where, text: r.ok ? ok : r.message ?? 'That did not save', bad: !r.ok })
      if (r.ok) router.refresh()
    })
  const sample = `${fmt.prefix}${'1'.repeat(fmt.item_digits)}${'0'.repeat(fmt.value_digits)}·`
  const length = fmt.prefix.length + fmt.item_digits + fmt.value_digits + 1

  return (
    <div className="bos-works">
      {canConfigure ? (
        <section className="bos-card" aria-labelledby="rules-h">
          <h2 id="rules-h">Counter rules</h2>
          <div className="bos-form-grid">
            <label><span className="bos-label">Your UPI ID — for the QR at the counter</span>
              <input value={vpa} onChange={(e) => setVpa(e.target.value.trim())} placeholder="shopname@bank" /></label>
            <label><span className="bos-label">Name shown when paying — optional</span>
              <input value={payee} onChange={(e) => setPayee(e.target.value)} maxLength={100} /></label>
            <label><span className="bos-label">Returns accepted for (days)</span>
              <input inputMode="numeric" value={windowDays} onChange={(e) => setWindowDays(e.target.value.replace(/\D/g, ''))} /></label>
            <label><span className="bos-label">Bill numbers each register keeps for offline use</span>
              <input inputMode="numeric" value={block} onChange={(e) => setBlock(e.target.value.replace(/\D/g, ''))} />
              <span className="bos-fieldhelp">Unused numbers go back to the series when a shift closes.</span></label>
          </div>
          <fieldset className="bos-inv-q" style={{ marginTop: '1rem' }}>
            <legend>Largest discount without a manager&apos;s PIN</legend>
            <div className="bos-form-grid">
              {ROLES.map(([k, label]) => (
                <label key={k}><span className="bos-label">{label} (% of the bill)</span>
                  <input inputMode="decimal" value={caps[k]} onChange={(e) => setCaps({ ...caps, [k]: e.target.value.replace(/[^\d.]/g, '') })} /></label>
              ))}
            </div>
            <p className="bos-fieldhelp">The owner has no limit. Voids of an earlier shift and returns after the window also need a manager&apos;s PIN.</p>
          </fieldset>
          <label className="bos-toggle" style={{ marginTop: '.5rem' }}>
            <input type="checkbox" checked={scale} onChange={(e) => setScale(e.target.checked)} />
            <span className="bos-toggle__track" aria-hidden />
            <span>We use a label-printing scale</span>
          </label>
          {scale ? (
            <div className="bos-form-grid" style={{ marginTop: '.6rem' }}>
              <label><span className="bos-label">Starts with</span><input inputMode="numeric" value={fmt.prefix} onChange={(e) => setFmt({ ...fmt, prefix: e.target.value.replace(/\D/g, '').slice(0, 3) })} /></label>
              <label><span className="bos-label">Item code digits</span><input inputMode="numeric" value={fmt.item_digits} onChange={(e) => setFmt({ ...fmt, item_digits: Number(e.target.value.replace(/\D/g, '')) || 0 })} /></label>
              <label><span className="bos-label">The label carries</span>
                <select value={fmt.value} onChange={(e) => setFmt({ ...fmt, value: e.target.value as 'weight' | 'price', value_decimals: e.target.value === 'weight' ? 3 : 2 })}>
                  <option value="weight">Weight (kg)</option><option value="price">Price (₹)</option>
                </select></label>
              <label><span className="bos-label">Value digits</span><input inputMode="numeric" value={fmt.value_digits} onChange={(e) => setFmt({ ...fmt, value_digits: Number(e.target.value.replace(/\D/g, '')) || 0 })} /></label>
              <label><span className="bos-label">Of which after the point</span><input inputMode="numeric" value={fmt.value_decimals} onChange={(e) => setFmt({ ...fmt, value_decimals: Number(e.target.value.replace(/\D/g, '')) || 0 })} /></label>
              <p className="bos-form-wide bos-fieldhelp">Looks like <code>{sample}</code> ({length} digits; a label has 13). Copy this from your scale&apos;s settings — the item code is the item&apos;s own code (SKU).</p>
            </div>
          ) : null}
          <label className="bos-form-wide" style={{ display: 'block', marginTop: '.8rem' }}><span className="bos-label">Line at the bottom of receipts — optional</span>
            <input value={footer} onChange={(e) => setFooter(e.target.value)} maxLength={300} style={{ width: '100%' }} placeholder="Thank you — visit again" /></label>
          <div className="bos-inv-buttons">
            <button type="button" disabled={pending} onClick={() => run('rules', () => saveCounter(businessId, {
              upi_vpa: vpa || null, upi_payee_name: payee || null, return_window_days: Number(windowDays || 0),
              discount_caps: Object.fromEntries(Object.entries(caps).map(([k, v]) => [k, Number(v || 0)])),
              block_size: Number(block || 50), receipt_footer: footer || null, weighed_label: scale ? fmt : null,
            }), 'Saved')}>Save</button>
            {msg?.where === 'rules' ? <p className={`bos-status${msg.bad ? ' bos-error' : ''}`} role="status">{msg.text}</p> : null}
          </div>
        </section>
      ) : (
        <p className="bos-hint">The owner sets the counter rules. UPI ID: {s.upi_vpa ?? 'not set'} · returns within {s.return_window_days} days.</p>
      )}

      {canApprove ? (
        <section className="bos-card" aria-labelledby="pin-h">
          <h2 id="pin-h">Your approval PIN</h2>
          <p className="bos-hint">On a cashier&apos;s screen you pick your name and type this PIN to approve a bigger discount, a void or a late return. {hasPin ? 'You have a PIN; setting a new one replaces it.' : 'You have not set one yet.'}</p>
          <form className="bos-inv-buttons" onSubmit={(e) => { e.preventDefault(); run('pin', () => setPin(businessId, pin), 'PIN saved'); setPinValue('') }}>
            <label className="sr-only" htmlFor="pin">New PIN</label>
            <input id="pin" type="password" inputMode="numeric" autoComplete="new-password" maxLength={6} value={pin}
              onChange={(e) => setPinValue(e.target.value.replace(/\D/g, ''))} placeholder="4–6 digits" style={{ maxWidth: 160 }} />
            <button type="submit" disabled={pending || pin.length < 4}>{hasPin ? 'Change PIN' : 'Set PIN'}</button>
            {msg?.where === 'pin' ? <p className={`bos-status${msg.bad ? ' bos-error' : ''}`} role="status">{msg.text}</p> : null}
          </form>
        </section>
      ) : null}

      {toVerify !== null ? (
        <section className="bos-card" aria-labelledby="upi-h">
          <h2 id="upi-h">UPI to verify {toVerify.length ? <span className="bos-tag">{toVerify.length}</span> : null}</h2>
          <p className="bos-hint">UPI taken at the counter without confirmation (for example while offline). Check your bank or UPI app, then mark each one.</p>
          {toVerify.length ? (
            <ul className="bos-inv-regs">
              {toVerify.map((p) => (
                <li key={p.id}>
                  <div><strong>{money(p.amount)}</strong> <span className="bos-tag">{p.number}</span><p>{p.received_on}{p.reference ? ` · ref ${p.reference}` : ''}</p></div>
                  <span className="bos-inv-buttons" style={{ marginTop: 0 }}>
                    <button type="button" disabled={pending} onClick={() => run('upi', () => verifyUpi(businessId, p.id, true), 'Marked received')}>Received</button>
                    <button type="button" className="btn-ghost" disabled={pending} onClick={() => run('upi', () => verifyUpi(businessId, p.id, false), 'Marked not received — the bill shows as unpaid')}>Not received</button>
                  </span>
                </li>
              ))}
            </ul>
          ) : <p className="bos-empty">Nothing to check.</p>}
          {msg?.where === 'upi' ? <p className={`bos-status${msg.bad ? ' bos-error' : ''}`} role="status">{msg.text}</p> : null}
        </section>
      ) : null}
    </div>
  )
}
