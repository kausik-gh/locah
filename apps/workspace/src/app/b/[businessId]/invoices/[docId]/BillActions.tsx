'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useState, useTransition } from 'react'
import { billAction, shareBill } from '../invoice-actions'
import { rupees, type Bill } from '../types'

type Panel = null | 'pay' | 'credit' | 'debit' | 'cancel'

/**
 * What can be done with this bill, and nothing else: a draft is issued or
 * deleted; an issued bill is shared, paid, corrected with a credit or debit
 * note, or cancelled (it keeps its number). The API re-checks every step.
 */
export function BillActions({
  businessId,
  bill,
  noteReasons,
  methods,
}: {
  businessId: string
  bill: Bill
  noteReasons: Record<string, Record<string, string>>
  methods: Record<string, string>
}) {
  const router = useRouter()
  const [panel, setPanel] = useState<Panel>(null)
  const [pending, start] = useTransition()
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState<string | null>(null)
  const [link, setLink] = useState<string | null>(null)
  const isNote = bill.doc_kind === 'credit_note' || bill.doc_kind === 'debit_note'
  const base = `/b/${businessId}/invoices`

  const run = (fn: () => Promise<{ ok: boolean; message?: string; data?: Bill }>, message: string, go?: (b?: Bill) => string | null) =>
    start(async () => {
      setError(null)
      setDone(null)
      const r = await fn()
      if (!r.ok) return setError(r.message ?? 'That did not work')
      setPanel(null)
      setDone(message)
      const dest = go?.(r.data)
      if (dest) router.push(dest)
      else router.refresh()
    })

  const share = (via: 'whatsapp' | 'copy') =>
    start(async () => {
      setError(null)
      const r = await shareBill(businessId, bill.id)
      if (!r.ok || !r.data) return setError(r.ok ? 'No link came back' : r.message)
      setLink(r.data.url)
      const text = `${r.data.message} ${r.data.url}`
      if (via === 'whatsapp') {
        const phone = (r.data.phone ?? '').replace(/[^\d]/g, '')
        window.open(`https://wa.me/${phone}?text=${encodeURIComponent(text)}`, '_blank', 'noopener')
        setDone('WhatsApp opened with the bill link')
      } else {
        try {
          await navigator.clipboard.writeText(r.data.url)
          setDone('Link copied')
        } catch {
          setDone('Copy the link below')
        }
      }
    })

  if (bill.status === 'cancelled') return null

  return (
    <section className="bos-card bos-inv-actions" aria-label="What you can do">
      {bill.status === 'draft' ? (
        <>
          <h2>Draft</h2>
          <p className="bos-hint">A draft has no number yet. Issuing takes the next number in the series and prices it at today&apos;s rates.</p>
          <div className="bos-inv-buttons">
            <button type="button" disabled={pending} onClick={() => run(() => billAction(businessId, bill.id, 'issue'), 'Issued')}>
              {pending ? 'Working…' : 'Issue bill'}
            </button>
            <Link className="btn btn-ghost" href={`${base}/new?draft=${bill.id}`}>Edit</Link>
            <button type="button" className="btn-danger" disabled={pending}
              onClick={() => run(() => billAction(businessId, bill.id, 'delete'), 'Draft deleted', () => base)}>
              Delete draft
            </button>
          </div>
        </>
      ) : (
        <>
          <h2>Send and settle</h2>
          <div className="bos-inv-buttons">
            <button type="button" disabled={pending} onClick={() => share('whatsapp')}>Send on WhatsApp</button>
            <button type="button" className="btn-ghost" disabled={pending} onClick={() => share('copy')}>Copy customer link</button>
          </div>
          {link ? <input className="bos-inv-link" readOnly value={link} aria-label="Customer link" onFocus={(e) => e.currentTarget.select()} /> : null}
          <div className="bos-inv-buttons">
            {!isNote && bill.outstanding > 0 ? (
              <button type="button" className="btn-ghost" onClick={() => setPanel(panel === 'pay' ? null : 'pay')} aria-expanded={panel === 'pay'}>
                Record money received
              </button>
            ) : null}
            {!isNote ? (
              <>
                <button type="button" className="btn-ghost" onClick={() => setPanel(panel === 'credit' ? null : 'credit')} aria-expanded={panel === 'credit'}>
                  Credit note
                </button>
                <button type="button" className="btn-ghost" onClick={() => setPanel(panel === 'debit' ? null : 'debit')} aria-expanded={panel === 'debit'}>
                  Debit note
                </button>
              </>
            ) : null}
            <button type="button" className="btn-quiet" onClick={() => setPanel(panel === 'cancel' ? null : 'cancel')} aria-expanded={panel === 'cancel'}>
              Cancel {isNote ? 'note' : 'bill'}
            </button>
          </div>
        </>
      )}

      {panel === 'pay' ? <PaymentForm bill={bill} methods={methods} pending={pending}
        onSubmit={(body) => run(() => billAction(businessId, bill.id, 'payments', body), 'Recorded')} /> : null}
      {panel === 'credit' || panel === 'debit' ? (
        <NoteForm kind={panel === 'credit' ? 'credit_note' : 'debit_note'} bill={bill} reasons={noteReasons[panel === 'credit' ? 'credit_note' : 'debit_note'] ?? {}}
          pending={pending}
          onSubmit={(body) => run(() => billAction(businessId, bill.id, 'notes', body), 'Note issued', (n) => (n ? `${base}/${n.id}` : null))} />
      ) : null}
      {panel === 'cancel' ? <CancelForm pending={pending} isNote={isNote}
        onSubmit={(reason) => run(() => billAction(businessId, bill.id, 'cancel', { reason }), 'Cancelled')} /> : null}

      <p className={`bos-status${error ? ' bos-error' : ''}`} role="status" aria-live="polite">{error ?? done ?? ''}</p>
    </section>
  )
}

