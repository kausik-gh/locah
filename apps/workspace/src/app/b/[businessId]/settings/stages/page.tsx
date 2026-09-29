import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import { PageHeader } from '@/components/ui'
import { StagesEditor, type StageSet } from './StagesEditor'

export const dynamic = 'force-dynamic'

const MODULES: { entity: StageSet['entity']; title: string; hint: string }[] = [
  { entity: 'orders', title: 'Orders',
    hint: 'Add the steps your team works through — “Picking” and “Packed” inside Preparing, say. Cancelling still releases stock and accepting still reserves it.' },
  { entity: 'leads', title: 'Enquiries',
    hint: 'Steps like “Site visit booked” inside Contacted. Winning an enquiry still makes the person a customer.' },
  { entity: 'projects', title: 'Projects',
    hint: 'Steps like “Site survey” and “Fabrication” inside In progress. Completing a project still closes it.' },
]

/**
 * Stages (P2-01; Capability Universe §24 #10 "configurable stage sets with
 * guarded transitions"): the business's own steps inside each module's
 * statuses. Only modules the business runs are shown.
 */
export default async function StagesPage({ params }: { params: { businessId: string } }) {
  const token = await getAccessToken()
  if (!token) redirect('/login')
  const b = params.businessId
  const [me, ...sets] = await Promise.all([
    apiTry<{ data: { permissions: string[] } }>(`/v1/me/context`, token, { 'X-Operating-Context': 'business', 'X-Business-Id': b }),
    ...MODULES.map((m) => apiTry<{ data: StageSet }>(`/v1/b/${b}/stages/${m.entity}`, token)),
  ])
  const canEdit = me.ok && (me.data.data.permissions ?? []).includes('settings.update')
  const shown = MODULES.map((m, i) => ({ ...m, res: sets[i] })).filter((m) => m.res.ok)
  return (
    <div className="bos-page">
      <PageHeader
        title="Stages"
        breadcrumb={<Link href={`/b/${b}/settings`}>← Settings</Link>}
        subtitle="Name the steps your work goes through. Each module keeps its own stages and rules; your steps sit inside them."
      />
      {shown.length === 0 ? (
        <p className="bos-hint">Stages come with orders, enquiries and projects. Turn one of them on in Modules first.</p>
      ) : (
        <div className="bos-works">
          {shown.map((m) => (m.res.ok ? (
            <StagesEditor key={m.entity} businessId={b} title={m.title} hint={m.hint} set={m.res.data.data}
              canEdit={canEdit} />
          ) : null))}
        </div>
      )}
    </div>
  )
}
