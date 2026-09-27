import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import { GateNotice, PageHeader } from '@/components/ModuleState'
import { AutomationActivity, AutomationCard, type Activity, type Automation } from './AutomationsEditor'

export const dynamic = 'force-dynamic'

/**
 * Settings → Automations (Capability Universe §2 rule 11, §24 #4; Business OS
 * Guide §6). Every automation LOCAH runs for this business, each step in plain
 * words, an off switch for the whole thing and for each step, and a log of
 * what actually happened.
 */
export default async function AutomationsPage({ params }: { params: { businessId: string } }) {
  const token = await getAccessToken()
  if (!token) redirect('/login')
  const res = await apiTry<{ data: { automations: Automation[]; activity: Activity[] } }>(
    `/v1/platform/businesses/${params.businessId}/automations`,
    token,
  )
  const header = (
    <PageHeader
      title="Automations"
      subtitle="What LOCAH does for you on its own. Every step is listed, and you can switch any of it off."
      breadcrumb={<Link href={`/b/${params.businessId}/settings`}>Settings</Link>}
    />
  )
  if (!res.ok) {
    return (
      <div className="bos-page">
        {header}
        <GateNotice error={res.error} businessId={params.businessId} moduleLabel="Automations" />
      </div>
    )
  }
  const { automations, activity } = res.data.data
  return (
    <div className="bos-page">
      {header}
      {automations.length === 0 ? (
        <div className="bos-empty">
          No automations yet. They appear here when you turn on a tool that has them — for example low-stock
          alerts with Inventory, or follow-up nudges with Leads.{' '}
          <Link href={`/b/${params.businessId}/modules`}>See your tools</Link>
        </div>
      ) : (
        <div className="bos-auto-list">
          {automations.map((a) => (
            <AutomationCard key={a.key} businessId={params.businessId} automation={a} />
          ))}
        </div>
      )}
      <section className="bos-section" aria-labelledby="log-h">
        <h2 className="bos-section__title" id="log-h">
          What automations did <span>last {activity.length}</span>
        </h2>
        <AutomationActivity items={activity} />
      </section>
    </div>
  )
}
