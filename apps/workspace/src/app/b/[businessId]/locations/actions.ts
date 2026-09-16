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

export async function createLocation(formData: FormData) {
  const businessId = String(formData.get('businessId'))
  await send(`/v1/platform/businesses/${businessId}/locations`, 'POST', {
    name: String(formData.get('name')),
    timezone: String(formData.get('timezone') || 'Asia/Kolkata'),
    phone: formData.get('phone') ? String(formData.get('phone')) : undefined,
    email: formData.get('email') ? String(formData.get('email')) : undefined,
  })
  revalidatePath(`/b/${businessId}/locations`)
}

export async function updateLocation(formData: FormData) {
  const businessId = String(formData.get('businessId'))
  const locationId = String(formData.get('locationId'))
  await send(`/v1/platform/businesses/${businessId}/locations/${locationId}`, 'PATCH', {
    name: String(formData.get('name')),
    phone: formData.get('phone') ? String(formData.get('phone')) : undefined,
    email: formData.get('email') ? String(formData.get('email')) : undefined,
    notes: formData.get('notes') ? String(formData.get('notes')) : undefined,
  })
  revalidatePath(`/b/${businessId}/locations/${locationId}`)
  revalidatePath(`/b/${businessId}/locations`)
}

export async function locationLifecycle(formData: FormData) {
  const businessId = String(formData.get('businessId'))
  const locationId = String(formData.get('locationId'))
  const action = String(formData.get('action'))
  await send(`/v1/platform/businesses/${businessId}/locations/${locationId}/${action}`, 'POST')
  revalidatePath(`/b/${businessId}/locations/${locationId}`)
  revalidatePath(`/b/${businessId}/locations`)
}
