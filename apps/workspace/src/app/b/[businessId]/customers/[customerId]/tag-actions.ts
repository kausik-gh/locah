'use server'

import { revalidatePath } from 'next/cache'
import { sendJson, type ActionResult } from '@/lib/server-send'

export async function saveTags(
  businessId: string,
  customerId: string,
  tags: string[],
  version: number,
): Promise<ActionResult<{ tags: string[]; version: number }>> {
  const r = await sendJson<{ tags: string[]; version: number }>(
    `/v1/platform/businesses/${businessId}/customers/${customerId}`,
    'PATCH',
    { tags, version },
  )
  if (r.ok) {
    revalidatePath(`/b/${businessId}/customers/${customerId}`)
    revalidatePath(`/b/${businessId}/customers`)
  }
  return r
}
