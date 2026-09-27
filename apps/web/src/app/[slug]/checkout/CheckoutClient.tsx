'use client'

import Link from 'next/link'
import { useEffect, useRef, useState } from 'react'
import {
  CartItem,
  cartStorageKey,
  placeCheckoutOrder,
  quoteDelivery,
  verifyCheckoutPayment,
} from '@/lib/checkout-api'

type Options = {
  fulfilment_modes: string[]
  payment_methods: string[]
  locations: Array<{ id: string; name: string; is_primary: boolean }>
  business: { display_name: string; slug: string }
}

type RazorpayCheckout = {
  provider: 'razorpay'
  order_id: string
  key_id: string
  amount: number
  currency: string
}

type CashfreeCheckout = {
  provider: 'cashfree'
  order_id: string
  payment_session_id: string
  mode: 'sandbox'
  amount: number
  currency: string
}

type CheckoutSession = RazorpayCheckout | CashfreeCheckout

type CashfreeSdk = {
  checkout: (options: { paymentSessionId: string; redirectTarget: '_modal' }) => Promise<{
    error?: { message?: string }
    redirect?: boolean
    paymentDetails?: unknown
  }>
}

let cashfreeSdk: CashfreeSdk | null = null

function loadCashfreeScript(): Promise<void> {
  if (typeof window === 'undefined') return Promise.resolve()
  if ((window as unknown as { Cashfree?: unknown }).Cashfree) return Promise.resolve()
  return new Promise((resolve, reject) => {
    const script = document.createElement('script')
    script.src = 'https://sdk.cashfree.com/js/v3/cashfree.js'
    script.async = true
    script.onload = () => resolve()
    script.onerror = () => reject(new Error('Could not load secure checkout.'))
    document.body.appendChild(script)
  })
}

function loadRazorpayScript(): Promise<void> {
  if (typeof window === 'undefined') return Promise.resolve()
  if (document.querySelector('script[src="https://checkout.razorpay.com/v1/checkout.js"]')) {
    return Promise.resolve()
  }
  return new Promise((resolve, reject) => {
    const script = document.createElement('script')
    script.src = 'https://checkout.razorpay.com/v1/checkout.js'
    script.async = true
    script.onload = () => resolve()
    script.onerror = () => reject(new Error('Could not load Razorpay Checkout.'))
    document.body.appendChild(script)
  })
}

