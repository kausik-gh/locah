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

export async function createCustomer(formData: FormData) {
  const businessId = String(formData.get('businessId'))
  await send(`/v1/platform/businesses/${businessId}/customers`, 'POST', {
    display_name: String(formData.get('display_name')),
    email: formData.get('email') ? String(formData.get('email')) : undefined,
    phone: formData.get('phone') ? String(formData.get('phone')) : undefined,
  })
  revalidatePath(`/b/${businessId}/customers`)
}

export async function setCustomerState(formData: FormData) {
  const businessId = String(formData.get('businessId'))
  const customerId = String(formData.get('customerId'))
  const action = String(formData.get('action'))
  await send(`/v1/platform/businesses/${businessId}/customers/${customerId}/${action}`, 'POST')
  revalidatePath(`/b/${businessId}/customers`)
  revalidatePath(`/b/${businessId}/customers/${customerId}`)
}

export async function addCustomerNote(formData: FormData) {
  const businessId = String(formData.get('businessId'))
  const customerId = String(formData.get('customerId'))
  await send(`/v1/platform/businesses/${businessId}/customers/${customerId}/notes`, 'POST', {
    body: String(formData.get('body')),
  })
  revalidatePath(`/b/${businessId}/customers/${customerId}`)
}
