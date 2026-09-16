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

export async function adjustStock(formData: FormData) {
  const businessId = String(formData.get('businessId'))
  await send(`/v1/platform/businesses/${businessId}/inventory/adjust`, 'POST', {
    offering_id: String(formData.get('offering_id')),
    location_id: String(formData.get('location_id')),
    quantity_delta: Number(formData.get('quantity_delta')),
    reason: String(formData.get('reason') || 'Manual adjustment'),
  })
  revalidatePath(`/b/${businessId}/inventory`)
}

export async function setOpeningStock(formData: FormData) {
  const businessId = String(formData.get('businessId'))
  await send(`/v1/platform/businesses/${businessId}/inventory/opening-stock`, 'POST', {
    offering_id: String(formData.get('offering_id')),
    location_id: String(formData.get('location_id')),
    quantity: Number(formData.get('quantity')),
  })
  revalidatePath(`/b/${businessId}/inventory`)
}
