'use server'

import { revalidatePath } from 'next/cache'
import { sendJson, type ActionResult } from '@/lib/server-send'

function refresh(businessId: string) {
  revalidatePath(`/b/${businessId}/inventory`, 'layout')
}

async function send<T = unknown>(businessId: string, path: string, body: unknown): Promise<ActionResult<T>> {
  const r = await sendJson<T>(`/v1/platform/businesses/${businessId}${path}`, 'POST', body)
  if (r.ok) refresh(businessId)
  return r
}

export async function requestTransfer(businessId: string, body: Record<string, unknown>) {
  return send(businessId, '/inventory/transfers', body)
}

export async function approveTransfer(businessId: string, transferId: string, idempotencyKey: string) {
  return send(businessId, `/inventory/transfers/${transferId}/approve`, { idempotency_key: idempotencyKey })
}

export async function sendTransfer(businessId: string, transferId: string, idempotencyKey: string) {
  return send(businessId, `/inventory/transfers/${transferId}/send`, { idempotency_key: idempotencyKey })
}

export async function receiveTransfer(businessId: string, transferId: string, idempotencyKey: string) {
  return send(businessId, `/inventory/transfers/${transferId}/receive`, { idempotency_key: idempotencyKey })
}

export async function addVan(businessId: string, name: string) {
  return send(businessId, '/locations', { name, stock_role: 'van' })
}
