import type { Metadata } from 'next'
import { notFound } from 'next/navigation'
import { PublicNav } from '@/components/public/PublicNav'
import { Hero } from '@/components/home/HomeSections'
import { ListingCard } from '@/components/marketplace/ListingCard'
import { CategoryIcon, familyTint } from '@/components/marketplace/CategoryIcon'
import type { Listing } from '@/lib/marketplace-api'
import '../../home.css'
import '../../marketplace/marketplace.css'
import './lab.css'

/**
 * /_internal/design-lab — LOCAH's own components in every state, for review.
 *
 * Not linked from anywhere, not indexed, and off in production unless
 * LOCAH_DESIGN_LAB=1 is set. Everything here is example data and says so.
 * Tenant website components are deliberately absent: they are styled only by
 * each business's theme and are not part of LOCAH's design system.
 */

export const dynamic = 'force-dynamic'

export const metadata: Metadata = {
  title: 'Design lab — LOCAH internal',
  robots: { index: false, follow: false },
}

const EXAMPLE_BUSINESSES = [
  { id: '00000000-0000-0000-0000-000000000001', display_name: 'Example Kitchen' },
  { id: '00000000-0000-0000-0000-000000000002', display_name: 'Example Salon' },
]

function listing(overrides: Partial<Listing>): Listing {
  return {
    result_type: 'business',
    business_id: overrides.slug || 'example',
    slug: 'example',
    display_name: 'Example business',
    description: 'Example description, written the way an owner would describe their business.',
    capability_flags: {},
    actions: [{ action: 'visit_website', label: 'Visit website', href: '#' }],
    highlights: [],
    ...overrides,
  }
}

const CARDS: Array<{ note: string; listing: Listing }> = [
  {
    note: 'Food: orders on, items listed',
    listing: listing({
      slug: 'ex-food', display_name: 'Example Home Kitchen', family: 'food-drink', family_label: 'Food & Drink',
      category: 'home-kitchens', category_label: 'Home Kitchens', area_label: 'Example Nagar, Chennai', icon: 'bowl',
      highlights: [{ title: 'Podi', image_url: null }, { title: 'Pickles', image_url: null }],
      actions: [
        { action: 'order', label: 'Order online', href: '#' },
        { action: 'whatsapp', label: 'WhatsApp', href: '#' },
        { action: 'visit_website', label: 'Visit website', href: '#' },
      ],
    }),
  },
  {
    note: 'Property: enquiries, projects',
    listing: listing({
      slug: 'ex-prop', display_name: 'Example Homes', family: 'real-estate', family_label: 'Real Estate',
      category: 'developers', category_label: 'Developers & Builders', area_label: 'OMR, Chennai', icon: 'building',
      highlights: [{ title: 'Example Meadows, villas', image_url: null }],
      actions: [
        { action: 'enquire', label: 'Send an enquiry', href: '#' },
        { action: 'call', label: 'Call', href: '#' },
        { action: 'visit_website', label: 'Visit website', href: '#' },
      ],
    }),
  },
  {
    note: 'Appointments: bookings on, exact distance',
    listing: listing({
      slug: 'ex-appt', display_name: 'Example Dental', family: 'health', family_label: 'Healthcare',
      category: 'dental', category_label: 'Dental', area_label: 'Example Street, Madurai', icon: 'cross',
      distance_km: 2.4, reason: 'You looked at Dental',
      actions: [
        { action: 'book', label: 'Book', href: '#' },
        { action: 'call', label: 'Call', href: '#' },
        { action: 'visit_website', label: 'Visit website', href: '#' },
      ],
    }),
  },
  {
    note: 'Trade: no module actions, website only',
    listing: listing({
      slug: 'ex-trade', display_name: 'Example Pumps', family: 'industrial', family_label: 'Industrial & Manufacturing',
      category: 'machinery', category_label: 'Machinery & Pumps', area_label: 'Kurichi, Coimbatore', icon: 'gear',
    }),
  },
]

