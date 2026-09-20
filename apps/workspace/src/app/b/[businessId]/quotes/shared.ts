/**
 * How a quote reads on screen.
 *
 * Presentation only. Nothing here decides an amount, a status or what may be
 * done next — those come from the API, which is the single author of a quote's
 * commercial truth. This file turns what it returns into words and formats.
 */

export type QuoteRow = {
  id: string
  quote_number: string
  revision: number
  status: string
  stored_status: string
  title: string | null
  customer_contact_id: string | null
  currency: string
  subtotal: string
  discount_amount: string
  charges_amount: string
  tax_amount: string
  total: string
  deposit_amount: string
  discount_type: string | null
  discount_value: string | null
  deposit_type: string | null
  deposit_value: string | null
  terms: string | null
  notes: string | null
  valid_until: string | null
  issued_at: string | null
  accepted_at: string | null
  rejected_at: string | null
  cancelled_at: string | null
  decision_reason: string | null
  supersedes_quote_id: string | null
  root_quote_id: string | null
  converted_to_type: string | null
  converted_to_id: string | null
  is_editable: boolean
  version: number
  items?: QuoteItem[]
  charges?: QuoteCharge[]
}

export type QuoteItem = {
  id: string
  offering_id: string | null
  title: string | null
  description: string | null
  unit_label: string | null
  quantity: string
  unit_price: string
  tax_rate: string
  discount_type: string | null
  discount_value: string | null
  line_subtotal: string
  line_discount: string
  line_tax: string
  line_total: string
  sort_order: number
}

export type QuoteCharge = {
  id: string
  label: string
  amount: string
  taxable: boolean
  tax_rate: string
  sort_order: number
}

/** Every status the API can report, in the owner's language. */
export const STATUS_LABEL: Record<string, string> = {
  draft: 'Draft',
  issued: 'Sent',
  accepted: 'Accepted',
  rejected: 'Declined',
  expired: 'Expired',
  cancelled: 'Cancelled',
  superseded: 'Revised',
}

/**
 * Maps onto StatusPill's own tone vocabulary so quotes read like the rest of
 * Workspace rather than inventing a second colour language.
 */
export const STATUS_TONE: Record<string, 'good' | 'warn' | 'bad' | 'neutral' | 'info'> = {
  draft: 'neutral',
  issued: 'info',
  accepted: 'good',
  rejected: 'bad',
  expired: 'warn',
  cancelled: 'neutral',
  superseded: 'neutral',
}

export function statusLabel(status: string): string {
  return STATUS_LABEL[status] ?? status
}

/**
 * Amounts, in the quote's own currency.
 *
 * The API sends money as a decimal string so nothing is lost on the way; it is
 * parsed here only to be formatted, never to be recomputed.
 */
export function money(amount: string | number | null | undefined, currency = 'INR'): string {
  const value = typeof amount === 'number' ? amount : Number(amount ?? 0)
  if (!Number.isFinite(value)) return '—'
  try {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: currency || 'INR',
      maximumFractionDigits: Number.isInteger(value) ? 0 : 2,
    }).format(value)
  } catch {
    return `${currency || 'INR'} ${value.toFixed(2)}`
  }
}

/** A quantity without trailing zeros: `2`, not `2.000`. */
export function qty(value: string | number | null | undefined): string {
  const n = Number(value ?? 0)
  if (!Number.isFinite(n)) return '—'
  return String(Number(n.toFixed(3)))
}

/** `Q-2026-0004` plus its revision, where there is one worth showing. */
export function quoteRef(quote: Pick<QuoteRow, 'quote_number' | 'revision'>): string {
  return quote.revision > 1 ? `${quote.quote_number} · rev ${quote.revision}` : quote.quote_number
}

/**
 * A validity date, as the calendar date it was chosen as.
 *
 * `valid_until` is stored as the last instant of the chosen day in UTC, so
 * rendering it in the reader's own zone moves it: an owner in India who typed
 * 11 October saw "Oct 12" read back, because 23:59 UTC is past midnight there.
 * The date is the meaningful part of this value, so it is formatted in the zone
 * it was recorded in.
 */
export function validityDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleDateString('en-GB', {
    timeZone: 'UTC',
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
}

/** Days until a quote lapses, or null when it has no validity date. */
export function daysUntil(iso: string | null | undefined): number | null {
  if (!iso) return null
  const then = new Date(iso).getTime()
  if (Number.isNaN(then)) return null
  return Math.ceil((then - Date.now()) / 86_400_000)
}

/**
 * What the business can still do with a quote.
 *
 * A mirror of the service's own rules for the purpose of deciding which buttons
 * to draw — never for deciding whether the action is allowed. The API refuses an
 * invalid transition regardless of what this returns, and the refusal is what
 * the owner sees.
 */
export function availableActions(status: string): {
  canEdit: boolean
  canIssue: boolean
  canDecide: boolean
  canCancel: boolean
  canRevise: boolean
  canShare: boolean
} {
  return {
    canEdit: status === 'draft',
    canIssue: status === 'draft',
    canDecide: status === 'issued',
    canCancel: status === 'draft' || status === 'issued',
    canRevise: ['issued', 'rejected', 'expired'].includes(status),
    canShare: ['issued', 'accepted', 'rejected', 'expired'].includes(status),
  }
}
