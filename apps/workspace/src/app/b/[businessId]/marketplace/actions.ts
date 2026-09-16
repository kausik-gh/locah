'use server'

import { revalidatePath } from 'next/cache'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'

export async function optInDiscoverable(formData: FormData) {
  const token = await getAccessToken()
  if (!token) redirect('/login')
  const businessId = String(formData.get('businessId') || '')
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000'
  await fetch(`${apiUrl}/v1/b/${businessId}/marketplace/opt-in`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ confirmed: formData.get('confirmed') === 'true' }),
  })
  revalidatePath(`/b/${businessId}/marketplace`)
}

export async function setVisibility(formData: FormData) {
  const token = await getAccessToken()
  if (!token) redirect('/login')
  const businessId = String(formData.get('businessId') || '')
  const visibility = String(formData.get('visibility') || 'private')
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000'
  await fetch(`${apiUrl}/v1/b/${businessId}/marketplace/visibility`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ visibility }),
  })
  revalidatePath(`/b/${businessId}/marketplace`)
}
