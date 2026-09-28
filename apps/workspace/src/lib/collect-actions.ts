'use server'

import { revalidatePath } from 'next/cache'
import { sendJson } from '@/lib/server-send'

const base = (b: string) => `/v1/platform/businesses/${b}/collect`

export type LinkResult = {
  id: string
  url: string
  message: string
  whatsapp: string | null
  amount: number
  purpose_label: string
}

/** A payment link for part or all of what is due on an order, booking, membership, bill or khata. */
export async function askForPayment(businessId: string, path: string, body: Record<string, unknown>) {
  const r = await sendJson<LinkResult>(`${base(businessId)}/requests`, 'POST', body)
  if (r.ok) revalidatePath(path)
  return r
}

export async function cancelPaymentLink(businessId: string, path: string, requestId: string) {
  const r = await sendJson(`${base(businessId)}/requests/${requestId}/cancel`, 'POST')
  if (r.ok) revalidatePath(path)
  return r
}

/** The owner checked their UPI app: the customer's payment arrived, or it did not. */
export async function confirmPayment(businessId: string, path: string, paymentId: string, arrived: boolean) {
  const r = await sendJson(`${base(businessId)}/payments/${paymentId}/confirm`, 'POST', { arrived })
  if (r.ok) {
    revalidatePath(path)
    revalidatePath(`/b/${businessId}/payments`)
  }
  return r
}

/** Cash at pickup, UPI at the counter, a card on the business's own terminal, a bank transfer. */
export async function recordMoney(businessId: string, path: string, body: Record<string, unknown>) {
  const r = await sendJson(`${base(businessId)}/record`, 'POST', body)
  if (r.ok) revalidatePath(path)
  return r
}
