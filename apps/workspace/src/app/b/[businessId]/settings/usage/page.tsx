import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import { GateNotice, PageHeader } from '@/components/ModuleState'
import { UsageMeter, type Meter } from './UsageMeter'

export const dynamic = 'force-dynamic'

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September',
  'October', 'November', 'December']

/**
 * Settings → Usage (Capability Universe §2 rule 13, §24 #9): what this
 * business used this month of anything that costs money per use, and a limit
 * the owner sets so it never surprises them.
 */
export default async function UsagePage({ params }: { params: { businessId: string } }) {
  const token = await getAccessToken()
  if (!token) redirect('/login')
  const res = await apiTry<{ data: Meter[] }>(`/v1/platform/businesses/${params.businessId}/usage`, token)
  const header = (
    <PageHeader
      title="Usage"
      subtitle="Anything that costs per use is counted here each month. Set a limit and LOCAH stops before it, and tells you at 80%."
      breadcrumb={<Link href={`/b/${params.businessId}/settings`}>Settings</Link>}
    />
  )
  if (!res.ok) {
    return (
      <div className="bos-page">
        {header}
        <GateNotice error={res.error} businessId={params.businessId} moduleLabel="Usage" />
      </div>
    )
  }
  const meters = res.data.data
  const [year, month] = (meters[0]?.period ?? '').split('-').map(Number)
  const periodLabel = month ? `${MONTHS[month - 1]} ${year}` : 'This month'
  const counting = meters.filter((m) => m.counting)
  const later = meters.filter((m) => !m.counting)
  return (
    <div className="bos-page">
      {header}
      <section className="bos-section" aria-labelledby="now-h" style={{ marginTop: 0 }}>
        <h2 className="bos-section__title" id="now-h">
          {periodLabel} <span>counted now</span>
        </h2>
        <div className="bos-meters">
          {counting.map((m) => (
            <UsageMeter key={m.resource} businessId={params.businessId} meter={m} />
          ))}
        </div>
      </section>
      <section className="bos-section" aria-labelledby="later-h">
        <h2 className="bos-section__title" id="later-h">
          Counted once connected
        </h2>
        <p className="bos-hint">
          These start counting when you connect the service that sends them. You can set a limit now so it is in
          place from the first message.
        </p>
        <div className="bos-meters">
          {later.map((m) => (
            <UsageMeter key={m.resource} businessId={params.businessId} meter={m} />
          ))}
        </div>
      </section>
    </div>
  )
}
