'use server'

import { revalidatePath } from 'next/cache'
import { sendJson, type ActionResult } from '@/lib/server-send'

export async function saveCap(businessId: string, resource: string, cap: number | null): Promise<ActionResult> {
  const r = await sendJson(
    `/v1/platform/businesses/${businessId}/usage/${encodeURIComponent(resource)}/cap`,
    'PUT',
    { cap },
  )
  if (r.ok) revalidatePath(`/b/${businessId}/settings/usage`)
  return r
}
