import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import { EmptyState, GateNotice, PageHeader, ROW, StatusPill, TABLE, TD, TH } from '@/components/ModuleState'

export const dynamic = 'force-dynamic'

type Campaign = {
  id: string
  name: string
  goal: string
  channel: string
  status: string
  budget_paise: number
  created_at: string
}

type Policy = {
  allowed: boolean
  status: string
  reason: string | null
  meta_targeting_check?: boolean
}

function rupees(paise: number): string {
  return `₹${(paise / 100).toFixed(0)}`
}

/** Campaign list. Creation, the builder and approval live on the campaign page. */
export default async function MarketingPage({ params }: { params: { businessId: string } }) {
  const token = await getAccessToken()
  if (!token) redirect('/login')

  const base = `/v1/platform/businesses/${params.businessId}`
  const campaignsRes = await apiTry<{ campaigns: Campaign[] }>(`${base}/marketing/campaigns`, token)
  if (!campaignsRes.ok) {
    return (
      <div>
        <PageHeader title="Campaigns" />
        <GateNotice error={campaignsRes.error} businessId={params.businessId} moduleLabel="Marketing" />
      </div>
    )
  }

  const policyRes = await apiTry<Policy>(`${base}/marketing/policy`, token)
  const policy = policyRes.ok ? policyRes.data : null
  const campaigns = campaignsRes.data.campaigns ?? []
  const blocked = policy?.allowed === false

  return (
    <div>
      <PageHeader
        title="Campaigns"
        subtitle="Goal, audience, offer, then the owner approves before anything is sent."
        actions={
          blocked ? null : <Link href={`/b/${params.businessId}/marketing/new`}>New campaign</Link>
        }
      />

      {policy && policy.status !== 'allowed' ? (
        <p style={{ maxWidth: '40rem' }}>
          <StatusPill value={policy.status} /> {policy.reason}
        </p>
      ) : null}

      {campaigns.length === 0 ? (
        <EmptyState>
          {blocked
            ? 'Marketing is off for this business.'
            : 'No campaigns yet. Create one, pick an audience, then submit it for approval.'}
        </EmptyState>
      ) : (
        <div className="ws-tablewrap">
          <table style={TABLE}>
            <thead>
              <tr>
                <th style={TH}>Name</th>
                <th style={TH}>Goal</th>
                <th style={TH}>Channel</th>
                <th style={TH}>Budget</th>
                <th style={TH}>Status</th>
              </tr>
            </thead>
            <tbody>
              {campaigns.map((campaign) => (
                <tr key={campaign.id} style={ROW}>
                  <td style={TD}>
                    <Link href={`/b/${params.businessId}/marketing/${campaign.id}`}>{campaign.name}</Link>
                  </td>
                  <td style={TD}>{campaign.goal}</td>
                  <td style={TD}>{campaign.channel}</td>
                  <td style={TD}>{rupees(campaign.budget_paise)}</td>
                  <td style={TD}>
                    <StatusPill value={campaign.status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
