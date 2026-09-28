'use client'

import { useState } from 'react'
import { submitEnquiry, type EnquiryBody } from '@/lib/checkout-api'

const TITLES: Record<string, string> = {
  enquiry: 'Send an enquiry',
  site_visit: 'Book a site visit',
  test_drive: 'Book a test drive',
  callback: 'Ask for a call back',
}

/**
 * An enquiry to the business (Capability Universe §6.3, §19.2): it lands in
 * their Enquiries as a lead. The details are used to reply to this enquiry
 * only. A hidden field catches bots.
 */
export function EnquiryForm({
  slug,
  businessName,
  offeringId,
  offeringTitle,
  purpose = 'enquiry',
}: {
  slug: string
  businessName: string
  offeringId?: string
  offeringTitle?: string
  purpose?: string
}) {
  const p = (purpose in TITLES ? purpose : 'enquiry') as NonNullable<EnquiryBody['purpose']>
  const wantsDate = p === 'site_visit' || p === 'test_drive'
  const [state, setState] = useState<'idle' | 'sending' | 'sent'>('idle')
  const [error, setError] = useState<string | null>(null)
  const [ref, setRef] = useState<string | null>(null)
  const today = new Date().toISOString().slice(0, 10)

  if (state === 'sent') {
    return (
      <div className="ls-enquiry ls-enquiry--sent" role="status">
        <h2 className="ls-title">Sent</h2>
        <p>{businessName} has your {p === 'enquiry' ? 'enquiry' : 'request'} and will get back to you.{ref ? ` Reference ${ref}.` : ''}</p>
      </div>
    )
  }
  return (
    <form
      className="ls-enquiry"
      onSubmit={async (e) => {
        e.preventDefault()
        const f = new FormData(e.currentTarget)
        setError(null)
        setState('sending')
        try {
          const r = await submitEnquiry(slug, {
            name: String(f.get('name') || ''),
            phone: String(f.get('phone') || '') || undefined,
            email: String(f.get('email') || '') || undefined,
            message: String(f.get('message') || '') || undefined,
            preferred_date: String(f.get('preferred_date') || '') || undefined,
            website: String(f.get('website') || '') || undefined,
            offering_id: offeringId,
            purpose: p,
          })
          setRef(r.reference ?? null)
          setState('sent')
        } catch (err) {
          setError(err instanceof Error ? err.message : 'That did not send. Try again.')
          setState('idle')
        }
      }}
    >
      <h2 className="ls-title">{TITLES[p]}</h2>
      {offeringTitle ? <p className="ls-sub">About: {offeringTitle}</p> : null}
      <label>
        <span>Your name</span>
        <input name="name" required maxLength={80} autoComplete="name" />
      </label>
      <label>
        <span>Phone</span>
        <input name="phone" type="tel" inputMode="tel" maxLength={20} autoComplete="tel" />
      </label>
      <label>
        <span>Email (optional if you gave a phone)</span>
        <input name="email" type="email" maxLength={254} autoComplete="email" />
      </label>
      {wantsDate ? (
        <label>
          <span>Preferred date</span>
          <input name="preferred_date" type="date" min={today} />
        </label>
      ) : null}
      <label>
        <span>Message</span>
        <textarea name="message" rows={4} maxLength={1000} />
      </label>
      <label className="ls-hp" aria-hidden="true">
        <span>Leave this empty</span>
        <input name="website" tabIndex={-1} autoComplete="off" />
      </label>
      <p className="ls-meta">We share your details with {businessName} only, so they can reply.</p>
      {error ? <p className="ls-offer__error" role="alert">{error}</p> : null}
      <button type="submit" className="ls-btn" disabled={state === 'sending'}>
        {state === 'sending' ? 'Sending…' : 'Send'}
      </button>
    </form>
  )
}
