import Link from 'next/link'
import { redirect } from 'next/navigation'
import { revalidatePath } from 'next/cache'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry, apiPost, apiSend } from '@/lib/api'
import { Card, GateNotice, PageHeader, Section, StatusPill } from '@/components/ui'
import { deactivateWorkforceMember } from '../actions'

export const dynamic = 'force-dynamic'

type Slot = {
  id: string
  location_id: string | null
  weekday: number | null
  exception_date: string | null
  start_time: string
  end_time: string
  is_available: boolean
}
type Member = {
  display_name: string
  designation: string | null
  status: string
  locations: { location_id: string; is_primary: boolean }[]
  services: { offering_id: string }[]
  availability: Slot[]
}
type Named = { id: string; name?: string; title?: string; offering_type?: string }

// Weekly hours count days as Python does: 0 is Monday.
const DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
const hhmm = (t: string) => t.slice(0, 5)
const BOOKABLE = new Set(['service', 'class_session', 'accommodation', 'rental'])

export default async function WorkforceMemberPage({
  params,
}: {
  params: { businessId: string; memberId: string }
}) {
  const token = await getAccessToken()
  if (!token) redirect('/login')
  const b = params.businessId
  const memberPath = `/v1/platform/businesses/${b}/workforce/members/${params.memberId}`
  const [memberRes, offeringsRes, locationsRes] = await Promise.all([
    apiTry<{ data: Member }>(memberPath, token),
    apiTry<{ data: Named[] }>(`/v1/platform/businesses/${b}/products`, token),
    apiTry<{ data: Named[] }>(`/v1/platform/businesses/${b}/locations`, token),
  ])
  if (!memberRes.ok) {
    return (
      <div>
        <PageHeader title="Team member" breadcrumb={<Link href={`/b/${b}/workforce`}>← Workforce</Link>} />
        <GateNotice error={memberRes.error} businessId={b} moduleLabel="Workforce" />
      </div>
    )
  }
  const m = memberRes.data.data
  const offerings = offeringsRes.ok ? offeringsRes.data.data || [] : []
  const locations = locationsRes.ok ? locationsRes.data.data || [] : []
  const placeName = (id: string | null) => (id ? locations.find((l) => l.id === id)?.name || 'Another place' : 'Any place')
  const serviceName = (id: string) => offerings.find((o) => o.id === id)?.title || 'A service'
  const weekly = m.availability
    .filter((a) => a.weekday !== null)
    .sort((x, y) => (x.weekday! - y.weekday!) || x.start_time.localeCompare(y.start_time))
  const dated = m.availability
    .filter((a) => a.exception_date)
    .sort((x, y) => x.exception_date!.localeCompare(y.exception_date!) || x.start_time.localeCompare(y.start_time))
  const today = new Date().toISOString().slice(0, 10)

  const here = `/b/${b}/workforce/${params.memberId}`

  async function assignLocation(formData: FormData) {
    'use server'
    const access = await getAccessToken()
    if (!access) throw new Error('Unauthorized')
    await apiPost(`${memberPath}/locations`, { location_id: String(formData.get('location_id')), is_primary: true }, access)
    revalidatePath(here)
  }

  async function associateService(formData: FormData) {
    'use server'
    const access = await getAccessToken()
    if (!access) throw new Error('Unauthorized')
    await apiPost(`${memberPath}/services`, { offering_id: String(formData.get('offering_id')) }, access)
    revalidatePath(here)
  }

  async function addWeekly(formData: FormData) {
    'use server'
    const access = await getAccessToken()
    if (!access) throw new Error('Unauthorized')
    await apiPost(
      `${memberPath}/availability`,
      {
        weekday: Number(formData.get('weekday')),
        start_time: String(formData.get('start_time')),
        end_time: String(formData.get('end_time')),
        is_available: formData.get('kind') !== 'break',
      },
      access
    )
    revalidatePath(here)
  }

  async function addDated(formData: FormData) {
    'use server'
    const access = await getAccessToken()
    if (!access) throw new Error('Unauthorized')
    const away = formData.get('kind') !== 'extra'
    const allDay = away && formData.get('all_day') === 'on'
    await apiPost(
      `${memberPath}/availability`,
      {
        exception_date: String(formData.get('exception_date')),
        start_time: allDay ? '00:00' : String(formData.get('start_time')),
        end_time: allDay ? '23:59' : String(formData.get('end_time')),
        is_available: !away,
      },
      access
    )
    revalidatePath(here)
  }

  async function remove(formData: FormData) {
    'use server'
    const access = await getAccessToken()
    if (!access) throw new Error('Unauthorized')
    await apiSend(`${memberPath}/availability/${String(formData.get('id'))}`, access, 'DELETE')
    revalidatePath(here)
  }

  async function deactivate() {
    'use server'
    await deactivateWorkforceMember(b, params.memberId)
  }

  const removeButton = (id: string) => (
    <form action={remove} style={{ display: 'inline' }}>
      <input type="hidden" name="id" value={id} />
      <button type="submit" className="btn-quiet">Remove</button>
    </form>
  )

  return (
    <div className="bos-page">
      <PageHeader
        title={m.display_name}
        breadcrumb={<Link href={`/b/${b}/workforce`}>← Workforce</Link>}
        actions={<StatusPill value={m.status === 'active' ? 'Active' : 'Inactive'} />}
      />
      <p style={{ marginTop: 0 }}>{m.designation || 'Team member'}</p>

      <Section title="Works at">
        <Card>
          <ul>
            {m.locations.map((l) => (
              <li key={l.location_id}>
                {placeName(l.location_id)}
                {l.is_primary ? ' · main' : ''}
              </li>
            ))}
          </ul>
          <form action={assignLocation} style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <select name="location_id" aria-label="Place">
              {locations.map((l) => (
                <option key={l.id} value={l.id}>{l.name}</option>
              ))}
            </select>
            <button type="submit">Add place</button>
          </form>
        </Card>
      </Section>

      <Section title="Does">
        <Card>
          {m.services.length ? (
            <ul>{m.services.map((s) => <li key={s.offering_id}>{serviceName(s.offering_id)}</li>)}</ul>
          ) : (
            <p>No services yet. Customers can book this person only for services listed here.</p>
          )}
          <form action={associateService} style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <select name="offering_id" aria-label="Service">
              {offerings.filter((o) => BOOKABLE.has(String(o.offering_type))).map((o) => (
                <option key={o.id} value={o.id}>{o.title}</option>
              ))}
            </select>
            <button type="submit">Add service</button>
          </form>
        </Card>
      </Section>

      <Section title="Weekly hours">
        <Card>
          {weekly.length ? (
            <ul>
              {weekly.map((a) => (
                <li key={a.id}>
                  {DAYS[a.weekday!]} · {hhmm(a.start_time)}–{hhmm(a.end_time)}
                  {a.is_available ? '' : ' · break'} · {placeName(a.location_id)} {removeButton(a.id)}
                </li>
              ))}
            </ul>
          ) : (
            <p>No hours saved, so bookings are not limited by this person&apos;s hours. Once any are saved, bookings fit inside them.</p>
          )}
          <form action={addWeekly} style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
            <select name="weekday" aria-label="Day" defaultValue="0">
              {DAYS.map((d, i) => <option key={d} value={i}>{d}</option>)}
            </select>
            <input name="start_time" type="time" defaultValue="09:00" aria-label="From" required />
            <input name="end_time" type="time" defaultValue="17:00" aria-label="Until" required />
            <select name="kind" aria-label="Kind" defaultValue="work">
              <option value="work">Working</option>
              <option value="break">Break (not bookable)</option>
            </select>
            <button type="submit">Add hours</button>
          </form>
        </Card>
      </Section>

      <Section title="Time off and one-off hours">
        <Card>
          {dated.length ? (
            <ul>
              {dated.map((a) => (
                <li key={a.id}>
                  {a.exception_date} · {a.is_available ? 'working' : 'away'}{' '}
                  {a.start_time.startsWith('00:00') && a.end_time.startsWith('23:59') ? 'all day' : `${hhmm(a.start_time)}–${hhmm(a.end_time)}`}{' '}
                  {removeButton(a.id)}
                </li>
              ))}
            </ul>
          ) : (
            <p>No leave or one-off hours.</p>
          )}
          <form action={addDated} style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
            <input name="exception_date" type="date" min={today} aria-label="Date" required />
            <select name="kind" aria-label="Kind" defaultValue="away">
              <option value="away">Away</option>
              <option value="extra">Working (instead of the usual hours)</option>
            </select>
            <label><input name="all_day" type="checkbox" defaultChecked /> All day</label>
            <input name="start_time" type="time" defaultValue="09:00" aria-label="From" />
            <input name="end_time" type="time" defaultValue="17:00" aria-label="Until" />
            <button type="submit">Save</button>
          </form>
        </Card>
      </Section>

      {m.status === 'active' ? (
        <form action={deactivate} style={{ marginTop: '2rem' }}>
          <button type="submit">Deactivate</button>
        </form>
      ) : null}
    </div>
  )
}
