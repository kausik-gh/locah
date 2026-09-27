import { platformUrl } from '@platform/config'
const apiUrl = platformUrl('api')

export type CartItem = {
  offering_id: string
  title: string
  quantity: number
  /** For display only — the server prices every line from the catalogue. */
  unit_price: number
  currency: string
  /** What was chosen: a pack, cuts / modifiers, a variant, or a gift amount. */
  options?: Record<string, unknown>
  variant_id?: string
  /** Words for the choice, e.g. "500 g · Boneless". */
  detail?: string
  /** Same offering with different choices = different lines. */
  key?: string
}

export function cartKey(item: Pick<CartItem, 'offering_id' | 'options' | 'variant_id'>): string {
  return `${item.offering_id}|${item.variant_id ?? ''}|${JSON.stringify(item.options ?? {})}`
}

/** Add to this site's basket (browser storage); merges identical choices. */
export function addToBasket(slug: string, item: CartItem): number {
  const storageKey = cartStorageKey(slug)
  let existing: CartItem[] = []
  try {
    existing = JSON.parse(localStorage.getItem(storageKey) || '[]')
  } catch {
    existing = []
  }
  const key = cartKey(item)
  const found = existing.find((i) => (i.key ?? cartKey(i)) === key)
  if (found) found.quantity += item.quantity
  else existing.push({ ...item, key })
  try {
    localStorage.setItem(storageKey, JSON.stringify(existing))
  } catch {
    /* storage unavailable — the checkout page re-reads from scratch */
  }
  return existing.reduce((n, i) => n + i.quantity, 0)
}

export type EnquiryBody = {
  name: string
  phone?: string
  email?: string
  message?: string
  offering_id?: string
  purpose?: 'enquiry' | 'site_visit' | 'test_drive' | 'callback'
  preferred_date?: string
  website?: string
}

export async function submitEnquiry(slug: string, body: EnquiryBody) {
  const res = await fetch(`${apiUrl}/v1/public/websites/${slug}/enquiries`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  const json = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(json?.error?.message || 'That did not send. Try again.')
  return json.data as { received: boolean; reference?: string }
}

export async function fetchCheckoutOptions(slug: string) {
  const res = await fetch(`${apiUrl}/v1/public/websites/${slug}/checkout/options`, {
    cache: 'no-store',
  })
  if (!res.ok) throw new Error('Checkout options unavailable')
  return (await res.json()).data
}

export async function fetchPublicOfferings(slug: string) {
  const res = await fetch(`${apiUrl}/v1/public/websites/${slug}/offerings`, {
    next: { revalidate: 30 },
  })
  if (!res.ok) return { offerings: [] as Array<Record<string, unknown>> }
  return (await res.json()).data
}

export async function quoteDelivery(slug: string, delivery_address: Record<string, unknown>) {
  const res = await fetch(`${apiUrl}/v1/public/websites/${slug}/checkout/quote`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ delivery_address }),
  })
  if (!res.ok) throw new Error('Quote failed')
  return (await res.json()).data
}

export async function placeCheckoutOrder(slug: string, body: Record<string, unknown>) {
  const res = await fetch(`${apiUrl}/v1/public/websites/${slug}/checkout`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  const json = await res.json().catch(() => ({}))
  if (!res.ok) {
    const message = json?.detail?.message || json?.error?.message || 'Checkout failed'
    throw new Error(message)
  }
  return json.data
}

export async function fetchTracking(orderId: string, token: string) {
  const res = await fetch(
    `${apiUrl}/v1/public/orders/${orderId}/tracking?token=${encodeURIComponent(token)}`,
    { cache: 'no-store' }
  )
  if (res.status === 404) return null
  if (!res.ok) throw new Error('Tracking unavailable')
  return (await res.json()).data
}

export function cartStorageKey(slug: string) {
  return `platform.cart.${slug}`
}
