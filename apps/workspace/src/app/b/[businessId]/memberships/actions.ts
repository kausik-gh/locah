'use server'

import { revalidatePath } from 'next/cache'
import { getAccessToken } from '@/lib/supabase/access-token'

const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000'

async function send(path: string, method: string, body?: unknown) {
  const token = await getAccessToken()
  if (!token) throw new Error('Unauthorized')
  const res = await fetch(`${apiUrl}${path}`, {
    method,
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`${method} ${path} failed: ${res.status} ${await res.text()}`)
  return res.json()
}

export async function createPlan(formData: FormData) {
  const businessId = String(formData.get('businessId'))
  await send(`/v1/platform/businesses/${businessId}/membership-plans`, 'POST', {
    name: String(formData.get('name')),
    description: formData.get('description') ? String(formData.get('description')) : undefined,
    price_amount: Number(formData.get('price_amount') || 0),
    duration_days: Number(formData.get('duration_days')),
    // Recurring billing stays closed pending FL-DEC-005; the API rejects it.
    billing_model: 'fixed_duration',
    status: String(formData.get('status') || 'draft'),
    visibility: String(formData.get('visibility') || 'private'),
  })
  revalidatePath(`/b/${businessId}/memberships`)
}

export async function archivePlan(formData: FormData) {
  const businessId = String(formData.get('businessId'))
  const planId = String(formData.get('planId'))
  await send(`/v1/platform/businesses/${businessId}/membership-plans/${planId}/archive`, 'POST')
  revalidatePath(`/b/${businessId}/memberships`)
}

export async function transitionEnrolment(formData: FormData) {
  const businessId = String(formData.get('businessId'))
  const enrolmentId = String(formData.get('enrolmentId'))
  const action = String(formData.get('action'))
  const reason = formData.get('reason') ? String(formData.get('reason')) : undefined
  await send(
    `/v1/platform/businesses/${businessId}/membership-enrolments/${enrolmentId}/${action}`,
    'POST',
    { reason }
  )
  revalidatePath(`/b/${businessId}/memberships`)
}
