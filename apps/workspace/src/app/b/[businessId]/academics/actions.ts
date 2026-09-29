'use server'

import { revalidatePath } from 'next/cache'
import { redirect } from 'next/navigation'
import { platformUrl } from '@platform/config'
import { getAccessToken } from '@/lib/supabase/access-token'

async function post(businessId: string, path: string, body: unknown) {
  const token = await getAccessToken()
  if (!token) redirect('/login')
  const response = await fetch(`${platformUrl('api')}/v1/b/${businessId}/academics${path}`, {
    method: 'POST', cache: 'no-store',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!response.ok) {
    const result = await response.json().catch(() => null)
    throw new Error(result?.error?.message || `Academic update failed (${response.status})`)
  }
  return response.json()
}

const value = (form: FormData, key: string) => String(form.get(key) || '').trim() || null

export async function createCourse(form: FormData): Promise<void> {
  const b = String(form.get('businessId'))
  await post(b, '/courses', { title: value(form, 'title'), description: value(form, 'description') })
  revalidatePath(`/b/${b}/academics`)
}

export async function createBatch(form: FormData): Promise<void> {
  const b = String(form.get('businessId'))
  const result = await post(b, '/batches', {
    course_id: value(form, 'course_id'), name: value(form, 'name'),
    teacher_member_id: value(form, 'teacher_member_id'),
    location_id: value(form, 'location_id'), room: value(form, 'room'),
    meeting_url: value(form, 'meeting_url'),
    starts_on: value(form, 'starts_on'), ends_on: value(form, 'ends_on'),
    capacity: value(form, 'capacity') ? Number(form.get('capacity')) : null,
  })
  revalidatePath(`/b/${b}/academics`)
  redirect(`/b/${b}/academics/${result.data.id}`)
}

export async function addSession(form: FormData): Promise<void> {
  const b = String(form.get('businessId'))
  const batch = String(form.get('batchId'))
  await post(b, `/batches/${batch}/sessions`, {
    starts_at: new Date(`${String(form.get('starts_at'))}:00+05:30`).toISOString(),
    ends_at: new Date(`${String(form.get('ends_at'))}:00+05:30`).toISOString(),
    topic: value(form, 'topic'), meeting_url: value(form, 'meeting_url'),
  })
  revalidatePath(`/b/${b}/academics/${batch}`)
}

export async function enrolStudent(form: FormData): Promise<void> {
  const b = String(form.get('businessId'))
  const batch = String(form.get('batchId'))
  await post(b, `/batches/${batch}/enrolments`, {
    student_contact_id: value(form, 'student_contact_id'),
    guardian_contact_id: value(form, 'guardian_contact_id'),
    is_minor: form.get('is_minor') === 'on',
  })
  revalidatePath(`/b/${b}/academics/${batch}`)
}

export async function createAssessment(form: FormData): Promise<void> {
  const b = String(form.get('businessId'))
  const batch = String(form.get('batchId'))
  await post(b, `/batches/${batch}/assessments`, {
    title: value(form, 'title'), maximum: Number(form.get('maximum')),
  })
  revalidatePath(`/b/${b}/academics/${batch}`)
}

export async function recordResult(form: FormData): Promise<void> {
  const b = String(form.get('businessId'))
  const batch = String(form.get('batchId'))
  await post(b, `/assessments/${String(form.get('assessmentId'))}/results`, {
    enrolment_id: value(form, 'enrolment_id'), marks: Number(form.get('marks')),
    teacher_note: value(form, 'teacher_note'),
  })
  revalidatePath(`/b/${b}/academics/${batch}`)
}

export async function postAnnouncement(form: FormData): Promise<void> {
  const b = String(form.get('businessId'))
  const batch = String(form.get('batchId'))
  await post(b, `/batches/${batch}/announcements`, {
    title: value(form, 'title'), body: value(form, 'body'),
  })
  revalidatePath(`/b/${b}/academics/${batch}`)
}
