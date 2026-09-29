import type { Words } from '@/lib/ws-words'

const english: Words = (text) => text

/** Where the order came from (Capability Universe §12: every channel ends in the same order). */
export const CHANNEL: Record<string, string> = {
  web: 'Website',
  whatsapp: 'WhatsApp',
  pos: 'Counter',
  phone: 'Phone',
  workspace: 'Entered by team',
  marketplace: 'Marketplace',
}

/** How the money stands, in words a shop owner uses. The stored values
 *  (`cod`, `pending_offline`) are internal states and must not reach the screen. */
const PAY_METHOD: Record<string, string> = {
  cod: 'Cash',
  pay_at_business: 'Pay at the shop',
  pay_later: 'Pay later',
  online: 'Online',
  card: 'Card',
  upi: 'UPI',
}
const PAY_STATUS: Record<string, string> = {
  pending_offline: 'to collect',
  pending: 'awaiting payment',
  paid: 'paid',
  partially_paid: 'part paid',
  refunded: 'refunded',
  partially_refunded: 'part refunded',
  failed: 'payment failed',
}

/** Once money has come in, how the customer first said they would pay no longer
 *  matters (an advance by UPI on a "cash at pickup" order is not cash). */
const SETTLED = new Set(['paid', 'partially_paid', 'refunded', 'partially_refunded'])

export function paymentLabel(o: { payment_method: string; payment_status: string }, t: Words = english): string {
  const status = t(PAY_STATUS[o.payment_status] || o.payment_status.replace(/_/g, ' '))
  if (SETTLED.has(o.payment_status)) return status.charAt(0).toUpperCase() + status.slice(1)
  const method = t(PAY_METHOD[o.payment_method] || o.payment_method.replace(/_/g, ' '))
  return `${method} · ${status}`
}

export function money(amount: number, currency: string): string {
  try {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: currency || 'INR',
      maximumFractionDigits: Number.isInteger(amount) ? 0 : 2,
    }).format(amount)
  } catch {
    return `${currency} ${amount}`
  }
}

/** A membership's or booking's money in words (no checkout choice to echo). */
export function paidWords(status: string | null | undefined): string {
  if (!status || status === 'pending' || status === 'pending_offline') return 'Not paid yet'
  if (status === 'deposit_paid') return 'Deposit paid'
  const words = PAY_STATUS[status] || status.replace(/_/g, ' ')
  return words.charAt(0).toUpperCase() + words.slice(1)
}