export default function DesignLabPage() {
  if (process.env.NODE_ENV === 'production' && process.env.LOCAH_DESIGN_LAB !== '1') notFound()
  return (
    <div className="locah-public">
      <div className="lab-banner">Internal design lab. Everything on this page is example data.</div>

      <section className="lab-section">
        <h2 className="lab-h">Navigation, signed out</h2>
        <PublicNav active="marketplace" />
        <h2 className="lab-h">Navigation, signed in as an owner</h2>
        <PublicNav signedIn businesses={EXAMPLE_BUSINESSES} />
        <h2 className="lab-h">Navigation, signed in as a customer</h2>
        <PublicNav signedIn audience="consumer" />
      </section>

      <section className="lab-section">
        <h2 className="lab-h">Homepage hero, signed in</h2>
        <Hero workspaceHref="#" businessName={EXAMPLE_BUSINESSES[0].display_name} />
      </section>

      <section className="lab-section lc-container lc-container--wide">
        <h2 className="lab-h">Palette</h2>
        <div className="lab-swatches">
          {['paper', 'cream', 'ink', 'night', 'action', 'orange', 'tint-haldi', 'tint-neem', 'tint-indigo', 'tint-clay', 'tint-lotus', 'tint-river', 'tint-sand'].map((t) => (
            <div key={t} className="lab-swatch">
              <span style={{ background: `var(--lc-${t})` }} />
              <code>--lc-{t}</code>
            </div>
          ))}
        </div>
        <h2 className="lab-h">Type</h2>
        <p style={{ fontFamily: 'var(--lc-font-head)', fontStretch: '108%', fontWeight: 620, fontSize: '3rem', lineHeight: 1.05 }}>
          Anek Latin, headlines
        </p>
        <p className="lc-serif" style={{ fontSize: '2.6rem', lineHeight: 1.1 }}>Instrument Serif, one line at a time</p>
        <p style={{ maxWidth: '60ch' }}>Plus Jakarta Sans for reading and controls. Body text stays at 16px or more; nothing is set below 12px.</p>
      </section>

      <section className="lab-section lc-container lc-container--wide">
        <h2 className="lab-h">Listing cards, by kind of business</h2>
        <ul className="mx-grid">
          {CARDS.map((c) => (
            <li key={c.note} style={{ flexDirection: 'column', gap: '0.5rem' }}>
              <code className="lab-note">{c.note}</code>
              <ListingCard listing={c.listing} />
            </li>
          ))}
        </ul>
      </section>

      <section className="lab-section lc-container lc-container--wide">
        <h2 className="lab-h">Category glyphs</h2>
        <div className="lab-glyphs">
          {['bowl', 'basket', 'storefront', 'hanger', 'scissors', 'dumbbell', 'cross', 'book', 'briefcase', 'shield', 'building', 'ruler', 'wrench', 'car', 'bed', 'sparkle', 'camera', 'chip', 'gear', 'boxes', 'truck', 'leaf', 'sun', 'paw', 'key', 'people'].map((g) => (
            <span key={g} className="lab-glyph" data-tint={familyTint(g)}>
              <CategoryIcon name={g} size={26} />
              <code>{g}</code>
            </span>
          ))}
        </div>
      </section>

      <section className="lab-section lc-container lc-container--wide">
        <h2 className="lab-h">Empty and error states</h2>
        <div className="mx-empty">
          <p className="mx-empty__title">No one is listed in Pets yet.</p>
          <p>Businesses appear here once they publish a website on LOCAH and choose to be listed.</p>
        </div>
        <div className="mx-empty">
          <p className="mx-empty__title">The Marketplace is not responding right now.</p>
          <p>Search still works from the box above, or try again in a moment.</p>
        </div>
        <p className="mx-note">Nothing matched every word, so these match some of them.</p>
      </section>
    </div>
  )
}
