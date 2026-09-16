import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import { DataTable, EmptyState, GateNotice, PageHeader, Section, StatusPill } from '@/components/ui'
import { createWorkforceMember } from './actions'

export const dynamic = 'force-dynamic'

/** Doc 11 §4.2 Workforce — people/providers list (no HR/payroll depth). */
export default async function WorkforcePage({
  params,
}: {
  params: { businessId: string }
}) {
  const token = await getAccessToken()
  if (!token) redirect('/login')
  const base = `/b/${params.businessId}`
  const [membersRes, locationsRes] = await Promise.all([
    apiTry<{ data: Array<Record<string, unknown>> }>(
      `/v1/platform/businesses/${params.businessId}/workforce/members`,
      token
    ),
    apiTry<{ data: Array<Record<string, unknown>> }>(
      `/v1/platform/businesses/${params.businessId}/locations`,
      token
    ),
  ])
  if (!membersRes.ok) {
    return (
      <div>
        <PageHeader title="Workforce" />
        <GateNotice error={membersRes.error} businessId={params.businessId} moduleLabel="Workforce" />
      </div>
    )
  }
  const members = membersRes.data.data || []
  const locations = locationsRes.ok ? locationsRes.data.data || [] : []
  const primary = locations.find((l) => l.is_primary) || locations[0]

  async function createMember(formData: FormData) {
    'use server'
    const locationId = String(formData.get('location_id') || primary?.id || '')
    await createWorkforceMember(params.businessId, {
      display_name: String(formData.get('display_name') || '').trim(),
      designation: String(formData.get('designation') || '') || null,
      location_ids: locationId ? [locationId] : [],
      primary_location_id: locationId || null,
    })
  }

  return (
    <div>
      <PageHeader
        title="Workforce"
        subtitle="Providers available for bookings. Linking a provider to a platform identity never grants Workspace access."
      />

      <DataTable
        rows={members}
        rowKey={(m) => String(m.id)}
        columns={[
          {
            key: 'name',
            header: 'Name',
            render: (m) => (
              <Link href={`${base}/workforce/${m.id}`}>{String(m.display_name)}</Link>
            ),
          },
          { key: 'status', header: 'Status', render: (m) => <StatusPill value={String(m.status)} /> },
          {
            key: 'identity',
            header: 'Identity linked',
            render: (m) => (
              <span style={{ color: 'var(--color-muted)' }}>
                {m.identity_id ? 'Yes — no Workspace grant' : 'No'}
              </span>
            ),
          },
        ]}
        empty={<EmptyState title="No providers yet">Add one below to make it bookable.</EmptyState>}
      />

      <Section title="Add a provider">
        <form action={createMember} style={{ display: 'flex', gap: '0.6rem', flexWrap: 'wrap', maxWidth: '44rem' }}>
          <input name="display_name" placeholder="Display name" required />
          <input name="designation" placeholder="Designation" />
          <select name="location_id" defaultValue={String(primary?.id || '')}>
            {locations.map((l) => (
              <option key={String(l.id)} value={String(l.id)}>
                {String(l.name)}
              </option>
            ))}
          </select>
          <button type="submit">Add provider</button>
        </form>
      </Section>
    </div>
  )
}
