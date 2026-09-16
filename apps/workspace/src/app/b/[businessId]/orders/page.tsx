import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import { DataTable, EmptyState, FilterTabs, GateNotice, PageHeader, StatusPill } from '@/components/ui'

export const dynamic = 'force-dynamic'

type OrderRow = {
  id: string
  order_number: string
  status: string
  payment_status: string
  payment_method: string
  total_amount: number
  currency: string
  created_at?: string
}

/** How the money stands, in words a shop owner uses. The stored values
 *  (`cod`, `pending_offline`) are internal states and must not reach the screen. */
const PAY_METHOD: Record<string, string> = {
  cod: 'Cash',
  online: 'Online',
  card: 'Card',
  upi: 'UPI',
}
const PAY_STATUS: Record<string, string> = {
  pending_offline: 'to collect',
  pending: 'awaiting payment',
  paid: 'paid',
  refunded: 'refunded',
  partially_refunded: 'part refunded',
  failed: 'payment failed',
}

function money(amount: number, currency: string): string {
  try {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: currency || 'INR',
      maximumFractionDigits: Number.isInteger(amount) ? 0 : 2,
    }).format(amount)
  } catch {
    return `${currency} ${amount}`
  }
}

function paymentLabel(o: { payment_method: string; payment_status: string }): string {
  const method = PAY_METHOD[o.payment_method] || o.payment_method.replace(/_/g, ' ')
  const status = PAY_STATUS[o.payment_status] || o.payment_status.replace(/_/g, ' ')
  return `${method} · ${status}`
}

/** Doc 11 §4.2 orders — board/list. */
export default async function OrdersBoardPage({
  params,
  searchParams,
}: {
  params: { businessId: string }
  searchParams?: { status?: string }
}) {
  const token = await getAccessToken()
  if (!token) redirect('/login')
  const base = `/b/${params.businessId}`
  const qs = searchParams?.status ? `?status=${encodeURIComponent(searchParams.status)}` : ''
  const res = await apiTry<{ data: OrderRow[] }>(
    `/v1/platform/businesses/${params.businessId}/orders${qs}`,
    token
  )
  if (!res.ok) {
    return (
      <div>
        <PageHeader title="Orders" />
        <GateNotice error={res.error} businessId={params.businessId} moduleLabel="Orders" />
      </div>
    )
  }
  const orders = res.data.data || []

  return (
    <div>
      <PageHeader title="Orders" subtitle="Accept, prepare, complete, or cancel each order from its detail page." />
      <FilterTabs
        current={searchParams?.status}
        hrefFor={(v) => `${base}/orders${v ? `?status=${v}` : ''}`}
        options={[
          { value: '', label: 'All' },
          { value: 'pending', label: 'Pending' },
          { value: 'accepted', label: 'Accepted' },
          { value: 'preparing', label: 'Preparing' },
          { value: 'ready', label: 'Ready' },
          { value: 'completed', label: 'Completed' },
          { value: 'cancelled', label: 'Cancelled' },
        ]}
      />
      <DataTable
        rows={orders}
        rowKey={(o) => o.id}
        columns={[
          {
            key: 'order_number',
            header: 'Order',
            render: (o) => <Link href={`${base}/orders/${o.id}`}>{o.order_number}</Link>,
          },
          { key: 'status', header: 'Status', render: (o) => <StatusPill value={o.status} /> },
          {
            key: 'payment',
            header: 'Payment',
            render: (o) => (
              <span style={{ color: 'var(--color-muted)' }}>{paymentLabel(o)}</span>
            ),
          },
          {
            key: 'total',
            header: 'Total',
            align: 'num',
            render: (o) => money(Number(o.total_amount) || 0, o.currency),
          },
        ]}
        empty={
          <EmptyState title="No orders here">
            {searchParams?.status
              ? `Nothing with status "${searchParams.status}" right now.`
              : 'Orders placed on your website land here for you to accept.'}
          </EmptyState>
        }
      />
    </div>
  )
}
