const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000'

export type CartItem = {
  offering_id: string
  title: string
  quantity: number
  unit_price: number
  currency: string
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
