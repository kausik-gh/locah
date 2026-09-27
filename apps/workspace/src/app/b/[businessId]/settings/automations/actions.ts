'use server'

import { revalidatePath } from 'next/cache'
import { sendJson, type ActionResult } from '@/lib/server-send'

export async function saveAutomation(
  businessId: string,
  ladderKey: string,
  change: { enabled?: boolean; config?: { disabled_steps: string[]; offset_hours?: Record<string, number> } },
): Promise<ActionResult> {
  const r = await sendJson(
    `/v1/platform/businesses/${businessId}/automations/${encodeURIComponent(ladderKey)}`,
    'PATCH',
    change,
  )
  if (r.ok) revalidatePath(`/b/${businessId}/settings/automations`)
  return r
}
