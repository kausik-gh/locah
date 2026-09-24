import type { Metadata } from 'next'
import Link from 'next/link'
import { redirect } from 'next/navigation'
import { fetchDiscover, type DiscoverResponse } from '@/lib/marketplace-api'
import { readPlace, readSeen } from '@/lib/visitor-signals'
import { getBookedBusinessIds, getNavAccount } from '@/lib/nav-account'
import { PublicNav } from '@/components/public/PublicNav'
import { PublicFooter } from '@/components/public/PublicFooter'
import { SearchBox } from '@/components/marketplace/SearchBox'
import { LocationControl } from '@/components/marketplace/LocationControl'
import { CategoryBento, Rail } from '@/components/marketplace/Rails'
import { ForgetBrowsing } from '@/components/marketplace/Remember'

export const dynamic = 'force-dynamic'

export const metadata: Metadata = {
  title: 'Marketplace — LOCAH',
  description:
    'Find local businesses on LOCAH by what they sell and where they are: food, shops, salons, clinics, classes, homes, services and suppliers.',
}

export default async function MarketplaceHomePage({
  searchParams,
}: {
  searchParams?: { q?: string }
}) {
  if (searchParams?.q) {
    redirect(`/marketplace/search?q=${encodeURIComponent(searchParams.q)}`)
  }

  const place = readPlace()
  const seen = readSeen()
  const account = await getNavAccount()
  const used = await getBookedBusinessIds(account.token)

  let data: DiscoverResponse | null = null
  try {
    data = await fetchDiscover({
      place: place?.param,
      fam: seen.fam,
      cat: seen.cat,
      searched: seen.searched,
      used,
    })
  } catch {
    data = null
  }

  const rails = data?.rails || []
  const total = data?.totals.businesses ?? 0
  const personal = rails.filter((r) => r.id === 'for_you' || r.id === 'again')
  const nearby = rails.find((r) => r.id === 'nearby')
  const rest = rails.filter((r) => !['for_you', 'again', 'nearby'].includes(r.id))

  return (
    <div className="locah-public">
      <PublicNav active="marketplace" signedIn={account.signedIn} businesses={account.businesses} />
      <main className="mx-page">
        <section className="mx-hero" aria-labelledby="mx-hero-title">
          <div className="lc-container lc-container--wide">
            <div className="mx-hero__top">
              <LocationControl label={place?.label} cities={data?.cities} />
              {total > 0 ? (
                <p className="mx-hero__count">
                  <span className="lc-num">{total}</span> {total === 1 ? 'business' : 'businesses'} listed
                </p>
              ) : null}
            </div>
            <h1 id="mx-hero-title" className="mx-hero__title">
              What do you need{place ? <> near <span className="mx-hero__place">{place.label}</span></> : ' nearby'}?
            </h1>
            <SearchBox />
            <p className="mx-hero__hint">
              Search by what you want, not by who you know: a dish, a service, a product, a PIN.
            </p>
          </div>
        </section>

        {data === null ? (
          <div className="lc-container lc-container--wide">
            <div className="mx-empty">
              <p className="mx-empty__title">The Marketplace is not responding right now.</p>
              <p>Search still works from the box above, or try again in a moment.</p>
            </div>
          </div>
        ) : null}

        {data && place && data.location_state === 'none_nearby' ? (
          <div className="lc-container lc-container--wide">
            <p className="mx-note mx-note--wide">
              Nothing is listed within 40 km of {place.label} yet, so here is everything else. As
              businesses near you publish, they will appear first.
            </p>
          </div>
        ) : null}

        {nearby ? (
          <div className="lc-container lc-container--wide">
            <Rail rail={nearby} first />
          </div>
        ) : null}

        {personal.length > 0 ? (
          <div className="lc-container lc-container--wide mx-personal">
            {personal.map((r) => (
              <Rail key={r.id} rail={r} first={!nearby} />
            ))}
            {seen.any ? <ForgetBrowsing /> : null}
          </div>
        ) : null}

        {data ? (
          <section className="mx-cats" aria-labelledby="mx-cats-title">
            <div className="lc-container lc-container--wide">
              <div className="mx-section-head">
                <h2 id="mx-cats-title">Browse by kind of business</h2>
                <Link className="mx-rail__all" href="/marketplace/categories">
                  All categories
                </Link>
              </div>
              <CategoryBento families={data.categories} />
            </div>
          </section>
        ) : null}

        {rest.length > 0 ? (
          <div className="lc-container lc-container--wide">
            {rest.map((r) => (
              <Rail key={r.id} rail={r} first={!nearby && personal.length === 0} />
            ))}
          </div>
        ) : null}

        {data && total === 0 ? (
          <div className="lc-container lc-container--wide">
            <div className="mx-empty">
              <p className="mx-empty__title">No businesses are listed yet.</p>
              <p>
                Businesses appear here once they publish a website on LOCAH and choose to be listed.
                If you run one, you can be among the first.
              </p>
              <div className="mx-empty__actions">
                <Link className="lc-btn lc-btn--primary" href="/start">
                  List your business
                </Link>
              </div>
            </div>
          </div>
        ) : null}

        <section className="mx-owners" aria-labelledby="mx-owners-title">
          <div className="lc-container lc-container--wide mx-owners__inner">
            <div>
              <h2 id="mx-owners-title">Run a business near here?</h2>
              <p>
                Tell LOCAH about it. Your website, your listing here and your orders and bookings
                come from the same conversation.
              </p>
            </div>
            <div className="mx-owners__ctas">
              <Link className="lc-btn lc-btn--primary lc-btn--lg" href="/start">
                List your business
              </Link>
              <Link className="lc-btn lc-btn--light lc-btn--lg" href="/how-it-works">
                How it works
              </Link>
            </div>
          </div>
        </section>
      </main>
      <PublicFooter />
    </div>
  )
}
