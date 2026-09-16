import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import { GateNotice, PageHeader } from '@/components/ModuleState'

export const dynamic = 'force-dynamic'

type Profile = {
  display_name?: string
  tagline?: string | null
  description?: string | null
  contact?: Record<string, unknown>
}

/** CORE-002 Business Profile. */
export default async function BusinessProfilePage({
  params,
}: {
  params: { businessId: string }
}) {
  const token = await getAccessToken()
  if (!token) redirect('/login')

  const res = await apiTry<{ data: Profile }>(
    `/v1/platform/businesses/${params.businessId}/profile`,
    token
  )
  if (!res.ok) {
    return (
      <div>
        <PageHeader title="Business Profile" />
        <GateNotice
          error={res.error}
          businessId={params.businessId}
          moduleLabel="the Business Profile"
        />
      </div>
    )
  }
  const profile = res.data.data

  return (
    <div>
      <PageHeader
        title="Business Profile"
        subtitle="Canonical public facts for your Business."
      />
      <dl style={{ maxWidth: '36rem', lineHeight: 1.6 }}>
        <dt style={{ fontWeight: 700 }}>Display name</dt>
        <dd>{profile.display_name || '—'}</dd>
        <dt style={{ fontWeight: 700, marginTop: '0.75rem' }}>Tagline</dt>
        <dd>{profile.tagline || '—'}</dd>
        <dt style={{ fontWeight: 700, marginTop: '0.75rem' }}>Description</dt>
        <dd>{profile.description || '—'}</dd>
      </dl>
    </div>
  )
}
