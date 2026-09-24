'use client'

import Link from 'next/link'
import { useMemo, useState } from 'react'
import type { TaxonomyFamily } from '@/lib/marketplace-api'
import { CategoryIcon, familyTint } from './CategoryIcon'

/** Every family and category, filterable as you type. The list is the API's. */
export function CategoryIndex({ families }: { families: TaxonomyFamily[] }) {
  const [q, setQ] = useState('')
  const needle = q.trim().toLowerCase()
  const shown = useMemo(() => {
    if (!needle) return families
    return families
      .map((f) => {
        const familyHit = f.label.toLowerCase().includes(needle) || f.blurb.toLowerCase().includes(needle)
        const categories = familyHit ? f.categories : f.categories.filter((c) => c.label.toLowerCase().includes(needle))
        return { ...f, categories }
      })
      .filter((f) => f.categories.length > 0)
  }, [families, needle])

  return (
    <div className="mx-index">
      <div className="mx-index__search">
        <label htmlFor="mx-index-q" className="lc-sr">
          Filter categories
        </label>
        <input
          id="mx-index-q"
          type="search"
          placeholder="Filter categories, like dental or tailoring"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          autoComplete="off"
        />
        <span className="mx-index__n" aria-live="polite">
          {shown.length} of {families.length}
        </span>
      </div>
      {shown.length === 0 ? (
        <p className="mx-index__empty">
          No category matches “{q}”.{' '}
          <Link className="lc-link lc-link--accent" href={`/marketplace/search?q=${encodeURIComponent(q)}`}>
            Search businesses for “{q}” instead
          </Link>
        </p>
      ) : (
        <div className="mx-index__grid">
          {shown.map((f) => (
            <section key={f.id} className="mx-index__family" aria-labelledby={`idx-${f.id}`}>
              <h3 id={`idx-${f.id}`}>
                <span className="mx-index__glyph" data-tint={familyTint(f.id)}>
                  <CategoryIcon name={f.icon} size={18} />
                </span>
                <Link href={`/marketplace/category/${f.id}`}>{f.label}</Link>
                <span className="mx-index__count lc-num">{f.count}</span>
              </h3>
              <ul>
                {f.categories.map((c) => (
                  <li key={c.id}>
                    <Link href={`/marketplace/category/${f.id}/${c.id}`}>
                      <span>{c.label}</span>
                      <span className={`lc-num${c.count ? '' : ' is-zero'}`}>
                        {c.count ? c.count : 'none yet'}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      )}
    </div>
  )
}
