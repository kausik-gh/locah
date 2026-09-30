import Link from 'next/link'
import { redirect } from 'next/navigation'
import { revalidatePath } from 'next/cache'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiPost, apiTry } from '@/lib/api'
import { Card, GateNotice, PageHeader, Section, StatusPill } from '@/components/ui'
import { transitionBooking } from '../actions'
import { LocalTime } from '@/components/LocalTime'
import { MoneySection } from '@/components/MoneySection'

export const dynamic = 'force-dynamic'

type Booking = {
  id: string; booking_number: string; title: string; reservation_mode: string; status: string
  starts_at: string; ends_at: string; provider_id: string | null; payment_status: string
  deposit_required: boolean; deposit_amount: number; hold_expires_at: string | null
  series_id: string | null; occurrence_index: number | null; cancellation_reason: string | null
}
type Series = { id: string; status: string; occurrences: { id: string; occurrence_index: number; starts_at: string; status: string }[] }

// Only the moves the booking's state allows (validation/booking.py ALLOWED_TRANSITIONS).
const NEXT: Record<string, { to: string; label: string; reason?: string }[]> = {
  pending: [{ to: 'confirmed', label: 'Confirm' }, { to: 'cancelled', label: 'Cancel', reason: 'Cancelled by staff' }],
  confirmed: [
    { to: 'checked_in', label: 'Arrived' },
    { to: 'no_show', label: 'No-show', reason: 'Did not arrive' },
    { to: 'cancelled', label: 'Cancel', reason: 'Cancelled by staff' },
  ],
  checked_in: [{ to: 'completed', label: 'Done' }, { to: 'cancelled', label: 'Cancel', reason: 'Cancelled by staff' }],
}
const STATUS: Record<string, string> = {
  pending: 'Pending', confirmed: 'Confirmed', checked_in: 'Arrived', completed: 'Done', cancelled: 'Cancelled',
  rejected: 'Declined', no_show: 'No-show',
}

