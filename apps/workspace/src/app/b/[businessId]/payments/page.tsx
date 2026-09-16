import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import {
  EmptyState,
  GateNotice,
  PageHeader,
  ROW,
  StatusPill,
  TABLE,
  TD,
  TH,
} from '@/components/ModuleState'
import { RazorpayConnect } from './RazorpayConnect'

export const dynamic = 'force-dynamic'

type Payment = {
  id: string
  source_type: string
  source_id: string
  amount: number
  currency: string
  payment_method: string
  status: string
  provider: string | null
  refunded_amount: number
  failure_reason: string | null
  created_at: string
}

type MerchantConnection = {
  provider: string
  status: string
  key_id?: string | null
  has_credentials?: boolean
  connection_mode?: string | null
  linked_account_id?: string | null
  linked_account_status?: string | null
  requires_merchant_keys?: boolean
  external_dependency?: boolean
  last_verified_at?: string | null
  verification_error?: string | null
  provider_metadata?: { mode?: string; connection_mode?: string }
} | null

const STATUSES = ['pending', 'succeeded', 'failed', 'refunded']

/** Doc 11 §8 Payments — money in, settlements, refunds. */
export default async function PaymentsPage({
  params,
  searchParams,
}: {
  params: { businessId: string }
  searchParams?: { status?: string }
}) {
  const token = await getAccessToken()
  if (!token) redirect('/login')

  const base = `/v1/platform/businesses/${params.businessId}`
  const qs = searchParams?.status ? `?status=${encodeURIComponent(searchParams.status)}` : ''
  const [res, merchantRes] = await Promise.all([
    apiTry<{ data: Payment[] }>(`${base}/payments${qs}`, token),
    apiTry<{ data: MerchantConnection }>(
      `${base}/payments/merchant-connection?provider=razorpay`,
      token
    ),
  ])
  if (!res.ok) {
    return (
      <div>
        <PageHeader title="Payments" />
        <GateNotice error={res.error} businessId={params.businessId} moduleLabel="Payments" />
      </div>
    )
  }
  const payments = res.data.data || []
  const merchant = merchantRes.ok ? merchantRes.data.data : null

  const settled = payments
    .filter((p) => p.status === 'succeeded')
    .reduce((sum, p) => sum + p.amount - p.refunded_amount, 0)
  const currency = payments[0]?.currency ?? 'INR'
  const pageBase = `/b/${params.businessId}/payments`

  return (
    <div>
      <PageHeader
        title="Payments"
        subtitle="Every payment attempt against an order, booking, or membership."
      />

      <RazorpayConnect businessId={params.businessId} merchant={merchant} />

      {(!merchant || merchant.status !== 'active') ? (
        <p
          style={{
            padding: '0.75rem 1rem',
            borderRadius: '8px',
            background: 'var(--status-warn-bg)',
            border: '1px solid var(--status-warn-bd)',
            marginBottom: '1.25rem',
            fontSize: '0.9rem',
          }}
        >
          Online card payments are not live until this business is linked through Razorpay above.
          Cash and offline settlement still work in the meantime.
        </p>
      ) : null}

      <p style={{ fontSize: '1.1rem' }}>
        Net settled:{' '}
        <strong style={{ fontVariantNumeric: 'tabular-nums' }}>
          {currency} {settled.toFixed(2)}
        </strong>
      </p>

      <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', margin: '1rem 0' }}>
        <Link href={pageBase}>All</Link>
        {STATUSES.map((status) => (
          <Link key={status} href={`${pageBase}?status=${status}`}>
            {status}
          </Link>
        ))}
      </div>

      <table style={TABLE}>
        <thead>
          <tr>
            <th style={TH}>For</th>
            <th style={TH}>Amount</th>
            <th style={TH}>Method</th>
            <th style={TH}>Status</th>
            <th style={TH}>Refunded</th>
            <th style={TH}>When</th>
          </tr>
        </thead>
        <tbody>
          {payments.map((payment) => (
            <tr key={payment.id} style={ROW}>
              <td style={TD}>
                <Link href={`${pageBase}/${payment.id}`}>{payment.source_type}</Link>
              </td>
              <td style={{ ...TD, fontVariantNumeric: 'tabular-nums' }}>
                {payment.currency} {payment.amount}
              </td>
              <td style={TD}>{payment.payment_method}</td>
              <td style={TD}>
                <StatusPill value={payment.status} />
                {payment.failure_reason ? (
                  <span style={{ opacity: 0.7 }}> — {payment.failure_reason}</span>
                ) : null}
              </td>
              <td style={{ ...TD, fontVariantNumeric: 'tabular-nums' }}>
                {payment.refunded_amount > 0 ? payment.refunded_amount : '—'}
              </td>
              <td style={TD}>{new Date(payment.created_at).toLocaleDateString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {payments.length === 0 ? (
        <EmptyState>
          No payments yet. They appear here as soon as an order, booking, or membership is paid
          for.
        </EmptyState>
      ) : null}
    </div>
  )
}
