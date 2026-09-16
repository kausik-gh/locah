'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'
import { CartItem, cartStorageKey, fetchPublicOfferings } from '@/lib/checkout-api'

export function OfferingsListSection({
  businessSlug,
  title,
  subtitle,
}: {
  businessSlug: string
  title: string
  subtitle?: string
}) {
  const [offerings, setOfferings] = useState<
    Array<{
      id: string
      title: string
      description?: string | null
      price_amount?: number | null
      currency?: string
    }>
  >([])

  useEffect(() => {
    fetchPublicOfferings(businessSlug).then((data) => {
      setOfferings((data.offerings || []) as typeof offerings)
    })
  }, [businessSlug])

  function addToCart(o: (typeof offerings)[number]) {
    const key = cartStorageKey(businessSlug)
    const existing: CartItem[] = JSON.parse(localStorage.getItem(key) || '[]')
    const found = existing.find((i) => i.offering_id === o.id)
    if (found) found.quantity += 1
    else {
      existing.push({
        offering_id: o.id,
        title: o.title,
        quantity: 1,
        unit_price: Number(o.price_amount || 0),
        currency: o.currency || 'INR',
      })
    }
    localStorage.setItem(key, JSON.stringify(existing))
  }

  return (
    <section style={{ padding: '2.5rem 1.5rem', maxWidth: '48rem', margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem' }}>
        <div>
          <h2>{title}</h2>
          {subtitle ? <p>{subtitle}</p> : null}
        </div>
        <Link href={`/${businessSlug}/checkout`}>Cart / Checkout</Link>
      </div>
      <ul style={{ listStyle: 'none', padding: 0, display: 'grid', gap: '0.75rem', marginTop: '1rem' }}>
        {offerings.map((o) => (
          <li
            key={o.id}
            style={{
              padding: '0.9rem 1rem',
              background: 'rgba(255,255,255,0.7)',
              border: '1px solid rgba(0,0,0,0.08)',
              display: 'flex',
              justifyContent: 'space-between',
              gap: '1rem',
            }}
          >
            <div>
              <div style={{ fontWeight: 700 }}>{o.title}</div>
              {o.description ? <p style={{ opacity: 0.8 }}>{o.description}</p> : null}
              <div style={{ opacity: 0.75 }}>
                {o.currency || 'INR'} {o.price_amount ?? '—'}
              </div>
            </div>
            <button type="button" onClick={() => addToCart(o)}>
              Add
            </button>
          </li>
        ))}
      </ul>
      {offerings.length === 0 ? <p style={{ opacity: 0.7 }}>No public offerings yet.</p> : null}
    </section>
  )
}