export default async function BookingDetailPage({ params }: { params: { businessId: string; bookingId: string } }) {
  const token = await getAccessToken()
  if (!token) redirect('/login')
  const b = params.businessId
  const base = `/v1/platform/businesses/${b}`
  const here = `/b/${b}/bookings/${params.bookingId}`
  const [bookingRes, historyRes, membersRes] = await Promise.all([
    apiTry<{ data: Booking }>(`${base}/bookings/${params.bookingId}`, token),
    apiTry<{ data: Array<Record<string, unknown>> }>(`${base}/bookings/${params.bookingId}/history`, token),
    apiTry<{ data: { id: string; display_name: string }[] }>(`${base}/workforce/members`, token),
  ])
  if (!bookingRes.ok) {
    return (
      <div>
        <PageHeader title="Booking" breadcrumb={<Link href={`/b/${b}/bookings`}>← Bookings</Link>} />
        <GateNotice error={bookingRes.error} businessId={b} moduleLabel="Bookings" />
      </div>
    )
  }
  const bk = bookingRes.data.data
  const history = historyRes.ok ? historyRes.data.data || [] : []
  const provider = membersRes.ok ? membersRes.data.data.find((m) => m.id === bk.provider_id) : undefined
  const seriesRes = bk.series_id ? await apiTry<{ data: Series }>(`${base}/bookings-series/${bk.series_id}`, token) : null
  const series = seriesRes && seriesRes.ok ? seriesRes.data.data : null
  const live = bk.status === 'pending' || bk.status === 'confirmed'

  async function move(formData: FormData) {
    'use server'
    await transitionBooking(b, params.bookingId, String(formData.get('to')), String(formData.get('reason') || '') || undefined)
  }
  async function repeat(formData: FormData) {
    'use server'
    const access = await getAccessToken()
    if (!access) throw new Error('Unauthorized')
    await apiPost(`${base}/bookings/${params.bookingId}/repeat`, {
      interval_weeks: Number(formData.get('interval_weeks') || 1), occurrences: Number(formData.get('occurrences') || 4),
    }, access)
    revalidatePath(here)
  }
  async function changeLater(formData: FormData) {
    'use server'
    const access = await getAccessToken()
    if (!access) throw new Error('Unauthorized')
    // A shift from this occurrence's own time - no clock or time zone involved.
    const shift = (Number(formData.get('days') || 0) * 24 * 60 + Number(formData.get('minutes') || 0)) * 60_000
    const start = new Date(new Date(bk.starts_at).getTime() + shift)
    const length = new Date(bk.ends_at).getTime() - new Date(bk.starts_at).getTime()
    await apiPost(`${base}/bookings-series/${bk.series_id}/change-future`, {
      from_booking_id: params.bookingId, starts_at: start.toISOString(),
      ends_at: new Date(start.getTime() + length).toISOString(),
    }, access)
    revalidatePath(here)
  }
  async function endSeries() {
    'use server'
    const access = await getAccessToken()
    if (!access) throw new Error('Unauthorized')
    await apiPost(`${base}/bookings-series/${bk.series_id}/end`, { from_booking_id: params.bookingId }, access)
    revalidatePath(here)
  }

  return (
    <div className="bos-page">
      <PageHeader
        title={`${bk.booking_number} · ${bk.title}`}
        breadcrumb={<Link href={`/b/${b}/bookings`}>← Bookings</Link>}
        actions={<StatusPill value={STATUS[bk.status] || bk.status} />}
      />
      <Card style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(12rem, 1fr))', gap: '1rem' }}>
        <div><small>When</small><p style={{ margin: 0 }}><LocalTime value={bk.starts_at} /> → <LocalTime value={bk.ends_at} /></p></div>
        <div><small>With</small><p style={{ margin: 0 }}>{provider?.display_name || 'Anyone free'}</p></div>
        <div><small>Payment</small><p style={{ margin: 0 }}>{bk.payment_status}{bk.deposit_required ? ` · deposit ₹${bk.deposit_amount}` : ''}</p></div>
        {bk.hold_expires_at && live ? (
          <div><small>Held until</small><p style={{ margin: 0 }}><LocalTime value={bk.hold_expires_at} /> — released if the deposit is not paid</p></div>
        ) : null}
        {bk.cancellation_reason ? <div><small>Reason</small><p style={{ margin: 0 }}>{bk.cancellation_reason}</p></div> : null}
      </Card>

      {(NEXT[bk.status] || []).length ? (
        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', marginTop: '1rem' }}>
          {(NEXT[bk.status] || []).map((n) => (
            <form key={n.to} action={move}>
              <input type="hidden" name="to" value={n.to} />
              {n.reason ? <input type="hidden" name="reason" value={n.reason} /> : null}
              <button type="submit" className={n.to === 'cancelled' || n.to === 'no_show' ? 'btn-quiet' : undefined}>{n.label}</button>
            </form>
          ))}
        </div>
      ) : null}

      <Section title="Repeats">
        <Card>
          {series ? (
            <>
              <p style={{ marginTop: 0 }}>
                {bk.occurrence_index} of {series.occurrences.length} · {series.status === 'ended' ? 'series ended' : 'weekly series'}
              </p>
              <ul>
                {series.occurrences.map((o) => (
                  <li key={o.id}>
                    {o.id === bk.id ? <strong>#{o.occurrence_index}</strong> : <Link href={`/b/${b}/bookings/${o.id}`}>#{o.occurrence_index}</Link>}{' '}
                    <LocalTime value={o.starts_at} /> · {STATUS[o.status] || o.status}
                  </li>
                ))}
              </ul>
              {series.status === 'active' && live ? (
                <>
                  <form action={changeLater} style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center', marginBottom: '0.5rem' }}>
                    <span>Move this and later ones by</span>
                    <label><input name="days" type="number" min={-6} max={6} defaultValue={0} style={{ width: '4.5rem' }} /> days</label>
                    <label><input name="minutes" type="number" min={-720} max={720} step={15} defaultValue={0} style={{ width: '5.5rem' }} /> minutes</label>
                    <button type="submit">Move</button>
                  </form>
                  <form action={endSeries}><button type="submit" className="btn-quiet">End the series from this one</button></form>
                </>
              ) : null}
            </>
          ) : live ? (
            <form action={repeat} style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
              <label>Every <select name="interval_weeks" defaultValue="1">{[1, 2, 3, 4].map((w) => <option key={w} value={w}>{w === 1 ? 'week' : `${w} weeks`}</option>)}</select></label>
              <label>for <input name="occurrences" type="number" min={2} max={52} defaultValue={4} style={{ width: '5rem' }} /> bookings</label>
              <button type="submit">Repeat</button>
            </form>
          ) : (
            <p style={{ margin: 0 }}>Not part of a series.</p>
          )}
        </Card>
      </Section>

      <MoneySection businessId={b} token={token} sourceType="booking" sourceId={params.bookingId} path={here} />
      <Section title="History">
        <ul>
          {history.map((h) => (
            <li key={String(h.id)}>
              {STATUS[String(h.from_status)] || '—'} → {STATUS[String(h.to_status)] || String(h.to_status)} (<LocalTime value={h.created_at as string | null} />)
              {h.reason ? ` · ${String(h.reason)}` : ''}
            </li>
          ))}
        </ul>
      </Section>
    </div>
  )
}
