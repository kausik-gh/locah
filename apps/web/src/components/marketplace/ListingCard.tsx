import Link from 'next/link'
import type { Listing, ListingAction } from '@/lib/marketplace-api'
import { CategoryIcon, familyTint } from './CategoryIcon'
import './listing-card.css'

/**
 * One Business as the Marketplace shows it.
 *
 * The card adapts to what kind of business it is, because people decide
 * differently: a kitchen by what it cooks, a developer by its projects, a
 * salon by whether it takes bookings, a supplier by what it supplies. It
 * only shows a rating when published verified reviews exist, and never shows
 * "popular", "open now" or a delivery time without evidence. It only offers an
 * action the API says works right now.
 */

type Variant = 'food' | 'property' | 'appointment' | 'trade' | 'general'

const VARIANT_BY_FAMILY: Record<string, Variant> = {
  'food-drink': 'food',
  'fresh-grocery': 'food',
  'real-estate': 'property',
  'build-interiors': 'property',
  beauty: 'appointment',
  fitness: 'appointment',
  health: 'appointment',
  learning: 'appointment',
  pets: 'appointment',
  'home-services': 'appointment',
  automotive: 'appointment',
  'stays-travel': 'appointment',
  events: 'appointment',
  industrial: 'trade',
  wholesale: 'trade',
  logistics: 'trade',
  professional: 'trade',
  finance: 'trade',
  technology: 'trade',
  agriculture: 'trade',
  energy: 'trade',
}

// Which action leads, per kind of business. Anything not listed falls back
// to the order the API returned.
// Every action appears in every order, so none is dropped: a developer that
// takes site-visit bookings shows Book, a restaurant that takes tables too.
const LEAD_ACTION: Record<Variant, string[]> = {
  food: ['order', 'book', 'whatsapp', 'call', 'enquire', 'join', 'request_quote', 'donate', 'site_visit'],
  property: ['site_visit', 'enquire', 'book', 'whatsapp', 'call', 'request_quote', 'order', 'join', 'donate'],
  appointment: ['book', 'join', 'whatsapp', 'call', 'enquire', 'request_quote', 'order', 'donate', 'site_visit'],
  trade: ['request_quote', 'enquire', 'order', 'call', 'whatsapp', 'book', 'join', 'site_visit', 'donate'],
  general: ['order', 'book', 'request_quote', 'enquire', 'join', 'donate', 'site_visit', 'whatsapp', 'call'],
}

export function variantFor(listing: Pick<Listing, 'family'>): Variant {
  return VARIANT_BY_FAMILY[listing.family || ''] || 'general'
}

export function pickActions(listing: Listing, max = 2): ListingAction[] {
  const actions = (listing.actions || []).filter((a) => a.action !== 'visit_website')
  // The business's own way of trading leads (a quote-led fabricator: "Get a
  // quote"; a subscription-led gym: its plans); the family order ranks the rest.
  const primary = listing.capability_flags?.primary
  const order = LEAD_ACTION[variantFor(listing)]
  const rank = (a: ListingAction) => (a.action === primary ? -1 : order.indexOf(a.action) < 0 ? 99 : order.indexOf(a.action))
  const ranked = [...actions].sort((a, b) => rank(a) - rank(b))
  return ranked.slice(0, max)
}

function isExternal(href: string) {
  return /^(https?:|tel:|mailto:)/.test(href)
}

// On a card there is room for one or two words.
const SHORT_LABEL: Record<string, string> = {
  order: 'Order',
  book: 'Book',
  enquire: 'Enquire',
  join: 'Plans',
  request_quote: 'Get a quote',
  site_visit: 'Site visit',
  donate: 'Donate',
  whatsapp: 'WhatsApp',
  call: 'Call',
}

export function ActionButton({
  action,
  primary,
  short,
  context,
}: {
  action: ListingAction
  primary?: boolean
  short?: boolean
  /** The business name, so "Call" is announced as "Call Crumb & Co". */
  context?: string
}) {
  const cls = `mx-act${primary ? ' mx-act--primary' : ''}`
  const label = short ? SHORT_LABEL[action.action] || action.label : action.label
  const aria = context ? `${action.label}, ${context}` : undefined
  if (isExternal(action.href)) {
    return (
      <a
        className={cls}
        href={action.href}
        aria-label={aria}
        {...(action.href.startsWith('http') ? { target: '_blank', rel: 'noopener noreferrer' } : {})}
      >
        {label}
      </a>
    )
  }
  return (
    <Link className={cls} href={action.href} aria-label={aria}>
      {label}
    </Link>
  )
}

export function ListingMedia({ listing, eager = false }: { listing: Listing; eager?: boolean }) {
  if (listing.cover_url) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        className="mx-card__img"
        src={listing.cover_url}
        alt=""
        loading={eager ? 'eager' : 'lazy'}
        decoding="async"
      />
    )
  }
  // No picture published: the family's glyph on its tint, and the initial.
  // Never a stock photo, which would show something this business is not.
  return (
    <div className="mx-card__fallback" data-tint={familyTint(listing.family)} aria-hidden="true">
      <CategoryIcon name={listing.icon} size={30} />
      <span>{listing.display_name.trim().slice(0, 1).toUpperCase()}</span>
    </div>
  )
}

function kicker(listing: Listing) {
  const what = listing.category_label || listing.family_label || 'Local business'
  const where = listing.area_label || listing.city
  return where ? `${what} · ${where}` : what
}

export function ListingCard({
  listing,
  size = 'md',
  eager = false,
}: {
  listing: Listing
  size?: 'md' | 'lg'
  eager?: boolean
}) {
  const variant = variantFor(listing)
  const actions = pickActions(listing, 2)
  const highlights = (listing.highlights || []).slice(0, 3)

  return (
    <article className={`mx-card mx-card--${variant} mx-card--${size}`}>
      <div className="mx-card__media">
        <ListingMedia listing={listing} eager={eager} />
        {listing.distance_km !== null && listing.distance_km !== undefined ? (
          <span className="mx-card__distance lc-num">
            {listing.distance_km < 1 ? 'Under 1 km' : `${listing.distance_km.toFixed(1)} km`}
          </span>
        ) : null}
      </div>
      <div className="mx-card__body">
        <p className="mx-card__kicker">{kicker(listing)}</p>
        <h3 className="mx-card__name">
          <Link className="mx-card__link" href={`/marketplace/${listing.slug}`}>
            {listing.display_name}
          </Link>
        </h3>
        {Boolean(listing.rating_count) && listing.rating_average != null ? (
          <p className="mx-card__rating" aria-label={`${listing.rating_average.toFixed(1)} out of 5 from ${listing.rating_count} verified reviews`}>
            <span aria-hidden="true">★</span> {listing.rating_average.toFixed(1)}
            <small>({listing.rating_count} verified)</small>
          </p>
        ) : null}
        {listing.description ? <p className="mx-card__desc">{listing.description}</p> : null}
        {highlights.length > 0 ? (
          <p className="mx-card__highlights">
            <span className="lc-sr">
              {variant === 'property' ? 'Projects: ' : variant === 'trade' ? 'Offers: ' : 'Includes: '}
            </span>
            {highlights.map((h) => (
              <span key={h.title}>{h.title}</span>
            ))}
          </p>
        ) : null}
        {listing.reason ? <p className="mx-card__reason">{listing.reason}</p> : null}
      </div>
      {actions.length > 0 ? (
        <div className="mx-card__actions">
          {actions.map((a, i) => (
            <ActionButton key={a.action} action={a} primary={i === 0} short context={listing.display_name} />
          ))}
        </div>
      ) : null}
    </article>
  )
}
