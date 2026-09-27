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
import { CashfreeConnect } from './CashfreeConnect'

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
  settlement?: { gross_amount?: number; platform_fee?: number; business_amount?: number } | null
  created_at: string
}

type MerchantConnection = {
  provider: string
  status: string
  last_verified_at?: string | null
  provider_metadata?: { vendor_id?: string; vendor_status?: string; masked_account?: string; settlement_method?: string }
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
      `${base}/payments/merchant-connection?provider=cashfree`,
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

  const received = payments
    .filter((p) => p.status === 'succeeded')
    .reduce((sum, p) => sum + p.amount - p.refunded_amount, 0)
  const currency = payments[0]?.currency ?? 'INR'
  const pageBase = `/b/${params.businessId}/payments`

  return (
    <div>
      <PageHeader
        title="Payments"
        subtitle="Customer payments to your business. Your LOCAH plan and invoices belong in Billing."
      />

      <CashfreeConnect businessId={params.businessId} merchant={merchant} />

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
          Online collection is unavailable until Cashfree vendor verification and a LOCAH fee
          rule are active. Cash and offline settlement still work.
        </p>
      ) : null}

      <p style={{ fontSize: '1.1rem' }}>
        Successfully paid, less completed refunds:{' '}
        <strong style={{ fontVariantNumeric: 'tabular-nums' }}>
          {currency} {received.toFixed(2)}
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

      <div className="ws-tablewrap">
        <table style={TABLE}>
          <thead>
            <tr>
              <th style={TH}>For</th>
              <th style={TH}>Amount</th>
              <th style={TH}>Method</th>
              <th style={TH}>Provider</th>
              <th style={TH}>Business share</th>
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
                <td style={TD}>{payment.provider || '—'}</td>
                <td style={{ ...TD, fontVariantNumeric: 'tabular-nums' }}>
                  {payment.settlement?.business_amount != null
                    ? `${payment.currency} ${payment.settlement.business_amount}` : '—'}
                </td>
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
      </div>
      {payments.length === 0 ? (
        <EmptyState>
          No payments yet. They appear here as soon as an order, booking, or membership is paid
          for.
        </EmptyState>
      ) : null}
    </div>
  )
}
