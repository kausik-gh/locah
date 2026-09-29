'use client'

import { useState, useTransition } from 'react'
import {
  askForPayment,
  cancelPaymentLink,
  confirmPayment,
  recordMoney,
  sendPaymentLink,
  type LinkResult,
} from '@/lib/collect-actions'

export type Attempt = {
  id: string
  amount: number
  method: string
  method_label: string
  status: string
  purpose: string | null
  reference: string | null
  attention: string | null
  created_at: string | null
  failure_reason: string | null
}
export type PaymentLink = {
  id: string
  amount: number
  purpose: string
  purpose_label: string
  status: string
  created_at: string | null
  expires_at: string
}
export type Due = {
  source_type: 'order' | 'booking' | 'membership' | 'invoice' | 'khata'
  source_id: string
  label: string
  total: number | null
  paid: number | null
  being_confirmed: number | null
  balance: number | null
  state: string
  state_words: string
  collectable: boolean
  why_not: string | null
  attempts: Attempt[]
  links: PaymentLink[]
}

const rupees = (v: number) =>
  new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: Number.isInteger(v) ? 0 : 2 }).format(v)
/** What the customer chose at checkout (pay on delivery, at pickup, later) — an intent, not money. */
const OFFLINE_INTENT = new Set(['cod', 'pay_at_business', 'pay_later'])
const STATUS_WORDS: Record<string, string> = {
  succeeded: 'Received',
  pending_offline: 'Waiting',
  processing: 'Being confirmed',
  failed: 'Not received',
  cancelled: 'Withdrawn',
  expired: 'Expired',
  refunded: 'Refunded',
  partially_refunded: 'Part refunded',
}

/**
 * Money on one transaction (Founder refinement — Payments §5, §10, §14): what
 * it costs, what was paid, what is waiting for you to confirm, what remains —
 * and the two ways to collect the rest: send a payment link, or record money
 * you took yourself. Nothing here marks money paid that you did not confirm.
 */
