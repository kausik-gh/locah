import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry, businessHeaders } from '@/lib/api'
import { PageHeader } from '@/components/ui'
import { OfferingEditor } from '../OfferingEditor'
import type { Kind, RateLite } from '../types'

export const dynamic = 'force-dynamic'

/** Which tools make a kind useful here: shown first, the rest under "Other kinds". */
const KIND_TOOLS: Record<string, string[]> = {
  product: ['orders'], weighed_product: ['orders'], menu_item: ['orders'], package: ['orders'],
  digital_product: ['orders'], service: ['bookings'], class_session: ['bookings'], accommodation: ['bookings'],
  rental: ['bookings'], membership_plan: ['memberships'], course: ['leads'], property_project: ['leads'],
  property_unit: ['leads'], vehicle: ['leads'], portfolio_item: ['leads'], cause: ['orders'],
}

/** Products & services → Add: pick what kind of thing it is, then fill its form. */
export default async function NewOfferingPage({
  params,
  searchParams,
}: {
  params: { businessId: string }
  searchParams: { kind?: string }
}) {
  const token = await getAccessToken()
  if (!token) redirect('/login')
  const [kindsRes, ctxRes, ratesRes] = await Promise.all([
    apiTry<{ data: Kind[] }>('/v1/public/offering-kinds', token),
    apiTry<{ data: { module_states: Record<string, string> } }>('/v1/me/context', token, businessHeaders(params.businessId)),
    apiTry<{ data: RateLite[] }>(`/v1/platform/businesses/${params.businessId}/pricing/rates`, token),
  ])
  const kinds = kindsRes.ok ? kindsRes.data.data : []
  const states = ctxRes.ok ? ctxRes.data.data.module_states : {}
  const on = (m: string) => ['active', 'ready', 'enabled'].includes(states[m] ?? '')
  const base = `/b/${params.businessId}/offerings`
  const chosen = kinds.find((k) => k.key === searchParams.kind)

  if (chosen) {
    return (
      <div className="bos-page">
        <PageHeader
          title={`New ${chosen.label.toLowerCase()}`}
          subtitle={chosen.help}
          breadcrumb={<Link href={`${base}/new`}>Choose another kind</Link>}
        />
        <OfferingEditor businessId={params.businessId} kind={chosen} offering={null} variants={[]}
          rates={ratesRes.ok ? ratesRes.data.data : []} />
      </div>
    )
  }
  const fits = kinds.filter((k) => (KIND_TOOLS[k.key] ?? []).some(on))
  const others = kinds.filter((k) => !fits.includes(k))
  const card = (k: Kind) => (
    <Link key={k.key} href={`${base}/new?kind=${k.key}`} className="bos-kindcard">
      <strong>{k.label}</strong>
      <span>{k.help}</span>
      <em>
        {k.flow === 'cart' ? 'Sold online and at the counter' : k.flow === 'booking' ? 'Booked by date and time'
          : k.flow === 'membership' ? 'Joined and renewed' : k.flow === 'give' ? 'People give to it' : 'People enquire'}
      </em>
    </Link>
  )
  return (
    <div className="bos-page">
      <PageHeader
        title="What are you adding?"
        subtitle="The kind decides the details we ask for, how it shows on your website and how people get it."
        breadcrumb={<Link href={base}>Products & services</Link>}
      />
      {fits.length ? (
        <section aria-labelledby="fit-h">
          <h2 className="bos-section__title" id="fit-h">For the tools you use</h2>
          <div className="bos-kindgrid">{fits.map(card)}</div>
        </section>
      ) : null}
      <section className="bos-section" aria-labelledby="other-h">
        <h2 className="bos-section__title" id="other-h">{fits.length ? 'Other kinds' : 'Kinds'}</h2>
        <div className="bos-kindgrid">{others.map(card)}</div>
      </section>
    </div>
  )
}
