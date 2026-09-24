import type { Metadata } from 'next'
import Link from 'next/link'
import { notFound } from 'next/navigation'
import { fetchMarketplaceProfile } from '@/lib/marketplace-api'
import { readPlace } from '@/lib/visitor-signals'
import { getNavAccount } from '@/lib/nav-account'
import { PublicNav } from '@/components/public/PublicNav'
import { PublicFooter } from '@/components/public/PublicFooter'
import { ActionButton, ListingCard, ListingMedia, variantFor } from '@/components/marketplace/ListingCard'
import { CategoryIcon, familyTint } from '@/components/marketplace/CategoryIcon'
import { Remember } from '@/components/marketplace/Remember'

export const dynamic = 'force-dynamic'

export async function generateMetadata({ params }: { params: { slug: string } }): Promise<Metadata> {
  const data = await fetchMarketplaceProfile(params.slug)
  if (!data) return {}
  const b = data.business
  const what = [b.category_label, b.area_label].filter(Boolean).join(', ')
  return {
    title: `${b.display_name}${what ? `, ${what}` : ''} — LOCAH Marketplace`,
    description: b.description || b.tagline || undefined,
    openGraph: b.cover_url ? { images: [b.cover_url] } : undefined,
  }
}

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

const HIGHLIGHT_HEADING: Record<string, string> = {
  food: 'From the menu',
  property: 'Projects',
  appointment: 'Services',
  trade: 'What they offer',
  general: 'From their website',
}

const SITE_ACTIONS = new Set(['order', 'book', 'join', 'enquire'])

const NOUN: Record<string, string> = {
  order: 'ordering',
  book: 'booking',
  join: 'joining a plan',
  enquire: 'enquiries',
}

/** "Ordering happens", "Booking and enquiries happen": only what exists. */
function handoffLine(actions: string[]) {
  const nouns = actions.map((a) => NOUN[a]).filter(Boolean)
  const list =
    nouns.length <= 1 ? nouns[0] : `${nouns.slice(0, -1).join(', ')} and ${nouns[nouns.length - 1]}`
  const text = `${list} ${nouns.length > 1 ? 'happen' : 'happens'}`
  return text.charAt(0).toUpperCase() + text.slice(1)
}

/** MKT-007 Marketplace Business Profile + MKT-008 offering handoff.
 *
 *  LOCAH's page about the Business, deliberately separate from the Business's
 *  own website. Every fact on it is something the Business published, and
 *  every button is an explicit handoff to something that works. */
