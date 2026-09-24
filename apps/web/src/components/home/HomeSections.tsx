import Link from 'next/link'
import type { Listing } from '@/lib/marketplace-api'
import {
  CORE_MODULES,
  LAUNCH_MODULES,
  REFERENCE_MODELS,
  ROADMAP_MODULES,
} from '@/lib/product-catalogue'
import { ListingCard } from '@/components/marketplace/ListingCard'
import { LivingSystem } from './LivingSystem'

/* Every snippet below is built from the same kind of markup the product uses,
   filled with example content and labelled as an example. Nothing here is a
   screenshot, and no number on this page describes LOCAH's own business. */

function ExampleTag({ children = 'Example' }: { children?: string }) {
  return <span className="hx-example">{children}</span>
}

/* ---------------------------------------------------------------- hero ---- */

export function Hero({
  workspaceHref,
  businessName,
}: {
  workspaceHref?: string
  businessName?: string
}) {
  return (
    <section className="hx-hero" aria-labelledby="hx-hero-title">
      <div className="lc-container lc-container--wide hx-hero__grid">
        <div className="hx-hero__copy">
          <h1 id="hx-hero-title" className="hx-hero__title">
            <span>From one conversation</span>
            <span className="hx-hero__serif">to a living business.</span>
          </h1>
          <p className="hx-hero__lead">
            Tell LOCAH about your business in your own words. It builds your website, lists you where
            people nearby are looking, and gives you one place to take orders, bookings and
            payments, all working from the same facts.
          </p>
          <div className="hx-hero__ctas">
            {workspaceHref ? (
              <a className="lc-btn lc-btn--primary lc-btn--lg" href={workspaceHref}>
                Open {businessName ? businessName : 'Workspace'}
              </a>
            ) : (
              <Link className="lc-btn lc-btn--primary lc-btn--lg" href="/start">
                Start your business
              </Link>
            )}
            <Link className="lc-btn lc-btn--ghost lc-btn--lg" href="/marketplace">
              Explore the Marketplace
            </Link>
          </div>
          <p className="hx-hero__fine">
            {workspaceHref
              ? 'Welcome back. Your businesses are in the menu at the top right.'
              : 'No card needed to set up. Nothing is public until you publish.'}
          </p>
        </div>
        <div className="hx-hero__visual">
          <LivingSystem />
        </div>
      </div>
    </section>
  )
}

/* ------------------------------------------------ conversation → system ---- */

const CHAT: Array<{ who: 'owner' | 'locah'; text: string }> = [
  { who: 'owner', text: 'I run a home kitchen in Anna Nagar. Podi, pickles, and biryani on weekends. Right now people order on WhatsApp.' },
  { who: 'locah', text: 'Do customers collect, or do you deliver?' },
  { who: 'owner', text: 'Pickup all week. On Sundays I deliver within 5 km.' },
  { who: 'locah', text: 'Then you need a menu, weekend pre-orders, and pickup or delivery. Here is what I understood.' },
]

