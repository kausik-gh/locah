'use server'

import { revalidatePath } from 'next/cache'
import { redirect } from 'next/navigation'
import { platformUrl } from '@platform/config'
import { getAccessToken } from '@/lib/supabase/access-token'

async function send(businessId: string, path: string, body: unknown) {
  const token = await getAccessToken()
  if (!token) redirect('/login')
  const response = await fetch(`${platformUrl('api')}/v1/b/${businessId}/jobs${path}`, {
    method: 'POST', cache: 'no-store',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!response.ok) {
    const result = await response.json().catch(() => null)
    throw new Error(result?.error?.message || `Job update failed (${response.status})`)
  }
  return response.json()
}

function optional(form: FormData, key: string) {
  return String(form.get(key) || '').trim() || null
}

export async function createJob(form: FormData): Promise<void> {
  const businessId = String(form.get('businessId'))
  const result = await send(businessId, '', {
    customer_contact_id: String(form.get('customer_contact_id')),
    title: String(form.get('title') || '').trim(),
    problem: optional(form, 'problem'),
    project_id: optional(form, 'project_id'),
    location_id: optional(form, 'location_id'),
    assigned_member_id: optional(form, 'assigned_member_id'),
    scheduled_at: optional(form, 'scheduled_at') ? new Date(`${String(form.get('scheduled_at'))}:00+05:30`).toISOString() : null,
    asset_description: optional(form, 'asset_description'),
    asset_serial: optional(form, 'asset_serial'),
    priority: String(form.get('priority') || 'normal'),
  })
  revalidatePath(`/b/${businessId}/jobs`)
  redirect(`/b/${businessId}/jobs/${result.data.id}`)
}

export async function assignJob(form: FormData): Promise<void> {
  const businessId = String(form.get('businessId'))
  const jobId = String(form.get('jobId'))
  await send(businessId, `/${jobId}/assign`, { member_id: String(form.get('member_id')) })
  revalidatePath(`/b/${businessId}/jobs/${jobId}`)
}

export async function moveJob(form: FormData): Promise<void> {
  const businessId = String(form.get('businessId'))
  const jobId = String(form.get('jobId'))
  await send(businessId, `/${jobId}/move`, {
    status: String(form.get('status')), version: Number(form.get('version')),
    work_performed: optional(form, 'work_performed'),
    completion_note: optional(form, 'completion_note'),
    approval_note: optional(form, 'approval_note'),
  })
  revalidatePath(`/b/${businessId}/jobs`)
  revalidatePath(`/b/${businessId}/jobs/${jobId}`)
}

export async function consumePart(form: FormData): Promise<void> {
  const businessId = String(form.get('businessId'))
  const jobId = String(form.get('jobId'))
  await send(businessId, `/${jobId}/parts`, {
    inventory_record_id: String(form.get('inventory_record_id')),
    quantity: Number(form.get('quantity')),
    serials: String(form.get('serials') || '').split(/[\n,]/).map((v) => v.trim()).filter(Boolean),
    idempotency_key: String(form.get('idempotency_key')),
  })
  revalidatePath(`/b/${businessId}/jobs/${jobId}`)
}

export async function returnPart(form: FormData): Promise<void> {
  const businessId = String(form.get('businessId'))
  const jobId = String(form.get('jobId'))
  await send(businessId, `/${jobId}/parts/${String(form.get('partId'))}/return`, {
    quantity: Number(form.get('quantity')),
    idempotency_key: String(form.get('idempotency_key')),
  })
  revalidatePath(`/b/${businessId}/jobs/${jobId}`)
}
