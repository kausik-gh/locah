import Link from 'next/link'
import type { Rail as RailData, TaxonomyFamily } from '@/lib/marketplace-api'
import { ListingCard } from './ListingCard'
import { CategoryIcon, familyTint } from './CategoryIcon'

export function Rail({ rail, first = false }: { rail: RailData; first?: boolean }) {
  const headingId = `rail-${rail.id}`
  return (
    <section className="mx-rail" aria-labelledby={headingId}>
      <div className="mx-rail__head">
        <div>
          <h2 id={headingId}>{rail.title}</h2>
          <p>{rail.explain}</p>
        </div>
        {rail.href && rail.total > rail.items.length ? (
          <Link className="mx-rail__all" href={rail.href}>
            See all <span className="lc-num">{rail.total}</span>
          </Link>
        ) : null}
      </div>
      <ul className="mx-rail__track">
        {rail.items.map((listing, i) => (
          <li key={listing.business_id}>
            <ListingCard listing={listing} eager={first && i < 2} />
          </li>
        ))}
      </ul>
    </section>
  )
}

/**
 * Categories as a bento: the families with the most listings get the biggest
 * tiles. Counts are real listings. A family nobody is in yet still appears in
 * the full index, marked "none yet", rather than being hidden or padded.
 */
export function CategoryBento({ families }: { families: TaxonomyFamily[] }) {
  const ranked = [...families]
    .map((f, index) => ({ f, index }))
    .sort((a, b) => b.f.count - a.f.count || a.index - b.index)
    .map(({ f }) => f)
  const tiles = ranked.slice(0, 8)
  return (
    <div className="mx-bento">
      {tiles.map((f, i) => {
        const top = f.categories.filter((c) => c.count > 0).slice(0, 3)
        return (
          <Link
            key={f.id}
            href={`/marketplace/category/${f.id}`}
            className={`mx-bento__tile mx-bento__tile--${i < 2 ? 'big' : 'small'}`}
            data-tint={familyTint(f.id)}
          >
            <span className="mx-bento__icon">
              <CategoryIcon name={f.icon} size={i < 2 ? 30 : 24} />
            </span>
            <span className="mx-bento__label">{f.label}</span>
            <span className="mx-bento__count">
              {f.count > 0 ? `${f.count} listed` : 'None listed yet'}
            </span>
            {i < 2 && top.length > 0 ? (
              <span className="mx-bento__subs">
                {top.map((c) => (
                  <span key={c.id}>
                    {c.label} <span className="lc-num">{c.count}</span>
                  </span>
                ))}
              </span>
            ) : i < 2 ? (
              <span className="mx-bento__blurb">{f.blurb}</span>
            ) : null}
          </Link>
        )
      })}
      <Link className="mx-bento__tile mx-bento__tile--all" href="/marketplace/categories">
        <span className="mx-bento__label">All {families.length} categories</span>
        <span className="mx-bento__count">Search the full index</span>
      </Link>
    </div>
  )
}
