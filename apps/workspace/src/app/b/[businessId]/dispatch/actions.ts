'use server'

import { revalidatePath } from 'next/cache'
import { getAccessToken } from '@/lib/supabase/access-token'
import { platformUrl } from '@platform/config'

const apiUrl = platformUrl('api')

async function post(path: string, body: Record<string, unknown>) {
  const token = await getAccessToken()
  if (!token) throw new Error('Unauthorized')
  const res = await fetch(`${apiUrl}${path}`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const json = await res.json().catch(() => ({}))
    throw new Error(json?.detail?.message || json?.error?.message || 'Dispatch update failed')
  }
}

export async function createDispatchJob(formData: FormData) {
  const businessId = String(formData.get('businessId'))
  const dropoffLine = String(formData.get('dropoff') || '').trim()
  await post(`/v1/b/${businessId}/dispatch/jobs`, {
    order_id: String(formData.get('orderId')),
    kind: String(formData.get('kind') || 'delivery'),
    planned_at: String(formData.get('plannedAt') || '') || null,
    dropoff: dropoffLine ? { line: dropoffLine } : null,
  })
  revalidatePath(`/b/${businessId}/dispatch`)
}

export async function assignDispatchJob(formData: FormData) {
  const businessId = String(formData.get('businessId'))
  const jobId = String(formData.get('jobId'))
  await post(`/v1/b/${businessId}/dispatch/jobs/${jobId}/assign`, {
    member_id: String(formData.get('memberId')),
  })
  revalidatePath(`/b/${businessId}/dispatch`)
  revalidatePath(`/b/${businessId}/dispatch/${jobId}`)
  revalidatePath(`/b/${businessId}/crew`)
}

export async function advanceDispatchJob(formData: FormData) {
  const businessId = String(formData.get('businessId'))
  const jobId = String(formData.get('jobId'))
  await post(`/v1/b/${businessId}/dispatch/jobs/${jobId}/status`, {
    status: String(formData.get('status')),
    proof_note: String(formData.get('proof') || '') || null,
    reason: String(formData.get('reason') || '') || null,
  })
  revalidatePath(`/b/${businessId}/dispatch`)
  revalidatePath(`/b/${businessId}/dispatch/${jobId}`)
  revalidatePath(`/b/${businessId}/crew`)
}
