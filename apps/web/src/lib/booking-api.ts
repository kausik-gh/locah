const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000'

export async function fetchBookingOptions(slug: string) {
  const res = await fetch(`${apiUrl}/v1/public/websites/${slug}/booking/options`, {
    cache: 'no-store',
  })
  if (!res.ok) throw new Error('Booking options unavailable')
  return (await res.json()).data
}

export async function checkBookingAvailability(slug: string, body: Record<string, unknown>) {
  const res = await fetch(`${apiUrl}/v1/public/websites/${slug}/booking/availability`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error('Availability check failed')
  return (await res.json()).data as {
    available: boolean
    reason?: string | null
    code?: string
  }
}

export async function createPublicBooking(slug: string, body: Record<string, unknown>) {
  const res = await fetch(`${apiUrl}/v1/public/websites/${slug}/bookings`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  const json = await res.json().catch(() => ({}))
  if (!res.ok) {
    const message = json?.detail?.message || json?.error?.message || 'Booking failed'
    const code = json?.detail?.details?.code || json?.detail?.code
    throw Object.assign(new Error(message), { code })
  }
  return json.data
}

export async function fetchManagedBooking(bookingId: string, token: string) {
  const res = await fetch(
    `${apiUrl}/v1/public/bookings/${bookingId}?token=${encodeURIComponent(token)}`,
    { cache: 'no-store' }
  )
  if (res.status === 404) return null
  const json = await res.json().catch(() => ({}))
  if (!res.ok) {
    const code = json?.detail?.details?.code
    if (code === 'expired_link') return { expired: true as const }
    throw new Error('Booking unavailable')
  }
  return { expired: false as const, booking: json.data }
}

export async function cancelManagedBooking(
  bookingId: string,
  token: string,
  reason: string
) {
  const res = await fetch(`${apiUrl}/v1/public/bookings/${bookingId}/cancel`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token, reason }),
  })
  const json = await res.json().catch(() => ({}))
  if (!res.ok) {
    const message = json?.detail?.message || 'Cancel failed'
    const code = json?.detail?.details?.code
    throw Object.assign(new Error(message), { code })
  }
  return json.data
}

export async function rescheduleManagedBooking(
  bookingId: string,
  token: string,
  starts_at: string,
  ends_at: string
) {
  const res = await fetch(`${apiUrl}/v1/public/bookings/${bookingId}/reschedule`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token, starts_at, ends_at }),
  })
  const json = await res.json().catch(() => ({}))
  if (!res.ok) {
    const message = json?.detail?.message || 'Reschedule failed'
    const code = json?.detail?.details?.code
    throw Object.assign(new Error(message), { code })
  }
  return json.data
}
