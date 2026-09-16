'use client'

import { useEffect, useState } from 'react'
import {
  cancelManagedBooking,
  fetchManagedBooking,
  rescheduleManagedBooking,
} from '@/lib/booking-api'

export default function ManageBookingClient({
  slug,
  bookingId,
  token,
}: {
  slug: string
  bookingId: string
  token: string
}) {
  const [state, setState] = useState<
    | { kind: 'loading' }
    | { kind: 'missing' }
    | { kind: 'expired' }
    | { kind: 'ready'; booking: Record<string, unknown> }
    | { kind: 'error'; message: string }
  >({ kind: 'loading' })
  const [message, setMessage] = useState<string | null>(null)
  const [newStart, setNewStart] = useState('')
  const [newEnd, setNewEnd] = useState('')

  useEffect(() => {
    if (!token) {
      setState({ kind: 'missing' })
      return
    }
    fetchManagedBooking(bookingId, token)
      .then((result) => {
        if (!result) setState({ kind: 'missing' })
        else if (result.expired) setState({ kind: 'expired' })
        else setState({ kind: 'ready', booking: result.booking })
      })
      .catch((e: Error) => setState({ kind: 'error', message: e.message }))
  }, [bookingId, token])

  async function onCancel() {
    setMessage(null)
    try {
      const data = await cancelManagedBooking(bookingId, token, 'Customer cancelled')
      setState({ kind: 'ready', booking: data })
      setMessage('Booking cancelled.')
    } catch (err) {
      const e = err as Error & { code?: string }
      if (e.code === 'cancellation_window_closed') {
        setMessage('The cancellation window has closed for this booking.')
      } else if (e.code === 'expired_link') {
        setState({ kind: 'expired' })
      } else {
        setMessage(e.message)
      }
    }
  }

  async function onReschedule(e: React.FormEvent) {
    e.preventDefault()
    setMessage(null)
    try {
      const data = await rescheduleManagedBooking(
        bookingId,
        token,
        new Date(newStart).toISOString(),
        new Date(newEnd).toISOString()
      )
      setState({ kind: 'ready', booking: data })
      setMessage('Booking rescheduled.')
    } catch (err) {
      const e2 = err as Error & { code?: string }
      if (e2.code === 'cancellation_window_closed') {
        setMessage('The reschedule window has closed for this booking.')
      } else {
        setMessage(e2.message)
      }
    }
  }

  if (state.kind === 'loading') {
    return <main style={{ padding: '3rem 1.25rem' }}>Loading…</main>
  }
  if (state.kind === 'missing') {
    return (
      <main style={{ maxWidth: 560, margin: '0 auto', padding: '3rem 1.25rem' }}>
        <h1>Booking not found</h1>
        <p>This management link is invalid.</p>
      </main>
    )
  }
  if (state.kind === 'expired') {
    return (
      <main style={{ maxWidth: 560, margin: '0 auto', padding: '3rem 1.25rem' }}>
        <h1>Link expired</h1>
        <p>This management link has expired. Contact the business for help.</p>
      </main>
    )
  }
  if (state.kind === 'error') {
    return (
      <main style={{ maxWidth: 560, margin: '0 auto', padding: '3rem 1.25rem' }}>
        <h1>Unavailable</h1>
        <p>{state.message}</p>
      </main>
    )
  }

  const b = state.booking
  return (
    <main style={{ maxWidth: 640, margin: '0 auto', padding: '3rem 1.25rem' }}>
      <p style={{ opacity: 0.65, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
        {slug}
      </p>
      <h1 style={{ fontSize: '2.2rem', margin: '0.35rem 0' }}>
        {String(b.booking_number)}
      </h1>
      <p>
        {String(b.title)} · {String(b.status)} · {String(b.starts_at)} → {String(b.ends_at)}
      </p>
      {message ? <p role="status">{message}</p> : null}

      {b.status !== 'cancelled' && b.status !== 'completed' ? (
        <>
          <button
            type="button"
            onClick={onCancel}
            style={{
              marginTop: '1rem',
              padding: '0.65rem 1rem',
              border: '1px solid #1c2a24',
              background: 'transparent',
              cursor: 'pointer',
            }}
          >
            Cancel booking
          </button>
          <form onSubmit={onReschedule} style={{ marginTop: '1.5rem', display: 'grid', gap: 8 }}>
            <h2 style={{ fontSize: '1.2rem', margin: 0 }}>Reschedule</h2>
            <input
              type="datetime-local"
              value={newStart}
              onChange={(e) => setNewStart(e.target.value)}
              required
            />
            <input
              type="datetime-local"
              value={newEnd}
              onChange={(e) => setNewEnd(e.target.value)}
              required
            />
            <button type="submit" style={{ padding: '0.65rem 1rem', cursor: 'pointer' }}>
              Save new time
            </button>
          </form>
        </>
      ) : null}
      <p style={{ marginTop: '2rem', opacity: 0.75 }}>
        Need help? Contact the business directly with your booking number.
      </p>
    </main>
  )
}
