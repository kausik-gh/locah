import { redirect } from 'next/navigation'
import { apiTry } from '@/lib/api'
import { getAccessToken } from '@/lib/supabase/access-token'
import { Card, PageHeader } from '@/components/ui'

export const dynamic = 'force-dynamic'

type Class = { id: string; topic: string | null; starts_at: string; ends_at: string; meeting_url: string | null }
type Result = { title: string; marks: number; maximum: number; teacher_note: string | null }
type Announcement = { id: string; title: string; body: string; created_at: string }
type Enrolment = { enrolment_id: string; student_name: string; batch_id: string; batch_name: string; course_title: string; sessions: Class[]; results: Result[]; announcements: Announcement[] }

export default async function MyAcademicsPage({ params }: { params: { businessId: string } }) {
  const token = await getAccessToken()
  if (!token) redirect(`/login?destination=${encodeURIComponent(`/my/academics/${params.businessId}`)}`)
  const res = await apiTry<{ data: Enrolment[] }>(`/v1/me/academics/${params.businessId}`, token)
  if (!res.ok) return <div><PageHeader title="Classes & progress" /><p>We could not load your class information right now.</p></div>
  const students = res.data.data || []
  return <main className="bos-page" style={{ maxWidth: '72rem', margin: '0 auto', padding: '1rem' }}>
    <PageHeader title="Classes & progress" subtitle="Only your own enrolments and children linked to your signed-in guardian contact appear here." />
    {!students.length ? <Card><p style={{ margin: 0 }}>No linked classes yet. Ask the academy to connect your account to the guardian or student contact on the enrolment.</p></Card> : null}
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 20rem), 1fr))', gap: '1rem' }}>
      {students.map((student) => <Card key={student.enrolment_id}>
        <h2 style={{ marginTop: 0 }}>{student.student_name}</h2>
        <p>{student.course_title} · {student.batch_name}</p>
        <h3>Coming classes</h3>
        {student.sessions.length ? <ul>{student.sessions.map((lesson) => <li key={lesson.id} style={{ marginBottom: '0.6rem' }}>
          {new Date(lesson.starts_at).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Kolkata' })} IST · {lesson.topic || 'Class'}
          {lesson.meeting_url ? <a href={lesson.meeting_url} style={{ display: 'block' }}>Open class link</a> : null}
        </li>)}</ul> : <p>No classes scheduled yet.</p>}
        <h3>Results</h3>
        {student.results.length ? <ul>{student.results.map((result) => <li key={result.title} style={{ marginBottom: '0.6rem' }}>
          {result.title}: <strong>{result.marks} / {result.maximum}</strong>
          {result.teacher_note ? <span style={{ display: 'block', color: 'var(--color-muted)' }}>{result.teacher_note}</span> : null}
        </li>)}</ul> : <p>No marks published yet.</p>}
        <h3>Notices</h3>
        {student.announcements.length ? <ul>{student.announcements.map((notice) => <li key={notice.id}><strong>{notice.title}</strong><p>{notice.body}</p></li>)}</ul>
          : <p>No notices yet.</p>}
      </Card>)}
    </div>
  </main>
}
