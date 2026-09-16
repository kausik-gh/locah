'use client'

import { useFormState, useFormStatus } from 'react-dom'
import {
  connectRazorpay,
  verifyRazorpay,
  type RazorpayState,
} from './actions'

type Merchant = {
  status: string
  key_id?: string | null
  has_credentials?: boolean
  last_verified_at?: string | null
  verification_error?: string | null
  provider_metadata?: { mode?: string }
} | null

const INITIAL: RazorpayState = { ok: false, error: null }

const CARD: React.CSSProperties = {
  padding: '1.25rem 1.4rem',
  borderRadius: '10px',
  border: '1px solid var(--color-border)',
  background: 'var(--color-surface)',
  maxWidth: '38rem',
}
const INPUT: React.CSSProperties = {
  width: '100%',
}

/** The four states the work order calls for, mapped from the API status. */
function statusLabel(m: Merchant): { text: string; tone: 'good' | 'warn' | 'bad' | 'neutral' } {
  if (!m || m.status === 'not_connected') return { text: 'Not connected', tone: 'neutral' }
  if (m.status === 'active') return { text: 'Active — verified', tone: 'good' }
  if (m.status === 'invalid_credentials')
    return { text: 'Invalid credentials', tone: 'bad' }
  if (m.status === 'pending') return { text: 'Connected — not yet verified', tone: 'warn' }
  return { text: m.status, tone: 'neutral' }
}

function Pill({ m }: { m: Merchant }) {
  const { text, tone } = statusLabel(m)
  const colors = {
    good: ['#1c5f2f', 'rgba(28,95,47,0.12)', 'rgba(28,95,47,0.4)'],
    warn: ['#8a6d1f', 'rgba(138,109,31,0.12)', 'rgba(138,109,31,0.4)'],
    bad: ['#a33333', 'rgba(163,51,51,0.12)', 'rgba(163,51,51,0.4)'],
    neutral: ['#4c5967', 'rgba(28,36,48,0.08)', 'var(--color-border-strong)'],
  }[tone]
  return (
    <span
      style={{
        display: 'inline-block',
        padding: '0.25rem 0.7rem',
        borderRadius: '999px',
        fontSize: '0.8rem',
        fontWeight: 600,
        color: colors[0],
        background: colors[1],
        border: `1px solid ${colors[2]}`,
      }}
    >
      {text}
    </span>
  )
}

function SubmitButton({ label, pendingLabel }: { label: string; pendingLabel: string }) {
  const { pending } = useFormStatus()
  return (
    <button
      type="submit"
      disabled={pending}
      style={{
        padding: '0.55rem 1.1rem',
        borderRadius: '7px',
        border: 'none',
        background: pending ? '#7d9c96' : '#1c5f57',
        color: '#fff',
        fontWeight: 600,
        fontSize: '0.9rem',
        cursor: pending ? 'progress' : 'pointer',
      }}
    >
      {pending ? pendingLabel : label}
    </button>
  )
}

export function RazorpayConnect({
  businessId,
  merchant,
}: {
  businessId: string
  merchant: Merchant
}) {
  const [connectState, connectAction] = useFormState(connectRazorpay, INITIAL)
  const [verifyState, verifyAction] = useFormState(verifyRazorpay, INITIAL)

  const connected = merchant?.has_credentials === true
  const showError =
    connectState.error ?? verifyState.error ?? merchant?.verification_error ?? null
  const showSuccess = connectState.ok || verifyState.ok

  return (
    <section style={{ ...CARD, marginBottom: '1.75rem' }}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: '1rem',
          flexWrap: 'wrap',
        }}
      >
        <h2 style={{ margin: 0, fontSize: '1.15rem' }}>Razorpay</h2>
        <Pill m={merchant} />
      </div>

      <p
        style={{
          fontSize: '0.9rem',
          color: '#4c5967',
          lineHeight: 1.6,
          margin: '0.6rem 0 1rem',
        }}
      >
        Complete KYC in your own{' '}
        <a href="https://dashboard.razorpay.com/app/keys" target="_blank" rel="noreferrer">
          Razorpay dashboard
        </a>
        , then paste your API keys here. The Key Secret is encrypted before it is stored and is
        never shown again. Payments still settle to your Razorpay account, not the platform.
      </p>

      {connected && merchant?.key_id ? (
        <p style={{ fontSize: '0.85rem', margin: '0 0 0.9rem' }}>
          Connected as{' '}
          <code style={{ fontSize: '0.85rem' }}>{merchant.key_id}</code>
          {merchant.provider_metadata?.mode ? ` (${merchant.provider_metadata.mode} mode)` : ''}
          {merchant.last_verified_at
            ? ` · last verified ${new Date(merchant.last_verified_at).toLocaleString()}`
            : ''}
        </p>
      ) : null}

      {showError && !showSuccess ? (
        <p
          role="alert"
          style={{
            margin: '0 0 0.9rem',
            padding: '0.6rem 0.85rem',
            borderRadius: '7px',
            border: '1px solid var(--status-bad-bd)',
            background: 'var(--status-bad-bg)',
            color: '#8d2f24',
            fontSize: '0.88rem',
            lineHeight: 1.5,
          }}
        >
          {showError}
        </p>
      ) : null}

      {showSuccess ? (
        <p
          style={{
            margin: '0 0 0.9rem',
            padding: '0.6rem 0.85rem',
            borderRadius: '7px',
            border: '1px solid rgba(28,95,47,0.35)',
            background: 'rgba(28,95,47,0.08)',
            color: '#1c5f2f',
            fontSize: '0.88rem',
          }}
        >
          Razorpay verified — you can now take online payments.
        </p>
      ) : null}

      <form action={connectAction} style={{ display: 'grid', gap: '0.8rem' }}>
        <input type="hidden" name="businessId" value={businessId} />
        <label style={{ display: 'grid', gap: '0.3rem' }}>
          <span style={{ fontSize: '0.85rem', fontWeight: 600 }}>Key ID</span>
          <input
            name="key_id"
            placeholder="rzp_live_XXXXXXXXXXXXXX"
            defaultValue={merchant?.key_id ?? ''}
            autoComplete="off"
            spellCheck={false}
            style={INPUT}
          />
        </label>
        <label style={{ display: 'grid', gap: '0.3rem' }}>
          <span style={{ fontSize: '0.85rem', fontWeight: 600 }}>
            Key Secret{connected ? ' (enter again to replace)' : ''}
          </span>
          <input
            name="key_secret"
            type="password"
            placeholder="••••••••••••••••••••"
            autoComplete="off"
            spellCheck={false}
            style={INPUT}
          />
        </label>
        <div style={{ display: 'flex', gap: '0.6rem', alignItems: 'center', flexWrap: 'wrap' }}>
          <SubmitButton label="Save & test connection" pendingLabel="Testing with Razorpay…" />
        </div>
      </form>

      {connected ? (
        <form action={verifyAction} style={{ marginTop: '0.8rem' }}>
          <input type="hidden" name="businessId" value={businessId} />
          <button
            type="submit"
            style={{
              background: 'none',
              border: 'none',
              padding: 0,
              color: '#1c5f57',
              fontSize: '0.85rem',
              textDecoration: 'underline',
              cursor: 'pointer',
            }}
          >
            Re-test the stored credentials
          </button>
        </form>
      ) : null}
    </section>
  )
}
