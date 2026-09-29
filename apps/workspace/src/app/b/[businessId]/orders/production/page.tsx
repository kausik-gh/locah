import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import { GateNotice, PageHeader } from '@/components/ui'
import { PrintButton } from './PrintButton'

export const dynamic = 'force-dynamic'

type Production = {
  date: string
  label: string
  orders: number
  items: { item: string; quantity: number; orders: string[]; notes: { order_number: string; label: string; text: string; due_words: string | null }[] }[]
}

function shift(day: string, by: number): string {
  const d = new Date(`${day}T00:00:00Z`)
  d.setUTCDate(d.getUTCDate() + by)
  return d.toISOString().slice(0, 10)
}

/** The day's production list (MD §21.1 bakeries; home kitchens' batch list): what to make, added up. */
export default async function ProductionPage({
  params,
  searchParams,
}: {
  params: { businessId: string }
  searchParams?: { date?: string }
}) {
  const token = await getAccessToken()
  if (!token) redirect('/login')
  const base = `/b/${params.businessId}`
  const q = searchParams?.date ? `?date=${encodeURIComponent(searchParams.date)}` : ''
  const res = await apiTry<{ data: Production }>(`/v1/platform/businesses/${params.businessId}/orders/production${q}`, token)
  if (!res.ok) {
    return (
      <div>
        <PageHeader title="Production list" breadcrumb={<Link href={`${base}/orders`}>← Orders</Link>} />
        <GateNotice error={res.error} businessId={params.businessId} moduleLabel="Orders" />
      </div>
    )
  }
  const p = res.data.data
  return (
    <div className="bos-production">
      <PageHeader
        title={`Production · ${p.label}`}
        subtitle={p.orders ? `${p.orders} order${p.orders === 1 ? '' : 's'} wanted this day.` : 'Nothing is wanted this day yet.'}
        breadcrumb={<Link href={`${base}/orders`}>← Orders</Link>}
        actions={
          <span className="bos-inv-buttons">
            <Link className="btn btn-ghost" href={`${base}/orders/production?date=${shift(p.date, -1)}`}>← Day before</Link>
            <Link className="btn btn-ghost" href={`${base}/orders/production?date=${shift(p.date, 1)}`}>Next day →</Link>
            <PrintButton />
          </span>
        }
      />
      {p.items.length ? (
        <ul className="bos-prodlist">
          {p.items.map((it) => (
            <li key={it.item} className="bos-card">
              <div className="bos-prodlist__row">
                <strong className="bos-prodlist__qty">{it.quantity} ×</strong>
                <span className="bos-prodlist__item">{it.item}</span>
              </div>
              {it.notes.length ? (
                <ul className="bos-prodlist__notes">
                  {it.notes.map((n, i) => (
                    <li key={i}>
                      <span>{n.order_number}{n.due_words ? ` · ${n.due_words}` : ''}</span> — {n.label}: <strong>“{n.text}”</strong>
                    </li>
                  ))}
                </ul>
              ) : null}
              <p className="bos-hint">Orders: {it.orders.join(', ')}</p>
            </li>
          ))}
        </ul>
      ) : (
        <p className="bos-hint">When customers order for this day, what to make shows here, added up.</p>
      )}
    </div>
  )
}
