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

export async function markRead(formData: FormData) {
  const businessId = String(formData.get('businessId'))
  const notificationId = String(formData.get('notificationId'))
  await send(
    `/v1/platform/businesses/${businessId}/notifications/${notificationId}/read`,
    'POST'
  )
  revalidatePath(`/b/${businessId}/notifications`)
}

export async function markAllRead(formData: FormData) {
  const businessId = String(formData.get('businessId'))
  await send(`/v1/platform/businesses/${businessId}/notifications/read-all`, 'POST')
  revalidatePath(`/b/${businessId}/notifications`)
}

export async function setPreference(formData: FormData) {
  const businessId = String(formData.get('businessId'))
  await send(`/v1/platform/businesses/${businessId}/notification-preferences`, 'PUT', {
    category: String(formData.get('category')),
    in_app_enabled: formData.get('in_app_enabled') === 'on',
  })
  revalidatePath(`/b/${businessId}/notifications`)
}
