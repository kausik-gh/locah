import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import { DataTable, EmptyState, FilterTabs, GateNotice, PageHeader, StatusPill } from '@/components/ui'
import { advanceOrderStatus } from './actions'
import { CHANNEL, money, paymentLabel } from './labels'

export const dynamic = 'force-dynamic'

type OrderRow = {
  id: string
  order_number: string
  status: string
  payment_status: string
  payment_method: string
  total_amount: number
  currency: string
  channel?: string | null
  due_at?: string | null
  created_at?: string
}

type Card = {
  id: string
  order_number: string
  status: string
  channel: string | null
  due_words: string
  customer: string | null
  mode: string | null
  total: number
  paid: number
  advance: number | null
  advance_state: 'paid' | 'awaited' | null
  items: { title: string; quantity: number; notes: Record<string, string> }[]
}
type Board = {
  buckets: { key: string; label: string; orders: Card[] }[]
  count: number
  preorder_items: number
  today: string
  tomorrow: string
}

/** The next step for an order on the board, in the words the counter uses. */
const NEXT: Record<string, [string, string]> = {
  pending: ['accepted', 'Accept'],
  accepted: ['preparing', 'Start preparing'],
  preparing: ['ready', 'Mark ready'],
  ready: ['completed', 'Hand over'],
}
const STATUS_WORDS: Record<string, string> = {
  pending: 'New',
  accepted: 'Accepted',
  preparing: 'Preparing',
  ready: 'Ready',
}
const EMPTY: Record<string, string> = {
  overdue: 'Nothing late.',
  now: 'Nothing due in the next few hours.',
  today: 'Nothing else wanted today.',
  tomorrow: 'Nothing wanted tomorrow yet.',
  later: 'No orders for later days yet.',
}

/**
 * Orders (Founder refinement — Orders & Customer Transactions): one list for
 * every channel — the channel is a filter, never a separate book. A business
 * that takes orders for a day (cakes, festival boxes, home-kitchen batches)
 * works them by when they are wanted: overdue, prepare now, today, tomorrow,
 * later, with the day's production list one tap away.
 */
