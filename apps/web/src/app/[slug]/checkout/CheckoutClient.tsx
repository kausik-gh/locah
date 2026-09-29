'use client'

import Link from 'next/link'
import { useEffect, useMemo, useState } from 'react'
import {
  CartItem,
  cartStorageKey,
  fetchGstStates,
  placeCheckoutOrder,
  priceCart,
  type PricedCart,
} from '@/lib/checkout-api'

type Options = {
  fulfilment_modes: string[]
  payment_methods: string[]
  /** Cash on delivery as the business set it (the same rule as its WhatsApp orders). */
  cod?: { on_delivery: boolean; first_order_cap: number | null }
  locations: Array<{ id: string; name: string; is_primary: boolean }>
  business: { display_name: string; slug: string }
}

type RazorpayCheckout = {
  provider: string
  order_id: string
  key_id: string
  amount: number
  currency: string
}

// The legacy online checkout (frozen, not extended — founder 2026-09-27): only
// for a business whose old Razorpay connection is still active.
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
    script.onerror = () => reject(new Error('Could not load the payment page.'))
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
      handler: () => window.location.reload(),
    })
    rzp.open()
  })
}

const rupees = (v: number | null | undefined) =>
  v === null || v === undefined
    ? ''
    : new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: Number.isInteger(v) ? 0 : 2 }).format(v)

const hour = (hhmm: string) => {
  const [h, m] = hhmm.split(':').map(Number)
  const suffix = h >= 12 ? 'pm' : 'am'
  const h12 = h % 12 === 0 ? 12 : h % 12
  return m ? `${h12}:${String(m).padStart(2, '0')} ${suffix}` : `${h12} ${suffix}`
}

const MODE_WORDS: Record<string, string> = { pickup: 'Pickup', delivery: 'Delivery', shipping: 'Shipping' }

type Confirmation = {
  order_number: string
  tracking: { href: string }
  state: string
  due_words: string | null
  advance: { amount: number; path: string } | null
  checkout?: RazorpayCheckout | null
  paymentError?: string | null
}

/**
 * The website checkout (Founder refinement — Orders & Customer Transactions):
 * basket → pickup or delivery → address → the day it is wanted (made-to-order
 * items) → how to pay → the server's prices, tax, delivery charge and advance →
 * place → confirmation, tracking and My Activity. Every amount on this page
 * comes from the server; the basket's own numbers are never sent.
 */
