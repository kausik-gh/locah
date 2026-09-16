import { notFound } from 'next/navigation'
import { RESERVED_SLUGS } from '@/lib/reserved-slugs'
import { fetchCheckoutOptions } from '@/lib/checkout-api'
import CheckoutClient from './CheckoutClient'

export const dynamic = 'force-dynamic'

/** WEB-007 Cart / Checkout — Doc 12 §11.2 `/{slug}/checkout`. */
export default async function CheckoutPage({ params }: { params: { slug: string } }) {
  if (RESERVED_SLUGS.has(params.slug)) notFound()
  let options
  try {
    options = await fetchCheckoutOptions(params.slug)
  } catch {
    notFound()
  }
  return (
    <div
      style={{
        minHeight: '100vh',
        fontFamily: 'Georgia, "Iowan Old Style", serif',
        background: 'linear-gradient(165deg, #f7f3eb, #e8eef4)',
        color: '#1a2229',
      }}
    >
      <CheckoutClient slug={params.slug} options={options} />
    </div>
  )
}
