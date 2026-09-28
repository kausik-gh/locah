'use client'

import { useRouter } from 'next/navigation'
import { useState, useTransition } from 'react'
import { postEntry, recordMoney, shareStatement, updateAccount } from '../khata-actions'
import { rupees, type AccountDetail } from '../types'
import { sendDocument } from '../../whatsapp/whatsapp-actions'

type Panel = 'money' | 'purchase' | 'limit' | 'fix' | 'statement' | null
const today = () => new Date().toISOString().slice(0, 10)

/**
 * What can be done to one khata: take money, share the statement on
 * WhatsApp, record a supplier's bill, and — for whoever manages the book —
 * set the limit and days to pay, correct a mistake, or close a settled
 * account.
 */
export function AccountActions({ businessId, account: a, canRecord, canManage, whatsapp = false }: {
  businessId: string; account: AccountDetail; canRecord: boolean; canManage: boolean; whatsapp?: boolean
}) {
  const router = useRouter()
  const [pending, start] = useTransition()
  const [panel, setPanel] = useState<Panel>(null)
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState<string | null>(null)
  const [link, setLink] = useState<string | null>(null)
  const customer = a.party_type === 'customer'
  const [money, setMoney] = useState({ amount: '', method: 'cash', reference: '', date: today() })
  const [buy, setBuy] = useState({ amount: '', reference: '', due: '', date: today() })
  const [limit, setLimit] = useState({ limit: a.credit_limit === null ? '' : String(a.credit_limit), days: a.credit_days === null ? '' : String(a.credit_days) })
  const [fix, setFix] = useState({ amount: '', up: false, note: '' })
  const [period, setPeriod] = useState({ from: '', to: '' })

  const run = (fn: () => Promise<{ ok: boolean; message?: string; data?: AccountDetail }>, message: string) =>
    start(async () => {
      setError(null)
      setDone(null)
      const r = await fn()
      if (!r.ok) return setError(r.message ?? 'That did not work')
      setPanel(null)
      setDone(message)
      router.refresh()
    })
  const toggle = (p: Panel) => { setPanel(panel === p ? null : p); setError(null) }

  const share = (via: 'whatsapp' | 'copy') =>
    start(async () => {
      setError(null)
      const r = await shareStatement(businessId, a.id)
      if (!r.ok || !r.data) return setError(r.ok ? 'No link came back' : r.message)
      setLink(r.data.url)
      if (via === 'whatsapp') {
        const phone = (r.data.phone ?? '').replace(/[^\d]/g, '')
        window.open(`https://wa.me/${phone}?text=${encodeURIComponent(`${r.data.message} ${r.data.url}`)}`, '_blank', 'noopener')
        setDone('WhatsApp opened with the statement link')
      } else {
        try {
          await navigator.clipboard.writeText(r.data.url)
          setDone('Link copied')
        } catch {
          setDone('Copy the link below')
        }
      }
    })

  const methods = Object.entries(a.methods)
  const closed = a.status === 'closed'

  return (
    <aside className="bos-inv-side">
      <section className="bos-card bos-inv-actions" aria-label="What you can do">
        <h2>{customer ? 'Collect and remind' : 'Pay and record'}</h2>
        {closed ? <p className="bos-hint">This account is closed.</p> : null}
        {canRecord && customer ? (
          <div className="bos-inv-buttons">
            {whatsapp ? (
              <button type="button" disabled={pending} onClick={() => run(async () => { const r = await sendDocument(businessId, 'statement', a.id); return r.ok ? { ok: true } : r }, 'Statement sent from your WhatsApp number')}>
                Send statement from your WhatsApp number
              </button>
            ) : null}
            <button type="button" className={whatsapp ? 'btn-ghost' : undefined} disabled={pending} onClick={() => share('whatsapp')}>
              {whatsapp ? 'Send from my phone' : 'Send statement on WhatsApp'}
            </button>
            <button type="button" className="btn-ghost" disabled={pending} onClick={() => share('copy')}>Copy customer link</button>
          </div>
        ) : null}
        {link ? <input className="bos-inv-link" readOnly value={link} aria-label="Customer statement link" onFocus={(e) => e.currentTarget.select()} /> : null}
        <div className="bos-inv-buttons">
          {canRecord && !closed ? (
            <button type="button" className="btn-ghost" onClick={() => toggle('money')} aria-expanded={panel === 'money'}>
              {customer ? 'Record money received' : 'Record money paid'}
            </button>
          ) : null}
          {canRecord && !customer && !closed ? (
            <button type="button" className="btn-ghost" onClick={() => toggle('purchase')} aria-expanded={panel === 'purchase'}>Record a purchase on credit</button>
          ) : null}
          <button type="button" className="btn-ghost" onClick={() => toggle('statement')} aria-expanded={panel === 'statement'}>Statement for a period</button>
        </div>

        {panel === 'money' ? (
          <form className="bos-inv-form" onSubmit={(e) => {
            e.preventDefault()
            run(() => recordMoney(businessId, a.id, { amount: Number(money.amount), method: money.method, reference: money.reference || undefined, entry_date: money.date || undefined }),
              customer ? 'Recorded — the oldest bills are settled first' : 'Payment recorded')
          }}>
            <label><span className="bos-label">Amount (₹)</span>
              <input inputMode="decimal" value={money.amount} onChange={(e) => setMoney({ ...money, amount: e.target.value.replace(/[^\d.]/g, '') })} autoFocus />
              {customer && a.balance > 0 ? <span className="bos-fieldhelp">They owe {rupees(a.balance)}.</span> : null}</label>
            <label><span className="bos-label">How</span>
              <select value={money.method} onChange={(e) => setMoney({ ...money, method: e.target.value })}>
                {methods.map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select></label>
            <label><span className="bos-label">Reference — optional</span><input value={money.reference} onChange={(e) => setMoney({ ...money, reference: e.target.value })} maxLength={120} placeholder="UTR, cheque no." /></label>
            <label><span className="bos-label">Date</span><input type="date" value={money.date} max={today()} onChange={(e) => setMoney({ ...money, date: e.target.value })} /></label>
            <button type="submit" disabled={pending || !Number(money.amount)}>{pending ? 'Saving…' : 'Record'}</button>
          </form>
        ) : null}

        {panel === 'purchase' ? (
          <form className="bos-inv-form" onSubmit={(e) => {
            e.preventDefault()
            run(() => postEntry(businessId, a.id, { kind: 'purchase', amount: Number(buy.amount), reference: buy.reference || undefined, due_date: buy.due || undefined, entry_date: buy.date || undefined }), 'Purchase recorded')
          }}>
            <label><span className="bos-label">Bill amount (₹)</span><input inputMode="decimal" value={buy.amount} onChange={(e) => setBuy({ ...buy, amount: e.target.value.replace(/[^\d.]/g, '') })} autoFocus /></label>
            <label><span className="bos-label">Their bill number — optional</span><input value={buy.reference} onChange={(e) => setBuy({ ...buy, reference: e.target.value })} maxLength={120} /></label>
            <label><span className="bos-label">Bill date</span><input type="date" value={buy.date} max={today()} onChange={(e) => setBuy({ ...buy, date: e.target.value })} /></label>
            <label><span className="bos-label">Due — optional</span><input type="date" value={buy.due} onChange={(e) => setBuy({ ...buy, due: e.target.value })} />
              {a.credit_days !== null ? <span className="bos-fieldhelp">Left empty: {a.credit_days} days after the bill.</span> : null}</label>
            <button type="submit" disabled={pending || !Number(buy.amount)}>{pending ? 'Saving…' : 'Record purchase'}</button>
          </form>
        ) : null}

        {panel === 'statement' ? (
          <div className="bos-inv-form">
            <label><span className="bos-label">From — optional</span><input type="date" value={period.from} onChange={(e) => setPeriod({ ...period, from: e.target.value })} /></label>
            <label><span className="bos-label">To — optional</span><input type="date" value={period.to} onChange={(e) => setPeriod({ ...period, to: e.target.value })} /></label>
            <span className="bos-fieldhelp">Left empty: the last 90 days.</span>
            <a className="btn" target="_blank" rel="noreferrer"
              href={`/b/${businessId}/khata/${a.id}/statement?${new URLSearchParams(Object.entries(period).filter(([, v]) => v))}`}>Open PDF</a>
          </div>
        ) : null}
        {done ? <p className="bos-status" role="status">{done}</p> : null}
        {error ? <p className="bos-status bos-error" role="alert">{error}</p> : null}
      </section>

      {canManage ? (
        <section className="bos-card bos-inv-actions" aria-label="Manage this account">
          <h2>Manage</h2>
          <div className="bos-inv-buttons">
            <button type="button" className="btn-ghost" onClick={() => toggle('limit')} aria-expanded={panel === 'limit'}>
              {customer ? 'Limit & days to pay' : 'Days to pay'}
            </button>
            {!closed ? <button type="button" className="btn-ghost" onClick={() => toggle('fix')} aria-expanded={panel === 'fix'}>Correct a mistake</button> : null}
            {a.balance === 0 ? (
              <button type="button" className="btn-quiet" disabled={pending}
                onClick={() => run(() => updateAccount(businessId, a.id, { status: closed ? 'active' : 'closed' }), closed ? 'Reopened' : 'Closed')}>
                {closed ? 'Reopen account' : 'Close account'}
              </button>
            ) : null}
          </div>
          {panel === 'limit' ? (
            <form className="bos-inv-form" onSubmit={(e) => {
              e.preventDefault()
              run(() => updateAccount(businessId, a.id, {
                ...(customer ? { credit_limit: limit.limit === '' ? null : Number(limit.limit) } : {}),
                credit_days: limit.days === '' ? null : Number(limit.days),
              }), 'Saved')
            }}>
              {customer ? (
                <label><span className="bos-label">Credit limit (₹)</span>
                  <input inputMode="decimal" value={limit.limit} onChange={(e) => setLimit({ ...limit, limit: e.target.value.replace(/[^\d.]/g, '') })} placeholder="No limit" />
                  <span className="bos-fieldhelp">Above it, credit needs a manager&apos;s PIN at the counter.</span></label>
              ) : null}
              <label><span className="bos-label">Days to pay</span>
                <input inputMode="numeric" value={limit.days} onChange={(e) => setLimit({ ...limit, days: e.target.value.replace(/\D/g, '') })} placeholder="Not set" /></label>
              <button type="submit" disabled={pending}>Save</button>
            </form>
          ) : null}
          {panel === 'fix' ? (
            <form className="bos-inv-form" onSubmit={(e) => {
              e.preventDefault()
              const v = Number(fix.amount)
              run(() => postEntry(businessId, a.id, { kind: 'adjustment', amount: fix.up ? v : -v, note: fix.note }), 'Correction added')
            }}>
              <p className="bos-hint" style={{ margin: 0 }}>Entries are never edited. A correction is a new entry, with its reason.</p>
              <div className="bos-choices bos-choices--stack" role="radiogroup" aria-label="Which way">
                <label className="bos-choice"><input type="radio" checked={!fix.up} onChange={() => setFix({ ...fix, up: false })} /><span>{customer ? 'They owe less' : 'You owe less'}</span></label>
                <label className="bos-choice"><input type="radio" checked={fix.up} onChange={() => setFix({ ...fix, up: true })} /><span>{customer ? 'They owe more' : 'You owe more'}</span></label>
              </div>
              <label><span className="bos-label">Amount (₹)</span><input inputMode="decimal" value={fix.amount} onChange={(e) => setFix({ ...fix, amount: e.target.value.replace(/[^\d.]/g, '') })} /></label>
              <label><span className="bos-label">Why</span><input value={fix.note} onChange={(e) => setFix({ ...fix, note: e.target.value })} maxLength={300} placeholder="e.g. Entered twice" /></label>
              <button type="submit" disabled={pending || !Number(fix.amount) || !fix.note.trim()}>Add correction</button>
            </form>
          ) : null}
        </section>
      ) : null}
    </aside>
  )
}
