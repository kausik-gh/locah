import Link from 'next/link'
import { randomUUID } from 'node:crypto'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import { GateNotice, PageHeader, ROW, StatusPill, TABLE, TD, TH } from '@/components/ModuleState'
import { recordSettlement, refreshRefund, refundPayment } from '../actions'

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
  provider_reference: string | null
  refunded_amount: number
  refundable_amount: number
  failure_code: string | null
  failure_reason: string | null
  settlement?: { gross_amount?: number; platform_fee?: number; business_amount?: number } | null
  created_at: string
}

type Refund = {
  id: string
  amount: number
  reason: string | null
  status: string
  created_at: string
}

export default async function PaymentDetailPage({
  params,
}: {
  params: { businessId: string; paymentId: string }
}) {
  const token = await getAccessToken()
  if (!token) redirect('/login')

  const base = `/v1/platform/businesses/${params.businessId}/payments/${params.paymentId}`
  const res = await apiTry<{ data: Payment }>(base, token)
  if (!res.ok) {
    return (
      <div>
        <Link href={`/b/${params.businessId}/payments`}>← Payments</Link>
        <PageHeader title="Payment" />
        <GateNotice error={res.error} businessId={params.businessId} moduleLabel="Payments" />
      </div>
    )
  }
  const payment = res.data.data

  const refundsRes = await apiTry<{ data: Refund[] }>(`${base}/refunds`, token)
  const refunds = refundsRes.ok ? refundsRes.data.data || [] : []

  const canSettle = payment.status === 'pending' && payment.payment_method !== 'online'
  const pendingRefunds = refunds.filter((r) => r.status === 'pending').reduce((n, r) => n + r.amount, 0)
  const availableRefund = Math.max(payment.refundable_amount - pendingRefunds, 0)
  const canRefund = ['succeeded', 'partially_refunded'].includes(payment.status) && availableRefund > 0

  return (
    <div>
      <Link href={`/b/${params.businessId}/payments`}>← Payments</Link>
      <PageHeader
        title={`${payment.currency} ${payment.amount}`}
        subtitle={`For a ${payment.source_type} · ${payment.payment_method}`}
      />

      <p>
        Status: <StatusPill value={payment.status} />
        {payment.provider ? ` · via ${payment.provider}` : ''}
      </p>
      {payment.provider_reference ? (
        <p style={{ opacity: 0.75 }}>Reference: {payment.provider_reference}</p>
      ) : null}
      {payment.failure_reason ? (
        <p
          style={{
            padding: '0.75rem 1rem',
            borderRadius: '8px',
            background: 'var(--status-bad-bg)',
            border: '1px solid var(--status-bad-bd)',
          }}
        >
          This payment failed: {payment.failure_reason}
          {payment.failure_code ? ` (${payment.failure_code})` : ''}
        </p>
      ) : null}
      <p>
        Refunded: {payment.currency} {payment.refunded_amount} · Still refundable:{' '}
        {payment.currency} {availableRefund.toFixed(2)}
      </p>
      {payment.settlement?.business_amount != null ? <p>
        Customer paid {payment.currency} {payment.settlement.gross_amount} · LOCAH fee{' '}
        {payment.currency} {payment.settlement.platform_fee} · Business share{' '}
        {payment.currency} {payment.settlement.business_amount}
      </p> : null}

      {canSettle ? (
        <section style={{ marginTop: '1.5rem' }}>
          <h2 >Record settlement</h2>
          <p style={{ opacity: 0.8 }}>
            Mark this as paid once you have received the money in person.
          </p>
          <form action={recordSettlement}>
            <input type="hidden" name="businessId" value={params.businessId} />
            <input type="hidden" name="paymentId" value={params.paymentId} />
            <input type="hidden" name="idempotency_key" value={randomUUID()} />
            <button type="submit" style={BUTTON}>
              Mark as settled
            </button>
          </form>
        </section>
      ) : null}

      {canRefund ? (
        <section style={{ marginTop: '1.75rem', maxWidth: '28rem' }}>
          <h2 >Refund</h2>
          <form action={refundPayment} style={{ display: 'grid', gap: '0.6rem' }}>
            <input type="hidden" name="businessId" value={params.businessId} />
            <input type="hidden" name="paymentId" value={params.paymentId} />
            <input
              name="amount"
              type="number"
              step="0.01"
              min="0.01"
              max={availableRefund}
              defaultValue={availableRefund}
              required
              style={INPUT}
            />
            <input name="reason" placeholder="Reason for the refund" required style={INPUT} />
            <button type="submit" style={BUTTON}>
              {payment.provider === 'cashfree' ? 'Request refund' : 'Issue refund'}
            </button>
          </form>
        </section>
      ) : null}

      {refunds.length > 0 ? (
        <section style={{ marginTop: '1.75rem' }}>
          <h2 >Refund history</h2>
          <div className="ws-tablewrap">
            <table style={TABLE}>
              <thead>
                <tr>
                  <th style={TH}>Amount</th>
                  <th style={TH}>Reason</th>
                  <th style={TH}>Status</th>
                  <th style={TH}>When</th>
                </tr>
              </thead>
              <tbody>
                {refunds.map((refund) => (
                  <tr key={refund.id} style={ROW}>
                    <td style={{ ...TD, fontVariantNumeric: 'tabular-nums' }}>
                      {payment.currency} {refund.amount}
                    </td>
                    <td style={TD}>{refund.reason || '—'}</td>
                    <td style={TD}>
                      <StatusPill value={refund.status} />
                      {refund.status === 'pending' && payment.provider === 'cashfree' ? (
                        <form action={refreshRefund} style={{ display: 'inline', marginLeft: '.6rem' }}>
                          <input type="hidden" name="businessId" value={params.businessId} />
                          <input type="hidden" name="paymentId" value={params.paymentId} />
                          <input type="hidden" name="refundId" value={refund.id} />
                          <button type="submit">Check status</button>
                        </form>
                      ) : null}
                    </td>
                    <td style={TD}>{new Date(refund.created_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}
    </div>
  )
}

const INPUT: React.CSSProperties = {
  width: '100%',
}
const BUTTON: React.CSSProperties = {
  justifySelf: 'start',
}
