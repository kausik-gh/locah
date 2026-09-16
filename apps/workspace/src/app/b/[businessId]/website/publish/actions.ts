'use server'

import { redirect } from 'next/navigation'
import { revalidatePath } from 'next/cache'
import { getAccessToken } from '@/lib/supabase/access-token'

export async function publishWebsite(formData: FormData) {
  const token = await getAccessToken()
  if (!token) redirect('/login')
  const businessId = String(formData.get('businessId') || '')
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000'
  await fetch(`${apiUrl}/v1/b/${businessId}/website/publish`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
  })
  revalidatePath(`/b/${businessId}/website`)
  revalidatePath(`/b/${businessId}/website/publish`)
}

export async function generatePreviewToken(formData: FormData) {
  const token = await getAccessToken()
  if (!token) redirect('/login')
  const businessId = String(formData.get('businessId') || '')
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000'
  const res = await fetch(`${apiUrl}/v1/b/${businessId}/website/preview-token`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: 'no-store',
  })
  if (!res.ok) return
  const payload = (await res.json()) as { data: { preview_path: string } }
  const webBase = process.env.NEXT_PUBLIC_WEB_URL || 'http://127.0.0.1:3000'
  redirect(`${webBase}${payload.data.preview_path}`)
}
