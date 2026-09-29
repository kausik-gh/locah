import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry, businessHeaders } from '@/lib/api'
import { GateNotice, PageHeader } from '@/components/ui'
import { SegmentBuilder, type RuleKind } from './SegmentBuilder'

export const dynamic = 'force-dynamic'

type Segment = { id: string; name: string; rule_words: string[]; count: number; whatsapp_offers: number }

/**
 * Segments (CR-04; MD §18.2 Audiences): groups of customers by what they did —
 * bought an item often, spent, stopped coming, owe on khata, a tag. Who is in a
 * segment is worked out from the records each time it is opened.
 */
export default async function SegmentsPage({ params }: { params: { businessId: string } }) {
  const token = await getAccessToken()
  if (!token) redirect('/login')
  const b = `/v1/platform/businesses/${params.businessId}`
  const base = `/b/${params.businessId}`
  const [res, items, tags, ctx] = await Promise.all([
    apiTry<{ data: Segment[]; meta: { rules: RuleKind[] } }>(`${b}/customers/segments`, token),
    apiTry<{ data: { id: string; title: string; status: string }[] }>(`${b}/products?status=active`, token),
    apiTry<{ data: { tag: string }[] }>(`${b}/customers/tags`, token),
    apiTry<{ data: { permissions: string[] } }>('/v1/me/context', token, businessHeaders(params.businessId)),
  ])
  const back = <Link href={`${base}/customers`}>Customers</Link>
  if (!res.ok) {
    return (
      <div className="bos-page">
        <PageHeader title="Segments" breadcrumb={back} />
        <GateNotice error={res.error} businessId={params.businessId} moduleLabel="Customers" />
      </div>
    )
  }
  const canSave = ctx.ok && ctx.data.data.permissions.includes('customers.update')
  const segments = res.data.data
  return (
    <div className="bos-page">
      <PageHeader title="Segments" breadcrumb={back}
        subtitle="Groups of customers by what they did. Counted from your orders, bills, bookings and khata each time you open one." />
      {segments.length ? (
        <ul className="bos-catalogue">
          {segments.map((s) => (
            <li key={s.id}>
              <Link href={`${base}/customers/segments/${s.id}`} className="bos-catalogue__main">
                <strong>{s.name}</strong>
                <span>{s.count === 1 ? '1 customer' : `${s.count} customers`}{s.whatsapp_offers ? ` · ${s.whatsapp_offers} said yes to offers on WhatsApp` : ''}</span>
                <span>{s.rule_words.join(' · ')}</span>
              </Link>
            </li>
          ))}
        </ul>
      ) : (
        <div className="bos-empty">No segments yet. Build one below — for example, customers who bought your best seller twice in 60 days.</div>
      )}
      <SegmentBuilder businessId={params.businessId} kinds={res.data.meta.rules} canSave={canSave}
        items={(items.ok ? items.data.data : []).filter((i) => i.status === 'active' && i.title !== 'Delivery fee').map((i) => ({ id: i.id, title: i.title }))}
        tags={tags.ok ? tags.data.data.map((t) => t.tag) : []} />
    </div>
  )
}
