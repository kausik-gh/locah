import Link from 'next/link'
import type { ReactNode } from 'react'
import type { SearchResponse, TaxonomyFamily } from '@/lib/marketplace-api'
import { ListingCard } from './ListingCard'
import { CategoryIcon, familyTint } from './CategoryIcon'

export type ResultParams = {
  q?: string
  family?: string
  category?: string
  can?: string[]
  sort?: string
  location?: string
  offset?: number
}

const CAPABILITIES: Array<{ id: string; label: string }> = [
  { id: 'order', label: 'Order online' },
  { id: 'book', label: 'Book' },
  { id: 'enquire', label: 'Send an enquiry' },
  { id: 'join', label: 'Plans and memberships' },
]

const SORTS: Array<{ id: string; label: string; needsPlace?: boolean }> = [
  { id: 'relevance', label: 'Best match' },
  { id: 'nearest', label: 'Nearest', needsPlace: true },
  { id: 'newest', label: 'Newest' },
  { id: 'name', label: 'A to Z' },
]

export const PAGE_SIZE = 24

export type ResultSearchParams = {
  q?: string
  family?: string
  category?: string
  can?: string | string[]
  sort?: string
  location?: string
  offset?: string
  type?: string
}

export function parseResultParams(sp: ResultSearchParams): ResultParams {
  const can = Array.isArray(sp.can) ? sp.can : sp.can ? [sp.can] : []
  const offset = Math.max(0, Math.min(1000, Number(sp.offset) || 0))
  return {
    q: sp.q?.trim().slice(0, 200) || undefined,
    family: sp.family || undefined,
    category: sp.category || undefined,
    can: can.flatMap((c) => c.split(',')).filter(Boolean).slice(0, 4),
    sort: sp.sort || undefined,
    location: sp.location?.trim().slice(0, 80) || undefined,
    offset,
  }
}

/** Every filter is a plain link, so results work without JavaScript and every
 *  state has a URL someone can share. Category pages keep their path. */
function makeHref(base: ResultParams, basePath: string, lockedTaxonomy: boolean) {
  return (change: Partial<ResultParams>) => {
    const next: ResultParams = { ...base, offset: undefined, ...change }
    let path = basePath
    if (lockedTaxonomy && ('family' in change || 'category' in change)) {
      if (next.family) path = `/marketplace/category/${next.family}${next.category ? `/${next.category}` : ''}`
      else path = '/marketplace/search'
    }
    const qs = new URLSearchParams()
    if (next.q) qs.set('q', next.q)
    if (!path.startsWith('/marketplace/category')) {
      if (next.family) qs.set('family', next.family)
      if (next.category) qs.set('category', next.category)
    }
    for (const c of next.can || []) qs.append('can', c)
    if (next.sort && next.sort !== 'relevance') qs.set('sort', next.sort)
    if (next.location) qs.set('location', next.location)
    if (next.offset) qs.set('offset', String(next.offset))
    const s = qs.toString()
    return s ? `${path}?${s}` : path
  }
}

