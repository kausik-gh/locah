'use server'

import { revalidatePath } from 'next/cache'
import { sendJson, type ActionResult } from '@/lib/server-send'

type Repriced = { rate: { id: string; value: number }; repriced: string[] }

export async function addRate(
  businessId: string,
  body: { label: string; unit: string; value: number | null },
): Promise<ActionResult<{ id: string }>> {
  const r = await sendJson<{ id: string }>(`/v1/platform/businesses/${businessId}/pricing/rates`, 'POST', body)
  if (r.ok) revalidatePath(`/b/${businessId}/offerings/rates`)
  return r
}

export async function enterRate(
  businessId: string,
  rateId: string,
  value: number,
  note: string | null,
): Promise<ActionResult<Repriced>> {
  const r = await sendJson<Repriced>(`/v1/platform/businesses/${businessId}/pricing/rates/${rateId}/values`, 'POST', {
    value,
    note,
  })
  if (r.ok) {
    revalidatePath(`/b/${businessId}/offerings/rates`)
    revalidatePath(`/b/${businessId}/offerings`)
    revalidatePath(`/b/${businessId}`)
  }
  return r
}
