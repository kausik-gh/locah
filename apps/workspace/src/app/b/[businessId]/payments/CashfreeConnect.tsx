'use client'

import { useFormState, useFormStatus } from 'react-dom'
import { connectCashfree, refreshCashfree, type CashfreeState } from './actions'

type Merchant = {
  status: string
  provider_metadata?: {
    vendor_id?: string
    vendor_status?: string
    masked_account?: string
    settlement_method?: string
  }
  last_verified_at?: string | null
} | null

const initial: CashfreeState = { ok: false, error: null }

function Submit({ children }: { children: React.ReactNode }) {
  const { pending } = useFormStatus()
  return <button type="submit" disabled={pending}>{pending ? 'Please wait…' : children}</button>
}

export function CashfreeConnect({ businessId, merchant }: { businessId: string; merchant: Merchant }) {
  const [setup, setupAction] = useFormState(connectCashfree, initial)
  const [refresh, refreshAction] = useFormState(refreshCashfree, initial)
  const active = merchant?.status === 'active'
  const metadata = merchant?.provider_metadata

  return (
    <section className="ws-card" style={{ padding: '1.5rem', marginBottom: '1.5rem' }}>
      <p style={{ textTransform: 'uppercase', letterSpacing: '.1em', fontSize: '.72rem', opacity: .7 }}>
        Settlement account · Cashfree sandbox
      </p>
      <h2 style={{ margin: '.35rem 0' }}>Accept online payments</h2>
      <p style={{ opacity: .75, maxWidth: '55ch' }}>
        Cashfree handles secure checkout and settles your share directly to your verified account.
        Cash and pay-at-business remain available while verification is pending.
      </p>
      <p role="status">
        <strong>{active ? 'Ready for sandbox payments' : merchant ? 'Verification pending' : 'Not set up'}</strong>
        {metadata?.vendor_status ? ` · Cashfree ${metadata.vendor_status}` : ''}
        {metadata?.masked_account ? ` · ${metadata.masked_account}` : ''}
      </p>
      {setup.error || refresh.error ? <p role="alert" style={{ color: 'var(--status-bad-fg)' }}>
        {setup.error || refresh.error}
      </p> : null}
      {setup.ok ? <p role="status">Submitted. Check the status below when Cashfree completes verification.</p> : null}
      {merchant ? (
        <form action={refreshAction}>
          <input type="hidden" name="businessId" value={businessId} />
          <Submit>Check verification status</Submit>
        </form>
      ) : (
        <form action={setupAction} style={{ display: 'grid', gap: '.9rem', maxWidth: '38rem' }}>
          <input type="hidden" name="businessId" value={businessId} />
          <label>Business or account holder name<input name="name" required autoComplete="organization" /></label>
          <label>Email<input name="email" type="email" required autoComplete="email" /></label>
          <label>Indian mobile number<input name="phone" inputMode="numeric" pattern="[0-9]{10}" required /></label>
          <label>Account type<select name="account_type" required>
            <option value="BUSINESS">Business</option><option value="INDIVIDUAL">Individual</option>
          </select></label>
          <label>Business type, if applicable<input name="business_type" placeholder="Proprietorship, LLP…" /></label>
          <label>PAN<input name="pan" required maxLength={10} autoCapitalize="characters" /></label>
          <label>GST, if registered<input name="gst" /></label>
          <label>CIN, if applicable<input name="cin" /></label>
          <hr style={{ width: '100%', opacity: .25 }} />
          <label>Bank account holder<input name="account_holder" required autoComplete="name" /></label>
          <label>Account number<input name="account_number" required inputMode="numeric" autoComplete="off" /></label>
          <label>IFSC<input name="ifsc" required autoCapitalize="characters" maxLength={11} /></label>
          <p style={{ fontSize: '.82rem', opacity: .7, margin: 0 }}>
            Bank and KYC details are sent to Cashfree for verification. LOCAH stores only a masked
            account reference and vendor status.
          </p>
          <Submit>Set up online payments</Submit>
        </form>
      )}
      {refresh.ok && refresh.status === 'active' ? <p role="status">Verification is active.</p> : null}
    </section>
  )
}
