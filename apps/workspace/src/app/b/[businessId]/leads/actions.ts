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

export async function createLead(formData: FormData) {
  const businessId = String(formData.get('businessId'))
  await send(`/v1/platform/businesses/${businessId}/leads`, 'POST', {
    display_name: String(formData.get('display_name')),
    email: formData.get('email') ? String(formData.get('email')) : undefined,
    phone: formData.get('phone') ? String(formData.get('phone')) : undefined,
    message: formData.get('message') ? String(formData.get('message')) : undefined,
    source: 'manual',
  })
  revalidatePath(`/b/${businessId}/leads`)
}

export async function moveLeadStage(formData: FormData) {
  const businessId = String(formData.get('businessId'))
  const leadId = String(formData.get('leadId'))
  const status = String(formData.get('status'))
  const reason = formData.get('reason') ? String(formData.get('reason')) : undefined
  await send(`/v1/platform/businesses/${businessId}/leads/${leadId}/move-stage`, 'POST', {
    status,
    reason,
  })
  revalidatePath(`/b/${businessId}/leads`)
  revalidatePath(`/b/${businessId}/leads/${leadId}`)
}

export async function addLeadNote(formData: FormData) {
  const businessId = String(formData.get('businessId'))
  const leadId = String(formData.get('leadId'))
  await send(`/v1/platform/businesses/${businessId}/leads/${leadId}/notes`, 'POST', {
    body: String(formData.get('body')),
  })
  revalidatePath(`/b/${businessId}/leads/${leadId}`)
}

export async function assignLead(formData: FormData) {
  const businessId = String(formData.get('businessId'))
  const leadId = String(formData.get('leadId'))
  const assignee = String(formData.get('assignee_identity_id') || '')
  await send(`/v1/platform/businesses/${businessId}/leads/${leadId}/assign`, 'POST', {
    assignee_identity_id: assignee || null,
  })
  revalidatePath(`/b/${businessId}/leads/${leadId}`)
}