function PaymentForm({ bill, methods, pending, onSubmit }: {
  bill: Bill; methods: Record<string, string>; pending: boolean; onSubmit: (b: Record<string, unknown>) => void
}) {
  const [amount, setAmount] = useState(String(bill.outstanding))
  const [method, setMethod] = useState('upi')
  const [reference, setReference] = useState('')
  const [on, setOn] = useState(new Date().toISOString().slice(0, 10))
  return (
    <form className="bos-inv-form" onSubmit={(e) => { e.preventDefault(); onSubmit({ amount: Number(amount), method, reference: reference || undefined, received_on: on }) }}>
      <label><span className="bos-label">Amount</span><input inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} required /></label>
      <label><span className="bos-label">How</span>
        <select value={method} onChange={(e) => setMethod(e.target.value)}>
          {Object.entries(methods).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
      </label>
      <label><span className="bos-label">Reference — optional</span><input value={reference} onChange={(e) => setReference(e.target.value)} placeholder="UPI or cheque number" maxLength={120} /></label>
      <label><span className="bos-label">Received on</span><input type="date" value={on} onChange={(e) => setOn(e.target.value)} /></label>
      <p className="bos-fieldhelp">{rupees(bill.outstanding)} outstanding.</p>
      <button type="submit" disabled={pending}>Record</button>
    </form>
  )
}

function NoteForm({ kind, bill, reasons, pending, onSubmit }: {
  kind: 'credit_note' | 'debit_note'; bill: Bill; reasons: Record<string, string>; pending: boolean
  onSubmit: (b: Record<string, unknown>) => void
}) {
  const [reason, setReason] = useState(Object.keys(reasons)[0] ?? '')
  const [restock, setRestock] = useState(true)
  const [values, setValues] = useState<Record<string, string>>({})
  const byQty = kind === 'credit_note' && reason === 'return'
  const lines = bill.lines ?? []
  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    const chosen = lines
      .filter((l) => Number(values[l.id] || 0) > 0)
      .map((l) => (byQty ? { original_line_id: l.id, quantity: Number(values[l.id]) } : { original_line_id: l.id, amount: Number(values[l.id]) }))
    onSubmit({ kind, reason, restock: byQty && restock, lines: chosen })
  }
  return (
    <form className="bos-inv-form" onSubmit={submit}>
      <fieldset className="bos-choices" style={{ border: 0, padding: 0, margin: 0 }}>
        <legend className="bos-label">Why</legend>
        {Object.entries(reasons).map(([k, v]) => (
          <label key={k} className="bos-choice"><input type="radio" name={`${kind}-reason`} checked={reason === k} onChange={() => setReason(k)} /> {v}</label>
        ))}
      </fieldset>
      <p className="bos-fieldhelp">
        {byQty ? 'How many of each came back.' : `How much ${kind === 'credit_note' ? 'less' : 'more'} for each line, in the bill's own terms${bill.prices_include_tax ? ' (including GST)' : ' (before GST)'}.`}
      </p>
      <ul className="bos-inv-notelines">
        {lines.map((l) => (
          <li key={l.id}>
            <span>{l.title}<small>{byQty ? `up to ${l.returnable_quantity}` : kind === 'credit_note' ? `up to ${rupees(l.creditable_amount)}` : ''}</small></span>
            <input inputMode="decimal" aria-label={`${byQty ? 'Quantity' : 'Amount'} for ${l.title}`} value={values[l.id] ?? ''}
              onChange={(e) => setValues({ ...values, [l.id]: e.target.value.replace(/[^\d.]/g, '') })} placeholder="0" />
          </li>
        ))}
      </ul>
      {byQty ? (
        <label className="bos-toggle">
          <input type="checkbox" checked={restock} onChange={(e) => setRestock(e.target.checked)} />
          <span className="bos-toggle__track" aria-hidden />
          <span>Put the returned items back in stock</span>
        </label>
      ) : null}
      <button type="submit" disabled={pending}>Issue {kind === 'credit_note' ? 'credit' : 'debit'} note</button>
    </form>
  )
}

function CancelForm({ pending, isNote, onSubmit }: { pending: boolean; isNote: boolean; onSubmit: (reason: string) => void }) {
  const [reason, setReason] = useState('')
  return (
    <form className="bos-inv-form" onSubmit={(e) => { e.preventDefault(); onSubmit(reason) }}>
      <p className="bos-fieldhelp">
        A cancelled {isNote ? 'note' : 'bill'} stays in your records with its number, marked cancelled.
        {isNote ? '' : ' If money was received or it has notes against it, raise a credit note instead.'}
      </p>
      <label><span className="bos-label">Reason</span><input value={reason} onChange={(e) => setReason(e.target.value)} required maxLength={500} /></label>
      <button type="submit" className="btn-danger" disabled={pending || !reason.trim()}>Cancel it</button>
    </form>
  )
}
