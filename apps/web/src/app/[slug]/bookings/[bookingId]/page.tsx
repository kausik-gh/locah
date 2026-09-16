import ManageBookingClient from './ManageBookingClient'

export const dynamic = 'force-dynamic'

/** WEB-010 Booking Management — Doc 09 expired link / cancel-window states. */
export default function ManageBookingPage({
  params,
  searchParams,
}: {
  params: { slug: string; bookingId: string }
  searchParams?: { token?: string }
}) {
  const token = searchParams?.token || ''
  return (
    <div
      style={{
        minHeight: '100vh',
        fontFamily: 'Georgia, "Iowan Old Style", serif',
        background: 'linear-gradient(165deg, #f4f7f2, #e6eef5)',
        color: '#1a2229',
      }}
    >
      <ManageBookingClient
        slug={params.slug}
        bookingId={params.bookingId}
        token={token}
      />
    </div>
  )
}
