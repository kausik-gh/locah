'use server'

import { revalidatePath } from 'next/cache'
import { sendJson, type ActionResult } from '@/lib/server-send'

export async function changeConsent(
  businessId: string,
  customerId: string,
  change: { purpose: string; channel: string; granted: boolean; note?: string },
): Promise<ActionResult> {
  const r = await sendJson(`/v1/platform/businesses/${businessId}/customers/${customerId}/consents`, 'POST', {
    ...change,
    source: 'staff_recorded',
  })
  if (r.ok) revalidatePath(`/b/${businessId}/customers/${customerId}`)
  return r
}
