import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import {
  GateNotice,
  PageHeader,
  Section,
  StatusPill,
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
  audience_snapshot: Record<string, unknown> | null
  offer_id: string | null
  creative: Record<string, unknown>
  approved_by: string | null
  approved_at: string | null
  approval_record: Record<string, unknown> | null
  version: number
}

function fmtPaise(paise: number | null): string {
  if (paise == null) return '—'
  if (paise === 0) return 'Free'
  return `₹${(paise / 100).toFixed(0)}`
}

/**
 * Campaign detail page: shows the full campaign state, approval record,
 * audience snapshot and creative. Owner can approve/dispatch from here.
 */
export default async function CampaignPage({
  params,
}: {
  params: { businessId: string; campaignId: string }
}) {
  const token = await getAccessToken()
  if (!token) redirect('/login')

  const base = `/v1/platform/businesses/${params.businessId}`
  const res = await apiTry<Campaign>(`${base}/marketing/campaigns/${params.campaignId}`, token)

  if (!res.ok) {
    return (
      <div>
        <PageHeader title="Campaign" />
        <GateNotice error={res.error} businessId={params.businessId} moduleLabel="Marketing" />
      </div>
    )
  }

  const c = res.data

  const FIELD_ROWS: { label: string; value: string }[] = [
    { label: 'ID', value: c.id },
    { label: 'Status', value: c.status },
    { label: 'Goal', value: c.goal },
    { label: 'Channel', value: c.channel },
    { label: 'Budget', value: fmtPaise(c.budget_paise) },
    { label: 'Estimated cost', value: fmtPaise(c.estimated_cost_paise) },
    { label: 'Actual cost', value: fmtPaise(c.actual_cost_paise) },
    { label: 'Version', value: String(c.version) },
    { label: 'Approved at', value: c.approved_at ? new Date(c.approved_at).toLocaleString('en-IN') : '—' },
  ]

  return (
    <div>
      <PageHeader title={c.name} description={`Campaign · ${c.channel}`} />

      <Section title="Details">
        <dl style={{ display: 'grid', gridTemplateColumns: '160px 1fr', gap: '0.35rem 1rem' }}>
          {FIELD_ROWS.map((r) => (
            <>
              <dt key={`dt-${r.label}`} style={{ color: 'var(--color-muted)', fontSize: '0.85rem' }}>
                {r.label}
              </dt>
              <dd key={`dd-${r.label}`} style={{ margin: 0, fontWeight: r.label === 'Status' ? 600 : undefined }}>
                {r.label === 'Status' ? <StatusPill status={r.value} /> : r.value}
              </dd>
            </>
          ))}
        </dl>
      </Section>

      {c.creative && Object.keys(c.creative).length > 0 && (
        <Section title="Creative">
          <pre
            style={{
              background: 'var(--color-surface-2)',
              borderRadius: 'var(--radius)',
              padding: '0.75rem 1rem',
              fontSize: '0.82rem',
              overflowX: 'auto',
              whiteSpace: 'pre-wrap',
            }}
          >
            {JSON.stringify(c.creative, null, 2)}
          </pre>
        </Section>
      )}

      {c.approval_record && Object.keys(c.approval_record).length > 0 && (
        <Section title="Approval record">
          <pre
            style={{
              background: 'var(--color-surface-2)',
              borderRadius: 'var(--radius)',
              padding: '0.75rem 1rem',
              fontSize: '0.82rem',
              overflowX: 'auto',
              whiteSpace: 'pre-wrap',
            }}
          >
            {JSON.stringify(c.approval_record, null, 2)}
          </pre>
        </Section>
      )}
    </div>
  )
}
