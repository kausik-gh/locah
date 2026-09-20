import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import { GateNotice, PageHeader } from '@/components/ModuleState'
import { transitionBooking } from '../actions'
import { LocalTime } from '@/components/LocalTime'

export const dynamic = 'force-dynamic'

export default async function BookingDetailPage({
  params,
}: {
  params: { businessId: string; bookingId: string }
}) {
  const token = await getAccessToken()
  if (!token) redirect('/login')
  const [bookingRes, historyRes] = await Promise.all([
    apiTry<{ data: Record<string, unknown> }>(
      `/v1/platform/businesses/${params.businessId}/bookings/${params.bookingId}`,
      token
    ),
    apiTry<{ data: Array<Record<string, unknown>> }>(
      `/v1/platform/businesses/${params.businessId}/bookings/${params.bookingId}/history`,
      token
    ),
  ])
  if (!bookingRes.ok) {
    return (
      <div>
        <Link href={`/b/${params.businessId}/bookings`}>← Bookings</Link>
        <PageHeader title="Booking" />
        <GateNotice error={bookingRes.error} businessId={params.businessId} moduleLabel="Bookings" />
      </div>
    )
  }
  const b = bookingRes.data.data
  const history = historyRes.ok ? historyRes.data.data || [] : []

  async function confirm() {
    'use server'
    await transitionBooking(params.businessId, params.bookingId, 'confirmed')
  }
  async function complete() {
    'use server'
    await transitionBooking(params.businessId, params.bookingId, 'completed')
  }
  async function cancel() {
    'use server'
    await transitionBooking(
      params.businessId,
      params.bookingId,
      'cancelled',
      'Cancelled by staff'
    )
  }

  return (
    <div>
      <p>
        <Link href={`/b/${params.businessId}/bookings`}>← Bookings</Link>
      </p>
      <h1>{String(b.booking_number)}</h1>
      <p>
        {String(b.title)} · {String(b.reservation_mode)} · {String(b.status)}
      </p>
      <p>
        <LocalTime value={b.starts_at as string | null} /> →{' '}
        <LocalTime value={b.ends_at as string | null} />
      </p>
      <p>
        Provider: {String(b.provider_id || '—')} · Payment: {String(b.payment_status)}
        {b.deposit_required ? ` · Deposit ${String(b.deposit_amount)}` : ''}
      </p>
      <div style={{ display: 'flex', gap: '0.75rem', marginTop: '1rem' }}>
        <form action={confirm}>
          <button type="submit">Confirm</button>
        </form>
        <form action={complete}>
          <button type="submit">Complete</button>
        </form>
        <form action={cancel}>
          <button type="submit">Cancel</button>
        </form>
      </div>
      <h2 style={{ marginTop: '2rem', fontSize: '1.2rem' }}>History</h2>
      <ul>
        {history.map((h) => (
          <li key={String(h.id)}>
            {String(h.from_status || '—')} → {String(h.to_status)} (
            <LocalTime value={h.created_at as string | null} />)
          </li>
        ))}
      </ul>
    </div>
  )
}
