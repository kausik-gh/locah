'use server'

import { revalidatePath } from 'next/cache'
import { businessSiteUrl } from '@platform/config'
import { sendJson, type ActionResult } from '@/lib/server-send'
import type { AccountDetail } from './types'

const api = (b: string) => `/v1/platform/businesses/${b}/ledger`

function refresh(businessId: string, id?: string) {
  revalidatePath(`/b/${businessId}/khata`)
  if (id) revalidatePath(`/b/${businessId}/khata/${id}`)
}

export async function openAccount(businessId: string, body: Record<string, unknown>): Promise<ActionResult<AccountDetail>> {
  const r = await sendJson<AccountDetail>(`${api(businessId)}/accounts`, 'POST', body)
  if (r.ok) refresh(businessId)
  return r
}

export async function updateAccount(businessId: string, id: string, body: Record<string, unknown>): Promise<ActionResult<AccountDetail>> {
  const r = await sendJson<AccountDetail>(`${api(businessId)}/accounts/${id}`, 'PATCH', body)
  if (r.ok) refresh(businessId, id)
  return r
}

/** Money received from a customer (settles their oldest bills first) or paid to a supplier. */
export async function recordMoney(businessId: string, id: string, body: Record<string, unknown>): Promise<ActionResult<AccountDetail>> {
  const r = await sendJson<AccountDetail>(`${api(businessId)}/accounts/${id}/payments`, 'POST', body)
  if (r.ok) {
    refresh(businessId, id)
    revalidatePath(`/b/${businessId}/invoices`)
  }
  return r
}

/** A supplier's bill on credit, a correction, or an opening balance. */
export async function postEntry(businessId: string, id: string, body: Record<string, unknown>): Promise<ActionResult<AccountDetail>> {
  const r = await sendJson<AccountDetail>(`${api(businessId)}/accounts/${id}/entries`, 'POST', body)
  if (r.ok) refresh(businessId, id)
  return r
}

type Share = { token: string; path: string; business_name: string; phone: string | null; message: string; url: string }

export async function shareStatement(businessId: string, id: string): Promise<ActionResult<Share>> {
  const r = await sendJson<Omit<Share, 'url'>>(`${api(businessId)}/accounts/${id}/share`, 'POST')
  if (!r.ok || !r.data) return r.ok ? { ok: false, message: 'No link came back' } : r
  const [, slug] = r.data.path.split('/')
  return { ok: true, data: { ...r.data, url: businessSiteUrl(slug, `/khata/${r.data.token}`) } }
}
