import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import { GateNotice, PageHeader } from '@/components/ui'
import { TransferBoard, type Good, type Place, type TransferCard } from '../TransferBoard'

export const dynamic = 'force-dynamic'

/** Operational transfer board: requested, in transit, received. */
export default async function TransfersPage({ params }: { params: { businessId: string } }) {
  const token = await getAccessToken()
  if (!token) redirect('/login')
  const b = params.businessId
  const [moves, locs, items] = await Promise.all([
    apiTry<{ data: TransferCard[] }>(`/v1/platform/businesses/${b}/inventory/transfers`, token),
    apiTry<{ data: Place[] }>(`/v1/platform/businesses/${b}/locations`, token),
    apiTry<{ data: Good[] }>(`/v1/platform/businesses/${b}/stock/items`, token),
  ])
  if (!moves.ok) {
    return <div className="bos-page"><PageHeader title="Transfers" /><GateNotice error={moves.error} businessId={b} moduleLabel="Stock" /></div>
  }
  return (
    <div className="bos-page">
      <PageHeader title="Transfers" subtitle="Stock leaves the source when it is sent, and arrives only when it is received." />
      <p className="bos-hint"><Link href={`/b/${b}/inventory`}>← Stock</Link> · <Link href={`/b/${b}/inventory/vans`}>Van stock</Link></p>
      <TransferBoard
        businessId={b}
        places={locs.ok ? locs.data.data : []}
        goods={items.ok ? items.data.data : []}
        transfers={moves.data.data}
      />
    </div>
  )
}
