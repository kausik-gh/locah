'use server'

import { revalidatePath } from 'next/cache'
import { sendJson, type ActionResult } from '@/lib/server-send'

export type Rule = Record<string, string | number>
export type Preview = {
  count: number
  whatsapp_offers: number
  members: { id: string; display_name: string; phone: string | null }[]
  rule_words: string[]
}

export async function previewSegment(businessId: string, rules: Rule[]): Promise<ActionResult<Preview>> {
  return sendJson<Preview>(`/v1/platform/businesses/${businessId}/customers/segments/preview`, 'POST', { rules })
}

export async function saveSegment(businessId: string, name: string, rules: Rule[]): Promise<ActionResult<{ id: string }>> {
  const r = await sendJson<{ id: string }>(`/v1/platform/businesses/${businessId}/customers/segments`, 'POST', { name, rules })
  if (r.ok) revalidatePath(`/b/${businessId}/customers/segments`)
  return r
}

export async function archiveSegment(businessId: string, segmentId: string): Promise<ActionResult> {
  const r = await sendJson(`/v1/platform/businesses/${businessId}/customers/segments/${segmentId}/archive`, 'POST')
  if (r.ok) revalidatePath(`/b/${businessId}/customers/segments`)
  return r
}
