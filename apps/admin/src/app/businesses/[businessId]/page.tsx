import Link from 'next/link'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import { AdminNotice, MONO, PageHeader, Pill, ROW, TABLE, TD, TH } from '@/components/AdminNotice'

export const dynamic = 'force-dynamic'

type SupportView = {
  business: {
    id: string
    slug: string
    display_name: string
    business_type: string | null
    state: string
    status: string
    visibility: string
    primary_owner_identity_id: string | null
    created_at: string | null
  }
  modules: Array<{ module_id: string; activation_state: string; activated_at: string | null }>
  locations: Array<{ id: string; name: string; is_primary: boolean; status: string }>
  active_member_count: number
}

/**
 * ADM-003 + ADM-008 — support hub for one Business.
 *
 * Loading this page writes an `admin.business.support_viewed` audit event
 * attributed to the calling Admin (server-side, in the endpoint). There is no
 * way to reach this view without that trace being recorded.
 */
export default async function AdminBusinessDetailPage({
  params,
}: {
  params: { businessId: string }
}) {
  const token = await getAccessToken()
  if (!token) {
    return (
      <div>
        <Link href="/businesses" style={{ color: '#9fd0ff' }}>
          ← Businesses
        </Link>
        <PageHeader title="Business" />
        <AdminNotice error={{ status: 0, code: 'NO_SESSION', message: 'no session' }} />
      </div>
    )
  }

  const res = await apiTry<{ data: SupportView }>(
    `/v1/admin/businesses/${params.businessId}/support`,
    token
  )
  if (!res.ok) {
    return (
      <div>
        <Link href="/businesses" style={{ color: '#9fd0ff' }}>
          ← Businesses
        </Link>
        <PageHeader title="Business" />
        <AdminNotice error={res.error} context="This Business does not exist." />
      </div>
    )
  }
  const { business, modules, locations, active_member_count } = res.data.data

  return (
    <div>
      <Link href="/businesses" style={{ color: '#9fd0ff' }}>
        ← Businesses
      </Link>
      <PageHeader
        title={business.display_name}
        subtitle={`${business.business_type ?? 'unset type'} · ${active_member_count} active member${
          active_member_count === 1 ? '' : 's'
        }`}
        action={
          <Link href="/audit" style={{ color: '#9fd0ff' }}>
            Audit trail →
          </Link>
        }
      />

      <div style={{ display: 'flex', gap: '0.6rem', flexWrap: 'wrap', marginBottom: '1.5rem' }}>
        <Pill value={business.state} />
        <Pill value={business.status} />
        <span style={{ opacity: 0.7 }}>{business.visibility}</span>
      </div>

      <dl style={{ display: 'grid', gridTemplateColumns: 'max-content 1fr', gap: '0.35rem 1rem', maxWidth: '40rem' }}>
        <dt style={{ opacity: 0.6 }}>Business ID</dt>
        <dd style={{ ...MONO, margin: 0 }}>{business.id}</dd>
        <dt style={{ opacity: 0.6 }}>Slug</dt>
        <dd style={{ ...MONO, margin: 0 }}>{business.slug}</dd>
        <dt style={{ opacity: 0.6 }}>Primary owner</dt>
        <dd style={{ ...MONO, margin: 0 }}>{business.primary_owner_identity_id ?? '—'}</dd>
        <dt style={{ opacity: 0.6 }}>Created</dt>
        <dd style={{ margin: 0 }}>
          {business.created_at ? new Date(business.created_at).toLocaleString() : '—'}
        </dd>
      </dl>

      <section style={{ marginTop: '2rem' }}>
        <h2 style={{ fontSize: '1.15rem' }}>Modules</h2>
        <div style={{ overflowX: 'auto' }}>
          <table style={TABLE}>
            <thead>
              <tr>
                <th style={TH}>Module</th>
                <th style={TH}>Activation state</th>
                <th style={TH}>Activated</th>
              </tr>
            </thead>
            <tbody>
              {modules.map((m) => (
                <tr key={m.module_id} style={ROW}>
                  <td style={{ ...TD, ...MONO }}>{m.module_id}</td>
                  <td style={TD}>
                    <Pill value={m.activation_state} />
                  </td>
                  <td style={TD}>
                    {m.activated_at ? new Date(m.activated_at).toLocaleDateString() : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {modules.length === 0 ? (
          <p style={{ opacity: 0.7 }}>No optional modules enabled.</p>
        ) : null}
      </section>

      <section style={{ marginTop: '2rem' }}>
        <h2 style={{ fontSize: '1.15rem' }}>Locations</h2>
        <ul style={{ lineHeight: 1.8 }}>
          {locations.map((loc) => (
            <li key={loc.id}>
              {loc.name}
              {loc.is_primary ? ' · primary' : ''} · <Pill value={loc.status} />
            </li>
          ))}
        </ul>
        {locations.length === 0 ? <p style={{ opacity: 0.7 }}>No locations.</p> : null}
      </section>
    </div>
  )
}
