'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'
import { cartStorageKey, fetchPublicOfferings, type CartItem } from '@/lib/checkout-api'

/**
 * The basket in the header — only when there is something to buy.
 *
 * Orders being switched on is not enough: a business that has not added a
 * single priced item yet would show a working-looking basket that can never
 * hold anything. So this asks for the live, priced items first and renders
 * nothing until there is at least one.
 */
export function CommerceCart({
  slug,
  variant = 'nav',
}: {
  slug: string
  variant?: 'nav' | 'footer'
}) {
  const [ready, setReady] = useState(false)
  const [count, setCount] = useState(0)

  useEffect(() => {
    let gone = false
    fetchPublicOfferings(slug)
      .then((data: { offerings?: Array<Record<string, unknown>> }) => {
        if (gone) return
        setReady((data?.offerings || []).some((row) => typeof row.price_amount === 'number'))
      })
      .catch(() => undefined)
    const read = () => {
      try {
        const cart: CartItem[] = JSON.parse(localStorage.getItem(cartStorageKey(slug)) || '[]')
        setCount(cart.reduce((sum, line) => sum + (line.quantity || 0), 0))
      } catch {
        setCount(0)
      }
    }
    read()
    window.addEventListener('locah-cart', read)
    window.addEventListener('storage', read)
    return () => {
      gone = true
      window.removeEventListener('locah-cart', read)
      window.removeEventListener('storage', read)
    }
  }, [slug])

  if (!ready) return null
  if (variant === 'footer') return <Link href={`/${slug}/checkout`}>Basket</Link>
  return (
    <Link className="ls-nav__cart" href={`/${slug}/checkout`}>
      Basket{count ? <span className="ls-nav__count">{count}</span> : null}
    </Link>
  )
}
