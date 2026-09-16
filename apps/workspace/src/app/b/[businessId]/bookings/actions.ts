'use server'

import { revalidatePath } from 'next/cache'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiPatch, apiPost } from '@/lib/api'

export async function transitionBooking(
  businessId: string,
  bookingId: string,
  status: string,
  reason?: string
) {
  const token = await getAccessToken()
  if (!token) throw new Error('Unauthorized')
  await apiPost(
    `/v1/platform/businesses/${businessId}/bookings/${bookingId}/status`,
    { status, reason },
    token
  )
  revalidatePath(`/b/${businessId}/bookings`)
  revalidatePath(`/b/${businessId}/bookings/${bookingId}`)
}

export async function updateBookingsPolicy(
  businessId: string,
  payload: Record<string, unknown>
) {
  const token = await getAccessToken()
  if (!token) throw new Error('Unauthorized')
  await apiPatch(
    `/v1/platform/businesses/${businessId}/bookings-policy`,
    payload,
    token
  )
  revalidatePath(`/b/${businessId}/bookings`)
}
