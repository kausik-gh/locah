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

export async function updateRegionalSettings(formData: FormData) {
  const businessId = String(formData.get('businessId'))
  await send(`/v1/platform/businesses/${businessId}/settings`, 'PATCH', {
    timezone: String(formData.get('timezone')),
    currency: String(formData.get('currency')),
    country: String(formData.get('country')),
    language: String(formData.get('language')),
  })
  revalidatePath(`/b/${businessId}/settings`)
}

export async function updatePreferences(formData: FormData) {
  const businessId = String(formData.get('businessId'))
  await send(`/v1/platform/businesses/${businessId}/preferences`, 'PATCH', {
    date_format: String(formData.get('date_format')),
    time_format: String(formData.get('time_format')),
    measurement_system: String(formData.get('measurement_system')),
  })
  revalidatePath(`/b/${businessId}/settings`)
}
