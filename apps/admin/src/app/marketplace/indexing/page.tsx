import Link from 'next/link'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import {
  AdminNotice,
  EmptyState,
  MONO,
  PageHeader,
  Pill,
  ROW,
  TABLE,
  TD,
  TH,
} from '@/components/AdminNotice'
import { reindexBusiness } from './actions'

export const dynamic = 'force-dynamic'

type HealthRow = {
  business_id: string
  last_status: string
  last_indexed_at?: string | null
  last_attempt_at?: string | null
  last_error?: string | null
  last_reason?: string | null
}

type DeadLetter = {
  id: string
  event_type: string
  final_error?: string | null
  attempt_count?: number | null
  created_at?: string | null
}

/**
 * Admin indexing health (Doc 11 §17.3).
 *
 * Per-Business staleness, manual re-index, and dead-letter visibility. Reads on
 * the server with the Super Admin's own session, like every other Admin page,
 * so an account without a grant gets the same honest refusal here as it does on
 * System Health rather than an empty form.
 */
export default async function AdminIndexingHealthPage({
  searchParams,
}: {
  searchParams: { status?: string }
}) {
  const status = (searchParams.status || '').trim()

  const header = (
    <>
      <p style={{ marginBottom: '0.75rem' }}>
        <Link href="/" style={{ color: '#9fd0ff' }}>
          ← Admin home
        </Link>
      </p>
      <PageHeader
        title="Marketplace indexing health"
        subtitle="Projection staleness, manual re-index, and indexing dead letters. The worker job marketplace.reconcile repairs drift periodically."
      />
    </>
  )

  const token = await getAccessToken()
  if (!token) {
    return (
      <div>
        {header}
        <AdminNotice error={{ status: 0, code: 'NO_SESSION', message: 'no session' }} />
      </div>
    )
  }

  const qs = status ? `?status=${encodeURIComponent(status)}` : ''
  const res = await apiTry<{ data: { health: HealthRow[]; dead_letters: DeadLetter[] } }>(
    `/v1/admin/marketplace/indexing${qs}`,
    token
  )
  if (!res.ok) {
    return (
      <div>
        {header}
        <AdminNotice error={res.error} />
      </div>
    )
  }

  const health = res.data.data.health || []
  const deadLetters = res.data.data.dead_letters || []

  return (
    <div>
      {header}

      <form method="get" style={{ display: 'flex', gap: '0.5rem', alignItems: 'flex-end' }}>
        <label style={{ display: 'grid', gap: '0.25rem' }}>
          <span style={{ opacity: 0.75, fontSize: '0.85rem' }}>Filter status</span>
          <select name="status" defaultValue={status} style={{ padding: '0.45rem 0.6rem' }}>
            <option value="">All</option>
            <option value="indexed">indexed</option>
            <option value="deindexed">deindexed</option>
            <option value="failed">failed</option>
            <option value="never">never</option>
          </select>
        </label>
        <button type="submit" style={{ padding: '0.5rem 0.9rem' }}>
          Apply
        </button>
      </form>

      <section style={{ marginTop: '1.75rem' }}>
        <h2 style={{ fontSize: '1.15rem' }}>Business index status</h2>
        {health.length === 0 ? (
          <EmptyState>
            {status
              ? `No businesses with indexing status “${status}”.`
              : 'No indexing health rows yet.'}
          </EmptyState>
        ) : (
          <table style={{ ...TABLE, marginTop: '0.75rem' }}>
            <thead>
              <tr>
                <th style={TH}>Business</th>
                <th style={TH}>Status</th>
                <th style={TH}>Last indexed</th>
                <th style={TH}>Reason / error</th>
                <th style={TH} />
              </tr>
            </thead>
            <tbody>
              {health.map((row) => (
                <tr key={row.business_id} style={ROW}>
                  <td style={{ ...TD, ...MONO }}>{row.business_id}</td>
                  <td style={TD}>
                    <Pill value={row.last_status} />
                  </td>
                  <td style={TD}>{row.last_indexed_at || '—'}</td>
                  <td style={{ ...TD, opacity: 0.85 }}>
                    {row.last_error || row.last_reason || '—'}
                  </td>
                  <td style={TD}>
                    <form action={reindexBusiness}>
                      <input type="hidden" name="businessId" value={row.business_id} />
                      <button type="submit">Re-index</button>
                    </form>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section style={{ marginTop: '2rem' }}>
        <h2 style={{ fontSize: '1.15rem' }}>Indexing dead letters</h2>
        {deadLetters.length === 0 ? (
          <EmptyState>No marketplace dead-letter events.</EmptyState>
        ) : (
          <ul style={{ marginTop: '0.75rem', lineHeight: 1.6 }}>
            {deadLetters.map((d) => (
              <li key={d.id}>
                <code>{d.event_type}</code> · attempts {d.attempt_count ?? '?'} ·{' '}
                {d.final_error || 'no error text'}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}
