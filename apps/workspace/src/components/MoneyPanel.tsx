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
import { WS_LOCALE, type Words } from '@/lib/ws-words'
import { useWsLang, useWsWords } from './WsWords'

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
  /** The advance a pre-order's items asked for. */
  advance?: number | null
}

const rupees = (v: number) =>
  new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: Number.isInteger(v) ? 0 : 2 }).format(v)
/** What the customer chose at checkout (pay on delivery, at pickup, later) — an intent, not money. */
const OFFLINE_INTENT = new Set(['cod', 'pay_at_business', 'pay_later'])
const statusWords = (t: Words): Record<string, string> => ({
  succeeded: t('Received'),
  pending_offline: t('Waiting'),
  processing: t('Being confirmed'),
  failed: t('Not received'),
  cancelled: t('Withdrawn'),
  expired: t('Expired'),
  refunded: t('Refunded'),
  partially_refunded: t('Part refunded'),
})

/**
 * Money on one transaction (Founder refinement — Payments §5, §10, §14): what
 * it costs, what was paid, what is waiting for you to confirm, what remains —
 * and the two ways to collect the rest: send a payment link, or record money
 * you took yourself. Nothing here marks money paid that you did not confirm.
 */
export function MoneyPanel({ businessId, path, due }: { businessId: string; path: string; due: Due }) {
  const t = useWsWords()
  const locale = WS_LOCALE[useWsLang()]
  const STATUS_WORDS = statusWords(t)
  const [pending, start] = useTransition()
  const [mode, setMode] = useState<'none' | 'ask' | 'record'>('none')
  const [link, setLink] = useState<LinkResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState<string | null>(null)
  const balance = due.balance ?? 0
  const waiting = due.attempts.filter((a) => a.method === 'upi_direct' && a.status === 'pending_offline')
  const canRecord = ['order', 'booking', 'membership'].includes(due.source_type)
  const advanceLeft = due.advance ? Math.max(0, due.advance - (due.paid ?? 0) - (due.being_confirmed ?? 0)) : 0
  const defaultPurpose = due.source_type === 'khata' ? 'dues' : advanceLeft > 0 ? 'advance' : (due.paid ?? 0) > 0 ? 'balance' : 'full'
  const defaultAmount = advanceLeft > 0 ? Math.min(advanceLeft, balance) : balance

  function run(fn: () => Promise<{ ok: boolean; message?: string; data?: unknown }>, after?: (d: unknown) => void) {
    setError(null)
    setDone(null)
    start(async () => {
      const r = await fn()
      if (!r.ok) setError('message' in r && r.message ? r.message : t('That did not save. Try again.'))
      else after?.(r.data)
    })
  }

  return (
    <div className="bos-money">
      <dl className="bos-money__sum">
        {due.total !== null ? (
          <div>
            <dt>{t('Total')}</dt>
            <dd>{rupees(due.total)}</dd>
          </div>
        ) : null}
        {due.source_type !== 'khata' ? (
          <div>
            <dt>{t('Paid')}</dt>
            <dd>{rupees(due.paid ?? 0)}</dd>
          </div>
        ) : null}
        {due.advance ? (
          <div>
            <dt>{t('Advance asked')}</dt>
            <dd>{rupees(due.advance)}</dd>
          </div>
        ) : null}
        {due.being_confirmed ? (
          <div>
            <dt>{t('Waiting for you')}</dt>
            <dd>{rupees(due.being_confirmed)}</dd>
          </div>
        ) : null}
        {due.balance !== null ? (
          <div>
            <dt>{due.source_type === 'khata' ? t('Owed') : t('Balance')}</dt>
            <dd className="is-balance">{rupees(due.balance)}</dd>
          </div>
        ) : null}
        <div>
          <dt>{t('State')}</dt>
          <dd>
            <span className={`bos-state ${due.state === 'paid' ? 'is-ready' : ''}`}>{t(due.state_words.split(' · ')[0])}</span>
          </dd>
        </div>
      </dl>

      {waiting.map((a) => (
        <div key={a.id} className="bos-money__confirm" role="group" aria-label={t('Payment to confirm')}>
          <p>
            <strong>{t('Customer says they paid {amount} by UPI', { amount: rupees(a.amount) })}</strong>
            {a.reference ? ` · ${t('reference {ref}', { ref: a.reference })}` : ''}. {t('Check your UPI app before confirming.')}
          </p>
          <div className="bos-money__row">
            <button type="button" disabled={pending}
              onClick={() => run(() => confirmPayment(businessId, path, a.id, true), () => setDone(t('Marked as received.')))}>
              {t('It arrived')}
            </button>
            <button type="button" className="btn-ghost" disabled={pending}
              onClick={() => run(() => confirmPayment(businessId, path, a.id, false), () => setDone(t('The customer can try again.')))}>
              {t('Not received')}
            </button>
          </div>
        </div>
      ))}

      {due.collectable && balance > 0 ? (
        <div className="bos-money__row">
          <button type="button" onClick={() => { setMode(mode === 'ask' ? 'none' : 'ask'); setLink(null) }}>
            {t('Ask for payment')}
          </button>
          {canRecord ? (
            <button type="button" className="btn-ghost" onClick={() => setMode(mode === 'record' ? 'none' : 'record')}>
              {t('Record money received')}
            </button>
          ) : null}
        </div>
      ) : !due.collectable && due.why_not ? (
        <p className="bos-hint">{t(due.why_not)}</p>
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
            <span>{t('Amount')}</span>
            <input name="amount" type="number" inputMode="decimal" min="1" step="0.01" max={balance}
              defaultValue={defaultAmount} required />
          </label>
          <label>
            <span>{t('For')}</span>
            <select name="purpose" defaultValue={defaultPurpose}>
              {due.source_type === 'khata' ? <option value="dues">{t('Dues')}</option> : (
                <>
                  <option value="full">{t('Full payment')}</option>
                  <option value="advance">{t('Advance')}</option>
                  <option value="deposit">{t('Deposit')}</option>
                  <option value="balance">{t('Balance')}</option>
                </>
              )}
            </select>
          </label>
          <label className="bos-money__wide">
            <span>{t('Note for the customer (optional)')}</span>
            <input name="note" maxLength={200} placeholder={t('e.g. Advance for the 2 kg cake on Saturday')} />
          </label>
          <button type="submit" disabled={pending}>{pending ? t('Making the link…') : t('Make payment link')}</button>
        </form>
      ) : null}

      {link ? (
        <div className="bos-money__link" role="status">
          <p>
            {t('Payment link for {amount} ({purpose}) is ready. It works for 7 days.', { amount: rupees(link.amount), purpose: t(link.purpose_label).toLowerCase() })}
          </p>
          <input readOnly value={link.url} aria-label={t('Payment link')} onFocus={(e) => e.currentTarget.select()} />
          <div className="bos-money__row">
            {link.from_number ? (
              <button type="button" disabled={pending}
                onClick={() => run(() => sendPaymentLink(businessId, link.id, link.url), () => setDone(t('Sent from your WhatsApp number.')))}>
                {t('Send from your WhatsApp number')}
              </button>
            ) : null}
            {link.whatsapp ? (
              <a className={link.from_number ? 'btn btn-ghost' : 'btn'} href={link.whatsapp} target="_blank" rel="noopener noreferrer">
                {link.from_number ? t('Send from my phone') : t('Send on WhatsApp')}
              </a>
            ) : null}
            <button type="button" className="btn-ghost"
              onClick={() => { void navigator.clipboard?.writeText(`${link.message}`); setDone(t('Copied.')) }}>
              {t('Copy message')}
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
              () => { setMode('none'); setDone(t('Recorded.')) }
            )
          }}
        >
          <label>
            <span>{t('Amount received')}</span>
            <input name="amount" type="number" inputMode="decimal" min="1" step="0.01" max={balance}
              defaultValue={balance} required />
          </label>
          <label>
            <span>{t('How')}</span>
            <select name="method" defaultValue="cash">
              <option value="cash">{t('Cash')}</option>
              <option value="upi">UPI</option>
              <option value="card">{t('Card on your terminal')}</option>
              <option value="bank_transfer">{t('Bank transfer')}</option>
            </select>
          </label>
          <label className="bos-money__wide">
            <span>{t('Reference (slip number, UTR — optional)')}</span>
            <input name="reference" maxLength={120} />
          </label>
          <button type="submit" disabled={pending}>{t('Record')}</button>
        </form>
      ) : null}

      <p className={`bos-status ${error ? 'bos-error' : ''}`} role="status">{error || done || ''}</p>

      {due.links.length ? (
        <>
          <h3 className="bos-money__h">{t('Payment links')}</h3>
          <ul className="bos-mini-list">
            {due.links.map((l) => (
              <li key={l.id}>
                <div>
                  <strong>{rupees(l.amount)} · {t(l.purpose_label)}</strong>
                  <p>{l.status === 'open' ? t('Waiting for the customer') : l.status === 'paid' ? t('Paid') : l.status === 'expired' ? t('Expired') : t('Cancelled')}</p>
                </div>
                {l.status === 'open' ? (
                  <button type="button" className="btn-ghost" disabled={pending}
                    onClick={() => run(() => cancelPaymentLink(businessId, path, l.id), () => setDone(t('Link cancelled.')))}>
                    {t('Cancel link')}
                  </button>
                ) : null}
              </li>
            ))}
          </ul>
        </>
      ) : null}

      {due.attempts.length ? (
        <>
          <h3 className="bos-money__h">{t('Payments')}</h3>
          <ul className="bos-mini-list">
            {due.attempts.map((a) => (
              <li key={a.id}>
                <div>
                  <strong>{rupees(a.amount)} · {t(a.method_label)}</strong>
                  <p>
                    {OFFLINE_INTENT.has(a.method) && a.status === 'pending_offline'
                      ? t('Not collected yet')
                      : OFFLINE_INTENT.has(a.method) && a.status === 'cancelled'
                        ? t(a.failure_reason || 'Closed')
                        : STATUS_WORDS[a.status] || a.status}
                    {a.reference ? ` · ${a.reference}` : ''}
                    {a.created_at ? ` · ${new Date(a.created_at).toLocaleDateString(locale, { day: 'numeric', month: 'short' })}` : ''}
                    {a.attention === 'paid_twice' ? ` · ${t('paid twice — refund due')}` : a.attention === 'refund_due' ? ` · ${t('order cancelled — refund due')}` : ''}
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
