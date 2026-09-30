import Link from 'next/link'
import { redirect } from 'next/navigation'
import { revalidatePath } from 'next/cache'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiPost, apiSend, apiTry } from '@/lib/api'
import { Card, EmptyState, GateNotice, PageHeader, Section, StatusPill } from '@/components/ui'

export const dynamic = 'force-dynamic'

type Resource = {
  id: string; location_id: string; resource_type: string; name: string; allocation_mode: 'exclusive' | 'pooled'
  capacity: number; max_party_size: number | null; buffer_after_minutes: number; granularity: string; is_active: boolean
  version: number
}

/**
 * What customers book time on: tables, rooms, chairs, studios, courts, halls,
 * vehicles. The booking engine hands a free one to a guest who does not pick
 * (tables to table bookings, rooms to stays) and never gives one away twice.
 */
const KINDS: Record<string, { label: string; plural: string; mode: 'exclusive' | 'pooled'; granularity: string; seats: string; help: string }> = {
  table: { label: 'Table', plural: 'Tables', mode: 'exclusive', granularity: 'slot', seats: 'Seats', help: 'Given to table bookings that fit.' },
  room: { label: 'Room', plural: 'Rooms', mode: 'exclusive', granularity: 'date_range', seats: 'Guests', help: 'Given to stays by the night.' },
  chair: { label: 'Chair or treatment room', plural: 'Chairs & treatment rooms', mode: 'exclusive', granularity: 'slot', seats: 'People', help: 'Held with each appointment.' },
  studio: { label: 'Studio (shared places)', plural: 'Studios', mode: 'pooled', granularity: 'slot', seats: 'Places', help: 'Several people at once, up to its places.' },
  court: { label: 'Court or bay', plural: 'Courts & bays', mode: 'exclusive', granularity: 'slot', seats: 'Players', help: 'Booked by the slot.' },
  hall: { label: 'Hall or lawn', plural: 'Halls & lawns', mode: 'exclusive', granularity: 'date_range', seats: 'Guests', help: 'Booked for event dates.' },
  vehicle: { label: 'Vehicle or equipment', plural: 'Vehicles & equipment', mode: 'exclusive', granularity: 'slot', seats: 'People', help: 'Hired for a time range.' },
}

export default async function ResourcesPage({ params }: { params: { businessId: string } }) {
  const token = await getAccessToken()
  if (!token) redirect('/login')
  const b = params.businessId
  const base = `/v1/platform/businesses/${b}`
  const here = `/b/${b}/bookings/resources`
  const [resRes, locRes] = await Promise.all([
    apiTry<{ data: { resources: Resource[] } }>(`${base}/bookings/resources?include_inactive=true`, token),
    apiTry<{ data: { id: string; name: string }[] }>(`${base}/locations`, token),
  ])
  const header = <PageHeader title="Tables, rooms & equipment" breadcrumb={<Link href={`/b/${b}/bookings`}>← Bookings</Link>}
    subtitle="What customers book time on. A guest who does not choose is given a free one that fits." />
  if (!resRes.ok) return <div className="bos-page">{header}<GateNotice error={resRes.error} businessId={b} moduleLabel="Bookings" /></div>
  const resources = resRes.data.data.resources ?? []
  const locations = locRes.ok ? locRes.data.data : []
  const placeName = (id: string) => locations.find((l) => l.id === id)?.name ?? ''

  async function add(formData: FormData) {
    'use server'
    const access = await getAccessToken()
    if (!access) throw new Error('Unauthorized')
    const kind = KINDS[String(formData.get('kind'))] ?? KINDS.table
    const size = Number(formData.get('size') || 1)
    await apiPost(`${base}/bookings/resources`, {
      location_id: String(formData.get('location_id')), resource_type: String(formData.get('kind')),
      name: String(formData.get('name')), allocation_mode: kind.mode, granularity: kind.granularity,
      capacity: kind.mode === 'pooled' ? size : 1, max_party_size: kind.mode === 'pooled' ? null : size,
      buffer_after_minutes: Number(formData.get('buffer') || 0),
    }, access)
    revalidatePath(here)
  }
  async function toggle(formData: FormData) {
    'use server'
    const access = await getAccessToken()
    if (!access) throw new Error('Unauthorized')
    await apiSend(`${base}/bookings/resources/${String(formData.get('id'))}`, access, 'PATCH',
      { is_active: formData.get('active') !== 'true' })
    revalidatePath(here)
  }

  const groups = Object.entries(KINDS).map(([key, k]) => [key, k, resources.filter((r) => r.resource_type === key)] as const)
  const other = resources.filter((r) => !(r.resource_type in KINDS))

  return (
    <div className="bos-page">
      {header}
      {!resources.length ? (
        <EmptyState title="Nothing set up yet">Add your tables, rooms or chairs so bookings can hold them.</EmptyState>
      ) : null}
      {groups.filter(([, , rows]) => rows.length).map(([key, k, rows]) => (
        <Section key={key} title={k.plural}>
          <Card>
            <ul style={{ margin: 0 }}>
              {rows.map((r) => (
                <li key={r.id} style={{ display: 'flex', gap: '0.6rem', alignItems: 'center', flexWrap: 'wrap', padding: '0.25rem 0' }}>
                  <strong>{r.name}</strong>
                  <span>{r.allocation_mode === 'pooled' ? `${r.capacity} places` : r.max_party_size ? `${k.seats.toLowerCase()} ${r.max_party_size}` : ''}</span>
                  {r.buffer_after_minutes ? <span>· {r.buffer_after_minutes} min to reset</span> : null}
                  {locations.length > 1 ? <span>· {placeName(r.location_id)}</span> : null}
                  <StatusPill value={r.is_active ? 'Taking bookings' : 'Paused'} tone={r.is_active ? 'good' : 'neutral'} />
                  <form action={toggle} style={{ display: 'inline' }}>
                    <input type="hidden" name="id" value={r.id} /><input type="hidden" name="active" value={String(r.is_active)} />
                    <button type="submit" className="btn-quiet">{r.is_active ? 'Pause' : 'Resume'}</button>
                  </form>
                </li>
              ))}
            </ul>
            <p style={{ margin: '0.4rem 0 0', color: 'var(--color-muted)', fontSize: '0.85rem' }}>{k.help}</p>
          </Card>
        </Section>
      ))}
      {other.length ? (
        <Section title="Other">
          <Card><ul style={{ margin: 0 }}>{other.map((r) => <li key={r.id}>{r.name} · {r.resource_type}</li>)}</ul></Card>
        </Section>
      ) : null}

      <Section title="Add">
        <Card>
          <form key={`add-${resources.length}`} action={add} style={{ display: 'grid', gap: '0.6rem', gridTemplateColumns: 'repeat(auto-fit, minmax(11rem, 1fr))', alignItems: 'end' }}>
            <label>Kind
              <select name="kind" defaultValue="table">
                {Object.entries(KINDS).map(([key, k]) => <option key={key} value={key}>{k.label}</option>)}
              </select>
            </label>
            <label>Name<input name="name" required placeholder="Table 4, Room 101…" maxLength={80} /></label>
            <label>Seats / guests / places<input name="size" type="number" min={1} max={500} defaultValue={4} required /></label>
            <label>Minutes to reset after<input name="buffer" type="number" min={0} max={240} defaultValue={0} /></label>
            {locations.length > 1 ? (
              <label>Place
                <select name="location_id">{locations.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}</select>
              </label>
            ) : <input type="hidden" name="location_id" value={locations[0]?.id ?? ''} />}
            <button type="submit" className="btn">Add</button>
          </form>
        </Card>
      </Section>
    </div>
  )
}
