import type { Metadata } from 'next'
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
  type ResultSearchParams as Search,
} from '@/components/marketplace/ResultsView'
import { Remember } from '@/components/marketplace/Remember'

export const dynamic = 'force-dynamic'

export function generateMetadata({ searchParams }: { searchParams: Search }): Metadata {
  const q = searchParams.q?.trim()
  return {
    title: q ? `“${q}” on the LOCAH Marketplace` : 'Search the Marketplace — LOCAH',
    robots: { index: false },
  }
}

export default async function MarketplaceSearchPage({ searchParams }: { searchParams: Search }) {
  const params = parseResultParams(searchParams)
  const place = readPlace()
  const account = await getNavAccount()

  const [data, families] = await Promise.all([
    fetchSearch({
      q: params.q,
      family: params.family,
      category: params.category,
      can: params.can,
      sort: params.sort,
      location: params.location,
      type: searchParams.type,
      offset: params.offset,
      limit: PAGE_SIZE,
      place: place?.param,
    }).catch(() => null as SearchResponse | null),
    fetchCategories().catch(() => [] as TaxonomyFamily[]),
  ])

  return (
    <div className="locah-public">
      <PublicNav active="marketplace" signedIn={account.signedIn} businesses={account.businesses} />
      <main className="mx-page">
        <div className="mx-bar">
          <div className="lc-container lc-container--wide mx-bar__inner">
            <SearchBox defaultValue={params.q} size="md" />
            <LocationControl label={place?.label} variant="inline" />
          </div>
        </div>
        <ResultsView
          data={data}
          families={families}
          params={params}
          basePath="/marketplace/search"
          title={params.q ? `Results for “${params.q}”` : 'All businesses'}
          placeLabel={place?.label}
        />
        {params.q && !params.offset ? <Remember q={params.q} /> : null}
      </main>
      <PublicFooter />
    </div>
  )
}
