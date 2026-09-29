'use server'

import { revalidatePath } from 'next/cache'
import { sendJson, type ActionResult } from '@/lib/server-send'

const path = (b: string, c: string) => `/v1/platform/businesses/${b}/customers/${c}`

export async function exportCustomer(businessId: string, customerId: string): Promise<ActionResult<Record<string, unknown>>> {
  return sendJson<Record<string, unknown>>(`${path(businessId, customerId)}/export`, 'GET')
}

export async function eraseCustomer(
  businessId: string,
  customerId: string,
  confirm: string,
  reason: string,
): Promise<ActionResult<{ removed: Record<string, number> }>> {
  const r = await sendJson<{ removed: Record<string, number> }>(`${path(businessId, customerId)}/erase`, 'POST', {
    confirm,
    reason: reason || null,
  })
  if (r.ok) {
    revalidatePath(`/b/${businessId}/customers/${customerId}`)
    revalidatePath(`/b/${businessId}/customers`)
    revalidatePath(`/b/${businessId}`)
  }
  return r
}

export async function declineRequest(businessId: string, customerId: string, requestId: string, reason: string): Promise<ActionResult> {
  const r = await sendJson(`/v1/platform/businesses/${businessId}/customers/privacy-requests/${requestId}/decline`, 'POST', { reason })
  if (r.ok) {
    revalidatePath(`/b/${businessId}/customers/${customerId}`)
    revalidatePath(`/b/${businessId}`)
  }
  return r
}