function FilterPanel({
  data,
  families,
  params,
  href,
  placeLabel,
}: {
  data: SearchResponse
  families: TaxonomyFamily[]
  params: ResultParams
  href: (c: Partial<ResultParams>) => string
  placeLabel?: string | null
}) {
  const facets = data.facets || { families: {}, categories: {}, capabilities: {} }
  const selectedFamily = families.find((f) => f.id === params.family)
  const can = params.can || []
  const total = data.page?.total ?? data.counts.businesses
  const showCaps = total > 0 || can.length > 0
  const familyOptions = families
    .filter((f) => (facets.families[f.id] || 0) > 0)
    .sort((a, b) => (facets.families[b.id] || 0) - (facets.families[a.id] || 0))

  return (
    <div className="mx-filters">
      <div className="mx-filters__group">
        <p className="mx-filters__title">Category</p>
        {selectedFamily ? (
          <ul>
            <li>
              <Link href={href({ family: undefined, category: undefined })} className="mx-filters__back">
                All categories
              </Link>
            </li>
            <li>
              <Link
                href={href({ category: undefined })}
                aria-current={!params.category ? 'true' : undefined}
                className="mx-filters__opt"
              >
                <span>All {selectedFamily.label}</span>
                <span className="lc-num">{facets.families[selectedFamily.id] || 0}</span>
              </Link>
            </li>
            {selectedFamily.categories
              .filter((c) => (facets.categories[c.id] || 0) > 0 || c.id === params.category)
              .map((c) => (
                <li key={c.id}>
                  <Link
                    href={href({ category: c.id })}
                    aria-current={params.category === c.id ? 'true' : undefined}
                    className="mx-filters__opt"
                  >
                    <span>{c.label}</span>
                    <span className="lc-num">{facets.categories[c.id] || 0}</span>
                  </Link>
                </li>
              ))}
          </ul>
        ) : familyOptions.length > 0 ? (
          <ul>
            {familyOptions.map((f) => (
              <li key={f.id}>
                <Link href={href({ family: f.id, category: undefined })} className="mx-filters__opt">
                  <span className="mx-filters__glyph" data-tint={familyTint(f.id)}>
                    <CategoryIcon name={f.icon} size={14} />
                  </span>
                  <span>{f.label}</span>
                  <span className="lc-num">{facets.families[f.id]}</span>
                </Link>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mx-filters__none">No categories in these results.</p>
        )}
      </div>

      {showCaps ? (
      <div className="mx-filters__group">
        <p className="mx-filters__title">What you can do</p>
        <ul>
          {CAPABILITIES.filter((c) => (facets.capabilities[c.id] || 0) > 0 || can.includes(c.id)).map((c) => {
            const on = can.includes(c.id)
            return (
              <li key={c.id}>
                <Link
                  href={href({ can: on ? can.filter((x) => x !== c.id) : [...can, c.id] })}
                  className="mx-filters__opt mx-filters__opt--check"
                  aria-current={on ? 'true' : undefined}
                >
                  <span className="mx-filters__box" aria-hidden="true" />
                  <span>{c.label}</span>
                  <span className="lc-num">{facets.capabilities[c.id] || 0}</span>
                </Link>
              </li>
            )
          })}
        </ul>
        {CAPABILITIES.every((c) => !(facets.capabilities[c.id] || 0) && !can.includes(c.id)) ? (
          <p className="mx-filters__none">These businesses take contact by phone, WhatsApp or their website.</p>
        ) : null}
      </div>
      ) : null}

      {placeLabel || params.location ? (
        <div className="mx-filters__group">
          <p className="mx-filters__title">Where</p>
          <ul>
            {params.location ? (
              <li>
                <Link href={href({ location: undefined })} className="mx-filters__opt" aria-current="true">
                  <span className="mx-filters__box" aria-hidden="true" />
                  <span>Only in {params.location}</span>
                </Link>
              </li>
            ) : placeLabel ? (
              <li>
                <Link href={href({ location: placeLabel })} className="mx-filters__opt mx-filters__opt--check">
                  <span className="mx-filters__box" aria-hidden="true" />
                  <span>Only in {placeLabel}</span>
                </Link>
              </li>
            ) : null}
          </ul>
        </div>
      ) : null}

      <div className="mx-filters__group">
        <p className="mx-filters__title">Sort</p>
        <ul className="mx-filters__sorts">
          {SORTS.filter((s) => !s.needsPlace || placeLabel).map((s) => (
            <li key={s.id}>
              <Link
                href={href({ sort: s.id })}
                aria-current={(params.sort || 'relevance') === s.id ? 'true' : undefined}
              >
                {s.label}
              </Link>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
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

export function ResultsView({
  data,
  families,
  params,
  basePath,
  lockedTaxonomy = false,
  title,
  intro,
  below,
  placeLabel,
}: {
  data: SearchResponse | null
  families: TaxonomyFamily[]
  params: ResultParams
  basePath: string
  lockedTaxonomy?: boolean
  title: string
  intro?: string
  /** Rendered under the heading: a category's blurb and sub-categories. */
  below?: ReactNode
  placeLabel?: string | null
}) {
  const href = makeHref(params, basePath, lockedTaxonomy)
  const familyLabel = families.find((f) => f.id === params.family)?.label
  const categoryLabel = families
    .find((f) => f.id === params.family)
    ?.categories.find((c) => c.id === params.category)?.label
  const total = data?.page?.total ?? data?.counts.businesses ?? 0
  const offset = params.offset || 0
  const listings = data?.businesses || []
  const activeChips: Array<{ label: string; href: string }> = []
  if (params.q) activeChips.push({ label: `“${params.q}”`, href: href({ q: undefined }) })
  if (familyLabel && !lockedTaxonomy) activeChips.push({ label: categoryLabel || familyLabel, href: href({ family: undefined, category: undefined }) })
  for (const c of params.can || []) {
    const cap = CAPABILITIES.find((x) => x.id === c)
    if (cap) activeChips.push({ label: cap.label, href: href({ can: (params.can || []).filter((x) => x !== c) }) })
  }
  if (params.location) activeChips.push({ label: `In ${params.location}`, href: href({ location: undefined }) })
  const filterCount = activeChips.length - (params.q ? 1 : 0)

  const summary = [
    `${total} ${total === 1 ? 'business' : 'businesses'}`,
    params.q ? `for “${params.q}”` : null,
    params.location ? `in ${params.location}` : placeLabel ? `ordered by distance from ${placeLabel}` : null,
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <div className="mx-results lc-container lc-container--wide">
      <header className="mx-results__head">
        <h1>{title}</h1>
        {intro ? <p className="mx-results__intro">{intro}</p> : null}
        {below}
        <p className="mx-results__summary" role="status">
          {data ? summary : 'Search is not available right now. Please try again in a moment.'}
        </p>
        {activeChips.length > 0 ? (
          <div className="mx-chips" aria-label="Active filters">
            {activeChips.map((c) => (
              <Link key={c.label} href={c.href} className="mx-chip mx-chip--on">
                {c.label}
                <span aria-hidden="true" className="mx-chip__x" />
                <span className="lc-sr">, remove</span>
              </Link>
            ))}
            {activeChips.length > 1 ? (
              <Link className="mx-chips__clear" href={lockedTaxonomy ? basePath : '/marketplace/search'}>
                Clear all
              </Link>
            ) : null}
          </div>
        ) : null}
      </header>

      <div className="mx-results__layout">
        {data ? (
          <aside className="mx-results__side" aria-label="Filters">
            <FilterPanel data={data} families={families} params={params} href={href} placeLabel={placeLabel} />
          </aside>
        ) : null}

        <div className="mx-results__main">
          {data ? (
            <details className="mx-sheet">
              <summary>
                Filters{filterCount > 0 ? <span className="mx-sheet__n lc-num">{filterCount}</span> : null}
              </summary>
              <div className="mx-sheet__panel">
                <FilterPanel data={data} families={families} params={params} href={href} placeLabel={placeLabel} />
              </div>
            </details>
          ) : null}

          {data?.match === 'any' && listings.length > 0 ? (
            <p className="mx-note">
              Nothing matched every word, so these match some of them.
            </p>
          ) : null}

          {data?.suggested_categories && data.suggested_categories.length > 0 && !params.family ? (
            <div className="mx-suggest">
              <span>Browse the category:</span>
              {data.suggested_categories.map((s) => (
                <Link
                  key={`${s.family}-${s.category}`}
                  className="mx-chip"
                  href={`/marketplace/category/${s.family}${s.category ? `/${s.category}` : ''}`}
                >
                  {s.category_label || s.family_label}
                </Link>
              ))}
            </div>
          ) : null}

          {listings.length > 0 ? (
            <ul className="mx-grid">
              {listings.map((l, i) => (
                <li key={l.business_id}>
                  <ListingCard listing={l} eager={i < 3} />
                </li>
              ))}
            </ul>
          ) : data ? (
            <div className="mx-empty">
              <p className="mx-empty__title">
                {params.q
                  ? `Nothing on LOCAH matches “${params.q}” yet.`
                  : categoryLabel || familyLabel
                    ? `No one is listed in ${categoryLabel || familyLabel} yet.`
                    : 'No businesses match these filters.'}
              </p>
              <p>
                {data.counts.indexed_businesses === 0
                  ? 'The Marketplace fills up as businesses publish their websites and choose to be listed.'
                  : params.q
                    ? 'Try fewer or simpler words, or the name of the business.'
                    : activeChips.length > 0
                      ? 'Remove a filter to see more.'
                      : 'Businesses appear here once they publish a website on LOCAH and choose to be listed.'}
              </p>
              <div className="mx-empty__actions">
                {activeChips.length > 0 ? (
                  <Link className="lc-btn lc-btn--ghost" href={lockedTaxonomy ? basePath : '/marketplace/search'}>
                    {params.q && activeChips.length === 1 ? 'Clear the search' : 'Clear filters'}
                  </Link>
                ) : null}
                <Link className="lc-btn lc-btn--ghost" href="/marketplace/categories">
                  Browse all categories
                </Link>
                <Link className="lc-btn lc-btn--ink" href="/start">
                  Run a business like this? List it
                </Link>
              </div>
            </div>
          ) : null}

          {total > PAGE_SIZE ? (
            <nav className="mx-pages" aria-label="Pages">
              {offset > 0 ? (
                <Link className="lc-btn lc-btn--ghost" href={href({ offset: Math.max(0, offset - PAGE_SIZE) })}>
                  Previous
                </Link>
              ) : (
                <span />
              )}
              <span className="lc-num">
                {offset + 1} to {Math.min(total, offset + PAGE_SIZE)} of {total}
              </span>
              {offset + PAGE_SIZE < total ? (
                <Link className="lc-btn lc-btn--ghost" href={href({ offset: offset + PAGE_SIZE })}>
                  Next
                </Link>
              ) : (
                <span />
              )}
            </nav>
          ) : null}

          {data && data.offerings.length > 0 ? (
            <section className="mx-items" aria-labelledby="mx-items-title">
              <h2 id="mx-items-title">Items matching “{params.q}”</h2>
              <ul>
                {data.offerings.map((o) => (
                  <li key={o.id}>
                    <Link href={o.business_slug ? `/marketplace/${o.business_slug}` : '/marketplace'}>
                      <strong>{o.title}</strong>
                      {o.description ? <span className="mx-items__desc">{o.description}</span> : null}
                      {money(o.price_from, o.currency) ? (
                        <span className="mx-items__price lc-num">{money(o.price_from, o.currency)}</span>
                      ) : null}
                    </Link>
                  </li>
                ))}
              </ul>
              <p className="mx-items__note">Prices are as each business published them.</p>
            </section>
          ) : null}
        </div>
      </div>
    </div>
  )
}
