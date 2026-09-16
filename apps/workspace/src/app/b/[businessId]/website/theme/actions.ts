'use server'

import { revalidatePath } from 'next/cache'
import { getAccessToken } from '@/lib/supabase/access-token'

export async function saveThemeNav(formData: FormData) {
  const token = await getAccessToken()
  if (!token) return
  const businessId = String(formData.get('businessId') || '')
  const primary = String(formData.get('primary_color') || '')
  const accent = String(formData.get('accent_color') || '')
  let navigation: unknown[] = []
  try {
    navigation = JSON.parse(String(formData.get('navigation_json') || '[]')) as unknown[]
  } catch {
    navigation = []
  }
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000'
  await fetch(`${apiUrl}/v1/b/${businessId}/website/theme`, {
    method: 'PATCH',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      theme: { primary_color: primary, accent_color: accent },
      navigation,
    }),
  })
  revalidatePath(`/b/${businessId}/website/theme`)
}
