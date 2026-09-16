'use server'

import { revalidatePath } from 'next/cache'
import { getAccessToken } from '@/lib/supabase/access-token'

const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000'

export async function advanceOrderStatus(formData: FormData) {
  const token = await getAccessToken()
  if (!token) throw new Error('Unauthorized')
  const businessId = String(formData.get('businessId'))
  const orderId = String(formData.get('orderId'))
  const status = String(formData.get('status'))
  const reason = formData.get('reason') ? String(formData.get('reason')) : undefined
  await fetch(`${apiUrl}/v1/platform/businesses/${businessId}/orders/${orderId}/status`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ status, reason }),
  })
  revalidatePath(`/b/${businessId}/orders/${orderId}`)
  revalidatePath(`/b/${businessId}/orders`)
}

export async function cancelOrder(formData: FormData) {
  const token = await getAccessToken()
  if (!token) throw new Error('Unauthorized')
  const businessId = String(formData.get('businessId'))
  const orderId = String(formData.get('orderId'))
  const reason = String(formData.get('reason') || 'Cancelled by Business')
  await fetch(`${apiUrl}/v1/platform/businesses/${businessId}/orders/${orderId}/cancel`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ reason }),
  })
  revalidatePath(`/b/${businessId}/orders/${orderId}`)
  revalidatePath(`/b/${businessId}/orders`)
}
