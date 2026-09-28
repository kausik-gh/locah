'use server'

import { revalidatePath } from 'next/cache'
import { businessSiteUrl } from '@platform/config'
import { sendJson, type ActionResult } from '@/lib/server-send'
import type { Bill } from './types'

const api = (b: string) => `/v1/platform/businesses/${b}`

function refresh(businessId: string, id?: string) {
  revalidatePath(`/b/${businessId}/invoices`)
  if (id) revalidatePath(`/b/${businessId}/invoices/${id}`)
}

export async function saveProfile(businessId: string, body: Record<string, unknown>): Promise<ActionResult> {
  const r = await sendJson(`${api(businessId)}/invoicing/profile`, 'PUT', body)
  if (r.ok) revalidatePath(`/b/${businessId}/settings/invoicing`)
  return r
}

export async function saveRegistration(businessId: string, id: string | null, body: Record<string, unknown>): Promise<ActionResult> {
  const r = id
    ? await sendJson(`${api(businessId)}/invoicing/registrations/${id}`, 'PATCH', body)
    : await sendJson(`${api(businessId)}/invoicing/registrations`, 'POST', body)
  if (r.ok) revalidatePath(`/b/${businessId}/settings/invoicing`)
  return r
}

export async function saveRegister(businessId: string, id: string | null, body: Record<string, unknown>): Promise<ActionResult> {
  const r = id
    ? await sendJson(`${api(businessId)}/invoicing/registers/${id}`, 'PATCH', body)
    : await sendJson(`${api(businessId)}/invoicing/registers`, 'POST', body)
  if (r.ok) revalidatePath(`/b/${businessId}/settings/invoicing`)
  return r
}

export async function addRate(businessId: string, body: Record<string, unknown>): Promise<ActionResult> {
  const r = await sendJson(`${api(businessId)}/invoicing/tax-rates`, 'POST', body)
  if (r.ok) revalidatePath(`/b/${businessId}/invoices/tax-rates`)
  return r
}

export async function removeRate(businessId: string, id: string): Promise<ActionResult> {
  const r = await sendJson(`${api(businessId)}/invoicing/tax-rates/${id}`, 'DELETE')
  if (r.ok) revalidatePath(`/b/${businessId}/invoices/tax-rates`)
  return r
}

export async function createBill(businessId: string, body: Record<string, unknown>): Promise<ActionResult<Bill>> {
  const r = await sendJson<Bill>(`${api(businessId)}/invoices`, 'POST', body)
  if (r.ok) refresh(businessId)
  return r
}

export async function updateDraft(businessId: string, id: string, body: Record<string, unknown>): Promise<ActionResult<Bill>> {
  const r = await sendJson<Bill>(`${api(businessId)}/invoices/${id}`, 'PATCH', body)
  if (r.ok) refresh(businessId, id)
  return r
}

export async function billAction(
  businessId: string,
  id: string,
  action: 'issue' | 'cancel' | 'notes' | 'payments' | 'delete',
  body?: Record<string, unknown>,
): Promise<ActionResult<Bill>> {
  const r = action === 'delete'
    ? await sendJson<Bill>(`${api(businessId)}/invoices/${id}`, 'DELETE')
    : await sendJson<Bill>(`${api(businessId)}/invoices/${id}/${action}`, 'POST', body ?? {})
  if (r.ok) refresh(businessId, id)
  return r
}

export async function billOrder(businessId: string, orderId: string, body: Record<string, unknown>): Promise<ActionResult<Bill>> {
  const r = await sendJson<Bill>(`${api(businessId)}/invoices/from-order/${orderId}`, 'POST', body)
  if (r.ok) {
    refresh(businessId)
    revalidatePath(`/b/${businessId}/orders/${orderId}`)
  }
  return r
}

type Share = { token: string; path: string; message: string; phone: string | null; url: string }

/** The customer's link to their bill, on the business's own website address. */
export async function shareBill(businessId: string, id: string): Promise<ActionResult<Share>> {
  const r = await sendJson<Omit<Share, 'url'>>(`${api(businessId)}/invoices/${id}/share`, 'GET')
  if (!r.ok || !r.data) return r.ok ? { ok: false, message: 'No link came back' } : r
  const [, slug] = r.data.path.split('/')
  return { ok: true, data: { ...r.data, url: businessSiteUrl(slug, `/bill/${r.data.token}`) } }
}
