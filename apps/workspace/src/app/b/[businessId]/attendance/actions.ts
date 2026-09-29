'use server'

import { randomUUID } from 'crypto'
import { revalidatePath } from 'next/cache'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { platformUrl } from '@platform/config'

async function submit(businessId: string, path: string, body: unknown): Promise<string | null> {
  const token = await getAccessToken()
  if (!token) return 'Please sign in again.'
  try {
    const res = await fetch(`${platformUrl('api')}/v1/b/${businessId}/attendance${path}`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      cache: 'no-store',
    })
    if (res.ok) return null
    const response = await res.json().catch(() => null)
    return String(response?.error?.message || response?.detail?.message || `Request failed (${res.status})`)
  } catch {
    return 'Attendance is temporarily unreachable.'
  }
}

function finish(businessId: string, error: string | null, path = ''): never {
  revalidatePath(`/b/${businessId}/attendance`)
  redirect(`/b/${businessId}/attendance${path}${error ? `${path ? '&' : '?'}notice=${encodeURIComponent(error)}` : ''}`)
}

export async function checkInMember(formData: FormData): Promise<void> {
  const businessId = String(formData.get('businessId'))
  const scanned = String(formData.get('enrolmentId') || '').trim().replace(/^locah:member:/i, '')
  // A membership card carries a short code; Memberships resolves it. A full ID still works.
  const isId = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(scanned)
  const locationId = String(formData.get('locationId') || '')
  const error = await submit(businessId, '/member-checkins', {
    ...(isId ? { enrolment_id: scanned } : { code: scanned }),
    location_id: locationId || null,
    channel: String(formData.get('channel') || 'manual'),
    idempotency_key: String(formData.get('requestKey') || randomUUID()),
  })
  finish(businessId, error, '?view=members')
}

export async function checkInStaff(formData: FormData): Promise<void> {
  const businessId = String(formData.get('businessId'))
  const error = await submit(businessId, '/staff-checkins', {
    member_id: String(formData.get('memberId')),
    location_id: String(formData.get('locationId')),
    idempotency_key: String(formData.get('requestKey') || randomUUID()),
  })
  finish(businessId, error, '?view=staff')
}

export async function checkOut(formData: FormData): Promise<void> {
  const businessId = String(formData.get('businessId'))
  const eventId = String(formData.get('eventId'))
  const error = await submit(businessId, `/events/${eventId}/checkout`, {
    version: Number(formData.get('version')),
  })
  finish(businessId, error)
}

export async function saveClassAttendance(formData: FormData): Promise<void> {
  const businessId = String(formData.get('businessId'))
  const sessionId = String(formData.get('sessionId'))
  const statuses: Record<string, string> = {}
  for (const [name, value] of formData.entries()) {
    if (name.startsWith('status:')) statuses[name.slice(7)] = String(value)
  }
  const error = await submit(businessId, `/sessions/${sessionId}/records`, {
    statuses,
    idempotency_key: String(formData.get('requestKey') || randomUUID()),
  })
  revalidatePath(`/b/${businessId}/attendance`)
  redirect(`/b/${businessId}/attendance/sessions/${sessionId}${error ? `?notice=${encodeURIComponent(error)}` : ''}`)
}

export async function correctClassAttendance(formData: FormData): Promise<void> {
  const businessId = String(formData.get('businessId'))
  const sessionId = String(formData.get('sessionId'))
  const eventId = String(formData.get('eventId'))
  const error = await submit(businessId, `/events/${eventId}/academic-correction`, {
    status: String(formData.get('status')),
    version: Number(formData.get('version')),
    reason: String(formData.get('reason')),
  })
  revalidatePath(`/b/${businessId}/attendance/sessions/${sessionId}`)
  redirect(`/b/${businessId}/attendance/sessions/${sessionId}${error ? `?notice=${encodeURIComponent(error)}` : ''}`)
}
