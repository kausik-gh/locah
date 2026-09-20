import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import { DetailShell, GateNotice, PageHeader, Section, StatusPill } from '@/components/ui'
import { advanceOrderStatus, cancelOrder } from '../actions'

export const dynamic = 'force-dynamic'

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
      currency: string
      items?: Array<{ title: string; quantity: number; line_total: number }>
    }
  }>(`/v1/platform/businesses/${params.businessId}/orders/${params.orderId}`, token)
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
          <button
            type="submit"
            className={status === 'rejected' ? 'btn-danger' : undefined}
            style={{ textTransform: 'capitalize' }}
          >
            {status}
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
        ['Payment', `${order.payment_method} · ${order.payment_status}`],
        ['Total', `${order.currency} ${order.total_amount}`],
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
                    <td>{item.title}</td>
                    <td data-num>{item.quantity}</td>
                    <td data-num>
                      {order.currency} {item.line_total}
                    </td>
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

      <p style={{ marginTop: '1.5rem', color: 'var(--color-muted)', fontSize: '0.88rem' }}>
        Refunds: use the Payments module transaction detail when a payment attempt exists.
      </p>
    </DetailShell>
  )
}
