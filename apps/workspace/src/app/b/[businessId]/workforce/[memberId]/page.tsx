import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry, apiPost } from '@/lib/api'
import { GateNotice, PageHeader } from '@/components/ModuleState'
import { deactivateWorkforceMember } from '../actions'

export const dynamic = 'force-dynamic'

export default async function WorkforceMemberPage({
  params,
}: {
  params: { businessId: string; memberId: string }
}) {
  const token = await getAccessToken()
  if (!token) redirect('/login')
  const [memberRes, offeringsRes, locationsRes] = await Promise.all([
    apiTry<{ data: Record<string, unknown> }>(
      `/v1/platform/businesses/${params.businessId}/workforce/members/${params.memberId}`,
      token
    ),
    apiTry<{ data: Array<Record<string, unknown>> }>(
      `/v1/platform/businesses/${params.businessId}/products`,
      token
    ),
    apiTry<{ data: Array<Record<string, unknown>> }>(
      `/v1/platform/businesses/${params.businessId}/locations`,
      token
    ),
  ])
  if (!memberRes.ok) {
    return (
      <div>
        <Link href={`/b/${params.businessId}/workforce`}>← Workforce</Link>
        <PageHeader title="Provider" />
        <GateNotice error={memberRes.error} businessId={params.businessId} moduleLabel="Workforce" />
      </div>
    )
  }
  const m = memberRes.data.data
  const offerings = offeringsRes.ok ? offeringsRes.data.data || [] : []
  const locations = locationsRes.ok ? locationsRes.data.data || [] : []

  async function assignLocation(formData: FormData) {
    'use server'
    const access = await getAccessToken()
    if (!access) throw new Error('Unauthorized')
    await apiPost(
      `/v1/platform/businesses/${params.businessId}/workforce/members/${params.memberId}/locations`,
      { location_id: String(formData.get('location_id')), is_primary: true },
      access
    )
  }

  async function associateService(formData: FormData) {
    'use server'
    const access = await getAccessToken()
    if (!access) throw new Error('Unauthorized')
    await apiPost(
      `/v1/platform/businesses/${params.businessId}/workforce/members/${params.memberId}/services`,
      { offering_id: String(formData.get('offering_id')) },
      access
    )
  }

  async function setAvailability(formData: FormData) {
    'use server'
    const access = await getAccessToken()
    if (!access) throw new Error('Unauthorized')
    await apiPost(
      `/v1/platform/businesses/${params.businessId}/workforce/members/${params.memberId}/availability`,
      {
        weekday: Number(formData.get('weekday')),
        start_time: String(formData.get('start_time')),
        end_time: String(formData.get('end_time')),
        is_available: true,
      },
      access
    )
  }

  async function deactivate() {
    'use server'
    await deactivateWorkforceMember(params.businessId, params.memberId)
  }

  return (
    <div>
      <p>
        <Link href={`/b/${params.businessId}/workforce`}>← Workforce</Link>
      </p>
      <h1>{String(m.display_name)}</h1>
      <p>
        {String(m.designation || 'Provider')} · {String(m.status)} · grants_workspace_access=
        {String(m.grants_workspace_access)}
      </p>

      <section style={{ marginTop: '1.5rem' }}>
        <h2 >Location applicability</h2>
        <ul>
          {((m.locations as Array<Record<string, unknown>>) || []).map((l) => (
            <li key={String(l.location_id)}>{String(l.location_id)}</li>
          ))}
        </ul>
        <form action={assignLocation} style={{ display: 'flex', gap: 8 }}>
          <select name="location_id">
            {locations.map((l) => (
              <option key={String(l.id)} value={String(l.id)}>
                {String(l.name)}
              </option>
            ))}
          </select>
          <button type="submit">Assign location</button>
        </form>
      </section>

      <section style={{ marginTop: '1.5rem' }}>
        <h2 >Service association</h2>
        <ul>
          {((m.services as Array<Record<string, unknown>>) || []).map((s) => (
            <li key={String(s.offering_id)}>{String(s.offering_id)}</li>
          ))}
        </ul>
        <form action={associateService} style={{ display: 'flex', gap: 8 }}>
          <select name="offering_id">
            {offerings.map((o) => (
              <option key={String(o.id)} value={String(o.id)}>
                {String(o.title)}
              </option>
            ))}
          </select>
          <button type="submit">Associate service</button>
        </form>
      </section>

      <section style={{ marginTop: '1.5rem' }}>
        <h2 >Schedules / availability</h2>
        <ul>
          {((m.availability as Array<Record<string, unknown>>) || []).map((a) => (
            <li key={String(a.id)}>
              weekday {String(a.weekday)} · {String(a.start_time)}–{String(a.end_time)}
            </li>
          ))}
        </ul>
        <form action={setAvailability} style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <input name="weekday" type="number" min={0} max={6} defaultValue={1} />
          <input name="start_time" defaultValue="09:00" />
          <input name="end_time" defaultValue="17:00" />
          <button type="submit">Add availability</button>
        </form>
      </section>

      <form action={deactivate} style={{ marginTop: '2rem' }}>
        <button type="submit">Deactivate provider</button>
      </form>
    </div>
  )
}