export default function CheckoutClient({
  slug,
  options,
  customer,
  authToken,
  reorder,
  unavailable,
}: {
  slug: string
  options: Options
  /** The signed-in LOCAH customer, if any: the order joins their own record. */
  customer?: { name: string; email: string } | null
  authToken?: string | null
  /** "Order again": the lines of an earlier order at today's price. */
  reorder?: CartItem[] | null
  unavailable?: string[]
}) {
  const [items, setItems] = useState<CartItem[]>([])
  const [loaded, setLoaded] = useState(false)
  const [mode, setMode] = useState(options.fulfilment_modes[0] || '')
  const [paymentMethod, setPaymentMethod] = useState(options.payment_methods[0] || 'cod')
  const [name, setName] = useState(customer?.name ?? '')
  const [email, setEmail] = useState('')
  const [phone, setPhone] = useState('')
  const [city, setCity] = useState('')
  const [line1, setLine1] = useState('')
  const [postal, setPostal] = useState('')
  const [stateCode, setStateCode] = useState('')
  const [states, setStates] = useState<{ code: string; name: string }[]>([])
  const [dueDate, setDueDate] = useState('')
  const [dueTime, setDueTime] = useState('')
  const [priced, setPriced] = useState<PricedCart | null>(null)
  const [pricing, setPricing] = useState(false)
  const [priceError, setPriceError] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [confirmation, setConfirmation] = useState<Confirmation | null>(null)

  useEffect(() => {
    if (reorder && reorder.length) {
      setItems(reorder)
      try {
        localStorage.setItem(cartStorageKey(slug), JSON.stringify(reorder))
      } catch {
        /* storage unavailable — the cart still holds the lines */
      }
    } else {
      try {
        const raw = localStorage.getItem(cartStorageKey(slug))
        setItems(raw ? (JSON.parse(raw) as CartItem[]) : [])
      } catch {
        setItems([])
      }
    }
    setLoaded(true)
  }, [slug, reorder])

  useEffect(() => {
    if (mode === 'delivery' && !states.length) fetchGstStates().then(setStates).catch(() => setStates([]))
  }, [mode, states.length])

  const cartBody = useMemo(
    () =>
      items.map((i) => ({ offering_id: i.offering_id, variant_id: i.variant_id, quantity: i.quantity, options: i.options })),
    [items]
  )
  const due = dueDate ? { date: dueDate, time: dueTime } : null
  const address = mode === 'delivery' ? { city, line1, postal_code: postal, state_code: stateCode || undefined } : undefined

  // The server prices the basket whenever something that changes the total changes.
  useEffect(() => {
    if (!items.length) {
      setPriced(null)
      return
    }
    let live = true
    setPricing(true)
    const t = setTimeout(() => {
      priceCart(slug, { items: cartBody, fulfilment_mode: mode || undefined, delivery_address: address, due })
        .then((p) => {
          if (!live) return
          setPriced(p)
          setPriceError(null)
          if (p.preorder.offered && !dueDate && p.preorder.needed) {
            const first = p.preorder.dates.find((d) => !d.full)
            if (first) {
              setDueDate(first.date)
              setDueTime(first.times[0])
            }
          }
        })
        .catch((e: unknown) => live && setPriceError(e instanceof Error ? e.message : 'We could not price your basket.'))
        .finally(() => live && setPricing(false))
    }, 250)
    return () => {
      live = false
      clearTimeout(t)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slug, cartBody, mode, city, line1, postal, stateCode, dueDate, dueTime])

  const pre = priced?.preorder
  const day = pre?.dates.find((d) => d.date === dueDate)
  const delivery = mode === 'delivery' ? priced?.delivery : null
  const payingNow = pre && pre.advance > 0 && dueDate ? pre.advance : 0
  const cod = priced?.cod ?? options.cod

  function persist(next: CartItem[]) {
    setItems(next)
    try {
      localStorage.setItem(cartStorageKey(slug), JSON.stringify(next))
    } catch {
      /* storage unavailable */
    }
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    if (!items.length) return setError('Your basket is empty.')
    if (!mode) return setError('This business is not taking pickup or delivery orders right now.')
    if (mode === 'delivery' && delivery && !delivery.serviceable) return setError('We do not deliver to this address yet.')
    if (pre?.needed && !dueDate) return setError('Choose the day you need it.')
    setSubmitting(true)
    try {
      const data = await placeCheckoutOrder(
        slug,
        {
          // Prices are never sent: the server prices each line from the catalogue.
          items: cartBody,
          fulfilment_mode: mode,
          payment_method: paymentMethod,
          location_id: options.locations.find((l) => l.is_primary)?.id || options.locations[0]?.id,
          delivery_address: address,
          guest: customer ? { name: name || customer.name, phone: phone || undefined } : { name, email, phone: phone || undefined },
          due: pre?.offered && dueDate ? due : undefined,
          idempotency_key: crypto.randomUUID(),
        },
        authToken
      )
      localStorage.removeItem(cartStorageKey(slug))
      const payment = data.payment as { checkout?: RazorpayCheckout; failure_reason?: string } | null | undefined
      setConfirmation({
        order_number: data.confirmation.order_number,
        tracking: data.tracking,
        state: data.state,
        due_words: pre?.offered && dueDate && day ? `${day.label}, ${hour(dueTime)}` : null,
        advance: data.advance ? { amount: data.advance.amount, path: data.advance.path } : null,
        checkout: payment?.checkout ?? null,
        paymentError: payment?.failure_reason ?? null,
      })
      if (payment?.checkout) openRazorpayCheckout(payment.checkout, options.business.display_name)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'That did not go through. Try again.')
    } finally {
      setSubmitting(false)
    }
  }

  if (confirmation) {
    return (
      <main className="ls-section">
        <div className="ls-inner ls-checkout">
          <header className="ls-bill__head">
            <p className="ls-meta">{options.business.display_name}</p>
            <h1 className="ls-title">Order confirmed</h1>
            <p className="ls-meta">Order {confirmation.order_number}{confirmation.due_words ? ` · ready ${confirmation.due_words}` : ''}</p>
          </header>
          {confirmation.advance ? (
            <div className="ls-bill__card">
              <p style={{ margin: 0 }}>
                Please pay the <strong>{rupees(confirmation.advance.amount)}</strong> advance to confirm your order. The rest is paid when you collect it.
              </p>
              <div className="ls-bill__actions">
                <Link className="ls-btn" href={confirmation.advance.path}>Pay {rupees(confirmation.advance.amount)} advance</Link>
              </div>
            </div>
          ) : (
            <p className="ls-meta">
              {confirmation.checkout && !['succeeded', 'paid'].includes(confirmation.state)
                ? 'Your order is held. Finish the payment to confirm it.'
                : confirmation.state === 'paid' || confirmation.state === 'succeeded'
                  ? 'Payment received.'
                  : confirmation.paymentError || (mode === 'delivery' ? 'Pay when it is delivered.' : 'Pay when you collect your order.')}
            </p>
          )}
          {confirmation.checkout ? (
            <button type="button" className="ls-btn" onClick={() => openRazorpayCheckout(confirmation.checkout!, options.business.display_name)}>
              Pay now
            </button>
          ) : null}
          <div className="ls-bill__actions">
            <Link className="ls-btn ls-btn--outline" href={confirmation.tracking.href}>Track your order</Link>
            <Link className="ls-btn ls-btn--outline" href={`/${slug}`}>Back to {options.business.display_name}</Link>
          </div>
        </div>
      </main>
    )
  }

  return (
    <main className="ls-section">
      <div className="ls-inner ls-checkout">
        <p>
          <Link href={`/${slug}`}>← {options.business.display_name}</Link>
        </p>
        <h1 className="ls-title">Your order</h1>
        {reorder && reorder.length ? <p className="ls-meta" role="status">Your earlier order, at today&apos;s prices. Change anything before you place it.</p> : null}
        {unavailable && unavailable.length ? <p className="ls-meta" role="status">No longer sold: {unavailable.join(', ')}.</p> : null}

        {loaded && items.length === 0 ? (
          <section className="ls-bill__card">
            <h2 className="ls-checkout__h">Your basket is empty</h2>
            <Link className="ls-btn" href={`/${slug}`}>See what {options.business.display_name} sells</Link>
          </section>
        ) : (
          <form onSubmit={onSubmit} className="ls-checkout__form">
            <section className="ls-bill__card" aria-labelledby="basket-h">
              <h2 id="basket-h" className="ls-checkout__h">Basket</h2>
              <ul className="ls-bill__lines">
                {items.map((item, idx) => {
                  const line = priced?.lines[idx]
                  return (
                    <li key={item.key ?? item.offering_id}>
                      <span>
                        {item.quantity} × {line?.title ?? item.title}
                        {!line && item.detail ? <small>{item.detail}</small> : null}
                      </span>
                      <span className="ls-checkout__line-end">
                        <strong>{line ? rupees(line.line_total) : '…'}</strong>
                        <button type="button" className="ls-checkout__remove"
                          onClick={() => persist(items.filter((i) => (i.key ?? i.offering_id) !== (item.key ?? item.offering_id)))}>
                          Remove
                        </button>
                      </span>
                    </li>
                  )
                })}
              </ul>
              {priced?.problems.length ? (
                <p className="ls-offer__error" role="alert">
                  {priced.problems.map((p) => `${p.title}: ${p.message}`).join(' · ')} — change the quantity or remove it.
                </p>
              ) : null}
            </section>

            <section className="ls-bill__card" aria-labelledby="how-h">
              <h2 id="how-h" className="ls-checkout__h">How you get it</h2>
              {options.fulfilment_modes.length === 0 ? (
                <p className="ls-meta">This business is not taking pickup or delivery orders right now.</p>
              ) : (
                <div className="ls-choice" role="radiogroup" aria-label="Pickup or delivery">
                  {options.fulfilment_modes.map((m) => (
                    <button key={m} type="button" role="radio" aria-checked={mode === m} className={`ls-chip${mode === m ? ' is-on' : ''}`}
                      onClick={() => setMode(m)}>
                      {MODE_WORDS[m] || m}
                    </button>
                  ))}
                </div>
              )}
              {mode === 'delivery' ? (
                <div className="ls-checkout__fields">
                  <label><span>Address</span><input name="line1" value={line1} onChange={(e) => setLine1(e.target.value)} required autoComplete="street-address" /></label>
                  <label><span>City</span><input name="city" value={city} onChange={(e) => setCity(e.target.value)} required autoComplete="address-level2" /></label>
                  <label><span>PIN code</span><input name="postal_code" value={postal} onChange={(e) => setPostal(e.target.value.replace(/[^\d]/g, ''))} inputMode="numeric" maxLength={6} autoComplete="postal-code" /></label>
                  {states.length ? (
                    <label><span>State</span>
                      <select value={stateCode} onChange={(e) => setStateCode(e.target.value)}>
                        <option value="">Choose</option>
                        {states.map((s) => <option key={s.code} value={s.code}>{s.name}</option>)}
                      </select>
                    </label>
                  ) : null}
                  {delivery ? (
                    <p className="ls-meta">{delivery.serviceable ? `Delivery charge ${rupees(delivery.charge ?? 0)}` : 'We do not deliver to this address yet.'}</p>
                  ) : null}
                </div>
              ) : null}
            </section>

            {pre?.offered ? (
              <section className="ls-bill__card" aria-labelledby="when-h">
                <h2 id="when-h" className="ls-checkout__h">{pre.needed ? 'When do you need it?' : 'Want it on a particular day?'}</h2>
                {pre.earliest_words ? <p className="ls-meta">Made to order — the earliest is {pre.earliest_words}.</p> : null}
                {pre.dates.filter((d) => !d.full).length === 0 ? (
                  <p className="ls-offer__error" role="alert">No day is open for these items right now. Call the business to ask.</p>
                ) : (
                  <div className="ls-checkout__fields">
                    <label>
                      <span>Day</span>
                      <select value={dueDate} onChange={(e) => {
                        const d = pre.dates.find((x) => x.date === e.target.value)
                        setDueDate(e.target.value)
                        setDueTime(d?.times[0] ?? '')
                      }}>
                        {!pre.needed ? <option value="">As soon as possible</option> : null}
                        {pre.dates.map((d) => (
                          <option key={d.date} value={d.date} disabled={d.full}>{d.label}{d.full ? ' — full' : ''}</option>
                        ))}
                      </select>
                    </label>
                    {day ? (
                      <label>
                        <span>Ready at</span>
                        <select value={dueTime} onChange={(e) => setDueTime(e.target.value)}>
                          {day.times.map((t) => <option key={t} value={t}>{hour(t)}</option>)}
                        </select>
                      </label>
                    ) : null}
                  </div>
                )}
                {priced?.due_error ? <p className="ls-offer__error" role="alert">{priced.due_error}</p> : null}
                {pre.cancel_hours !== null && pre.cancel_hours !== undefined ? (
                  <p className="ls-meta">You can cancel up to {pre.cancel_hours} hours before it is due.</p>
                ) : null}
              </section>
            ) : null}

            <section className="ls-bill__card" aria-labelledby="pay-h">
              <h2 id="pay-h" className="ls-checkout__h">Paying</h2>
              <div className="ls-choice" role="radiogroup" aria-label="How you pay">
                {options.payment_methods.map((m) => (
                  <button key={m} type="button" role="radio" aria-checked={paymentMethod === m}
                    className={`ls-chip${paymentMethod === m ? ' is-on' : ''}`} onClick={() => setPaymentMethod(m)}>
                    {m === 'cod' ? (mode === 'delivery' ? 'Cash on delivery' : 'Pay at pickup') : 'Pay online'}
                  </button>
                ))}
              </div>
              {payingNow > 0 ? (
                <p className="ls-meta">This order asks for a {rupees(payingNow)} advance — you pay it by UPI right after placing the order.</p>
              ) : null}
              {mode === 'delivery' && paymentMethod === 'cod' && cod && !cod.on_delivery ? (
                <p className="ls-meta">Cash on delivery is not available. Choose pickup to pay when you collect.</p>
              ) : null}
              {mode === 'delivery' && paymentMethod === 'cod' && cod?.on_delivery && cod.first_order_cap !== null ? (
                <p className="ls-meta">For a first order, cash on delivery is up to {rupees(cod.first_order_cap)}.</p>
              ) : null}
            </section>

            <section className="ls-bill__card" aria-labelledby="you-h">
              <h2 id="you-h" className="ls-checkout__h">Your details</h2>
              {customer ? (
                <p className="ls-meta">
                  Ordering as <strong>{customer.name || customer.email}</strong> · {customer.email}. It will be in{' '}
                  <Link href={`/${slug}/account`}>your account</Link>.
                </p>
              ) : (
                <p className="ls-meta">
                  <a href={`/login?destination=${encodeURIComponent(`/${slug}/checkout`)}`}>Sign in</a> to keep this order with your others, or order as a guest.
                </p>
              )}
              <div className="ls-checkout__fields">
                <label><span>Name</span><input name="name" aria-label="Name" value={name} onChange={(e) => setName(e.target.value)} required autoComplete="name" /></label>
                {customer ? null : (
                  <label><span>Email</span><input name="email" type="email" aria-label="Email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" /></label>
                )}
                <label><span>Phone (for updates on WhatsApp)</span><input name="phone" aria-label="Phone" value={phone} onChange={(e) => setPhone(e.target.value)} inputMode="tel" autoComplete="tel" /></label>
              </div>
            </section>

            <section className="ls-bill__card" aria-label="Total">
              <dl className="ls-bill__totals">
                <dt>Items</dt>
                <dd>{priced ? rupees(priced.items_total) : '…'}</dd>
                {priced && priced.tax_amount > 0 ? (
                  <>
                    <dt>GST{priced.tax_included ? ' (included)' : ''}</dt>
                    <dd>{rupees(priced.tax_amount)}</dd>
                  </>
                ) : null}
                {delivery?.serviceable ? (
                  <>
                    <dt>Delivery</dt>
                    <dd>{rupees(delivery.charge ?? 0)}</dd>
                  </>
                ) : null}
                <dt className="is-total">Total</dt>
                <dd className="is-total">{priced ? rupees(priced.total) : '…'}</dd>
                {payingNow > 0 && priced ? (
                  <>
                    <dt>Advance now</dt>
                    <dd>{rupees(payingNow)}</dd>
                    <dt>Balance at {mode === 'delivery' ? 'delivery' : 'pickup'}</dt>
                    <dd>{rupees(Math.max(0, priced.total - payingNow))}</dd>
                  </>
                ) : null}
              </dl>
              {priceError ? <p className="ls-offer__error" role="alert">{priceError}</p> : null}
              {error ? <p className="ls-offer__error" role="alert">{error}</p> : null}
              <button type="submit" className="ls-btn ls-checkout__place" disabled={submitting || pricing || !mode || !priced}>
                {submitting
                  ? 'Placing your order…'
                  : paymentMethod === 'online'
                    ? 'Place order and pay'
                    : payingNow > 0
                      ? `Place order · pay ${rupees(payingNow)} advance`
                      : 'Place order'}
              </button>
            </section>
          </form>
        )}
      </div>
    </main>
  )
}
