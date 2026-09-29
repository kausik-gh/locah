import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import { GateNotice, PageHeader } from '@/components/ui'
import { KitchenSetup } from './KitchenSetup'

export const dynamic = 'force-dynamic'

type Station = { id: string; key: string; name: string; active: boolean }
type Kind = { key: string; name: string }
type Route = { offering_id: string; station_ids: string[] }
type Offering = { id: string; title: string; offering_type?: string; status: string }

/**
 * Which stations this business cooks on, and which items go to each.
 * The pass itself is the full-screen kitchen display.
 */
export default async function KitchenStationsPage({ params }: { params: { businessId: string } }) {
  const token = await getAccessToken()
  if (!token) redirect(`/login?destination=${encodeURIComponent(`/b/${params.businessId}/kitchen`)}`)
  const businessId = params.businessId
  const [setup, products] = await Promise.all([
    apiTry<{ data: { stations: Station[]; station_kinds: Kind[]; routes: Route[] } }>(
      `/v1/platform/businesses/${businessId}/kitchen/stations`,
      token,
    ),
    apiTry<{ data: Offering[] }>(`/v1/platform/businesses/${businessId}/products`, token),
  ])
  if (!setup.ok) return <GateNotice error={setup.error} businessId={businessId} moduleLabel="Kitchen display" />
  const offerings = (products.ok ? products.data.data : []).filter((item) => item.status === 'active')
  return (
    <>
      <PageHeader
        title="Kitchen stations"
        subtitle="Items go to the stations you choose. Anything prepared with no station lands on General."
        actions={<Link className="btn" href={`/kds/${businessId}`}>Open the pass</Link>}
      />
      <KitchenSetup
        businessId={businessId}
        stations={setup.data.data.stations.filter((station) => station.active)}
        kinds={setup.data.data.station_kinds}
        routes={setup.data.data.routes}
        offerings={offerings.map((item) => ({ id: item.id, title: item.title, kind: item.offering_type || '' }))}
      />
    </>
  )
}
