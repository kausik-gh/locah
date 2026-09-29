import Link from 'next/link'
import { randomUUID } from 'crypto'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import { Card, EmptyState, GateNotice, PageHeader, StatusPill } from '@/components/ui'
import { checkInMember, checkInStaff, checkOut } from './actions'

export const dynamic = 'force-dynamic'

type Event = {
  id: string; context: string; status: string; source_id: string
  subject_member_id: string | null; subject_contact_id: string | null; subject_name?: string | null
  location_id: string | null; recorded_at: string; version: number
}
type ClassSession = { id: string; batch_name: string; topic: string | null; starts_at: string }
type Options = { member: { id: string; name: string } | null; locations: { id: string; name: string }[] }

const time = (value: string) => new Intl.DateTimeFormat('en-IN', {
  timeZone: 'Asia/Kolkata', hour: 'numeric', minute: '2-digit',
}).format(new Date(value))

export default async function AttendancePage({ params, searchParams }: {
  params: { businessId: string }
  searchParams?: { view?: string; notice?: string }
}) {
  const token = await getAccessToken()
  if (!token) redirect('/login')
  const businessId = params.businessId
  const base = `/v1/b/${businessId}/attendance`
  const [eventRes, optionsRes, sessionsRes, contextRes] = await Promise.all([
    apiTry<{ data: Event[] }>(`${base}/events?today=true`, token),
    apiTry<{ data: Options }>(`${base}/self`, token),
    apiTry<{ data: ClassSession[] }>(`${base}/sessions/today`, token),
    apiTry<{ data: { module_states: Record<string, string> } }>('/v1/me/context', token,
      { 'X-Operating-Context': 'business', 'X-Business-Id': businessId }),
  ])
  if (!eventRes.ok) return <><PageHeader title="Attendance" /><GateNotice error={eventRes.error} businessId={businessId} moduleLabel="Attendance" /></>
  const events = eventRes.data.data || []
  const options = optionsRes.ok ? optionsRes.data.data : { member: null, locations: [] }
  const sessions = sessionsRes.ok ? sessionsRes.data.data || [] : []
  const modules = contextRes.ok ? contextRes.data.data.module_states : {}
  const showAcademics = modules.academics === 'active'
  const showMemberships = modules.memberships === 'active'
  const view = searchParams?.view || 'today'
  const tabs = [
    { id: 'today', label: 'Today' },
    ...(showAcademics ? [{ id: 'classes', label: 'Classes' }] : []),
    ...(showMemberships ? [{ id: 'members', label: 'Member check-in' }] : []),
    { id: 'staff', label: 'My site check-in' },
  ]
  return <div>
    <PageHeader title="Attendance" subtitle="One record of presence across classes, membership visits and staff sites." />
    <nav aria-label="Attendance views" style={{ display: 'flex', flexWrap: 'wrap', gap: '.5rem', marginBottom: '1.5rem' }}>
      {tabs.map(tab => <Link key={tab.id} href={`/b/${businessId}/attendance?view=${tab.id}`}
        aria-current={view === tab.id ? 'page' : undefined}
        style={{ border: '1px solid var(--color-border)', borderRadius: '999px', padding: '.45rem .85rem',
          background: view === tab.id ? 'var(--color-surface)' : 'transparent', textDecoration: 'none' }}>
        {tab.label}
      </Link>)}
    </nav>
    {searchParams?.notice ? <Card tone="urgent" style={{ marginBottom: '1rem' }}><p role="alert">{searchParams.notice}</p></Card> : null}
    {view === 'classes' && showAcademics ? <section>
      <h2>Today&apos;s classes</h2>
      {sessions.length ? <div style={{ display: 'grid', gap: '.75rem' }}>{sessions.map(session =>
        <Card key={session.id} interactive><Link href={`/b/${businessId}/attendance/sessions/${session.id}`}
          style={{ display: 'block', textDecoration: 'none' }}>
          <strong>{session.batch_name}</strong><div>{session.topic || 'Class session'}</div>
          <small>{time(session.starts_at)} IST · Open roster →</small>
        </Link></Card>)}</div> : <EmptyState title="No sessions today">A scheduled class will appear here when Academics is connected.</EmptyState>}
    </section> : null}
    {view === 'members' && showMemberships ? <section style={{ maxWidth: 640 }}>
      <h2>Member check-in</h2>
      <p style={{ color: 'var(--color-muted)' }}>Scan the member&apos;s card or type their code. Memberships decides whether the visit is allowed; a refused visit is never recorded.</p>
      <Card><form action={checkInMember} style={{ display: 'grid', gap: '.8rem' }}>
        <input type="hidden" name="businessId" value={businessId} />
        <input type="hidden" name="requestKey" value={randomUUID()} />
        <label>Member code<input name="enrolmentId" required autoComplete="off" placeholder="Scan or type the code" /></label>
        <label>Location<select name="locationId"><option value="">Business-wide</option>{options.locations.map(location =>
          <option key={location.id} value={location.id}>{location.name}</option>)}</select></label>
        <label>Method<select name="channel"><option value="qr">QR scan</option><option value="manual">Manual</option></select></label>
        <button type="submit" className="ws-btn ws-btn--primary">Check in member</button>
      </form></Card>
    </section> : null}
    {view === 'staff' ? <section style={{ maxWidth: 640 }}>
      <h2>My site check-in</h2>
      <p style={{ color: 'var(--color-muted)' }}>Records presence only. No coordinates were supplied or verified.</p>
      {options.member && options.locations.length ? <Card><form action={checkInStaff} style={{ display: 'grid', gap: '.8rem' }}>
        <input type="hidden" name="businessId" value={businessId} />
        <input type="hidden" name="memberId" value={options.member.id} />
        <input type="hidden" name="requestKey" value={randomUUID()} />
        <strong>{options.member.name}</strong>
        <label>Site<select name="locationId" required>{options.locations.map(location =>
          <option key={location.id} value={location.id}>{location.name}</option>)}</select></label>
        <button type="submit" className="ws-btn ws-btn--primary">Check in at site</button>
      </form></Card> : <EmptyState title="No site check-in available">Your active workforce profile and an accessible location are required.</EmptyState>}
    </section> : null}
    {view === 'today' ? <section>
      <h2>Today&apos;s presence</h2>
      {events.length ? <div style={{ display: 'grid', gap: '.65rem' }}>{events.map(event =>
        <Card key={event.id} style={{ display: 'flex', gap: '1rem', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap' }}>
          <div><strong>{event.context.replace(/_/g, ' ')}</strong><div style={{ color: 'var(--color-muted)', fontSize: '.85rem' }}>
            {time(event.recorded_at)} IST · {event.subject_name || event.subject_member_id || event.subject_contact_id}
          </div></div>
          <div style={{ display: 'flex', gap: '.65rem', alignItems: 'center' }}><StatusPill value={event.status} />
            {event.status === 'checked_in' && (event.context !== 'staff_site' || event.subject_member_id === options.member?.id) ?
              <form action={checkOut}><input type="hidden" name="businessId" value={businessId} />
                <input type="hidden" name="eventId" value={event.id} /><input type="hidden" name="version" value={event.version} />
                <button type="submit" className="ws-btn">Check out</button></form> : null}
          </div>
        </Card>)}</div> : <EmptyState title="No attendance recorded today">Check-ins and saved class rosters will appear here.</EmptyState>}
    </section> : null}
  </div>
}
