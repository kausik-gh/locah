'use server'

import { revalidatePath } from 'next/cache'
import { sendJson, type ActionResult } from '@/lib/server-send'

export type Priced = {
  lines: { offering_id: string; title: string; quantity: number; unit_price: number; line_total: number }[]
  tax_amount: number
  tax_included: boolean
  items_total: number
  delivery: { serviceable: boolean; charge: number | null } | null
  total: number
  problems: { offering_id: string; title: string; available: number; message: string }[]
  preorder: {
    needed: boolean
    offered: boolean
    earliest_words: string | null
    dates: { date: string; label: string; times: string[]; full: boolean }[]
    advance: number
  }
  due_error: string | null
}

export type Placed = {
  order: { id: string; order_number: string }
  confirmation: { order_number: string; grand_total: number }
  advance: { amount: number; request_id: string; path: string; url: string } | null
}

export type Changed = {
  preview: boolean
  before_total: number
  total: number
  paid: number
  to_collect: number
  refund_due: number
  tax_amount: number
  changes: string[]
  version?: number
}

const base = (b: string) => `/v1/platform/businesses/${b}`

export async function pricePhoneOrder(businessId: string, body: Record<string, unknown>): Promise<ActionResult<Priced>> {
  return sendJson<Priced>(`${base(businessId)}/orders/phone/price`, 'POST', body)
}

export async function placePhoneOrder(businessId: string, body: Record<string, unknown>): Promise<ActionResult<Placed>> {
  const r = await sendJson<Placed>(`${base(businessId)}/orders/phone`, 'POST', body)
  if (r.ok) revalidatePath(`/b/${businessId}/orders`)
  return r
}

export async function variantsFor(businessId: string, offeringId: string): Promise<ActionResult<{ id: string; name: string; price_amount: number | null }[]>> {
  return sendJson(`${base(businessId)}/products/${offeringId}/variants`, 'GET')
}

export async function changeOrder(
  businessId: string,
  orderId: string,
  body: Record<string, unknown>,
  preview: boolean,
): Promise<ActionResult<Changed>> {
  const r = await sendJson<Changed>(`${base(businessId)}/orders/${orderId}/change${preview ? '?preview=true' : ''}`, 'POST', body)
  if (r.ok && !preview) revalidatePath(`/b/${businessId}/orders/${orderId}`)
  return r
}
