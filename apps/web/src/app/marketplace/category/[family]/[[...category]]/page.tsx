import type { Metadata } from 'next'
import Link from 'next/link'
import { notFound } from 'next/navigation'
import { fetchCategories, fetchSearch, type SearchResponse, type TaxonomyFamily } from '@/lib/marketplace-api'
import { readPlace } from '@/lib/visitor-signals'
import { getNavAccount } from '@/lib/nav-account'
import { PublicNav } from '@/components/public/PublicNav'
import { PublicFooter } from '@/components/public/PublicFooter'
import { SearchBox } from '@/components/marketplace/SearchBox'
import { LocationControl } from '@/components/marketplace/LocationControl'
import {
  PAGE_SIZE,
  ResultsView,
  parseResultParams,
  type ResultSearchParams,
} from '@/components/marketplace/ResultsView'
import { Remember } from '@/components/marketplace/Remember'
import { CategoryIcon, familyTint } from '@/components/marketplace/CategoryIcon'

export const dynamic = 'force-dynamic'

type Params = { family: string; category?: string[] }

async function resolve(params: Params) {
  const families = await fetchCategories().catch(() => [] as TaxonomyFamily[])
  const family = families.find((f) => f.id === params.family)
  const categoryId = params.category?.[0]
  const category = family?.categories.find((c) => c.id === categoryId)
  return { families, family, category, categoryId }
}

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const { family, category } = await resolve(params)
  if (!family) return {}
  const name = category ? category.label : family.label
  return {
    title: `${name} on the LOCAH Marketplace`,
    description: `${name} listed on LOCAH: businesses that published their own website and chose to be found.`,
  }
}

export default async function CategoryPage({
  params,
  searchParams,
}: {
  params: Params
  searchParams: ResultSearchParams
}) {
  const { families, family, category, categoryId } = await resolve(params)
  if (families.length > 0 && (!family || (categoryId && !category) || (params.category?.length || 0) > 1)) {
    notFound()
  }
  const place = readPlace()
  const account = await getNavAccount()
  const base = parseResultParams(searchParams)
  const result = { ...base, family: params.family, category: categoryId }

  const data = await fetchSearch({
    q: result.q,
    family: result.family,
    category: result.category,
    can: result.can,
    sort: result.sort,
    location: result.location,
    offset: result.offset,
    limit: PAGE_SIZE,
    place: place?.param,
  }).catch(() => null as SearchResponse | null)

  const basePath = `/marketplace/category/${params.family}${categoryId ? `/${categoryId}` : ''}`
  const title = category?.label || family?.label || 'Category'

  const below = family ? (
    <div className="mx-cathead__below">
      <div className="mx-cathead__row">
        <span className="mx-cathead__glyph" data-tint={familyTint(family.id)}>
          <CategoryIcon name={family.icon} size={26} />
        </span>
        <p className="mx-cathead__blurb">{category ? `Part of ${family.label}: ${family.blurb.toLowerCase()}.` : `${family.blurb}.`}</p>
      </div>
      {!category ? (
        <div className="mx-chips mx-chips--scroll" aria-label={`Categories in ${family.label}`}>
          {family.categories.map((c) => (
            <Link key={c.id} className="mx-chip" href={`/marketplace/category/${family.id}/${c.id}`}>
              {c.label} <span className="lc-num mx-chip__n">{c.count}</span>
            </Link>
          ))}
        </div>
      ) : null}
    </div>
  ) : null

  return (
    <div className="locah-public">
      <PublicNav active="marketplace" signedIn={account.signedIn} businesses={account.businesses} />
      <main className="mx-page">
        <div className="mx-bar">
          <div className="lc-container lc-container--wide mx-bar__inner">
            <SearchBox
              defaultValue={result.q}
              size="md"
              hidden={{ family: params.family, category: categoryId }}
              placeholder={`Search in ${title}`}
            />
            <LocationControl label={place?.label} variant="inline" />
          </div>
        </div>

        {family ? (
          <div className="lc-container lc-container--wide mx-cathead">
            <nav className="mx-crumbs" aria-label="Breadcrumb">
              <Link href="/marketplace">Marketplace</Link>
              <span aria-hidden="true">/</span>
              {category ? (
                <>
                  <Link href={`/marketplace/category/${family.id}`}>{family.label}</Link>
                  <span aria-hidden="true">/</span>
                  <span aria-current="page">{category.label}</span>
                </>
              ) : (
                <span aria-current="page">{family.label}</span>
              )}
            </nav>
          </div>
        ) : null}

        <ResultsView
          data={data}
          families={families}
          params={result}
          basePath={basePath}
          lockedTaxonomy
          title={title}
          below={below}
          placeLabel={place?.label}
        />
        <Remember family={params.family} category={categoryId} />
      </main>
      <PublicFooter />
    </div>
  )
}
