'use client'

import { useState } from 'react'
import { platformUrl } from '@platform/config'

export type PayMethod = { method: string; label: string; upi_link?: string; upi_id?: string; how?: string }
export type PayView = {
  business: { name: string; slug: string; contact?: { phone?: string; whatsapp?: string } }
  for: string
  purpose: string
  purpose_label: string
  note: string | null
  state: 'open' | 'being_confirmed' | 'failed' | 'paid' | 'cancelled' | 'expired'
  state_words: string | null
  amount_due: number | null
  already_paid: number | null
  paying_now: number
  balance_after: number | null
  balance_now: number | null
  methods: PayMethod[]
  last_attempt: { status: string; reference: string | null } | null
  expires_at: string
}

const rupees = (v: number) =>
  new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: Number.isInteger(v) ? 0 : 2 }).format(v)

/** The customer's side of a payment link: pay, say so, check again, or take it back. */
export function PayActions({
  slug,
  token,
  initial,
  qrUrl,
}: {
  slug: string
  token: string
  initial: PayView
  qrUrl: string
}) {
  const [view, setView] = useState<PayView>(initial)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [utr, setUtr] = useState('')
  const api = `${platformUrl('api')}/v1/public/websites/${encodeURIComponent(slug)}/pay/${encodeURIComponent(token)}`
  const upi = view.methods.find((m) => m.method === 'upi_direct')

  async function call(path: string, body?: unknown, method = 'POST') {
    setBusy(true)
    setError(null)
    try {
      const res = await fetch(`${api}${path}`, {
        method,
        headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
        body: body === undefined ? undefined : JSON.stringify(body),
        cache: 'no-store',
      })
      const json = await res.json().catch(() => null)
      if (!res.ok) throw new Error(json?.error?.message || 'That did not go through. Try again.')
      setView(json.data as PayView)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'That did not go through. Try again.')
    } finally {
      setBusy(false)
    }
  }

  const closed = view.state === 'paid' || view.state === 'cancelled' || view.state === 'expired'
  return (
    <>
      <header className="ls-bill__head">
        <p className="ls-meta">Payment to {view.business.name}</p>
        <h1 className="ls-title">{view.for}</h1>
        {view.note ? <p className="ls-meta">{view.note}</p> : null}
      </header>

      {view.state_words ? (
        <p className={`ls-pay__state ls-pay__state--${view.state}`} role="status">
          {view.state_words}
        </p>
      ) : null}

      <div className="ls-bill__card">
        <dl className="ls-bill__totals ls-pay__totals">
          {view.amount_due !== null ? (
            <>
              <dt>Amount due</dt>
              <dd>{rupees(view.amount_due)}</dd>
            </>
          ) : null}
          {view.already_paid ? (
            <>
              <dt>Already paid</dt>
              <dd>{rupees(view.already_paid)}</dd>
            </>
          ) : null}
          {!closed ? (
            <>
              <dt className="is-total">{view.purpose_label} — paying now</dt>
              <dd className="is-total">{rupees(view.paying_now)}</dd>
            </>
          ) : null}
          {view.balance_after !== null && !closed && view.balance_after > 0 ? (
            <>
              <dt>Balance after this</dt>
              <dd>{rupees(view.balance_after)}</dd>
            </>
          ) : null}
          {closed && view.balance_now !== null && view.balance_now > 0 ? (
            <>
              <dt className="is-total">Balance remaining</dt>
              <dd className="is-total">{rupees(view.balance_now)}</dd>
            </>
          ) : null}
        </dl>
      </div>

      {view.state === 'being_confirmed' ? (
        <div className="ls-pay__wait">
          <p className="ls-meta">
            {view.business.name} checks their UPI app and confirms it. You don&apos;t need to pay again.
          </p>
          <div className="ls-bill__actions">
            <button type="button" className="ls-btn" disabled={busy} onClick={() => call('', undefined, 'GET')}>
              Check again
            </button>
            <button
              type="button"
              className="ls-btn ls-btn--outline"
              disabled={busy}
              onClick={() => call('/not-paid')}
            >
              I haven&apos;t paid yet
            </button>
          </div>
        </div>
      ) : null}

      {(view.state === 'open' || view.state === 'failed') && upi ? (
        <div className="ls-pay__method">
          <a className="ls-btn ls-pay__upi" href={upi.upi_link}>
            {view.state === 'failed' ? 'Try again — pay by UPI' : `Pay ${rupees(view.paying_now)} by UPI`}
          </a>
          <p className="ls-meta">{upi.how}</p>
          <details className="ls-pay__qr">
            <summary>On a computer? Scan to pay</summary>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={qrUrl} alt={`UPI QR code to pay ${view.business.name}`} width={180} height={180} />
            <p className="ls-meta">UPI ID {upi.upi_id}</p>
          </details>
          <label className="ls-pay__utr">
            <span>UPI reference (optional)</span>
            <input value={utr} onChange={(e) => setUtr(e.target.value)} maxLength={120} inputMode="text" />
          </label>
          <button
            type="button"
            className="ls-btn ls-btn--outline"
            disabled={busy}
            onClick={() => call('/paid', { reference: utr || undefined })}
          >
            I have paid {rupees(view.paying_now)}
          </button>
        </div>
      ) : null}

      {(view.state === 'open' || view.state === 'failed') && !upi ? (
        <p className="ls-meta">
          {view.business.name} has not set up online payment for this link yet.
          {view.business.contact?.phone ? ` Call ${view.business.contact.phone} to pay another way.` : ''}
        </p>
      ) : null}

      {error ? (
        <p className="ls-offer__error" role="alert">
          {error}
        </p>
      ) : null}
    </>
  )
}
