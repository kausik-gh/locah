'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'
import { claimWaitlistOffer, fetchWaitlistOffer, type WaitlistOffer } from '@/lib/booking-api'
import { LANG_LOCALE } from '@/lib/site-words'
import { useSiteLang, useWords } from '@/components/website/SiteWords'

function when(raw: string, locale?: string): string {
  const d = new Date(raw)
  if (Number.isNaN(d.getTime())) return raw
  return d.toLocaleString(locale, { weekday: 'short', day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' })
}

export default function WaitlistOfferClient({ slug, entryId, token }: { slug: string; entryId: string; token: string }) {
  const t = useWords()
  const lang = useSiteLang()
  const locale = lang === 'en' ? undefined : LANG_LOCALE[lang]
  const [offer, setOffer] = useState<WaitlistOffer | null | 'missing'>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [booked, setBooked] = useState<{ id: string; number: string; manage: string } | null>(null)

  useEffect(() => {
    fetchWaitlistOffer(slug, entryId, token).then((o) => setOffer(o ?? 'missing')).catch(() => setOffer('missing'))
  }, [slug, entryId, token])

  async function take() {
    setBusy(true)
    setError(null)
    try {
      const b = await claimWaitlistOffer(slug, entryId, token)
      setBooked({ id: b.id, number: b.booking_number, manage: b.management_token })
    } catch (e) {
      const code = (e as Error & { code?: string }).code
      setError(code === 'offer_expired' ? t('This offer has run out') : t('Sorry - that place has just been taken'))
    } finally {
      setBusy(false)
    }
  }

  const box = { maxWidth: 640, margin: '0 auto', padding: '3rem 1.25rem' }
  if (offer === null) return <main style={box}><p>{t('Loading…')}</p></main>
  if (offer === 'missing') return <main style={box}><h1>{t('This offer has run out')}</h1></main>
  if (booked) {
    return (
      <main style={box}>
        <h1 style={{ fontSize: '2.2rem', margin: '0 0 0.75rem' }}>{t('It is yours')}</h1>
        <p>{t('Booking {number} is reserved.', { number: booked.number })}</p>
        <p style={{ marginTop: '1.25rem' }}>
          <Link href={`/${slug}/bookings/${booked.id}?token=${encodeURIComponent(booked.manage)}`}>{t('Manage this booking')}</Link>
        </p>
      </main>
    )
  }
  return (
    <main style={box}>
      <p style={{ letterSpacing: '0.08em', textTransform: 'uppercase', opacity: 0.65 }}>{offer.business.display_name}</p>
      <h1 style={{ fontSize: '2.2rem', margin: '0.4rem 0 0.75rem' }}>{t('A place opened up')}</h1>
      <p>
        {offer.title} · {when(offer.starts_at, locale)}
        {offer.party_size > 1 ? ` · ${t('Party of {n}', { n: offer.party_size })}` : ''}
      </p>
      {offer.can_take && offer.offer_expires_at ? (
        <>
          <p>{t('Kept for you until {time}.', { time: when(offer.offer_expires_at, locale) })}</p>
          <button type="button" onClick={take} disabled={busy} style={{ marginTop: '1rem' }}>
            {busy ? t('Taking it…') : t('Take this place')}
          </button>
        </>
      ) : (
        <p>{offer.status === 'booked' ? t('You have already taken this place.') : t('This offer has run out')}</p>
      )}
      {error ? <p role="alert" style={{ marginTop: '1rem' }}>{error}</p> : null}
    </main>
  )
}
