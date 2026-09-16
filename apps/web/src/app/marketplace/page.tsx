import type { Metadata } from 'next'
import Link from 'next/link'
import { redirect } from 'next/navigation'
import { fetchSearch } from '@/lib/marketplace-api'
import { PublicNav } from '@/components/public/PublicNav'
import { PublicFooter } from '@/components/public/PublicFooter'
import { BusinessCard, typeLabel } from '@/components/public/BusinessCard'

export const revalidate = 30

export const metadata: Metadata = {
  title: 'Marketplace — LOCAH',
  description:
    'Discover local businesses on LOCAH: restaurants, salons, gyms, stays, shops and services you can order from or book directly.',
}

/** Categories offered as entry points. Only types the platform supports. */
const CATEGORIES = [
  { type: 'restaurant', label: 'Restaurants' },
  { type: 'cafe', label: 'Cafés' },
  { type: 'salon', label: 'Salons' },
  { type: 'spa', label: 'Spas' },
  { type: 'gym', label: 'Gyms' },
  { type: 'studio', label: 'Studios' },
  { type: 'hotel', label: 'Hotels' },
  { type: 'homestay', label: 'Stays' },
  { type: 'retail', label: 'Shops' },
  { type: 'education', label: 'Classes' },
  { type: 'professional_service', label: 'Services' },
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

export default async function MarketplaceHomePage({
  searchParams,
}: {
  searchParams?: { q?: string }
}) {
  if (searchParams?.q) {
    redirect(`/search?q=${encodeURIComponent(searchParams.q)}`)
  }

  const data = await fetchSearch({}).catch(() => null)
  const businesses = data?.businesses || []
  const offerings = (data?.offerings || []).slice(0, 8)

  // Only advertise a category that has something behind it.
  const present = new Set(businesses.map((b) => b.business_type || ''))
  const categories = CATEGORIES.filter((c) => present.has(c.type))

  return (
    <div className="locah-public">
      <PublicNav active="marketplace" />
      <main>
        <section className="lc-section lc-section--tight lc-ground-paper">
          <div className="lc-container lc-container--wide">
            <p className="lc-eyebrow">Marketplace</p>
            <h1 className="lc-display" style={{ maxWidth: '18ch' }}>
              Everything open <span className="lc-mark">near you</span>.
            </h1>
            <p className="lc-lead">
              Search local businesses and what they offer — then order, book or enquire on their
              own site. No account needed to look around.
            </p>

            <form className="lc-search" action="/search" method="get" role="search">
              <input
                name="q"
                type="search"
                aria-label="What are you looking for?"
                placeholder="Biryani, a haircut, a weekend away…"
              />
              <span className="lc-search__divider" aria-hidden="true" />
              <input name="location" aria-label="Where?" placeholder="Where?" />
              <button className="lc-btn lc-btn--primary" type="submit">
                Search
              </button>
            </form>

            {categories.length > 0 ? (
              <div className="lc-chiprail" style={{ marginTop: 'var(--sp-5)' }}>
                {categories.map((c) => (
                  <Link className="lc-chip" key={c.type} href={`/search?type=${c.type}`}>
                    {c.label}
                  </Link>
                ))}
              </div>
            ) : null}
          </div>
        </section>

        <section className="lc-section">
          <div className="lc-container lc-container--wide">
            {businesses.length === 0 ? (
              <div className="lc-empty">
                <p className="lc-empty__title">No businesses are listed yet</p>
                <p className="lc-empty__body">
                  Businesses appear here once they publish a website and choose to be
                  discoverable. If you run one, you can be listed today.
                </p>
                <Link className="lc-btn lc-btn--primary" href="/start">
                  List your business
                </Link>
              </div>
            ) : (
              <>
                <div className="lc-row lc-row--between" style={{ marginBottom: 'var(--sp-6)' }}>
                  <div>
                    <p className="lc-eyebrow">Browse</p>
                    <h2>
                      {businesses.length} business{businesses.length === 1 ? '' : 'es'} on LOCAH
                    </h2>
                  </div>
                  <Link className="lc-link lc-link--accent" href="/search">
                    Search with filters
                  </Link>
                </div>

                <div className="lc-grid lc-grid--3">
                  {businesses.map((b) => (
                    <BusinessCard key={b.business_id} business={b} />
                  ))}
                </div>
              </>
            )}
          </div>
        </section>

        {offerings.length > 0 ? (
          <section className="lc-section lc-ground-cream">
            <div className="lc-container lc-container--wide">
              <p className="lc-eyebrow">On the shelves</p>
              <h2 style={{ marginBottom: 'var(--sp-6)' }}>What you can buy right now.</h2>
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
                    <p className="lc-card__body">{typeLabel(o.offering_type)}</p>
                    {o.price_from !== null && o.price_from !== undefined ? (
                      <p className="lc-stat__value" style={{ fontSize: '1.25rem', marginTop: '0.6rem' }}>
                        {money(o.price_from, o.currency)}
                      </p>
                    ) : null}
                  </Link>
                ))}
              </div>
            </div>
          </section>
        ) : null}

        <section className="lc-section lc-ground-ink">
          <div className="lc-container">
            <div className="lc-center">
              <h2>Run a business near here?</h2>
              <p className="lc-lead" style={{ marginInline: 'auto' }}>
                Get a website, a listing in this Marketplace, and somewhere to manage what comes
                back — set up in an afternoon.
              </p>
              <div className="lc-row lc-row--center" style={{ marginTop: 'var(--sp-6)' }}>
                <Link className="lc-btn lc-btn--primary lc-btn--lg" href="/start">
                  List your business
                </Link>
                <Link className="lc-btn lc-btn--ghost lc-btn--lg" href="/for-businesses">
                  How it works
                </Link>
              </div>
            </div>
          </div>
        </section>
      </main>
      <PublicFooter />
    </div>
  )
}
