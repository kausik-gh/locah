import Link from 'next/link'
import { getAccessToken } from '@/lib/supabase/access-token'
import { listMyBusinesses, type BusinessSummary } from '@/lib/platform-api'
import { fetchSearch, type SearchResponse } from '@/lib/marketplace-api'
import { PublicNav } from '@/components/public/PublicNav'
import { PublicFooter } from '@/components/public/PublicFooter'
import { businessSiteUrl, platformUrl } from '@platform/config'

export const dynamic = 'force-dynamic'

const WORKSPACE_URL = platformUrl('workspace')

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

/**
 * How a Business's website address reads, without the scheme.
 *
 * `locah.app/...` used to be written in by hand here. It is not a domain LOCAH
 * owns, and it contradicts the address the platform actually issues, so it is
 * derived from the same place every other link is.
 */
function siteAddress(slug: string): string {
  return businessSiteUrl(slug).replace(/^https?:\/\//, '')
}

/* ---------------------------------------------------------------- hero ---- */

/** A real business's real website, drawn small. Never mock copy: if the
 *  Marketplace is empty this falls back to the generic frame below. */
function SitePreview({ live }: { live: SearchResponse | null }) {
  // The business and the offerings are two separate lists on one search
  // response, so taking the head of each put someone else's prices under this
  // business's name — a music school advertising balayage. Prefer the first
  // business that has offerings of its own in the same response, and show only
  // those; the claim this frame is making is that the site is real.
  const offerings = live?.offerings || []
  const businesses = live?.businesses || []
  const business =
    businesses.find((b) => offerings.some((o) => o.business_id === b.business_id)) ??
    businesses[0]
  const items = business
    ? offerings.filter((o) => o.business_id === business.business_id).slice(0, 3)
    : []

  return (
    <div className="lc-frame" aria-hidden="true">
      <div className="lc-frame__bar">
        <span className="lc-frame__dot" />
        <span className="lc-frame__dot" />
        <span className="lc-frame__dot" />
        <span className="lc-frame__addr">
          {business?.slug ? siteAddress(business.slug) : siteAddress('your-business')}
        </span>
      </div>
      <div className="lc-frame__body">
        <div className="hp-mini">
          <div className="hp-mini__nav">
            <strong>{business?.display_name || 'Your Business'}</strong>
            <span>Home</span>
            <span>Menu</span>
            <span>Contact</span>
          </div>
          <div className="hp-mini__hero">
            <p className="hp-mini__eyebrow">
              {(business?.business_type || 'local business').replace(/_/g, ' ')}
            </p>
            <h3>{business?.display_name || 'Everything you make, online'}</h3>
            <span className="hp-mini__cta">Order now</span>
          </div>
          <div className="hp-mini__items">
            {items.length > 0
              ? items.map((o) => (
                  <div className="hp-mini__item" key={o.id}>
                    <span>{o.title}</span>
                    <b>{money(o.price_from, o.currency)}</b>
                  </div>
                ))
              : ['Your first product', 'Your second product', 'Your third product'].map((t) => (
                  <div className="hp-mini__item" key={t}>
                    <span>{t}</span>
                    <b>—</b>
                  </div>
                ))}
          </div>
        </div>
      </div>
    </div>
  )
}

function Hero({ live }: { live: SearchResponse | null }) {
  return (
    <section className="lc-section lc-ground-paper hp-hero">
      <div className="lc-container lc-container--wide">
        <div className="lc-split">
          <div className="lc-rise lc-rise-1">
            <p className="lc-eyebrow">Local Businesses. Limitless Possibilities.</p>
            <h1 className="lc-display">
              Your business, <span className="lc-mark">fully digital</span> — in an afternoon.
            </h1>
            <p className="lc-lead">
              Tell LOCAH what you do. You get a real website, a listing customers can find you
              through, and working orders, bookings and payments — not a pile of tools to stitch
              together yourself.
            </p>
            <div className="lc-row" style={{ marginTop: 'var(--sp-6)' }}>
              <Link className="lc-btn lc-btn--primary lc-btn--lg" href="/start">
                Get started
              </Link>
              <Link className="lc-btn lc-btn--ghost lc-btn--lg" href="/marketplace">
                Explore the Marketplace
              </Link>
            </div>
            <p className="lc-small lc-muted" style={{ marginTop: 'var(--sp-4)' }}>
              No card required to set up. Your site stays private until you publish it.
            </p>
          </div>

          <div className="lc-rise lc-rise-2" style={{ position: 'relative' }}>
            <SitePreview live={live} />
            {/* Sit outside the frame edges — overlapping the preview would
                hide the very thing they are pointing at. */}
            <div className="lc-float" style={{ right: '-1.75rem', top: '-1.25rem' }}>
              <p className="lc-float__label">Website</p>
              <p className="lc-float__value">Generated &amp; editable</p>
            </div>
            <div className="lc-float" style={{ left: '-2.25rem', bottom: '-2.75rem' }}>
              <p className="lc-float__label">Orders</p>
              <p className="lc-float__value">Live from day one</p>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}

/* ------------------------------------------------------------- journey ---- */

const JOURNEY = [
  {
    eyebrow: 'Presence',
    title: 'A website that looks like your business',
    body: 'LOCAH reads what kind of business you run and builds a structured site to match — a menu for a café, rooms for a stay, plans for a gym. Every word and image stays editable.',
    points: ['Pages, sections and theme', 'Your photos or ours', 'Publish when you are ready'],
  },
  {
    eyebrow: 'Discovery',
    title: 'Customers can actually find you',
    body: 'Publishing puts you in the LOCAH Marketplace, where people search by what they want and where they are — not by whether they already knew your name.',
    points: ['Searchable by type and place', 'Your offerings are indexed', 'One link that works everywhere'],
  },
  {
    eyebrow: 'Trade',
    title: 'Take the order without leaving',
    body: 'The same catalogue that fills your website fills your checkout. Customers order or book on your site and it lands in your Workspace as real work to do.',
    points: ['Cart, checkout and tracking', 'Pickup or delivery', 'Pay online or on collection'],
  },
  {
    eyebrow: 'Operations',
    title: 'Run the business, not the software',
    body: 'Orders, bookings, customers, payments and stock live in one Workspace. Switch on only the parts your business needs — the rest stays out of your way.',
    points: ['One place for the day', 'Modules you choose', 'Roles for your team'],
  },
]

function Journey() {
  return (
    <section className="lc-section lc-ground-cream">
      <div className="lc-container lc-container--wide">
        <div className="lc-center" style={{ marginBottom: 'var(--sp-8)' }}>
          <p className="lc-eyebrow">From &ldquo;I have a business&rdquo; to a business that runs</p>
          <h2>Four things every local business needs. One platform that does all four.</h2>
        </div>

        <div className="lc-grid lc-grid--2">
          {JOURNEY.map((j) => (
            <article className="lc-card" key={j.title}>
              <p className="lc-eyebrow">{j.eyebrow}</p>
              <h3 className="lc-card__title">{j.title}</h3>
              <p className="lc-card__body">{j.body}</p>
              <ul className="hp-ticks">
                {j.points.map((p) => (
                  <li key={p}>{p}</li>
                ))}
              </ul>
            </article>
          ))}
        </div>
      </div>
    </section>
  )
}

/* ---------------------------------------------------------------- types ---- */

const TYPES = [
  { label: 'Restaurants & cafés', detail: 'Menu, orders, delivery' },
  { label: 'Home food', detail: 'Daily menu, pickup, pre-orders' },
  { label: 'Salons & spas', detail: 'Services, appointments, staff' },
  { label: 'Gyms & studios', detail: 'Plans, classes, memberships' },
  { label: 'Hotels & stays', detail: 'Rooms, availability, bookings' },
  { label: 'Real estate', detail: 'Listings, enquiries, viewings' },
  { label: 'Retail', detail: 'Products, stock, fulfilment' },
  { label: 'Professional services', detail: 'Services, leads, invoicing' },
  { label: 'Classes & coaching', detail: 'Schedules, seats, enrolment' },
]

function BuiltFor() {
  return (
    <section className="lc-section">
      <div className="lc-container lc-container--wide">
        <div className="lc-split">
          <div>
            <p className="lc-eyebrow">Built for your kind of business</p>
            <h2>A café and a gym should not get the same website.</h2>
            <p className="lc-lead">
              LOCAH models your business properly — what you sell, how people get it, and what you
              need to run it. The website, the checkout and the Workspace all change to match.
            </p>
            <Link className="lc-btn lc-btn--primary" href="/start" style={{ marginTop: 'var(--sp-5)' }}>
              Set up your business
            </Link>
          </div>
          <ul className="hp-types">
            {TYPES.map((t) => (
              <li key={t.label}>
                <strong>{t.label}</strong>
                <span className="lc-muted lc-small">{t.detail}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  )
}

/* ----------------------------------------------------------------- how ---- */

function HowItWorks() {
  return (
    <section className="lc-section lc-ground-ink">
      <div className="lc-container lc-container--wide">
        <div className="lc-split">
          <div>
            <p className="lc-eyebrow">How it works</p>
            <h2>Four steps, and you are open.</h2>
            <p className="lc-lead" style={{ color: 'var(--locah-n-300)' }}>
              Most owners are published the same day. Nothing you enter is thrown away — it becomes
              your catalogue, your site and your storefront at once.
            </p>
          </div>
          <ol className="lc-steps">
            <li className="lc-step">
              <div>
                <p className="lc-step__title">Tell us what you do</p>
                <p className="lc-step__body">
                  Your business type, name and place. A handful of questions that change depending
                  on what you run — not a database form.
                </p>
              </div>
            </li>
            <li className="lc-step">
              <div>
                <p className="lc-step__title">LOCAH builds your site</p>
                <p className="lc-step__body">
                  Pages, sections, copy and theme, generated as structured content you can edit —
                  never a block of code you cannot change.
                </p>
              </div>
            </li>
            <li className="lc-step">
              <div>
                <p className="lc-step__title">Make it yours, then publish</p>
                <p className="lc-step__body">
                  Edit any text or image, add your offerings, preview it, and publish when it reads
                  the way you want.
                </p>
              </div>
            </li>
            <li className="lc-step">
              <div>
                <p className="lc-step__title">Start taking orders</p>
                <p className="lc-step__body">
                  You appear in the Marketplace, customers order or book, and the work arrives in
                  your Workspace.
                </p>
              </div>
            </li>
          </ol>
        </div>
      </div>
    </section>
  )
}

/* --------------------------------------------------------- marketplace ---- */

function LiveOnLocah({ live }: { live: SearchResponse | null }) {
  const businesses = (live?.businesses || []).slice(0, 6)
  if (businesses.length === 0) return null

  return (
    <section className="lc-section lc-ground-cream">
      <div className="lc-container lc-container--wide">
        <div className="lc-row lc-row--between" style={{ marginBottom: 'var(--sp-6)' }}>
          <div>
            <p className="lc-eyebrow">For customers</p>
            <h2>Discover what is open around you.</h2>
          </div>
          <Link className="lc-btn lc-btn--ghost" href="/marketplace">
            Open the Marketplace
          </Link>
        </div>

        <div className="lc-grid lc-grid--3">
          {businesses.map((b) => (
            <Link className="lc-mediacard" key={b.business_id} href={`/${b.slug}`}>
              <div className="lc-mediacard__media">
                <div className="lc-mediacard__fallback">
                  {b.display_name.slice(0, 1).toUpperCase()}
                </div>
              </div>
              <div className="lc-mediacard__body">
                <h3 className="lc-mediacard__title">{b.display_name}</h3>
                <p className="lc-mediacard__meta">
                  {(b.business_type || 'Local business').replace(/_/g, ' ')}
                  {b.city ? ` · ${b.city}` : ''}
                </p>
                {b.description ? <p className="lc-muted lc-small">{b.description}</p> : null}
              </div>
            </Link>
          ))}
        </div>
      </div>
    </section>
  )
}

/* ----------------------------------------------------------------- CTA ---- */

function ClosingCta() {
  return (
    <section className="lc-section">
      <div className="lc-container">
        <div className="lc-center">
          <h2>Ready to take your business digital?</h2>
          <p className="lc-lead" style={{ marginInline: 'auto' }}>
            Set it up once. Your website, your listing and your day-to-day all come from the same
            place — so they never disagree.
          </p>
          <div className="lc-row lc-row--center" style={{ marginTop: 'var(--sp-6)' }}>
            <Link className="lc-btn lc-btn--primary lc-btn--lg" href="/start">
              Set up your business
            </Link>
            <Link className="lc-btn lc-btn--ghost lc-btn--lg" href="/for-businesses">
              See how it works
            </Link>
          </div>
        </div>
      </div>
    </section>
  )
}

/** Signed-in owners keep the marketing page but get a way back to work. */
function ResumeBar({ businesses }: { businesses: BusinessSummary[] }) {
  const first = businesses[0]
  return (
    <div className="hp-resume">
      <div className="lc-container lc-container--wide lc-row lc-row--between">
        <span className="lc-small">
          Signed in — you run{' '}
          <strong>{first.display_name}</strong>
          {businesses.length > 1 ? ` and ${businesses.length - 1} more` : ''}.
        </span>
        <a className="lc-btn lc-btn--sm lc-btn--primary" href={`${WORKSPACE_URL}/b/${first.id}`}>
          Open Workspace
        </a>
      </div>
    </div>
  )
}

export default async function HomePage() {
  const token = await getAccessToken()

  // Both are best-effort: the front door must render even if the API is down.
  const [businesses, live] = await Promise.all([
    token
      ? listMyBusinesses(token)
          .then((bs) => bs.filter((b) => b.state !== 'closed'))
          .catch(() => [] as BusinessSummary[])
      : Promise.resolve([] as BusinessSummary[]),
    fetchSearch({}).catch(() => null),
  ])

  return (
    <div className="locah-public">
      <PublicNav signedIn={Boolean(token)} />
      {businesses.length > 0 ? <ResumeBar businesses={businesses} /> : null}
      <main>
        <Hero live={live} />
        <Journey />
        <BuiltFor />
        <HowItWorks />
        <LiveOnLocah live={live} />
        <ClosingCta />
      </main>
      <PublicFooter />
    </div>
  )
}
