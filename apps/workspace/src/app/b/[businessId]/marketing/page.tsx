import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import {
  DataTable,
  EmptyState,
  GateNotice,
  PageHeader,
  Section,
  StatusPill,
  TABLE,
  TH,
  TD,
  ROW,
} from '@/components/ModuleState'

export const dynamic = 'force-dynamic'

type Campaign = {
  id: string
  name: string
  goal: string
  channel: string
  status: string
  budget_paise: number
  estimated_cost_paise: number | null
  actual_cost_paise: number
  audience_segment_id: string | null
  offer_id: string | null
  approved_at: string | null
  created_at: string
}

type MarketingPolicy = {
  allowed: boolean
  status: string
  reason: string | null
  requires_declaration: boolean
}

function fmtCost(paise: number | null): string {
  if (paise == null) return '—'
  if (paise === 0) return 'Free'
  return `₹${(paise / 100).toFixed(0)}`
}

/**
 * Doc 11 §9.7 Marketing — MK-01 through MK-10. Campaign list, policy gate,
 * and entry point to create new campaigns.
 */
export default async function MarketingPage({ params }: { params: { businessId: string } }) {
  const token = await getAccessToken()
  if (!token) redirect('/login')

  const base = `/v1/platform/businesses/${params.businessId}`
  const [campaignsRes, policyRes] = await Promise.all([
    apiTry<{ campaigns: Campaign[] }>(`${base}/marketing/campaigns`, token),
    apiTry<MarketingPolicy>(`${base}/marketing/policy`, token),
  ])

  if (!campaignsRes.ok) {
    return (
      <div>
        <PageHeader title="Campaigns" />
        <GateNotice error={campaignsRes.error} businessId={params.businessId} moduleLabel="Marketing" />
      </div>
    )
  }

  const campaigns = campaignsRes.data.campaigns ?? []
  const policy = policyRes.ok ? policyRes.data : null

  return (
    <div>
      <PageHeader
        title="Campaigns"
        description="Send WhatsApp broadcasts, create offers, and track results."
        action={
          policy?.allowed !== false
            ? { label: 'New campaign', href: `/b/${params.businessId}/marketing/new` }
            : undefined
        }
      />

      {policy && !policy.allowed && (
        <Section title="Restricted category">
          <div
            style={{
              padding: '0.75rem 1rem',
              borderRadius: 'var(--radius)',
              background: 'var(--color-warning-bg, #fffbeb)',
              border: '1px solid var(--color-warning, #fbbf24)',
              fontSize: '0.9rem',
              color: 'var(--color-warning-fg, #92400e)',
            }}
          >
            ⚠️ Marketing is restricted for your business category.{' '}
            {policy.reason ?? 'Please contact support for details.'}
          </div>
        </Section>
      )}

      {policy?.requires_declaration && (
        <Section title="Declaration required">
          <div
            style={{
              padding: '0.75rem 1rem',
              borderRadius: 'var(--radius)',
              background: 'var(--color-info-bg, #eff6ff)',
              border: '1px solid var(--color-info, #60a5fa)',
              fontSize: '0.9rem',
            }}
          >
            ℹ️ Your category requires an additional declaration before sending campaigns.
            This will be shown when you approve a campaign.
          </div>
        </Section>
      )}

      <Section title="Your campaigns">
        {campaigns.length === 0 ? (
          <EmptyState
            title="No campaigns yet"
            description="Create a WhatsApp broadcast campaign to reach your opted-in customers."
            action={
              policy?.allowed !== false
                ? { label: 'New campaign', href: `/b/${params.businessId}/marketing/new` }
                : undefined
            }
          />
        ) : (
          <TABLE>
            <thead>
              <tr>
                <TH>Name</TH>
                <TH>Goal</TH>
                <TH>Channel</TH>
                <TH>Budget</TH>
                <TH>Cost</TH>
                <TH>Status</TH>
                <TH>Created</TH>
              </tr>
            </thead>
            <tbody>
              {campaigns.map((c) => (
                <ROW key={c.id}>
                  <TD>
                    <Link href={`/b/${params.businessId}/marketing/${c.id}`}>{c.name}</Link>
                  </TD>
                  <TD>{c.goal}</TD>
                  <TD style={{ textTransform: 'capitalize' }}>{c.channel}</TD>
                  <TD>{fmtCost(c.budget_paise)}</TD>
                  <TD>{fmtCost(c.actual_cost_paise)}</TD>
                  <TD>
                    <StatusPill status={c.status} />
                  </TD>
                  <TD>{new Date(c.created_at).toLocaleDateString('en-IN')}</TD>
                </ROW>
              ))}
            </tbody>
          </TABLE>
        )}
      </Section>
    </div>
  )
}