export default async function OrdersPage({
  params,
  searchParams,
}: {
  params: { businessId: string }
  searchParams?: { status?: string; channel?: string; view?: string }
}) {
  const token = await getAccessToken()
  if (!token) redirect('/login')
  const base = `/b/${params.businessId}`
  const boardRes = await apiTry<{ data: Board }>(`/v1/platform/businesses/${params.businessId}/orders/board`, token)
  const board = boardRes.ok ? boardRes.data.data : null
  const takesDated = !!board && (board.count > 0 || board.preorder_items > 0)
  const view = searchParams?.view === 'list' || !takesDated ? 'list' : searchParams?.view === 'board' ? 'board' : 'board'

  const viewTabs = takesDated ? (
    <FilterTabs
      current={view}
      hrefFor={(v) => `${base}/orders?view=${v}`}
      options={[
        { value: 'board', label: 'By day wanted', count: board?.count },
        { value: 'list', label: 'All orders' },
      ]}
    />
  ) : null

  if (view === 'board' && board) {
    return (
      <div>
        <PageHeader
          title="Orders"
          subtitle="Orders for a day, by when they are wanted. Tap the next step as you go."
          actions={
            <span className="bos-inv-buttons">
              <Link className="btn btn-ghost" href={`${base}/orders/production?date=${board.today}`}>Today’s production</Link>
              <Link className="btn btn-ghost" href={`${base}/orders/production?date=${board.tomorrow}`}>Tomorrow’s production</Link>
            </span>
          }
        />
        {viewTabs}
        <div className="bos-board">
          {board.buckets.map((b) => (
            <section key={b.key} className={`bos-board__col bos-board__col--${b.key}`} aria-labelledby={`col-${b.key}`}>
              <h2 id={`col-${b.key}`} className="bos-board__h">
                {b.label} <span className="bos-board__n">{b.orders.length}</span>
              </h2>
              {b.orders.length === 0 ? <p className="bos-hint">{EMPTY[b.key]}</p> : null}
              {b.orders.map((o) => (
                <article key={o.id} className="bos-ordercard">
                  <header className="bos-ordercard__head">
                    <Link href={`${base}/orders/${o.id}`}><strong>{o.order_number}</strong></Link>
                    <span className="bos-ordercard__when">{o.due_words}</span>
                  </header>
                  <p className="bos-ordercard__who">
                    {o.customer || 'Customer'}
                    {o.mode ? ` · ${o.mode === 'delivery' ? 'Delivery' : 'Pickup'}` : ''}
                    {o.channel ? ` · ${CHANNEL[o.channel] || o.channel}` : ''}
                  </p>
                  <ul className="bos-ordercard__items">
                    {o.items.map((it, i) => (
                      <li key={i}>
                        <span>{it.quantity} × {it.title.replace(/\s(?:·|—)\s“[^”]*”/g, '')}</span>
                        {Object.entries(it.notes).map(([label, text]) => (
                          <span key={label} className="bos-ordercard__note">{label}: “{text}”</span>
                        ))}
                      </li>
                    ))}
                  </ul>
                  <footer className="bos-ordercard__foot">
                    <StatusPill value={STATUS_WORDS[o.status] || o.status} />
                    {o.advance !== null ? (
                      <span className={`bos-state ${o.advance_state === 'paid' ? 'is-ready' : ''}`}>
                        {o.advance_state === 'paid' ? 'Advance paid' : `Advance ${money(o.advance, 'INR')} awaited`}
                      </span>
                    ) : null}
                    {NEXT[o.status] ? (
                      <form action={advanceOrderStatus}>
                        <input type="hidden" name="businessId" value={params.businessId} />
                        <input type="hidden" name="orderId" value={o.id} />
                        <input type="hidden" name="status" value={NEXT[o.status][0]} />
                        <button type="submit" className="btn-ghost">{NEXT[o.status][1]}</button>
                      </form>
                    ) : null}
                  </footer>
                </article>
              ))}
            </section>
          ))}
        </div>
      </div>
    )
  }

  const qs = new URLSearchParams()
  if (searchParams?.status) qs.set('status', searchParams.status)
  if (searchParams?.channel) qs.set('channel', searchParams.channel)
  const res = await apiTry<{ data: OrderRow[] }>(
    `/v1/platform/businesses/${params.businessId}/orders${qs.toString() ? `?${qs}` : ''}`,
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
  const keep = (extra: Record<string, string | undefined>) => {
    const q = new URLSearchParams({ view: 'list' })
    for (const [k, v] of Object.entries({ status: searchParams?.status, channel: searchParams?.channel, ...extra })) {
      if (v) q.set(k, v)
    }
    return `${base}/orders?${q}`
  }

  return (
    <div>
      <PageHeader title="Orders" subtitle="Every order, from every channel, in one list. Open one to accept, prepare and complete it." />
      {viewTabs}
      <FilterTabs
        current={searchParams?.status}
        hrefFor={(v) => keep({ status: v || undefined })}
        options={[
          { value: '', label: 'All' },
          { value: 'pending', label: 'New' },
          { value: 'accepted', label: 'Accepted' },
          { value: 'preparing', label: 'Preparing' },
          { value: 'ready', label: 'Ready' },
          { value: 'completed', label: 'Completed' },
          { value: 'cancelled', label: 'Cancelled' },
        ]}
      />
      <FilterTabs
        current={searchParams?.channel}
        hrefFor={(v) => keep({ channel: v || undefined })}
        options={[{ value: '', label: 'Any channel' }, ...Object.entries(CHANNEL).map(([value, label]) => ({ value, label }))]}
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
            key: 'channel',
            header: 'From',
            render: (o) => (o.channel ? <span className="bos-tag">{CHANNEL[o.channel] || o.channel}</span> : '—'),
          },
          {
            key: 'payment',
            header: 'Payment',
            render: (o) => <span style={{ color: 'var(--color-muted)' }}>{paymentLabel(o)}</span>,
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
            {searchParams?.status || searchParams?.channel
              ? 'Nothing matches these filters right now.'
              : 'Orders placed on your website, WhatsApp, the counter or by phone land here.'}
          </EmptyState>
        }
      />
    </div>
  )
}
