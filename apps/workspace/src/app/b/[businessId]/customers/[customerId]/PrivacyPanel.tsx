'use client'

import { useRouter } from 'next/navigation'
import { useState, useTransition } from 'react'
import { declineRequest, eraseCustomer, exportCustomer } from './privacy-actions'

export type Privacy = {
  erased_at: string | null
  open: string[]
  kept: { what: string; why: string; for: string }[]
  requests: { id: string; kind: string; status: string; source: string; note: string | null; resolution_note: string | null; created_at: string }[]
}

const day = (s: string) => new Date(s).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })

/**
 * Their data (CR-08; MD §25.1 DPDP): download everything held about them, and
 * erase their personal details for good — once nothing is still open — keeping
 * only what the law requires. A customer's own request shows here first.
 */
export function PrivacyPanel({ businessId, customerId, name, privacy, canExport, canErase }: {
  businessId: string
  customerId: string
  name: string
  privacy: Privacy
  canExport: boolean
  canErase: boolean
}) {
  const router = useRouter()
  const [pending, start] = useTransition()
  const [msg, setMsg] = useState<{ text: string; bad: boolean } | null>(null)
  const [confirm, setConfirm] = useState('')
  const [reason, setReason] = useState('')
  const [decline, setDecline] = useState('')
  const asked = privacy.requests.find((r) => r.kind === 'erasure' && r.status === 'open')

  const download = () => {
    setMsg(null)
    start(async () => {
      const r = await exportCustomer(businessId, customerId)
      if (!r.ok) return setMsg({ text: r.message, bad: true })
      const blob = new Blob([JSON.stringify(r.data, null, 2)], { type: 'application/json' })
      const a = document.createElement('a')
      a.href = URL.createObjectURL(blob)
      a.download = `customer-${name.toLowerCase().replace(/[^a-z0-9]+/g, '-')}.json`
      a.click()
      URL.revokeObjectURL(a.href)
      setMsg({ text: 'Downloaded. The file has everything you keep about them.', bad: false })
    })
  }
  const erase = () => {
    setMsg(null)
    start(async () => {
      const r = await eraseCustomer(businessId, customerId, confirm, reason)
      if (!r.ok) return setMsg({ text: r.message, bad: true })
      setMsg({ text: 'Their details are erased.', bad: false })
      router.refresh()
    })
  }
  const refuse = (id: string) => {
    setMsg(null)
    start(async () => {
      const r = await declineRequest(businessId, customerId, id, decline)
      if (!r.ok) return setMsg({ text: r.message, bad: true })
      setDecline('')
      setMsg({ text: 'Declined. They will see your reason in their account.', bad: false })
      router.refresh()
    })
  }

  if (privacy.erased_at) {
    return (
      <section className="bos-card bos-privacy" aria-labelledby="privacy-h">
        <h2 id="privacy-h">Their data</h2>
        <p>Their personal details were erased on {day(privacy.erased_at)}. Bills and khata entries the law requires stay, without their name or contact.</p>
      </section>
    )
  }

  return (
    <section className="bos-card bos-privacy" aria-labelledby="privacy-h">
      <h2 id="privacy-h">Their data</h2>
      {asked ? (
        <div className="bos-privacy__ask" role="note">
          <p><strong>They asked you to delete their details</strong> on {day(asked.created_at)}{asked.note ? ` — “${asked.note}”` : ''}.</p>
          {canErase ? (
            <div className="bos-privacy__decline">
              <input aria-label="Why you cannot delete yet" value={decline} maxLength={500} onChange={(e) => setDecline(e.target.value)}
                placeholder="If you cannot yet, say why (for example money still owed)" />
              <button type="button" className="btn-ghost" disabled={pending} onClick={() => refuse(asked.id)}>Decline</button>
            </div>
          ) : null}
        </div>
      ) : null}
      {canExport ? (
        <p><button type="button" className="btn-ghost" onClick={download} disabled={pending}>Download their data</button></p>
      ) : null}
      {canErase ? (
        privacy.open.length ? (
          <div>
            <p><strong>Erase their details</strong> — finish these first:</p>
            <ul className="bos-privacy__open">{privacy.open.map((o) => <li key={o}>{o}</li>)}</ul>
          </div>
        ) : (
          <div className="bos-privacy__erase">
            <p><strong>Erase their details for good.</strong> Their name, phone, email, tags, notes, enquiries, WhatsApp chat and delivery addresses are removed. This keeps:</p>
            <ul>{privacy.kept.map((k) => <li key={k.what}>{k.what} — {k.why}, {k.for}</li>)}</ul>
            <div className="bos-form-grid">
              <label>
                <span className="bos-label">Type “{name}” to confirm</span>
                <input name="erase-confirm" value={confirm} onChange={(e) => setConfirm(e.target.value)} autoComplete="off" />
              </label>
              <label>
                <span className="bos-label">Reason — optional</span>
                <input name="erase-reason" value={reason} maxLength={300} onChange={(e) => setReason(e.target.value)} placeholder="Asked by the customer" />
              </label>
            </div>
            <button type="button" className="bos-danger" onClick={erase}
              disabled={pending || confirm.trim().toLowerCase() !== name.trim().toLowerCase()}>
              {pending ? 'Erasing…' : 'Erase their details'}
            </button>
          </div>
        )
      ) : null}
      <p className={`bos-status${msg?.bad ? ' bos-error' : ''}`} role="status" aria-live="polite">{msg?.text ?? ''}</p>
    </section>
  )
}