function openRazorpayCheckout(checkout: RazorpayCheckout, name: string) {
  void loadRazorpayScript().then(() => {
    const RazorpayCtor = (window as unknown as { Razorpay?: new (opts: Record<string, unknown>) => { open: () => void } }).Razorpay
    if (!RazorpayCtor) return
    const rzp = new RazorpayCtor({
      key: checkout.key_id,
      amount: Math.round(checkout.amount * 100),
      currency: checkout.currency,
      order_id: checkout.order_id,
      name,
      handler: () => {
        window.location.reload()
      },
    })
    rzp.open()
  })
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
  const openedCheckoutId = useRef<string | null>(null)
  const [confirmation, setConfirmation] = useState<{
    order_number: string
    tracking: { href: string; order_id: string; token: string }
    orderId: string
    token: string
    state: string
    checkout?: CheckoutSession | null
    paymentError?: string | null
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

  useEffect(() => {
    if (confirmation?.checkout && openedCheckoutId.current !== confirmation.checkout.order_id) {
      openedCheckoutId.current = confirmation.checkout.order_id
      if (confirmation.checkout.provider === 'cashfree') {
        void openCashfreeCheckout(confirmation.checkout, confirmation.orderId, confirmation.token)
      } else {
        openRazorpayCheckout(confirmation.checkout as RazorpayCheckout, options.business.display_name)
      }
    }
    // The provider session opens once on initial order placement. A retry is
    // deliberately user-initiated using the button below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [confirmation, options.business.display_name])

  async function openCashfreeCheckout(checkout: CashfreeCheckout, orderId: string, token: string) {
    try {
      await loadCashfreeScript()
      const factory = (window as unknown as {
        Cashfree?: (options: { mode: 'sandbox' }) => CashfreeSdk
      }).Cashfree
      if (!factory) throw new Error('Secure checkout is unavailable')
      cashfreeSdk ??= factory({ mode: 'sandbox' })
      const result = await cashfreeSdk.checkout({
        paymentSessionId: checkout.payment_session_id,
        redirectTarget: '_modal',
      })
      if (result.error) {
        setConfirmation((current) => current ? {
          ...current, paymentError: result.error?.message || 'Checkout closed. No payment was confirmed.',
        } : current)
      }
      if (result.redirect) return
      // paymentDetails is only an SDK result, not proof of a paid order.
      // SDK completion is not proof of payment. Verify with Cashfree on server.
      const status = await verifyCheckoutPayment(orderId, token)
      if (status === 'succeeded') localStorage.removeItem(cartStorageKey(slug))
      setConfirmation((current) => current ? { ...current, state: status } : current)
    } catch (err) {
      setConfirmation((current) => current ? {
        ...current,
        state: 'processing',
        paymentError: err instanceof Error ? err.message : 'Payment status is still being checked',
      } : current)
    }
  }

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
          // Prices shown in the cart are illustrative. Server reprices.
        })),
        fulfilment_mode: mode,
        payment_method: paymentMethod,
        location_id: options.locations.find((l) => l.is_primary)?.id || options.locations[0]?.id,
        delivery_address:
          mode === 'delivery' ? { city, line1, postal_code: postal } : undefined,
        guest: { name, email, phone: phone || undefined },
        idempotency_key: crypto.randomUUID(),
      })
      const payment = data.payment as
        | {
            checkout?: CheckoutSession
            failure_reason?: string
          }
        | null
        | undefined
      setConfirmation({
        order_number: data.confirmation.order_number,
        tracking: data.tracking,
        orderId: data.tracking.order_id,
        token: data.tracking.token,
        state: data.state,
        checkout: payment?.checkout ?? null,
        paymentError: payment?.failure_reason ?? null,
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Checkout failed')
    } finally {
      setSubmitting(false)
    }
  }

  if (confirmation) {
    const paid = confirmation.state === 'succeeded' || confirmation.state === 'paid'
    const cashfree = confirmation.checkout?.provider === 'cashfree'
    return (
      <div style={{ maxWidth: '32rem', margin: '0 auto', padding: '2rem 1.25rem' }}>
        <h1>
          {paid ? 'Payment successful'
            : confirmation.checkout
            ? confirmation.paymentError ? 'Payment not confirmed' : 'Confirming your payment'
            : confirmation.state === 'payment_failed' || confirmation.state === 'failed'
              ? 'Order placed — payment did not go through'
              : 'Order confirmed'}
        </h1>
        <p>
          Order <strong>{confirmation.order_number}</strong>
        </p>
        <p style={{ opacity: 0.8 }}>
          {paid ? 'Payment verified by the server. Your order can now be fulfilled.'
            : confirmation.checkout
            ? confirmation.paymentError || 'Your order is held while we confirm the payment. Do not pay twice.'
            : confirmation.state === 'pending_offline'
              ? 'Pay when you collect your order.'
              : confirmation.paymentError
                  ? confirmation.paymentError
                  : 'The business has received your order.'}
        </p>
        {error ? <p role="alert" style={{ color: '#b00020' }}>{error}</p> : null}
        {!paid && cashfree ? <p>
          <button type="button" onClick={() => {
            void verifyCheckoutPayment(confirmation.orderId, confirmation.token).then((status) => {
              setConfirmation((current) => current ? { ...current, state: status } : current)
            }).catch((err) => setError(err instanceof Error ? err.message : 'Could not check status'))
          }}>Check payment status</button>
        </p> : null}
        {!paid && confirmation.checkout && (!cashfree || confirmation.paymentError) ? (
          <p>
            <button
              type="button"
              onClick={() => {
                if (confirmation.checkout?.provider === 'cashfree') {
                  void openCashfreeCheckout(confirmation.checkout, confirmation.orderId, confirmation.token)
                } else if (confirmation.checkout) {
                  openRazorpayCheckout(confirmation.checkout as RazorpayCheckout, options.business.display_name)
                }
              }}
            >
              {cashfree ? 'Try secure payment again' : 'Pay now'}
            </button>
          </p>
        ) : null}
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
                placeholder={paymentMethod === 'online' ? 'Phone for secure payment' : 'Phone (optional)'}
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                required={paymentMethod === 'online'}
              />
            </div>
          </section>

          <p style={{ fontWeight: 700 }}>
            Total: {items[0]?.currency || 'INR'} {grand.toFixed(2)}
          </p>
          {error ? <p style={{ color: '#b00020' }}>{error}</p> : null}
          <button type="submit" disabled={submitting || !mode}>
            {submitting
              ? 'Placing order…'
              : paymentMethod === 'online'
                ? 'Place order and pay'
                : 'Place order'}
          </button>
        </form>
      )}
    </div>
  )
}
