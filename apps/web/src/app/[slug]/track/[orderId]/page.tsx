import Link from 'next/link'
import { notFound } from 'next/navigation'
import { RESERVED_SLUGS } from '@/lib/reserved-slugs'
import { fetchTracking } from '@/lib/checkout-api'

export const dynamic = 'force-dynamic'

/** WEB-008 Order Tracking — Doc 12 §11.2 / Doc 09 WEB-008. */
export default async function TrackOrderPage({
  params,
  searchParams,
}: {
  params: { slug: string; orderId: string }
  searchParams?: { token?: string }
}) {
  if (RESERVED_SLUGS.has(params.slug)) notFound()
  const token = searchParams?.token
  if (!token) {
    return (
      <TrackingShell slug={params.slug}>
        <h1>Tracking unavailable</h1>
        <p>This tracking link is missing a token.</p>
      </TrackingShell>
    )
  }
  const data = await fetchTracking(params.orderId, token)
  if (!data) {
    return (
      <TrackingShell slug={params.slug}>
        <h1>Invalid tracking link</h1>
        <p>We could not find this order. The link may be incorrect.</p>
      </TrackingShell>
    )
  }
  if (data.state === 'expired') {
    return (
      <TrackingShell slug={params.slug}>
        <h1>Tracking link expired</h1>
        <p>Order {data.order?.order_number} can no longer be viewed with this link.</p>
      </TrackingShell>
    )
  }

  return (
    <TrackingShell slug={params.slug}>
      <h1>Order {data.order.order_number}</h1>
      <p style={{ opacity: 0.8 }}>Order status: {data.order.status}</p>
      <p style={{ opacity: 0.8 }}>Payment: {data.order.payment_status}</p>
      {data.fulfilment ? (
        <section style={{ marginTop: '1.25rem' }}>
          <h2>Fulfilment</h2>
          <p>Mode: {data.fulfilment.mode}</p>
          <p>Status: {data.fulfilment.customer_status}</p>
          {data.state === 'delayed' ? (
            <p style={{ color: '#8a5a00' }}>Delivery appears delayed. Contact the Business if needed.</p>
          ) : null}
          {data.state === 'failed' ? (
            <p style={{ color: '#b00020' }}>Fulfilment failed. Contact the Business for help.</p>
          ) : null}
          {data.state === 'cancelled' ? <p>This fulfilment was cancelled.</p> : null}
        </section>
      ) : null}
    </TrackingShell>
  )
}

function TrackingShell({ slug, children }: { slug: string; children: React.ReactNode }) {
  return (
    <div
      style={{
        minHeight: '100vh',
        fontFamily: 'Georgia, serif',
        background: 'linear-gradient(165deg, #f4f7f2, #eef2f7)',
        color: '#152028',
        padding: '2rem 1.25rem',
      }}
    >
      <div style={{ maxWidth: '36rem', margin: '0 auto' }}>
        <Link href={`/${slug}`}>← Website</Link>
        <div style={{ marginTop: '1rem' }}>{children}</div>
      </div>
    </div>
  )
}
