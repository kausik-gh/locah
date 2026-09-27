'use server'

import { revalidatePath } from 'next/cache'
import { sendJson, type ActionResult } from '@/lib/server-send'

const base = (b: string) => `/v1/platform/businesses/${b}/pos`

export async function saveCounter(businessId: string, body: Record<string, unknown>): Promise<ActionResult> {
  const r = await sendJson(`${base(businessId)}/settings`, 'PUT', body)
  if (r.ok) revalidatePath(`/b/${businessId}/settings/counter`)
  return r
}

export async function setPin(businessId: string, pin: string): Promise<ActionResult> {
  return sendJson(`${base(businessId)}/pin`, 'PUT', { pin })
}

export async function verifyUpi(businessId: string, paymentId: string, received: boolean): Promise<ActionResult> {
  const r = await sendJson(`${base(businessId)}/payments/${paymentId}/verify`, 'POST', { received })
  if (r.ok) revalidatePath(`/b/${businessId}/settings/counter`)
  return r
}

export async function giveInStoreCode(businessId: string, offeringId: string): Promise<ActionResult<{ barcode: string }>> {
  const r = await sendJson<{ barcode: string }>(`${base(businessId)}/in-store-code/${offeringId}`, 'POST')
  if (r.ok) revalidatePath(`/b/${businessId}/offerings/${offeringId}`)
  return r
}
