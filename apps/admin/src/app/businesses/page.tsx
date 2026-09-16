import Link from 'next/link'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import { AdminNotice, EmptyState, MONO, PageHeader, Pill, ROW, TABLE, TD, TH } from '@/components/AdminNotice'

export const dynamic = 'force-dynamic'

type BusinessRow = {
  id: string
  slug: string
  display_name: string
  state: string
  status: string
  visibility: string
  created_at: string | null
}

const STATES = ['draft', 'onboarding', 'active', 'dormant', 'closed']
const STANDINGS = ['in_good_standing', 'under_review', 'suspended']

/** ADM-002 — search across all joined Businesses. */
export default async function AdminBusinessesPage({
  searchParams,
}: {
  searchParams?: { query?: string; state?: string; business_status?: string }
}) {
  const token = await getAccessToken()
  if (!token) {
    return (
      <div>
        <PageHeader title="Businesses" />
        <AdminNotice error={{ status: 0, code: 'NO_SESSION', message: 'no session' }} />
      </div>
    )
  }

  const qs = new URLSearchParams()
  if (searchParams?.query) qs.set('query', searchParams.query)
  if (searchParams?.state) qs.set('state', searchParams.state)
  if (searchParams?.business_status) qs.set('business_status', searchParams.business_status)
  const suffix = qs.toString() ? `?${qs.toString()}` : ''

  const res = await apiTry<{ data: BusinessRow[] }>(`/v1/admin/businesses${suffix}`, token)
  if (!res.ok) {
    return (
      <div>
        <PageHeader title="Businesses" />
        <AdminNotice error={res.error} />
      </div>
    )
  }
  const businesses = res.data.data || []

  return (
    <div>
      <PageHeader
        title="Businesses"
        subtitle={`${businesses.length} shown`}
      />

      <form method="get" style={{ display: 'flex', gap: '0.6rem', flexWrap: 'wrap', marginBottom: '1.25rem' }}>
        <input
          name="query"
          defaultValue={searchParams?.query ?? ''}
          placeholder="Name or slug"
          style={INPUT}
        />
        <select name="state" defaultValue={searchParams?.state ?? ''} style={INPUT}>
          <option value="">Any lifecycle</option>
          {STATES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <select
          name="business_status"
          defaultValue={searchParams?.business_status ?? ''}
          style={INPUT}
        >
          <option value="">Any standing</option>
          {STANDINGS.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <button type="submit" style={BUTTON}>
          Search
        </button>
      </form>

      <div style={{ overflowX: 'auto' }}>
        <table style={TABLE}>
          <thead>
            <tr>
              <th style={TH}>Business</th>
              <th style={TH}>Lifecycle</th>
              <th style={TH}>Standing</th>
              <th style={TH}>Visibility</th>
              <th style={TH}>Created</th>
            </tr>
          </thead>
          <tbody>
            {businesses.map((b) => (
              <tr key={b.id} style={ROW}>
                <td style={TD}>
                  <Link href={`/businesses/${b.id}`} style={{ color: '#9fd0ff' }}>
                    {b.display_name}
                  </Link>
                  <div style={{ ...MONO, opacity: 0.55 }}>{b.slug}</div>
                </td>
                <td style={TD}>
                  <Pill value={b.state} />
                </td>
                <td style={TD}>
                  <Pill value={b.status} />
                </td>
                <td style={TD}>{b.visibility}</td>
                <td style={TD}>{b.created_at ? new Date(b.created_at).toLocaleDateString() : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {businesses.length === 0 ? (
        <EmptyState>No Businesses match this search.</EmptyState>
      ) : null}
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
