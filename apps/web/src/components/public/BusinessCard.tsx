import Link from 'next/link'

/** Human labels for the business types the platform actually supports. */
export const TYPE_LABELS: Record<string, string> = {
  restaurant: 'Restaurant',
  cafe: 'Café',
  retail: 'Shop',
  salon: 'Salon',
  spa: 'Spa',
  hotel: 'Hotel',
  homestay: 'Stay',
  gym: 'Gym',
  studio: 'Studio',
  clinic: 'Clinic',
  professional_service: 'Professional service',
  education: 'Classes',
  other: 'Local business',
  not_sure: 'Local business',
}

export function typeLabel(t?: string | null) {
  if (!t) return 'Local business'
  return TYPE_LABELS[t] || t.replace(/_/g, ' ')
}

/** What a visitor can do here, read from the capability flags the Marketplace
 *  projection actually publishes — never guessed from the business type.
 *  Keys are those emitted by marketplace_indexing: order, book, join, enquire,
 *  contact, visit_website. The last two are true for everyone, so they say
 *  nothing useful on a card and are left out. */
function capabilityChips(flags?: Record<string, boolean>): string[] {
  if (!flags) return []
  const out: string[] = []
  if (flags.order) out.push('Order online')
  if (flags.book) out.push('Book')
  if (flags.join) out.push('Memberships')
  if (flags.enquire) out.push('Enquire')
  return out.slice(0, 3)
}

export type MarketplaceBusiness = {
  business_id: string
  slug: string
  display_name: string
  description?: string | null
  business_type?: string | null
  city?: string | null
  capability_flags?: Record<string, boolean>
}

export function BusinessCard({ business, featured = false }: { business: MarketplaceBusiness; featured?: boolean }) {
  const chips = capabilityChips(business.capability_flags)
  const initial = business.display_name.trim().slice(0, 1).toUpperCase()

  return (
    <Link className={`lc-mediacard${featured ? ' mk-featured-card' : ''}`} href={`/${business.slug}`}>
      {/* No photo yet: a monogram tinted by trade, so a gym and a bakery are
          visually distinct. Deliberately not a stock photo — the card should
          not imply imagery the business has not supplied. */}
      <div className="lc-mediacard__media">
        <div
          className="lc-mediacard__fallback"
          data-type={business.business_type || 'other'}
          aria-hidden="true"
        >
          {initial}
        </div>
      </div>
      <div className="lc-mediacard__body">
        {featured ? <p className="lc-eyebrow">In focus / Local business</p> : null}
        <h3 className="lc-mediacard__title">{business.display_name}</h3>
        <p className="lc-mediacard__meta">
          {typeLabel(business.business_type)}
          {business.city ? ` · ${business.city}` : ''}
        </p>
        {business.description ? (
          <p className="lc-muted lc-small mk-clamp">{business.description}</p>
        ) : null}
        {chips.length > 0 ? (
          <div className="lc-mediacard__foot">
            {chips.map((c) => (
              <span className="lc-badge" key={c}>
                {c}
              </span>
            ))}
          </div>
        ) : null}
      </div>
    </Link>
  )
}
