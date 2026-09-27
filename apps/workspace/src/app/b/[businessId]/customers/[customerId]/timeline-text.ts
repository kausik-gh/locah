/**
 * A customer timeline entry in words. Entries carry a structured summary
 * (order number, status…); this page used to print that object raw.
 */
export type TimelineSummary = Record<string, unknown> | string | null

const s = (v: unknown) => (v === null || v === undefined ? '' : String(v))
const human = (v: unknown) => s(v).replace(/_/g, ' ')
const rupees = (v: unknown) =>
  typeof v === 'number' ? `₹${v.toLocaleString('en-IN', { maximumFractionDigits: 2 })}` : ''

export function timelineText(type: string, summary: TimelineSummary): string {
  const x = summary && typeof summary === 'object' ? summary : {}
  const [area, verb] = type.split('.')
  if (type === 'customer.registered') return 'Became a customer'
  if (area === 'order') {
    const n = s(x.order_number)
    if (verb === 'created') return `Placed order ${n}${x.total_amount !== undefined ? ` · ${rupees(x.total_amount)}` : ''}`
    return `Order ${n} ${human(x.status || verb)}`
  }
  if (area === 'booking') {
    const n = s(x.booking_number)
    if (verb === 'created') return `Booked ${n}`
    return `Booking ${n} ${human(x.status || verb)}`
  }
  if (area === 'membership') return `Membership ${human(x.status || verb)}`
  if (area === 'lead') return `Enquiry ${human(x.status || verb)}`
  if (typeof summary === 'string' && summary) return summary
  return human(type.replace('.', ' '))
}
