import type { Metadata } from 'next'
import Link from 'next/link'
import { fetchSearch } from '@/lib/marketplace-api'
import { PublicNav } from '@/components/public/PublicNav'
import { PublicFooter } from '@/components/public/PublicFooter'
import { BusinessCard, typeLabel } from '@/components/public/BusinessCard'

export const dynamic = 'force-dynamic'

export const metadata: Metadata = {
  title: 'Search — LOCAH Marketplace',
  description: 'Search local businesses and what they offer on LOCAH.',
}

const TYPES = [
  { value: '', label: 'Any kind' },
  { value: 'restaurant', label: 'Restaurants' },
  { value: 'cafe', label: 'Cafés' },
  { value: 'salon', label: 'Salons' },
  { value: 'spa', label: 'Spas' },
  { value: 'gym', label: 'Gyms' },
  { value: 'studio', label: 'Studios' },
  { value: 'hotel', label: 'Hotels' },
  { value: 'homestay', label: 'Stays' },
  { value: 'retail', label: 'Shops' },
  { value: 'education', label: 'Classes' },
  { value: 'professional_service', label: 'Services' },
]

function money(amount?: number | null, currency?: string | null) {
  if (amount === null || amount === undefined) return null
  try {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: currency || 'INR',
      maximumFractionDigits: Number.isInteger(amount) ? 0 : 2,
    }).format(amount)
  } catch {
    return `${currency || 'INR'} ${amount}`
  }
}

export default async function SearchPage({
  searchParams,
}: {
  searchParams?: { q?: string; location?: string; type?: string }
}) {
  const q = searchParams?.q || ''
  const location = searchParams?.location || ''
  const type = searchParams?.type || ''

  const data = await fetchSearch({
    q: q || undefined,
    location: location || undefined,
    type: type || undefined,
  }).catch(() => null)

  const businesses = data?.businesses || []
  const offerings = data?.offerings || []
  const described = [q && `“${q}”`, location && `in ${location}`, type && typeLabel(type)]
    .filter(Boolean)
    .join(' ')

  return (
    <div className="locah-public">
      <PublicNav active="marketplace" />
      <main>
        <section className="lc-section lc-section--tight lc-ground-paper">
          <div className="lc-container lc-container--wide">
            <p className="lc-eyebrow">Marketplace</p>
            <h1 style={{ marginBottom: 'var(--sp-5)' }}>
              {described ? <>Results for {described}</> : 'Search local businesses'}
            </h1>

            <form className="lc-search" method="get" role="search">
              <input
                name="q"
                type="search"
                defaultValue={q}
                aria-label="What are you looking for?"
                placeholder="Biryani, a haircut, a weekend away…"
              />
              <span className="lc-search__divider" aria-hidden="true" />
              <input
                name="location"
                defaultValue={location}
                aria-label="Where?"
                placeholder="Where?"
              />
              <span className="lc-search__divider" aria-hidden="true" />
              <select name="type" defaultValue={type} aria-label="Kind of business">
                {TYPES.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
              <button className="lc-btn lc-btn--primary" type="submit">
                Search
              </button>
            </form>
          </div>
        </section>

        <section className="lc-section">
          <div className="lc-container lc-container--wide">
            {data === null ? (
              <div className="lc-empty">
                <p className="lc-empty__title">Search is unavailable right now</p>
                <p className="lc-empty__body">
                  We could not reach the Marketplace. Try again in a moment.
                </p>
              </div>
            ) : data.state === 'sparse_market' ? (
              <div className="lc-empty">
                <p className="lc-empty__title">The Marketplace is just getting started</p>
                <p className="lc-empty__body">
                  Only a few businesses are listed here so far. Browse everything that is
                  available, or add yours.
                </p>
                <div className="lc-row lc-row--center">
                  <Link className="lc-btn lc-btn--ghost" href="/marketplace">
                    Browse all
                  </Link>
                  <Link className="lc-btn lc-btn--primary" href="/start">
                    List your business
                  </Link>
                </div>
              </div>
            ) : businesses.length === 0 && offerings.length === 0 ? (
              <div className="lc-empty">
                <p className="lc-empty__title">Nothing matched {described || 'that search'}</p>
                <p className="lc-empty__body">
                  Try a broader word, drop the location, or choose a different kind of business.
                </p>
                <Link className="lc-btn lc-btn--ghost" href="/marketplace">
                  Browse everything
                </Link>
              </div>
            ) : (
              <>
                {businesses.length > 0 ? (
                  <>
                    <div className="lc-row lc-row--between" style={{ marginBottom: 'var(--sp-5)' }}>
                      <h2>
                        {businesses.length} business{businesses.length === 1 ? '' : 'es'}
                      </h2>
                    </div>
                    <div className="lc-grid lc-grid--3" style={{ marginBottom: 'var(--sp-9)' }}>
                      {businesses.map((b) => (
                        <BusinessCard key={b.business_id} business={b} />
                      ))}
                    </div>
                  </>
                ) : null}

                {offerings.length > 0 ? (
                  <>
                    <h2 style={{ marginBottom: 'var(--sp-5)' }}>
                      {offerings.length} matching item{offerings.length === 1 ? '' : 's'}
                    </h2>
                    <div className="lc-grid lc-grid--4">
                      {offerings.map((o) => (
                        <Link
                          className="lc-card lc-card--interactive"
                          key={o.id}
                          href={o.business_slug ? `/${o.business_slug}` : '/marketplace'}
                        >
                          <h3 className="lc-card__title" style={{ fontSize: '1.02rem' }}>
                            {o.title}
                          </h3>
                          {o.description ? (
                            <p className="lc-card__body mk-clamp">{o.description}</p>
                          ) : null}
                          {o.price_from !== null && o.price_from !== undefined ? (
                            <p
                              className="lc-stat__value"
                              style={{ fontSize: '1.2rem', marginTop: '0.6rem' }}
                            >
                              {money(o.price_from, o.currency)}
                            </p>
                          ) : null}
                        </Link>
                      ))}
                    </div>
                  </>
                ) : null}
              </>
            )}
          </div>
        </section>
      </main>
      <PublicFooter />
    </div>
  )
}
