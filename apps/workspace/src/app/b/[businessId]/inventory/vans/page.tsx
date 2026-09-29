import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import { GateNotice, PageHeader } from '@/components/ui'
import type { Good, Place } from '../TransferBoard'
import { VanBoard, type VanCard } from '../VanBoard'

export const dynamic = 'force-dynamic'

/** What a van is carrying, what is on the way, and the move back to the store. */
export default async function VansPage({ params }: { params: { businessId: string } }) {
  const token = await getAccessToken()
  if (!token) redirect('/login')
  const b = params.businessId
  const [board, locs, items] = await Promise.all([
    apiTry<{ data: { vans: VanCard[] } }>(`/v1/platform/businesses/${b}/inventory/vans`, token),
    apiTry<{ data: Place[] }>(`/v1/platform/businesses/${b}/locations`, token),
    apiTry<{ data: Good[] }>(`/v1/platform/businesses/${b}/stock/items`, token),
  ])
  if (!board.ok) {
    return <div className="bos-page"><PageHeader title="Van stock" /><GateNotice error={board.error} businessId={b} moduleLabel="Stock" /></div>
  }
  return (
    <div className="bos-page">
      <PageHeader title="Van stock" subtitle="A van is a stock location. Parts used on a job leave this balance." />
      <p className="bos-hint"><Link href={`/b/${b}/inventory`}>← Stock</Link> · <Link href={`/b/${b}/inventory/transfers`}>Transfers</Link></p>
      <VanBoard
        businessId={b}
        vans={board.data.data.vans}
        places={locs.ok ? locs.data.data : []}
        goods={items.ok ? items.data.data : []}
      />
    </div>
  )
}
