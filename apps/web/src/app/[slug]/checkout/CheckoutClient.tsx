'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'
import {
  CartItem,
  cartStorageKey,
  placeCheckoutOrder,
  quoteDelivery,
} from '@/lib/checkout-api'

type Options = {
  fulfilment_modes: string[]
  payment_methods: string[]
  locations: Array<{ id: string; name: string; is_primary: boolean }>
  business: { display_name: string; slug: string }
}

export default function CheckoutClient({
  slug,
  options,
}: {
  slug: string
  options: Options
}) {
  const [items, setItems] = useState<CartItem[]>([])
  const [mode, setMode] = useState(options.fulfilment_modes[0] || '')
  const [paymentMethod, setPaymentMethod] = useState(options.payment_methods[0] || 'cod')
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [phone, setPhone] = useState('')
  const [city, setCity] = useState('')
  const [line1, setLine1] = useState('')
  const [postal, setPostal] = useState('')
  const [deliveryCharge, setDeliveryCharge] = useState(0)
  const [serviceable, setServiceable] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [confirmation, setConfirmation] = useState<{
    order_number: string
    tracking: { href: string }
    state: string
  } | null>(null)

  useEffect(() => {
    try {
      const raw = localStorage.getItem(cartStorageKey(slug))
      setItems(raw ? (JSON.parse(raw) as CartItem[]) : [])
    } catch {
      setItems([])
    }
  }, [slug])

  useEffect(() => {
    if (mode !== 'delivery' || !city) {
      setDeliveryCharge(0)
      setServiceable(true)
      return
    }
    quoteDelivery(slug, { city, line1, postal_code: postal })
      .then((q) => {
        setServiceable(Boolean(q.serviceable))
        setDeliveryCharge(Number(q.delivery_charge || 0))
      })
      .catch(() => {
        setServiceable(false)
        setDeliveryCharge(0)
      })
  }, [slug, mode, city, line1, postal])

  const subtotal = items.reduce((sum, i) => sum + i.unit_price * i.quantity, 0)
  const grand = subtotal + (mode === 'delivery' ? deliveryCharge : 0)

  function persist(next: CartItem[]) {
    setItems(next)
    localStorage.setItem(cartStorageKey(slug), JSON.stringify(next))
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    if (items.length === 0) {
      setError('Your cart is empty.')
      return
    }
    if (!mode) {
      setError('No fulfilment mode is available for this Business.')
      return
    }
    if (mode === 'delivery' && !serviceable) {
      setError('Delivery is not available for this address.')
      return
    }
    setSubmitting(true)
    try {
      const data = await placeCheckoutOrder(slug, {
        items: items.map((i) => ({
          offering_id: i.offering_id,
          quantity: i.quantity,
          unit_price: i.unit_price,
        })),
        fulfilment_mode: mode,
        payment_method: paymentMethod,
        location_id: options.locations.find((l) => l.is_primary)?.id || options.locations[0]?.id,
        delivery_address:
          mode === 'delivery' ? { city, line1, postal_code: postal } : undefined,
        guest: { name, email, phone: phone || undefined },
        idempotency_key: crypto.randomUUID(),
      })
      localStorage.removeItem(cartStorageKey(slug))
      setConfirmation({
        order_number: data.confirmation.order_number,
        tracking: data.tracking,
        state: data.state,
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Checkout failed')
    } finally {
      setSubmitting(false)
    }
  }

  if (confirmation) {
    return (
      <div style={{ maxWidth: '32rem', margin: '0 auto', padding: '2rem 1.25rem' }}>
        <h1>Order confirmed</h1>
        <p>
          Order <strong>{confirmation.order_number}</strong>
        </p>
        <p style={{ opacity: 0.8 }}>
          {confirmation.state === 'pending_offline'
            ? 'Pay when you collect your order.'
            : confirmation.state === 'paid'
              ? 'Payment received.'
              : 'The business has received your order.'}
        </p>
        <p>
          <Link href={confirmation.tracking.href}>Track your order</Link>
        </p>
        <p style={{ marginTop: '1.5rem' }}>
          <Link href={`/${slug}`}>Back to website</Link>
        </p>
      </div>
    )
  }

  return (
    <div style={{ maxWidth: '40rem', margin: '0 auto', padding: '2rem 1.25rem' }}>
      <p>
        <Link href={`/${slug}`}>← {options.business.display_name}</Link>
      </p>
      <h1 style={{ fontSize: '2rem', margin: '0.75rem 0' }}>Checkout</h1>

      {items.length === 0 ? (
        <section>
          <h2>Your cart is empty</h2>
          <p>Add offerings from the Business Website, then return here.</p>
          <Link href={`/${slug}`}>Browse offerings</Link>
        </section>
      ) : (
        <form onSubmit={onSubmit} style={{ display: 'grid', gap: '1.25rem' }}>
          <section>
            <h2>Cart</h2>
            <ul style={{ listStyle: 'none', padding: 0, display: 'grid', gap: '0.5rem' }}>
              {items.map((item) => (
                <li
                  key={item.offering_id}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    gap: '1rem',
                    padding: '0.6rem 0',
                    borderBottom: '1px solid rgba(0,0,0,0.08)',
                  }}
                >
                  <div>
                    <div style={{ fontWeight: 600 }}>{item.title}</div>
                    <div style={{ opacity: 0.7 }}>
                      {item.currency} {item.unit_price} × {item.quantity}
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => persist(items.filter((i) => i.offering_id !== item.offering_id))}
                  >
                    Remove
                  </button>
                </li>
              ))}
            </ul>
            <p>
              Subtotal: {items[0]?.currency || 'INR'} {subtotal.toFixed(2)}
            </p>
          </section>

          <section>
            <h2>Fulfilment</h2>
            {options.fulfilment_modes.length === 0 ? (
              <p>No pickup/delivery modes are configured.</p>
            ) : (
              <div style={{ display: 'flex', gap: '0.75rem' }}>
                {options.fulfilment_modes.map((m) => (
                  <label key={m}>
                    <input
                      type="radio"
                      name="mode"
                      checked={mode === m}
                      onChange={() => setMode(m)}
                    />{' '}
                    {m}
                  </label>
                ))}
              </div>
            )}
            {mode === 'delivery' ? (
              <div style={{ display: 'grid', gap: '0.5rem', marginTop: '0.75rem' }}>
                <input
                  placeholder="Address line"
                  value={line1}
                  onChange={(e) => setLine1(e.target.value)}
                  required
                />
                <input
                  placeholder="City"
                  value={city}
                  onChange={(e) => setCity(e.target.value)}
                  required
                />
                <input
                  placeholder="Postal code"
                  value={postal}
                  onChange={(e) => setPostal(e.target.value)}
                />
                <p>
                  {serviceable
                    ? `Delivery charge: ${deliveryCharge.toFixed(2)}`
                    : 'Address not in a delivery zone'}
                </p>
              </div>
            ) : null}
          </section>

          <section>
            <h2>Payment</h2>
            <div style={{ display: 'flex', gap: '0.75rem' }}>
              {options.payment_methods.map((m) => (
                <label key={m}>
                  <input
                    type="radio"
                    name="pay"
                    checked={paymentMethod === m}
                    onChange={() => setPaymentMethod(m)}
                  />{' '}
                  {m === 'cod' ? 'Cash on delivery' : 'Online'}
                </label>
              ))}
            </div>
          </section>

          <section>
            <h2>Contact</h2>
            <div style={{ display: 'grid', gap: '0.5rem' }}>
              <input
                placeholder="Name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
              />
              <input
                type="email"
                placeholder="Email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
              <input
                placeholder="Phone (optional)"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
              />
            </div>
          </section>

          <p style={{ fontWeight: 700 }}>
            Total: {items[0]?.currency || 'INR'} {grand.toFixed(2)}
          </p>
          {error ? <p style={{ color: '#b00020' }}>{error}</p> : null}
          <button type="submit" disabled={submitting || !mode}>
            {submitting ? 'Placing order…' : 'Place order'}
          </button>
        </form>
      )}
    </div>
  )
}