export function MoneyPanel({ businessId, path, due }: { businessId: string; path: string; due: Due }) {
  const [pending, start] = useTransition()
  const [mode, setMode] = useState<'none' | 'ask' | 'record'>('none')
  const [link, setLink] = useState<LinkResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState<string | null>(null)
  const balance = due.balance ?? 0
  const waiting = due.attempts.filter((a) => a.method === 'upi_direct' && a.status === 'pending_offline')
  const canRecord = ['order', 'booking', 'membership'].includes(due.source_type)
  const defaultPurpose = due.source_type === 'khata' ? 'dues' : (due.paid ?? 0) > 0 ? 'balance' : 'full'

  function run(fn: () => Promise<{ ok: boolean; message?: string; data?: unknown }>, after?: (d: unknown) => void) {
    setError(null)
    setDone(null)
    start(async () => {
      const r = await fn()
      if (!r.ok) setError('message' in r && r.message ? r.message : 'That did not save. Try again.')
      else after?.(r.data)
    })
  }

  return (
    <div className="bos-money">
      <dl className="bos-money__sum">
        {due.total !== null ? (
          <div>
            <dt>Total</dt>
            <dd>{rupees(due.total)}</dd>
          </div>
        ) : null}
        {due.source_type !== 'khata' ? (
          <div>
            <dt>Paid</dt>
            <dd>{rupees(due.paid ?? 0)}</dd>
          </div>
        ) : null}
        {due.being_confirmed ? (
          <div>
            <dt>Waiting for you</dt>
            <dd>{rupees(due.being_confirmed)}</dd>
          </div>
        ) : null}
        {due.balance !== null ? (
          <div>
            <dt>{due.source_type === 'khata' ? 'Owed' : 'Balance'}</dt>
            <dd className="is-balance">{rupees(due.balance)}</dd>
          </div>
        ) : null}
        <div>
          <dt>State</dt>
          <dd>
            <span className={`bos-state ${due.state === 'paid' ? 'is-ready' : ''}`}>{due.state_words.split(' · ')[0]}</span>
          </dd>
        </div>
      </dl>

      {waiting.map((a) => (
        <div key={a.id} className="bos-money__confirm" role="group" aria-label="Payment to confirm">
          <p>
            <strong>Customer says they paid {rupees(a.amount)} by UPI</strong>
            {a.reference ? ` · reference ${a.reference}` : ''}. Check your UPI app before confirming.
          </p>
          <div className="bos-money__row">
            <button type="button" disabled={pending}
              onClick={() => run(() => confirmPayment(businessId, path, a.id, true), () => setDone('Marked as received.'))}>
              It arrived
            </button>
            <button type="button" className="btn-ghost" disabled={pending}
              onClick={() => run(() => confirmPayment(businessId, path, a.id, false), () => setDone('The customer can try again.'))}>
              Not received
            </button>
          </div>
        </div>
      ))}

      {due.collectable && balance > 0 ? (
        <div className="bos-money__row">
          <button type="button" onClick={() => { setMode(mode === 'ask' ? 'none' : 'ask'); setLink(null) }}>
            Ask for payment
          </button>
          {canRecord ? (
            <button type="button" className="btn-ghost" onClick={() => setMode(mode === 'record' ? 'none' : 'record')}>
              Record money received
            </button>
          ) : null}
        </div>
      ) : !due.collectable && due.why_not ? (
        <p className="bos-hint">{due.why_not}</p>
      ) : null}

      {mode === 'ask' && !link ? (
        <form
          className="bos-money__form"
          onSubmit={(e) => {
            e.preventDefault()
            const f = new FormData(e.currentTarget)
            run(
              () => askForPayment(businessId, path, {
                source_type: due.source_type, source_id: due.source_id, amount: Number(f.get('amount')),
                purpose: String(f.get('purpose')), note: String(f.get('note') || '') || undefined,
              }),
              (d) => setLink(d as LinkResult)
            )
          }}
        >
          <label>
            <span>Amount</span>
            <input name="amount" type="number" inputMode="decimal" min="1" step="0.01" max={balance}
              defaultValue={balance} required />
          </label>
          <label>
            <span>For</span>
            <select name="purpose" defaultValue={defaultPurpose}>
              {due.source_type === 'khata' ? <option value="dues">Dues</option> : (
                <>
                  <option value="full">Full payment</option>
                  <option value="advance">Advance</option>
                  <option value="deposit">Deposit</option>
                  <option value="balance">Balance</option>
                </>
              )}
            </select>
          </label>
          <label className="bos-money__wide">
            <span>Note for the customer (optional)</span>
            <input name="note" maxLength={200} placeholder="e.g. Advance for the 2 kg cake on Saturday" />
          </label>
          <button type="submit" disabled={pending}>{pending ? 'Making the link…' : 'Make payment link'}</button>
        </form>
      ) : null}

      {link ? (
        <div className="bos-money__link" role="status">
          <p>
            Payment link for <strong>{rupees(link.amount)}</strong> ({link.purpose_label.toLowerCase()}) is ready.
            It works for 7 days.
          </p>
          <input readOnly value={link.url} aria-label="Payment link" onFocus={(e) => e.currentTarget.select()} />
          <div className="bos-money__row">
            {link.from_number ? (
              <button type="button" disabled={pending}
                onClick={() => run(() => sendPaymentLink(businessId, link.id, link.url), () => setDone('Sent from your WhatsApp number.'))}>
                Send from your WhatsApp number
              </button>
            ) : null}
            {link.whatsapp ? (
              <a className={link.from_number ? 'btn btn-ghost' : 'btn'} href={link.whatsapp} target="_blank" rel="noopener noreferrer">
                {link.from_number ? 'Send from my phone' : 'Send on WhatsApp'}
              </a>
            ) : null}
            <button type="button" className="btn-ghost"
              onClick={() => { void navigator.clipboard?.writeText(`${link.message}`); setDone('Copied.') }}>
              Copy message
            </button>
          </div>
        </div>
      ) : null}

      {mode === 'record' ? (
        <form
          className="bos-money__form"
          onSubmit={(e) => {
            e.preventDefault()
            const f = new FormData(e.currentTarget)
            run(
              () => recordMoney(businessId, path, {
                source_type: due.source_type, source_id: due.source_id, amount: Number(f.get('amount')),
                method: String(f.get('method')), reference: String(f.get('reference') || '') || undefined,
              }),
              () => { setMode('none'); setDone('Recorded.') }
            )
          }}
        >
          <label>
            <span>Amount received</span>
            <input name="amount" type="number" inputMode="decimal" min="1" step="0.01" max={balance}
              defaultValue={balance} required />
          </label>
          <label>
            <span>How</span>
            <select name="method" defaultValue="cash">
              <option value="cash">Cash</option>
              <option value="upi">UPI</option>
              <option value="card">Card on your terminal</option>
              <option value="bank_transfer">Bank transfer</option>
            </select>
          </label>
          <label className="bos-money__wide">
            <span>Reference (slip number, UTR — optional)</span>
            <input name="reference" maxLength={120} />
          </label>
          <button type="submit" disabled={pending}>Record</button>
        </form>
      ) : null}

      <p className={`bos-status ${error ? 'bos-error' : ''}`} role="status">{error || done || ''}</p>

      {due.links.length ? (
        <>
          <h3 className="bos-money__h">Payment links</h3>
          <ul className="bos-mini-list">
            {due.links.map((l) => (
              <li key={l.id}>
                <div>
                  <strong>{rupees(l.amount)} · {l.purpose_label}</strong>
                  <p>{l.status === 'open' ? 'Waiting for the customer' : l.status === 'paid' ? 'Paid' : l.status === 'expired' ? 'Expired' : 'Cancelled'}</p>
                </div>
                {l.status === 'open' ? (
                  <button type="button" className="btn-ghost" disabled={pending}
                    onClick={() => run(() => cancelPaymentLink(businessId, path, l.id), () => setDone('Link cancelled.'))}>
                    Cancel link
                  </button>
                ) : null}
              </li>
            ))}
          </ul>
        </>
      ) : null}

      {due.attempts.length ? (
        <>
          <h3 className="bos-money__h">Payments</h3>
          <ul className="bos-mini-list">
            {due.attempts.map((a) => (
              <li key={a.id}>
                <div>
                  <strong>{rupees(a.amount)} · {a.method_label}</strong>
                  <p>
                    {OFFLINE_INTENT.has(a.method) && a.status === 'pending_offline'
                      ? 'Not collected yet'
                      : OFFLINE_INTENT.has(a.method) && a.status === 'cancelled'
                        ? a.failure_reason || 'Closed'
                        : STATUS_WORDS[a.status] || a.status}
                    {a.reference ? ` · ${a.reference}` : ''}
                    {a.created_at ? ` · ${new Date(a.created_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })}` : ''}
                    {a.attention === 'paid_twice' ? ' · paid twice — refund due' : ''}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        </>
      ) : null}
    </div>
  )
}