export function ConversationToSystem() {
  return (
    <section className="hx-convo" aria-labelledby="hx-convo-title">
      <div className="lc-container lc-container--wide">
        <div className="hx-head">
          <h2 id="hx-convo-title">You talk. LOCAH writes it down properly.</h2>
          <p>
            No forms to fill in first. What you say becomes your business record, and everything
            else is built from it. You check it before anything goes live.
          </p>
        </div>
        <div className="hx-convo__grid">
          <div className="hx-chat" aria-label="Example conversation">
            <div className="hx-chat__bar">
              <span>Setting up</span>
              <ExampleTag>Example conversation</ExampleTag>
            </div>
            <ol className="hx-chat__list">
              {CHAT.map((m, i) => (
                <li key={i} className={`hx-chat__msg hx-chat__msg--${m.who}`}>
                  <span className="lc-sr">{m.who === 'owner' ? 'Owner:' : 'LOCAH:'}</span>
                  {m.text}
                </li>
              ))}
            </ol>
            <div className="hx-chat__compose" aria-hidden="true">
              <span>Type or speak your answer</span>
              <span className="hx-chat__mic" />
            </div>
          </div>

          <div className="hx-derived" aria-label="What LOCAH set up from that conversation">
            <div className="hx-derived__row hx-derived__row--head">
              <span className="hx-derived__label">Your business</span>
              <strong>Home Kitchen</strong>
              <span className="hx-derived__meta">Anna Nagar, Chennai</span>
            </div>
            <div className="hx-derived__row">
              <span className="hx-derived__label">On the menu</span>
              <div className="hx-chips">
                <span>Podi</span>
                <span>Pickles</span>
                <span>Weekend biryani</span>
              </div>
            </div>
            <div className="hx-derived__row">
              <span className="hx-derived__label">Switched on</span>
              <div className="hx-chips hx-chips--on">
                <span>Offerings</span>
                <span>Orders</span>
                <span>Payments</span>
                <span>Pickup and delivery</span>
              </div>
            </div>
            <div className="hx-derived__row">
              <span className="hx-derived__label">Website pages</span>
              <div className="hx-chips">
                <span>Menu</span>
                <span>How ordering works</span>
                <span>Contact</span>
              </div>
            </div>
            <div className="hx-derived__row">
              <span className="hx-derived__label">Marketplace</span>
              <span>Food &amp; Drink, Home Kitchens, once you publish and choose to be listed</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}

/* ------------------------------------------------------- connected bento ---- */

export function ConnectedBento() {
  return (
    <section className="hx-bento-wrap" aria-labelledby="hx-bento-title">
      <div className="lc-container lc-container--wide">
        <div className="hx-head hx-head--split">
          <h2 id="hx-bento-title">Everything knows about everything else.</h2>
          <p>
            Change a price once and it changes on your website, in your listing and at checkout. An
            order placed on your site is already waiting in your Workspace.
          </p>
        </div>

        <div className="hx-bento">
          <article className="hx-tile hx-tile--site">
            <header>
              <h3>Website</h3>
              <ExampleTag />
            </header>
            <div className="hx-mini-site">
              <p className="hx-mini-site__kicker">This weekend</p>
              <p className="hx-mini-site__title">Mutton biryani, pre-order by Friday</p>
              <div className="hx-mini-site__row">
                <span>Serves 2</span>
                <span className="hx-mini-site__btn">Add to order</span>
              </div>
            </div>
            <p className="hx-tile__foot">Built from your facts as pages and sections you can edit.</p>
          </article>

          <article className="hx-tile hx-tile--market">
            <header>
              <h3>Marketplace</h3>
              <ExampleTag />
            </header>
            <div className="hx-mini-listing">
              <span className="hx-mini-listing__mark" aria-hidden="true">H</span>
              <div>
                <strong>Home Kitchen</strong>
                <small>Home Kitchens · Anna Nagar</small>
              </div>
            </div>
            <p className="hx-tile__foot">Found by what you sell and where you are.</p>
          </article>

          <article className="hx-tile hx-tile--orders">
            <header>
              <h3>Orders</h3>
              <ExampleTag />
            </header>
            <ul className="hx-mini-orders">
              <li>
                <span>2 × Mutton biryani</span>
                <span className="hx-state hx-state--new">New</span>
              </li>
              <li>
                <span>Podi combo</span>
                <span className="hx-state">Ready</span>
              </li>
            </ul>
          </article>

          <article className="hx-tile hx-tile--book">
            <header>
              <h3>Bookings</h3>
              <ExampleTag />
            </header>
            <div className="hx-slots" aria-hidden="true">
              <span>10:00</span>
              <span className="is-on">10:30</span>
              <span>11:00</span>
              <span className="is-off">11:30</span>
            </div>
            <p className="hx-tile__foot">Against real availability, for salons, clinics, classes and stays.</p>
          </article>

          <article className="hx-tile hx-tile--pay">
            <header>
              <h3>Payments</h3>
              <ExampleTag />
            </header>
            <p className="hx-mini-pay">
              <span className="lc-num">₹840</span>
              <small>Paid online · order ready for pickup</small>
            </p>
          </article>

          <article className="hx-tile hx-tile--team">
            <header>
              <h3>Team</h3>
              <ExampleTag />
            </header>
            <p className="hx-mini-team">
              <span aria-hidden="true">R</span>
              Ravi can update orders. He cannot see payouts.
            </p>
          </article>
        </div>
      </div>
    </section>
  )
}

/* ------------------------------------------------------------ how it works ---- */

const STEPS = [
  {
    title: 'Talk it through',
    body: 'Answer a few questions in your own words, typed or spoken. The questions change with the kind of business you run.',
    snippet: (
      <div className="hx-step__snip hx-step__snip--ask">
        <p>What do most customers come to you for?</p>
        <span className="hx-step__input">Weekend biryani and podi</span>
      </div>
    ),
  },
  {
    title: 'Check what LOCAH understood',
    body: 'Every fact is shown back to you. Correct anything before it is used.',
    snippet: (
      <ul className="hx-step__snip hx-step__snip--facts">
        <li>Home kitchen</li>
        <li>Anna Nagar, Chennai</li>
        <li>Pickup, Sunday delivery</li>
      </ul>
    ),
  },
  {
    title: 'Publish when it reads right',
    body: 'Your website stays private until you publish. Listing in the Marketplace is a separate choice.',
    snippet: (
      <div className="hx-step__snip hx-step__snip--publish">
        <span className="hx-switch" aria-hidden="true" />
        <span>List me in the Marketplace</span>
      </div>
    ),
  },
  {
    title: 'Run the day from one place',
    body: 'Orders, bookings, enquiries and payments arrive in your Workspace as work to do.',
    snippet: (
      <div className="hx-step__snip hx-step__snip--run">
        <span>New order</span>
        <strong>2 × Mutton biryani</strong>
      </div>
    ),
  },
]

export function HowItWorks() {
  return (
    <section className="hx-how" aria-labelledby="hx-how-title">
      <div className="lc-container lc-container--wide">
        <div className="hx-head hx-head--split">
          <h2 id="hx-how-title">Four steps from first word to first order.</h2>
          <p>
            <Link className="lc-link lc-link--accent" href="/how-it-works">
              Read how it works in detail
            </Link>
          </p>
        </div>
        <ol className="hx-steps">
          {STEPS.map((s, i) => (
            <li key={s.title} className="hx-step">
              <span className="hx-step__n lc-num" aria-hidden="true">
                {i + 1}
              </span>
              <h3>{s.title}</h3>
              <p>{s.body}</p>
              {s.snippet}
            </li>
          ))}
        </ol>
        <p className="hx-how__note">
          <ExampleTag /> The snippets show example content.
        </p>
      </div>
    </section>
  )
}

/* ------------------------------------------------------- live marketplace ---- */

export function LiveMarketplace({ listings, total }: { listings: Listing[]; total: number }) {
  if (listings.length === 0) return null
  return (
    <section className="hx-live" aria-labelledby="hx-live-title">
      <div className="lc-container lc-container--wide">
        <div className="hx-head hx-head--split">
          <div>
            <h2 id="hx-live-title">Open on LOCAH right now.</h2>
            <p className="hx-live__count">
              {total === 1 ? 'One business has' : `${total} businesses have`} published and chosen to be
              listed. These are real listings.
            </p>
          </div>
          <Link className="lc-btn lc-btn--ink" href="/marketplace">
            Browse the Marketplace
          </Link>
        </div>
        <div className="hx-rail" role="list">
          {listings.slice(0, 8).map((l) => (
            <div role="listitem" key={l.business_id} className="hx-rail__item">
              <ListingCard listing={l} />
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

/* ---------------------------------------------------- what LOCAH can become ---- */

const GROUPS: Array<{ title: string; line: string; models: string[] }> = [
  {
    title: 'Sell',
    line: 'Menus, products and stock, ordered and paid for.',
    models: ['Food business', 'Retail commerce', 'High-frequency retail'],
  },
  {
    title: 'Serve',
    line: 'Time with you, booked against real availability.',
    models: ['Appointment services', 'Membership business', 'Education & cohorts', 'Repair & home services'],
  },
  {
    title: 'Host',
    line: 'Rooms and resources, reserved by date.',
    models: ['Accommodation', 'Rental & resources'],
  },
  {
    title: 'Win work',
    line: 'Enquiries followed up until they are won or lost.',
    models: ['Lead-driven business', 'Professional services'],
  },
]

export function WhatItBecomes() {
  const byName = new Map(REFERENCE_MODELS.map((m) => [m.name, m]))
  return (
    <section className="hx-become" aria-labelledby="hx-become-title">
      <div className="lc-container lc-container--wide">
        <div className="hx-head">
          <h2 id="hx-become-title">A kitchen and a clinic should not get the same system.</h2>
          <p>
            LOCAH is designed around how different businesses actually trade, and switches on only
            what yours needs.
          </p>
        </div>
        <div className="hx-become__grid">
          {GROUPS.map((g) => (
            <div className="hx-become__group" key={g.title}>
              <h3 className="hx-become__title">{g.title}</h3>
              <p className="hx-become__line">{g.line}</p>
              <ul>
                {g.models.map((name) => {
                  const m = byName.get(name)
                  if (!m) return null
                  return (
                    <li key={name}>
                      <strong>{m.examples}</strong>
                      <span>{m.path}</span>
                    </li>
                  )
                })}
              </ul>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

/* -------------------------------------------------------- module ecosystem ---- */

export function ModuleEcosystem() {
  return (
    <section className="hx-mods" aria-labelledby="hx-mods-title">
      <div className="lc-container lc-container--wide hx-mods__grid">
        <div>
          <h2 id="hx-mods-title">Built as modules. Switched on when you need them.</h2>
          <p className="hx-mods__lead">
            Every business starts with the foundation. The rest is there when your business grows
            into it, and out of the way until then.
          </p>
          <Link className="lc-link lc-link--accent" href="/capabilities">
            See every capability
          </Link>
        </div>
        <div className="hx-mods__rings">
          <div className="hx-ring">
            <p className="hx-ring__label">Always on</p>
            <div className="hx-ring__chips">
              {CORE_MODULES.map((m) => (
                <span key={m.id}>{m.name}</span>
              ))}
            </div>
          </div>
          <div className="hx-ring hx-ring--launch">
            <p className="hx-ring__label">Switch on at any time</p>
            <div className="hx-ring__chips">
              {LAUNCH_MODULES.map((m) => (
                <span key={m.id} title={m.blurb}>
                  {m.name}
                </span>
              ))}
            </div>
          </div>
          <div className="hx-ring hx-ring--later">
            <p className="hx-ring__label">Planned, not yet available</p>
            <div className="hx-ring__chips">
              {ROADMAP_MODULES.slice(0, 8).map((m) => (
                <span key={m.id}>{m.name}</span>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}

/* ----------------------------------------------------------- why different ---- */

export function WhyDifferent() {
  return (
    <section className="hx-why" aria-labelledby="hx-why-title">
      <div className="lc-container lc-container--wide">
        <h2 id="hx-why-title" className="hx-why__title">
          Why LOCAH is different
        </h2>
        <div className="hx-why__grid">
          <div>
            <p className="hx-why__big">One business, one record.</p>
            <p>
              Your website, listing, checkout and Workspace read the same facts. There is nothing to
              keep in sync because there is only one copy.
            </p>
          </div>
          <div>
            <p className="hx-why__big">Your website is yours to change.</p>
            <p>
              It is made of pages and sections, not code. Edit any word or picture, and publish
              only when it reads right.
            </p>
          </div>
          <div>
            <p className="hx-why__big">No invented stars.</p>
            <p>
              The Marketplace shows what a business published and what you can actually do there.
              No fake ratings, no paid-looking badges, no guessed opening hours.
            </p>
          </div>
        </div>
      </div>
    </section>
  )
}

/* ---------------------------------------------------------- pricing preview ---- */

export function PricingPreview() {
  return (
    <section className="hx-price" aria-labelledby="hx-price-title">
      <div className="lc-container lc-container--wide hx-price__grid">
        <h2 id="hx-price-title">Start free. Pay when you are open for business.</h2>
        <div className="hx-price__cols">
          <div>
            <p className="hx-price__label">Pay as you go</p>
            <p className="hx-price__amount lc-num">₹499</p>
            <p className="hx-price__unit">per website build and publish, with 30 days of hosting</p>
          </div>
          <div>
            <p className="hx-price__label">LOCAH Monthly</p>
            <p className="hx-price__amount lc-num">₹999</p>
            <p className="hx-price__unit">a month per business: hosting, Workspace and up to 5 rebuilds</p>
          </div>
        </div>
        <p className="hx-price__fine">
          Prices in Indian Rupees; GST is shown before payment. What your customers pay you is
          separate.{' '}
          <Link className="lc-link lc-link--accent" href="/pricing">
            Full pricing
          </Link>
        </p>
      </div>
    </section>
  )
}

/* ---------------------------------------------------------------- closing ---- */

export function ClosingCta({ signedIn }: { signedIn: boolean }) {
  return (
    <section className="hx-close" aria-labelledby="hx-close-title">
      <div className="lc-container lc-container--wide hx-close__inner">
        <h2 id="hx-close-title">
          <span>Tell us about your business.</span>
          <span className="hx-close__serif">We will help you run it.</span>
        </h2>
        <div className="hx-close__ctas">
          <Link className="lc-btn lc-btn--primary lc-btn--lg" href="/start">
            {signedIn ? 'Start another business' : 'Start your business'}
          </Link>
          <Link className="lc-btn lc-btn--light lc-btn--lg" href="/contact">
            Talk to us
          </Link>
        </div>
      </div>
    </section>
  )
}
