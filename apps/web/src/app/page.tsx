import Link from 'next/link'
import { getAccessToken } from '@/lib/supabase/access-token'
import { listMyBusinesses, type BusinessSummary } from '@/lib/platform-api'
import { fetchSearch, type SearchResponse } from '@/lib/marketplace-api'
import { PublicNav } from '@/components/public/PublicNav'
import { PublicFooter } from '@/components/public/PublicFooter'
import { platformUrl } from '@platform/config'

export const dynamic = 'force-dynamic'

const WORKSPACE_URL = platformUrl('workspace')

/* ---------------------------------------------------------------- hero ---- */

/** An honest product map, not a pretend customer website. When search is
 * available the business and one offering come from the same real record. */
function BusinessSystem({ live }: { live: SearchResponse | null }) {
  const business = live?.businesses.find((b) =>
    live.offerings.some((o) => o.business_id === b.business_id)
  ) ?? live?.businesses[0]
  const offering = business
    ? live?.offerings.find((o) => o.business_id === business.business_id)
    : undefined

  return <div className="ui-system-map" aria-label="How a business connects across LOCAH">
    <div className="ui-system-map__top"><span>01 / The business</span><strong>{business?.display_name ?? 'Your business'}</strong><p>{business?.description ?? 'Start by telling LOCAH what you do.'}</p></div>
    <div className="ui-system-map__connector" aria-hidden="true"><span>↓</span></div>
    <div className="ui-system-map__grid">
      <div><span>02 / Presence</span><strong>Website</strong><p>Pages you can review and edit</p></div>
      <div><span>03 / Discovery</span><strong>Marketplace</strong><p>Findable when you publish</p></div>
      <div><span>04 / Operations</span><strong>Workspace</strong><p>{offering ? `One place to manage ${offering.title}` : 'The tools your business needs'}</p></div>
    </div>
    <div className="ui-system-map__foot">One business record <span aria-hidden="true">↗</span> Connected places to work</div>
  </div>
}

function Hero({ live }: { live: SearchResponse | null }) {
  return (
    <section className="lc-section lc-ground-paper hp-hero">
      <div className="lc-container lc-container--wide">
        <div className="lc-split">
          <div className="lc-rise lc-rise-1">
            <p className="lc-eyebrow">Local Businesses. Limitless Possibilities.</p>
            <h1 className="lc-display">
              Tell us about your business. <span className="lc-mark">We help you run it.</span>
            </h1>
            <p className="lc-lead">
              Start with a conversation. LOCAH turns what it learns into a website, a place to be
              discovered and the tools to manage what happens next — together, not stitched together.
            </p>
            <div className="lc-row" style={{ marginTop: 'var(--sp-6)' }}>
              <Link className="lc-btn lc-btn--primary lc-btn--lg" href="/start">
                Get started
              </Link>
              <Link className="lc-btn lc-btn--ghost lc-btn--lg" href="/how-it-works">
                See how it works
              </Link>
            </div>
            <p className="lc-small lc-muted" style={{ marginTop: 'var(--sp-4)' }}>
              No card required to set up. Your site stays private until you publish it.
            </p>
          </div>

          <div className="lc-rise lc-rise-2"><BusinessSystem live={live} /></div>
        </div>
      </div>
    </section>
  )
}

function Transformation() {
  return <section className="ui-transformation" aria-labelledby="transformation-title">
    <div className="lc-container lc-container--wide">
      <div className="ui-transformation__heading"><p className="lc-eyebrow">One conversation. A connected business.</p><h2 id="transformation-title">From what you know to what customers see.</h2></div>
      <div className="ui-transformation__flow">
        <div><span>01 / Tell us</span><strong>“Here is what my business does.”</strong><p>Speak in your own words.</p></div>
        <div><span>02 / Make sense of it</span><strong>A clear business foundation.</strong><p>Review the details before they travel.</p></div>
        <div><span>03 / Put it to work</span><strong>Presence and operations, connected.</strong><p>Website, discovery and relevant tools.</p></div>
      </div>
    </div>
  </section>
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
          <h2>Every part of the business should know the other parts.</h2>
        </div>

        <div className="ui-journey-grid">
          {JOURNEY.map((j, i) => (
            <article className="ui-journey-card" key={j.title}>
              <p className="lc-eyebrow">0{i + 1} / {j.eyebrow}</p>
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
        <Link className="lc-link lc-link--accent ui-journey-more" href="/product">Explore the connected product →</Link>
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
              LOCAH models what you offer, how people reach you and which tools you need to run it.
              Your presence and Workspace can reflect the business you actually have.
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
              Your answers become a shared starting point for your business profile, website and
              operating tools. You review them before anything is published.
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
                  When your business is published and its modules are enabled, customers can find
                  you and their orders or bookings arrive in your Workspace.
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
              Start with what makes your business yours. Build its presence, connect the right tools
              and keep everything current from one Workspace.
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
        <Transformation />
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
