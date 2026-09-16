import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import { AdminNotice, EmptyState, MONO, PageHeader, Pill, ROW, TABLE, TD, TH } from '@/components/AdminNotice'

export const dynamic = 'force-dynamic'

type AuditEvent = {
  id: string
  event_type: string
  actor_identity_id: string
  actor_context: string
  business_id: string | null
  resource_type: string | null
  resource_id: string | null
  action: string
  reason: string | null
  occurred_at: string | null
}

const CONTEXTS = ['business', 'personal', 'admin', 'guest_checkout', 'system']

/**
 * ADM-018 — append-only evidence view over `platform_audit_events`.
 *
 * Read-only by construction: the API has no write or delete path to that
 * table. This page can only filter and display.
 */
export default async function AdminAuditPage({
  searchParams,
}: {
  searchParams?: {
    business_id?: string
    actor_identity_id?: string
    event_type?: string
    actor_context?: string
    resource_type?: string
  }
}) {
  const token = await getAccessToken()
  if (!token) {
    return (
      <div>
        <PageHeader title="Audit & Activity" />
        <AdminNotice error={{ status: 0, code: 'NO_SESSION', message: 'no session' }} />
      </div>
    )
  }

  const qs = new URLSearchParams()
  for (const key of [
    'business_id',
    'actor_identity_id',
    'event_type',
    'actor_context',
    'resource_type',
  ] as const) {
    const v = searchParams?.[key]
    if (v) qs.set(key, v)
  }
  qs.set('limit', '200')

  const res = await apiTry<{ data: AuditEvent[] }>(`/v1/admin/audit?${qs.toString()}`, token)
  if (!res.ok) {
    return (
      <div>
        <PageHeader title="Audit & Activity" />
        <AdminNotice error={res.error} />
      </div>
    )
  }
  const events = res.data.data || []

  return (
    <div>
      <PageHeader
        title="Audit & Activity"
        subtitle={`${events.length} event${events.length === 1 ? '' : 's'} (newest first, capped at 200)`}
      />

      <form method="get" style={{ display: 'flex', gap: '0.6rem', flexWrap: 'wrap', marginBottom: '1.25rem' }}>
        <input
          name="business_id"
          defaultValue={searchParams?.business_id ?? ''}
          placeholder="Business ID"
          style={INPUT}
        />
        <input
          name="actor_identity_id"
          defaultValue={searchParams?.actor_identity_id ?? ''}
          placeholder="Actor identity ID"
          style={INPUT}
        />
        <input
          name="event_type"
          defaultValue={searchParams?.event_type ?? ''}
          placeholder="Event type prefix, e.g. payment."
          style={INPUT}
        />
        <select name="actor_context" defaultValue={searchParams?.actor_context ?? ''} style={INPUT}>
          <option value="">Any context</option>
          {CONTEXTS.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
        <button type="submit" style={BUTTON}>
          Filter
        </button>
      </form>

      <div style={{ overflowX: 'auto' }}>
        <table style={TABLE}>
          <thead>
            <tr>
              <th style={TH}>When</th>
              <th style={TH}>Event</th>
              <th style={TH}>Actor</th>
              <th style={TH}>Context</th>
              <th style={TH}>Resource</th>
              <th style={TH}>Reason</th>
            </tr>
          </thead>
          <tbody>
            {events.map((e) => (
              <tr key={e.id} style={ROW}>
                <td style={{ ...TD, whiteSpace: 'nowrap' }}>
                  {e.occurred_at ? new Date(e.occurred_at).toLocaleString() : '—'}
                </td>
                <td style={{ ...TD, ...MONO }}>
                  {e.event_type}
                  <div style={{ opacity: 0.55 }}>{e.action}</div>
                </td>
                <td style={{ ...TD, ...MONO, opacity: 0.75 }}>{e.actor_identity_id.slice(0, 8)}…</td>
                <td style={TD}>
                  <Pill value={e.actor_context} />
                </td>
                <td style={{ ...TD, ...MONO, opacity: 0.75 }}>
                  {e.resource_type ?? '—'}
                  {e.resource_id ? ` ${e.resource_id.slice(0, 8)}…` : ''}
                </td>
                <td style={TD}>{e.reason ?? '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {events.length === 0 ? <EmptyState>No audit events match this filter.</EmptyState> : null}
    </div>
  )
}

const INPUT: React.CSSProperties = {
  padding: '0.45rem 0.55rem',
  borderRadius: '6px',
  border: '1px solid rgba(255,255,255,0.2)',
  background: 'rgba(255,255,255,0.06)',
  color: '#e8eef4',
  font: 'inherit',
}
const BUTTON: React.CSSProperties = {
  padding: '0.45rem 1rem',
  borderRadius: '6px',
  border: '1px solid rgba(255,255,255,0.25)',
  background: '#2d6cdf',
  color: '#fff',
  font: 'inherit',
  cursor: 'pointer',
}
