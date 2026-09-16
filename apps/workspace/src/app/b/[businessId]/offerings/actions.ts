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

export async function createOffering(formData: FormData) {
  const businessId = String(formData.get('businessId'))
  const price = formData.get('price_amount')
  await send(`/v1/platform/businesses/${businessId}/products`, 'POST', {
    title: String(formData.get('title')),
    description: formData.get('description') ? String(formData.get('description')) : undefined,
    offering_type: String(formData.get('offering_type') || 'product'),
    price_amount: price ? Number(price) : undefined,
    status: String(formData.get('status') || 'draft'),
  })
  revalidatePath(`/b/${businessId}/offerings`)
}

export async function archiveOffering(formData: FormData) {
  const businessId = String(formData.get('businessId'))
  const offeringId = String(formData.get('offeringId'))
  await send(`/v1/platform/businesses/${businessId}/products/${offeringId}/archive`, 'POST')
  revalidatePath(`/b/${businessId}/offerings`)
}

export async function restoreOffering(formData: FormData) {
  const businessId = String(formData.get('businessId'))
  const offeringId = String(formData.get('offeringId'))
  await send(`/v1/platform/businesses/${businessId}/products/${offeringId}/restore`, 'POST')
  revalidatePath(`/b/${businessId}/offerings`)
}
