import Link from 'next/link'
import { randomUUID } from 'crypto'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import { Card, EmptyState, GateNotice, PageHeader, StatusPill } from '@/components/ui'
import { correctClassAttendance, saveClassAttendance } from '../../actions'

export const dynamic = 'force-dynamic'

type Student = {
  contact_id: string; name: string; status: string; saved: boolean
  event_id: string | null; version: number | null
}
type Roster = { session_id: string; batch_id: string; students: Student[] }

export default async function ClassAttendancePage({ params, searchParams }: {
  params: { businessId: string; sessionId: string }
  searchParams?: { notice?: string }
}) {
  const token = await getAccessToken()
  if (!token) redirect('/login')
  const businessId = params.businessId
  const [rosterRes, contextRes] = await Promise.all([
    apiTry<{ data: Roster }>(`/v1/b/${businessId}/attendance/sessions/${params.sessionId}/roster`, token),
    apiTry<{ data: { permissions: string[] } }>('/v1/me/context', token,
      { 'X-Operating-Context': 'business', 'X-Business-Id': businessId }),
  ])
  if (!rosterRes.ok) return <><PageHeader title="Class attendance" /><GateNotice error={rosterRes.error} businessId={businessId} moduleLabel="Attendance" /></>
  const students = rosterRes.data.data.students
  const allSaved = students.length > 0 && students.every(student => student.saved)
  const canManage = contextRes.ok && contextRes.data.data.permissions.includes('attendance.manage')
  return <div>
    <PageHeader title="Class attendance" subtitle="Everyone starts as present. Change exceptions, then save the class once."
      breadcrumb={<Link href={`/b/${businessId}/attendance?view=classes`}>← Today&apos;s classes</Link>} />
    {searchParams?.notice ? <Card tone="urgent" style={{ marginBottom: '1rem' }}><p role="alert">{searchParams.notice}</p></Card> : null}
    {!students.length ? <EmptyState title="No enrolled students">Only active enrolments in this class appear here.</EmptyState> : null}
    {students.length && !allSaved ? <form action={saveClassAttendance}>
      <input type="hidden" name="businessId" value={businessId} />
      <input type="hidden" name="sessionId" value={params.sessionId} />
      <input type="hidden" name="requestKey" value={randomUUID()} />
      <div style={{ display: 'grid', gap: '.65rem' }}>{students.map(student =>
        <Card key={student.contact_id} style={{ display: 'flex', gap: '.75rem', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap' }}>
          <strong>{student.name}</strong>
          <label><span className="sr-only">{student.name} attendance</span>
            <select name={`status:${student.contact_id}`} defaultValue={student.status} aria-label={`${student.name} attendance`}>
              <option value="present">Present</option><option value="absent">Absent</option>
              <option value="late">Late</option><option value="excused">Excused</option>
            </select>
          </label>
        </Card>)}</div>
      <button type="submit" className="ws-btn ws-btn--primary" style={{ marginTop: '1rem' }}>Save class attendance</button>
    </form> : null}
    {allSaved ? <section><h2>Saved roster</h2><div style={{ display: 'grid', gap: '.65rem' }}>
      {students.map(student => <Card key={student.contact_id} style={{ display: 'flex', gap: '.75rem', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap' }}>
        <strong>{student.name}</strong><StatusPill value={student.status} />
        {canManage && student.event_id && student.version ? <form action={correctClassAttendance} style={{ display: 'flex', gap: '.5rem', flexWrap: 'wrap' }}>
          <input type="hidden" name="businessId" value={businessId} /><input type="hidden" name="sessionId" value={params.sessionId} />
          <input type="hidden" name="eventId" value={student.event_id} /><input type="hidden" name="version" value={student.version} />
          <select name="status" defaultValue={student.status} aria-label={`Correct ${student.name} attendance`}>
            <option value="present">Present</option><option value="absent">Absent</option>
            <option value="late">Late</option><option value="excused">Excused</option>
          </select>
          <input name="reason" required maxLength={1000} placeholder="Correction reason" aria-label="Correction reason" />
          <button type="submit" className="ws-btn">Correct</button>
        </form> : null}
      </Card>)}
    </div></section> : null}
  </div>
}
