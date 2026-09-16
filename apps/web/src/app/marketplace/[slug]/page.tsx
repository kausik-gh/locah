import Link from 'next/link'
import { notFound } from 'next/navigation'
import { fetchMarketplaceProfile } from '@/lib/marketplace-api'

export const revalidate = 60

/** MKT-007 Marketplace Business Profile + MKT-008 offering handoff. */
export default async function MarketplaceBusinessProfilePage({
  params,
  searchParams,
}: {
  params: { slug: string }
  searchParams?: { offering_id?: string; intent?: string; location_id?: string }
}) {
  const data = await fetchMarketplaceProfile(params.slug)
  if (!data) notFound()

  const selectedOffering = searchParams?.offering_id
    ? data.offerings.find((o: { id: string }) => o.id === searchParams.offering_id)
    : null

  return (
    <div
      style={{
        minHeight: '100vh',
        fontFamily: 'Georgia, serif',
        background: '#f7f4ef',
        color: '#1a2229',
        padding: '2rem 1.25rem 4rem',
      }}
    >
      <div style={{ maxWidth: '48rem', margin: '0 auto' }}>
        <Link href="/search">← Search</Link>
        <h1 style={{ fontSize: '2.4rem', margin: '0.75rem 0 0.35rem' }}>
          {data.business.display_name}
        </h1>
        <p style={{ opacity: 0.75 }}>
          {[data.business.business_type, data.business.city].filter(Boolean).join(' · ')}
        </p>
        {data.business.description ? (
          <p style={{ marginTop: '1rem', lineHeight: 1.6 }}>{data.business.description}</p>
        ) : null}

        <section style={{ marginTop: '1.5rem' }}>
          <h2 style={{ fontSize: '1.1rem' }}>Actions</h2>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.6rem', marginTop: '0.5rem' }}>
            {(data.actions || []).map((action: { action: string; label: string; href: string }) => (
              <Link
                key={action.action}
                href={
                  action.action === 'visit_website'
                    ? action.href
                    : `${action.href}${action.href.includes('?') ? '&' : '?'}${
                        searchParams?.offering_id
                          ? `offering_id=${searchParams.offering_id}&`
                          : ''
                      }${
                        searchParams?.location_id
                          ? `location_id=${searchParams.location_id}&`
                          : ''
                      }intent=${searchParams?.intent || action.action}`
                }
                style={{
                  padding: '0.55rem 0.9rem',
                  background: action.action === 'visit_website' ? '#1a2229' : '#fff',
                  color: action.action === 'visit_website' ? '#fff' : '#1a2229',
                  border: '1px solid #1a2229',
                  textDecoration: 'none',
                }}
              >
                {action.label}
              </Link>
            ))}
          </div>
          <p style={{ fontSize: '0.9rem', marginTop: '0.75rem', opacity: 0.8 }}>
            Marketplace Profile is separate from the Business Website. “Visit Website” is an
            explicit handoff.
          </p>
        </section>

        {selectedOffering ? (
          <section
            style={{
              marginTop: '1.5rem',
              padding: '1rem',
              border: '1px solid rgba(0,0,0,0.12)',
              background: '#fff',
            }}
          >
            <h2>Selected offering</h2>
            <p style={{ fontWeight: 700 }}>{selectedOffering.title}</p>
            <Link href={selectedOffering.handoff.href}>Continue on Website</Link>
          </section>
        ) : null}

        <section style={{ marginTop: '2rem' }}>
          <h2>Offerings</h2>
          <ul style={{ listStyle: 'none', padding: 0, display: 'grid', gap: '0.6rem' }}>
            {(data.offerings || []).map(
              (o: {
                id: string
                title: string
                offering_type: string
                handoff: { href: string }
              }) => (
                <li key={o.id} style={{ padding: '0.75rem', background: 'rgba(255,255,255,0.8)' }}>
                  <div style={{ fontWeight: 700 }}>{o.title}</div>
                  <div style={{ opacity: 0.7 }}>{o.offering_type}</div>
                  <Link href={o.handoff.href}>Open on Website</Link>
                </li>
              )
            )}
          </ul>
        </section>
      </div>
    </div>
  )
}
