import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import { DetailShell, GateNotice, PageHeader, Section, StatusPill } from '@/components/ui'
import { advanceOrderStatus, cancelOrder } from '../actions'
import { OrderBill } from './OrderBill'
import { MoneySection } from '@/components/MoneySection'
import { money, paymentLabel } from '../labels'
import { LocalTime } from '@/components/LocalTime'

export const dynamic = 'force-dynamic'

/** What each button does, in words (the stored states never reach the screen). */
const ACTION_WORDS: Record<string, string> = {
  accepted: 'Accept',
  rejected: 'Reject',
  preparing: 'Start preparing',
  ready: 'Mark ready',
  completed: 'Complete',
}

/** Doc 11 §4.2 order detail — state actions, cancel coordination. */
export default async function OrderDetailPage({
  params,
}: {
  params: { businessId: string; orderId: string }
}) {
  const token = await getAccessToken()
  if (!token) redirect('/login')
  const base = `/b/${params.businessId}`
  const res = await apiTry<{
    data: {
      id: string
      order_number: string
      status: string
      payment_status: string
      payment_method: string
      total_amount: number
      subtotal: number
      tax_amount: number
      discount_amount: number
      round_off: number
      tax_basis: { engine?: string; inclusive?: boolean; intra_state?: boolean; scheme?: string; rates_missing?: string[] }
      due_at?: string | null
      advance_amount?: number | null
      preorder_terms?: { cancel_hours?: number | null }
      currency: string
      items?: Array<{ title: string; quantity: number; line_total: number; basis_words?: string | null }>
    }
  }>(`/v1/platform/businesses/${params.businessId}/orders/${params.orderId}`, token)
  const bills = await apiTry<{ data: Array<{ id: string; number: string | null; kind_label: string; status: string; doc_kind: string }> }>(
    `/v1/platform/businesses/${params.businessId}/invoices?order_id=${params.orderId}&kind=invoices`, token)
  if (!res.ok) {
    return (
      <div>
        <PageHeader title="Order" breadcrumb={<Link href={`${base}/orders`}>← Orders</Link>} />
        <GateNotice error={res.error} businessId={params.businessId} moduleLabel="Orders" />
      </div>
    )
  }
  const order = res.data.data
  const nextByStatus: Record<string, string[]> = {
    pending: ['accepted', 'rejected'],
    accepted: ['preparing'],
    preparing: ['ready'],
    ready: ['completed'],
  }
  const next = nextByStatus[order.status] || []
  const cancellable = ['pending', 'accepted', 'preparing', 'ready'].includes(order.status)

  const actions = (
    <>
      {next.map((status) => (
        <form key={status} action={advanceOrderStatus}>
          <input type="hidden" name="businessId" value={params.businessId} />
          <input type="hidden" name="orderId" value={params.orderId} />
          <input type="hidden" name="status" value={status} />
          {status === 'rejected' ? (
            <input type="hidden" name="reason" value="Rejected by Business" />
          ) : null}
          <button type="submit" className={status === 'rejected' ? 'btn-danger' : undefined}>
            {ACTION_WORDS[status] || status}
          </button>
        </form>
      ))}
      {cancellable ? (
        <form action={cancelOrder}>
          <input type="hidden" name="businessId" value={params.businessId} />
          <input type="hidden" name="orderId" value={params.orderId} />
          <input type="hidden" name="reason" value="Cancelled from Workspace" />
          <button type="submit" className="btn-ghost">
            Cancel order
          </button>
        </form>
      ) : null}
    </>
  )

  return (
    <DetailShell
      breadcrumb={<Link href={`${base}/orders`}>← Orders</Link>}
      title={order.order_number}
      status={<StatusPill value={order.status} />}
      meta={[
        ['Payment', paymentLabel(order)],
        ['Total', money(Number(order.total_amount) || 0, order.currency)],
        ...(order.due_at ? [['Wanted for', <LocalTime key="due" value={order.due_at} />] as [string, React.ReactNode]] : []),
        ...(order.advance_amount ? [['Advance asked', money(Number(order.advance_amount), order.currency)] as [string, React.ReactNode]] : []),
      ]}
      actions={next.length || cancellable ? actions : undefined}
    >
      <Section title="Items">
        <div
          style={{
            border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius)',
            overflow: 'hidden',
            background: 'var(--color-surface)',
          }}
        >
          <div className="ws-tablewrap">
            <table>
              <thead>
                <tr>
                  <th>Item</th>
                  <th data-num>Qty</th>
                  <th data-num>Line total</th>
                </tr>
              </thead>
              <tbody>
                {(order.items || []).map((item, idx) => (
                  <tr key={idx}>
                    <td>
                      {item.title}
                      {item.basis_words ? <small className="bos-line-basis">{item.basis_words}</small> : null}
                    </td>
                    <td data-num>{item.quantity}</td>
                    <td data-num>{money(Number(item.line_total) || 0, order.currency)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {(order.items || []).length === 0 ? (
            <p style={{ padding: '1rem', color: 'var(--color-muted)', margin: 0 }}>
              No line items on this order.
            </p>
          ) : null}
        </div>
      </Section>

      {order.tax_basis?.engine ? (
        <dl className="bos-inv-ordertax">
          <dt>Before tax</dt><dd>{money(Number(order.subtotal) || 0, order.currency)}</dd>
          {order.discount_amount ? (<><dt>Discount</dt><dd>− {money(Number(order.discount_amount) || 0, order.currency)}</dd></>) : null}
          <dt>{order.tax_basis.scheme !== 'regular' ? 'Tax' : order.tax_basis.intra_state ? 'CGST + SGST' : 'IGST'}</dt>
          <dd>{money(Number(order.tax_amount) || 0, order.currency)}{order.tax_basis.inclusive ? ' (included in prices)' : ''}</dd>
          {order.round_off ? (<><dt>Round-off</dt><dd>{money(Number(order.round_off) || 0, order.currency)}</dd></>) : null}
          <dt>Total</dt><dd>{money(Number(order.total_amount) || 0, order.currency)}</dd>
        </dl>
      ) : null}
      {order.tax_basis?.rates_missing?.length ? (
        <p className="bos-inv-warn">No GST rate yet for: {order.tax_basis.rates_missing.join(', ')}. Add it in Tax rates before billing.</p>
      ) : null}

      {bills.ok ? (
        <Section title="Bill">
          <OrderBill
            businessId={params.businessId}
            orderId={params.orderId}
            cancelled={['cancelled', 'rejected'].includes(order.status)}
            live={bills.data.data.find((x) => x.status !== 'cancelled') ?? null}
          />
        </Section>
      ) : null}

      <MoneySection businessId={params.businessId} token={token} sourceType="order" sourceId={params.orderId}
        path={`${base}/orders/${params.orderId}`} />
    </DetailShell>
  )
}
