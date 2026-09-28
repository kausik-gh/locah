'use server'

import { revalidatePath } from 'next/cache'
import { sendJson, type ActionResult } from '@/lib/server-send'

const api = (b: string) => `/v1/platform/businesses/${b}/stock`

function refresh(businessId: string) {
  revalidatePath(`/b/${businessId}/inventory`, 'layout')
}

async function send<T = unknown>(businessId: string, path: string, method: string, body?: unknown): Promise<ActionResult<T>> {
  const r = await sendJson<T>(`${api(businessId)}${path}`, method, body)
  if (r.ok) refresh(businessId)
  return r
}

/** Goods in: quantity (or buying units), cost, batch and expiry, serial numbers. */
export async function receiveStock(businessId: string, body: Record<string, unknown>) {
  return send<{ on_hand_text: string; quantity_text: string }>(businessId, '/receipts', 'POST', body)
}

export async function recordWastage(businessId: string, body: Record<string, unknown>) {
  return send<{ quantity_text: string; on_hand_text: string }>(businessId, '/wastage', 'POST', body)
}

export async function writeOffBatch(businessId: string, batchId: string, note?: string) {
  return send(businessId, `/batches/${batchId}/write-off`, 'POST', { note: note || null })
}

export async function setYield(businessId: string, body: Record<string, unknown>) {
  return send(businessId, '/yields', 'PUT', body)
}

export async function cutAndPortion(businessId: string, body: Record<string, unknown>) {
  return send<{ trim_text: string; trim_percent: number }>(businessId, '/conversions', 'POST', body)
}

export async function setReorder(businessId: string, recordId: string, body: Record<string, unknown>) {
  return send(businessId, `/records/${recordId}/reorder`, 'PATCH', body)
}

export async function configureItem(businessId: string, offeringId: string, body: Record<string, unknown>) {
  return send(businessId, `/items/${offeringId}`, 'PATCH', body)
}

export async function startCount(businessId: string, body: Record<string, unknown>) {
  return send<{ id: string }>(businessId, '/counts', 'POST', body)
}

export async function saveCount(businessId: string, countId: string, lines: { inventory_record_id: string; counted_quantity: number | null }[]) {
  return send(businessId, `/counts/${countId}/lines`, 'PUT', { lines })
}

export async function submitCount(businessId: string, countId: string) {
  return send(businessId, `/counts/${countId}/submit`, 'POST')
}

export async function decideCount(businessId: string, countId: string, approve: boolean, note?: string) {
  return send<{ variances_applied?: number }>(businessId, `/counts/${countId}/decision`, 'POST', { approve, note: note || null })
}

export type SerialInfo = {
  serial: string; title: string; status: string; sold_at: string | null; warranty_until: string | null
  in_warranty: boolean; warranty_months: number | null; bill_number?: string | null
  customer?: { name: string; phone: string | null } | null
}

export async function lookupSerial(businessId: string, serial: string): Promise<ActionResult<SerialInfo>> {
  return sendJson<SerialInfo>(`${api(businessId)}/serials/${encodeURIComponent(serial.trim())}`, 'GET')
}
