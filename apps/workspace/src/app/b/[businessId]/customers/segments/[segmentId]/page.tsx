import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry, businessHeaders } from '@/lib/api'
import { GateNotice, PageHeader } from '@/components/ui'
import { ArchiveSegment } from './ArchiveSegment'

export const dynamic = 'force-dynamic'

type Segment = {
  id: string
  name: string
  rule_words: string[]
  count: number
  whatsapp_offers: number
  members: { id: string; display_name: string; phone: string | null; tags: string[]; last_interaction_at: string | null }[]
}

/** One segment: its rules in words and who is in it right now (CR-04). */
export default async function SegmentPage({ params }: { params: { businessId: string; segmentId: string } }) {
  const token = await getAccessToken()
  if (!token) redirect('/login')
  const base = `/b/${params.businessId}`
  const [res, ctx] = await Promise.all([
    apiTry<{ data: Segment }>(`/v1/platform/businesses/${params.businessId}/customers/segments/${params.segmentId}`, token),
    apiTry<{ data: { permissions: string[] } }>('/v1/me/context', token, businessHeaders(params.businessId)),
  ])
  const back = <Link href={`${base}/customers/segments`}>Segments</Link>
  if (!res.ok) {
    return (
      <div className="bos-page">
        <PageHeader title="Segment" breadcrumb={back} />
        <GateNotice error={res.error} businessId={params.businessId} moduleLabel="Customers" />
      </div>
    )
  }
  const s = res.data.data
  const canChange = ctx.ok && ctx.data.data.permissions.includes('customers.update')
  return (
    <div className="bos-page">
      <PageHeader title={s.name} breadcrumb={back} subtitle={s.rule_words.join(' · ')}
        actions={canChange ? <ArchiveSegment businessId={params.businessId} segmentId={s.id} /> : null} />
      <p className="bos-seg-count">{s.count === 1 ? '1 customer' : `${s.count} customers`}</p>
      <p className="bos-hint">{s.whatsapp_offers} said yes to offers on WhatsApp — only they can be sent one. Counted just now from your records.</p>
      {s.members.length ? (
        <ul className="bos-catalogue">
          {s.members.map((m) => (
            <li key={m.id}>
              <Link href={`${base}/customers/${m.id}`} className="bos-catalogue__main">
                <strong>{m.display_name}</strong>
                <span>{[m.phone, m.tags.join(', ')].filter(Boolean).join(' · ') || '—'}</span>
              </Link>
            </li>
          ))}
        </ul>
      ) : (
        <div className="bos-empty">Nobody matches these rules right now.</div>
      )}
      {s.count > s.members.length ? <p className="bos-hint">Showing the first {s.members.length} of {s.count}.</p> : null}
    </div>
  )
}
