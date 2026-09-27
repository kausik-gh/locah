'use server'

import { revalidatePath } from 'next/cache'
import { sendJson, type ActionResult } from '@/lib/server-send'

export async function saveOffering(
  businessId: string,
  offeringId: string | null,
  body: Record<string, unknown>,
): Promise<ActionResult<{ id: string }>> {
  const r = offeringId
    ? await sendJson<{ id: string }>(`/v1/platform/businesses/${businessId}/products/${offeringId}`, 'PATCH', body)
    : await sendJson<{ id: string }>(`/v1/platform/businesses/${businessId}/products`, 'POST', body)
  if (r.ok) {
    revalidatePath(`/b/${businessId}/offerings`)
    if (offeringId) revalidatePath(`/b/${businessId}/offerings/${offeringId}`)
  }
  return r
}

export async function makeVariants(businessId: string, offeringId: string): Promise<ActionResult> {
  const r = await sendJson(`/v1/platform/businesses/${businessId}/products/${offeringId}/variants/matrix`, 'POST')
  if (r.ok) revalidatePath(`/b/${businessId}/offerings/${offeringId}`)
  return r
}

export async function setArchived(businessId: string, offeringId: string, archived: boolean): Promise<ActionResult> {
  const r = await sendJson(
    `/v1/platform/businesses/${businessId}/products/${offeringId}/${archived ? 'archive' : 'restore'}`,
    'POST',
  )
  if (r.ok) revalidatePath(`/b/${businessId}/offerings`)
  return r
}
