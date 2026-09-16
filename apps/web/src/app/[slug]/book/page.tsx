import { notFound } from 'next/navigation'
import { RESERVED_SLUGS } from '@/lib/reserved-slugs'
import { fetchBookingOptions } from '@/lib/booking-api'
import BookClient from './BookClient'

export const dynamic = 'force-dynamic'

/** WEB-009 Booking Flow — Doc 11 §4.1 / Doc 09 WEB-009. */
export default async function BookPage({ params }: { params: { slug: string } }) {
  if (RESERVED_SLUGS.has(params.slug)) notFound()
  let options
  try {
    options = await fetchBookingOptions(params.slug)
  } catch {
    notFound()
  }
  return (
    <div
      style={{
        minHeight: '100vh',
        fontFamily: 'Georgia, "Iowan Old Style", serif',
        background: 'linear-gradient(165deg, #f4f7f2, #e6eef5)',
        color: '#1a2229',
      }}
    >
      <BookClient slug={params.slug} options={options} />
    </div>
  )
}