export default async function MarketplaceBusinessProfilePage({
  params,
  searchParams,
}: {
  params: { slug: string }
  searchParams?: { offering_id?: string }
}) {
  const place = readPlace()
  const [data, account] = await Promise.all([
    fetchMarketplaceProfile(params.slug, place?.param),
    getNavAccount(),
  ])
  if (!data) notFound()

  const b = data.business
  const variant = variantFor(b)
  const actions = data.actions || []
  const site = actions.filter((a) => SITE_ACTIONS.has(a.action))
  const direct = actions.filter((a) => a.action === 'whatsapp' || a.action === 'call')
  const visit = actions.find((a) => a.action === 'visit_website')
  const highlights = (b.highlights || []).filter(
    (h): h is { title: string; image_url: string } => Boolean(h.image_url)
  )
  const listed = (b.highlights || []).filter((h) => !h.image_url)
  const offerings = data.offerings || []
  const selected = searchParams?.offering_id
    ? offerings.find((o) => o.id === searchParams.offering_id)
    : undefined
  const since = b.published_at
    ? new Date(b.published_at).toLocaleDateString('en-IN', { month: 'long', year: 'numeric' })
    : null

  return (
    <div className="locah-public">
      <PublicNav active="marketplace" signedIn={account.signedIn} businesses={account.businesses} />
      <main className="mx-page">
        <div className="lc-container lc-container--wide mx-prof">
          <nav className="mx-crumbs" aria-label="Breadcrumb">
            <Link href="/marketplace">Marketplace</Link>
            {b.family ? (
              <>
                <span aria-hidden="true">/</span>
                <Link href={`/marketplace/category/${b.family}`}>{b.family_label}</Link>
              </>
            ) : null}
            {b.family && b.category ? (
              <>
                <span aria-hidden="true">/</span>
                <Link href={`/marketplace/category/${b.family}/${b.category}`}>{b.category_label}</Link>
              </>
            ) : null}
          </nav>

          <div className="mx-prof__head">
            <div className="mx-prof__id">
              <div className="mx-prof__brand">
                {b.logo_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img className="mx-prof__logo" src={b.logo_url} alt="" />
                ) : (
                  <span className="mx-prof__logo mx-prof__logo--glyph" data-tint={familyTint(b.family)} aria-hidden="true">
                    <CategoryIcon name={b.icon} size={26} />
                  </span>
                )}
                <p className="mx-prof__kicker">
                  {[b.category_label || b.family_label || 'Local business', b.area_label || b.city]
                    .filter(Boolean)
                    .join(' · ')}
                  {b.distance_km !== null && b.distance_km !== undefined ? (
                    <span className="lc-num"> · {b.distance_km < 1 ? 'under 1 km' : `${b.distance_km.toFixed(1)} km`} away</span>
                  ) : null}
                </p>
              </div>
              <h1 className="mx-prof__name">{b.display_name}</h1>
              {b.tagline && b.tagline !== b.description && b.tagline !== b.display_name ? (
                <p className="mx-prof__tag">{b.tagline}</p>
              ) : null}
              {b.description ? <p className="mx-prof__desc">{b.description}</p> : null}

              <div className="mx-prof__actions">
                {site.map((a, i) => (
                  <ActionButton key={a.action} action={a} primary={i === 0} />
                ))}
                {direct.map((a, i) => (
                  <ActionButton key={a.action} action={a} primary={site.length === 0 && i === 0} />
                ))}
                {visit ? <ActionButton action={visit} /> : null}
              </div>
              {site.length > 0 ? (
                <p className="mx-prof__handoff">
                  {handoffLine(site.map((a) => a.action))} on {b.display_name}&rsquo;s own website.
                </p>
              ) : null}
            </div>
            <div className="mx-prof__cover">
              <ListingMedia listing={b} eager />
            </div>
          </div>

          {selected ? (
            <section className="mx-prof__selected" aria-label="The item you were looking at">
              <p>You were looking at</p>
              <h2>{selected.title}</h2>
              {selected.description ? <p>{selected.description}</p> : null}
              <Link className="lc-btn lc-btn--primary" href={selected.handoff.href}>
                Continue on their website
              </Link>
            </section>
          ) : null}

          {highlights.length > 0 || listed.length > 0 ? (
            <section className="mx-prof__section" aria-labelledby="mx-hl">
              <h2 id="mx-hl">{HIGHLIGHT_HEADING[variant]}</h2>
              {highlights.length > 0 ? (
                <ul className="mx-hl">
                  {highlights.map((h) => (
                    <li key={h.title}>
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img src={h.image_url} alt="" loading="lazy" decoding="async" />
                      <span>{h.title}</span>
                    </li>
                  ))}
                </ul>
              ) : null}
              {listed.length > 0 ? (
                <ul className="mx-listed">
                  {listed.map((h) => (
                    <li key={h.title}>{h.title}</li>
                  ))}
                </ul>
              ) : null}
            </section>
          ) : null}

          {offerings.length > 0 ? (
            <section className="mx-prof__section" aria-labelledby="mx-off">
              <h2 id="mx-off">Listed items</h2>
              <ul className="mx-offers">
                {offerings.map((o) => (
                  <li key={o.id}>
                    <Link href={o.handoff.href}>
                      <span className="mx-offers__title">{o.title}</span>
                      {o.description ? <span className="mx-offers__desc">{o.description}</span> : null}
                      {money(o.price_from, o.currency) ? (
                        <span className="mx-offers__price lc-num">{money(o.price_from, o.currency)}</span>
                      ) : null}
                    </Link>
                  </li>
                ))}
              </ul>
              <p className="mx-prof__fine">Prices are as {b.display_name} published them.</p>
            </section>
          ) : null}

          <section className="mx-prof__facts" aria-label="Details">
            <dl>
              {b.category_label || b.family_label ? (
                <div>
                  <dt>Kind of business</dt>
                  <dd>{b.category_label || b.family_label}</dd>
                </div>
              ) : null}
              {b.area_label || b.city ? (
                <div>
                  <dt>Area</dt>
                  <dd>
                    {b.area_label || b.city}
                    {b.postal_code ? `, ${b.postal_code}` : ''}
                  </dd>
                </div>
              ) : null}
              {since ? (
                <div>
                  <dt>Website published</dt>
                  <dd>{since}</dd>
                </div>
              ) : null}
              {visit ? (
                <div>
                  <dt>Website</dt>
                  <dd>
                    <Link className="lc-link lc-link--accent" href={visit.href}>
                      Visit {b.display_name}
                    </Link>
                  </dd>
                </div>
              ) : null}
            </dl>
            <p className="mx-prof__trust">
              Everything here is what {b.display_name} published on LOCAH. LOCAH does not add
              ratings, reviews or opening hours of its own.
            </p>
          </section>

          {data.related.length > 0 ? (
            <section className="mx-prof__section" aria-labelledby="mx-rel">
              <h2 id="mx-rel">More {b.family_label || 'businesses'}{b.city ? ' nearby' : ''}</h2>
              <ul className="mx-rail__track">
                {data.related.map((l) => (
                  <li key={l.business_id}>
                    <ListingCard listing={l} />
                  </li>
                ))}
              </ul>
            </section>
          ) : null}
        </div>
        <Remember family={b.family} category={b.category} />
      </main>
      <PublicFooter />
    </div>
  )
}
