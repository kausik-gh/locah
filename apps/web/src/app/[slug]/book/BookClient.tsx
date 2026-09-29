'use client'

import Link from 'next/link'
import { useMemo, useState } from 'react'
import {
  checkBookingAvailability,
  createPublicBooking,
} from '@/lib/booking-api'
import { useWords } from '@/components/website/SiteWords'

type Options = {
  business: { display_name: string; slug: string }
  locations: Array<{ id: string; name: string; status: string }>
  services: Array<{ id: string; title: string; price_amount: number | null }>
  providers: Array<{
    id: string
    display_name: string
    location_ids: string[]
    offering_ids: string[]
  }>
  policy: {
    require_deposit: boolean
    deposit_amount: number | null
    cancel_window_hours: number
  }
  payment_methods: string[]
}

export default function BookClient({
  slug,
  options,
  customer,
  authToken,
}: {
  slug: string
  options: Options
  /** The signed-in LOCAH customer, if any: the booking joins their own record. */
  customer?: { name: string; email: string } | null
  authToken?: string | null
}) {
  const t = useWords()
  const [locationId, setLocationId] = useState(options.locations[0]?.id || '')
  const [serviceId, setServiceId] = useState(options.services[0]?.id || '')
  const [providerId, setProviderId] = useState('')
  const [startsAt, setStartsAt] = useState('')
  const [endsAt, setEndsAt] = useState('')
  const [name, setName] = useState(customer?.name ?? '')
  const [email, setEmail] = useState(customer?.email ?? '')
  const [phone, setPhone] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [errorCode, setErrorCode] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [confirmation, setConfirmation] = useState<{
    id: string
    booking_number: string
    management_token: string
    deposit_required: boolean
    deposit_amount: number
    payment_status: string
  } | null>(null)

  const providers = useMemo(() => {
    return options.providers.filter((p) => {
      const locOk = !locationId || p.location_ids.includes(locationId)
      // When a service is selected, provider must be associated (server validates too).
      const svcOk = !serviceId || p.offering_ids.includes(serviceId)
      return locOk && svcOk
    })
  }, [options.providers, locationId, serviceId])

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setErrorCode(null)
    if (!locationId || !startsAt || !endsAt || !name || !email) {
      setError(t('Location, slot, and guest details are required.'))
      setErrorCode('policy_restriction')
      return
    }
    setSubmitting(true)
    try {
      const avail = await checkBookingAvailability(slug, {
        location_id: locationId,
        offering_id: serviceId || null,
        provider_id: providerId || null,
        reservation_mode: 'appointment',
        starts_at: new Date(startsAt).toISOString(),
        ends_at: new Date(endsAt).toISOString(),
        party_size: 1,
      })
      if (!avail.available) {
        setError(avail.reason || t('Selected slot is unavailable'))
        setErrorCode(avail.code || 'slot_conflict')
        setSubmitting(false)
        return
      }
      const data = await createPublicBooking(slug, {
        location_id: locationId,
        offering_id: serviceId || null,
        provider_id: providerId || null,
        reservation_mode: 'appointment',
        starts_at: new Date(startsAt).toISOString(),
        ends_at: new Date(endsAt).toISOString(),
        payment_method: options.payment_methods[0] || 'cod',
        guest: { name, email, phone: phone || null },
      }, authToken)
      setConfirmation({
        id: String(data.id),
        booking_number: String(data.booking_number),
        management_token: String(data.management_token),
        deposit_required: Boolean(data.deposit_required),
        deposit_amount: Number(data.deposit_amount || 0),
        payment_status: String(data.payment_status),
      })
    } catch (err) {
      const e = err as Error & { code?: string }
      setError(e.message)
      setErrorCode(e.code || null)
    } finally {
      setSubmitting(false)
    }
  }

  if (confirmation) {
    return (
      <main style={{ maxWidth: 640, margin: '0 auto', padding: '3rem 1.25rem' }}>
        <p style={{ letterSpacing: '0.08em', textTransform: 'uppercase', opacity: 0.65 }}>
          {options.business.display_name}
        </p>
        <h1 style={{ fontSize: '2.4rem', margin: '0.4rem 0 0.75rem' }}>{t('Confirmed')}</h1>
        <p>
          {t('Booking {number} is reserved.', { number: confirmation.booking_number })}
          {confirmation.deposit_required
            ? ` ${t('Deposit {amount}', { amount: confirmation.deposit_amount })} · ${confirmation.payment_status}.`
            : null}
        </p>
        <p style={{ marginTop: '1.25rem' }}>
          <Link
            href={`/${slug}/bookings/${confirmation.id}?token=${encodeURIComponent(confirmation.management_token)}`}
          >
            {t('Manage this booking')}
          </Link>
        </p>
      </main>
    )
  }

  return (
    <main style={{ maxWidth: 720, margin: '0 auto', padding: '3rem 1.25rem' }}>
      <p style={{ letterSpacing: '0.08em', textTransform: 'uppercase', opacity: 0.65 }}>
        {options.business.display_name}
      </p>
      <h1 style={{ fontSize: '2.6rem', margin: '0.35rem 0 0.5rem' }}>{t('Book')}</h1>
      <p style={{ opacity: 0.8, marginBottom: '1.75rem' }}>
        {t('Choose a location, service, provider, and time.')}
      </p>

      {errorCode === 'location_closed' ? (
        <p role="alert">{t('This location is closed. Pick another location.')}</p>
      ) : null}
      {errorCode === 'slot_conflict' ? (
        <p role="alert">{t('That slot is no longer available. Choose another time.')}</p>
      ) : null}
      {error && errorCode !== 'location_closed' && errorCode !== 'slot_conflict' ? (
        <p role="alert">{error}</p>
      ) : null}

      <form onSubmit={onSubmit} style={{ display: 'grid', gap: '0.9rem' }}>
        <label>
          {t('Location')}
          <select
            value={locationId}
            onChange={(e) => setLocationId(e.target.value)}
            style={{ display: 'block', width: '100%', marginTop: 4, padding: '0.55rem' }}
          >
            {options.locations.map((l) => (
              <option key={l.id} value={l.id}>
                {l.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          {t('Service')}
          <select
            value={serviceId}
            onChange={(e) => setServiceId(e.target.value)}
            style={{ display: 'block', width: '100%', marginTop: 4, padding: '0.55rem' }}
          >
            <option value="">{t('Any / none')}</option>
            {options.services.map((s) => (
              <option key={s.id} value={s.id}>
                {s.title}
              </option>
            ))}
          </select>
        </label>
        <label>
          {t('Provider')}
          <select
            value={providerId}
            onChange={(e) => setProviderId(e.target.value)}
            style={{ display: 'block', width: '100%', marginTop: 4, padding: '0.55rem' }}
          >
            <option value="">{t('No preference')}</option>
            {providers.map((p) => (
              <option key={p.id} value={p.id}>
                {p.display_name}
              </option>
            ))}
          </select>
        </label>
        <label>
          {t('Starts')}
          <input
            type="datetime-local"
            value={startsAt}
            onChange={(e) => setStartsAt(e.target.value)}
            required
            style={{ display: 'block', width: '100%', marginTop: 4, padding: '0.55rem' }}
          />
        </label>
        <label>
          {t('Ends')}
          <input
            type="datetime-local"
            value={endsAt}
            onChange={(e) => setEndsAt(e.target.value)}
            required
            style={{ display: 'block', width: '100%', marginTop: 4, padding: '0.55rem' }}
          />
        </label>
        <label>
          {t('Name')}
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            style={{ display: 'block', width: '100%', marginTop: 4, padding: '0.55rem' }}
          />
        </label>
        <label>
          {t('Email')}
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            readOnly={Boolean(customer)}
            required
            style={{ display: 'block', width: '100%', marginTop: 4, padding: '0.55rem' }}
          />
        </label>
        <label>
          {t('Phone')}
          <input
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            style={{ display: 'block', width: '100%', marginTop: 4, padding: '0.55rem' }}
          />
        </label>
        {options.policy.require_deposit ? (
          <p style={{ opacity: 0.85 }}>
            {t('A deposit of {amount} is required.', { amount: options.policy.deposit_amount ?? '' })}
          </p>
        ) : null}
        <button type="submit" className="ls-btn" disabled={submitting} style={{ marginTop: '0.5rem' }}>
          {submitting ? t('Booking…') : t('Confirm booking')}
        </button>
      </form>
    </main>
  )
}
