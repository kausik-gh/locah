import { platformUrl } from '@platform/config'
const apiUrl = platformUrl('api')

/** What every Marketplace surface shows about a Business. Every field comes
 *  from what the Business published; there are deliberately no ratings,
 *  review counts, popularity, opening status or delivery times here, because
 *  LOCAH does not record them. */
export type ListingAction = {
  action: 'order' | 'book' | 'join' | 'enquire' | 'whatsapp' | 'call' | 'visit_website' | string
  label: string
  href: string
}

export type Listing = {
  result_type: 'business'
  business_id: string
  slug: string
  display_name: string
  description?: string | null
  business_type?: string | null
  city?: string | null
  locality?: string | null
  region?: string | null
  postal_code?: string | null
  area_label?: string | null
  family?: string | null
  family_label?: string | null
  category?: string | null
  category_label?: string | null
  icon?: string
  cover_url?: string | null
  logo_url?: string | null
  /** Items the Business's own site lists, pictured ones first. */
  highlights?: Array<{ title: string; image_url: string | null }>
  offering_count?: number
  published_at?: string | null
  capability_flags?: Record<string, boolean>
  actions?: ListingAction[]
  distance_km?: number | null
  reason?: string | null
}

export type OfferingHit = {
  id: string
  business_id: string
  business_slug?: string | null
  title: string
  offering_type: string
  description?: string | null
  price_from?: number | null
  currency?: string | null
}

export type TaxonomyFamily = {
  id: string
  label: string
  blurb: string
  icon: string
  count: number
  categories: Array<{ id: string; label: string; count: number }>
}

export type SearchResponse = {
  state: 'results' | 'no_results' | 'sparse_market'
  match?: 'all' | 'any'
  query: {
    q: string | null
    location: string | null
    type: string | null
    family?: string | null
    category?: string | null
    capabilities?: string[]
    sort?: string
    near?: string | null
  }
  businesses: Listing[]
  offerings: OfferingHit[]
  facets?: {
    families: Record<string, number>
    categories: Record<string, number>
    capabilities: Record<string, number>
  }
  suggested_categories?: Array<{
    family: string
    family_label: string
    category: string | null
    category_label: string | null
  }>
  page?: { offset: number; limit: number; total: number }
  counts: {
    businesses: number
    offerings: number
    indexed_businesses: number
    matching_businesses?: number
  }
}

export type Rail = {
  id: string
  title: string
  explain: string
  href: string | null
  total: number
  items: Listing[]
}

export type DiscoverResponse = {
  place: { label: string; precision: string } | null
  location_state: 'none' | 'nearby' | 'none_nearby'
  rails: Rail[]
  categories: TaxonomyFamily[]
  cities: Array<{ city: string; count: number }>
  totals: { businesses: number }
  personalised: boolean
}

export type Profile = {
  business: Listing & {
    id: string
    tagline?: string | null
    public_contact?: Record<string, string>
  }
  actions: ListingAction[]
  related: Listing[]
  offerings: Array<OfferingHit & { category?: string | null; handoff: { href: string } }>
  website_handoff: { href: string }
}

/** Where the visitor said they are, forwarded exactly as stored in their
 *  own cookie: rounded coordinates, or the town or PIN they typed. */
export type PlaceParam = { near?: string; place?: string }

function placeParams(qs: URLSearchParams, place?: PlaceParam) {
  if (place?.near) qs.set('near', place.near)
  else if (place?.place) qs.set('place', place.place)
}

export async function fetchSearch(params: {
  q?: string
  location?: string
  type?: string
  family?: string
  category?: string
  can?: string[]
  sort?: string
  offset?: number
  limit?: number
  place?: PlaceParam
}): Promise<SearchResponse> {
  const qs = new URLSearchParams()
  if (params.q) qs.set('q', params.q)
  if (params.location) qs.set('location', params.location)
  if (params.type) qs.set('type', params.type)
  if (params.family) qs.set('family', params.family)
  if (params.category) qs.set('category', params.category)
  for (const c of params.can || []) qs.append('can', c)
  if (params.sort) qs.set('sort', params.sort)
  if (params.offset) qs.set('offset', String(params.offset))
  if (params.limit) qs.set('limit', String(params.limit))
  placeParams(qs, params.place)
  const res = await fetch(`${apiUrl}/v1/public/search?${qs.toString()}`, {
    next: { revalidate: 30 },
  })
  if (!res.ok) throw new Error('Search failed')
  const json = (await res.json()) as { data: SearchResponse }
  return json.data
}

export async function fetchDiscover(params: {
  place?: PlaceParam
  fam?: string
  cat?: string
  searched?: string[]
  used?: string[]
}): Promise<DiscoverResponse> {
  const qs = new URLSearchParams()
  placeParams(qs, params.place)
  if (params.fam) qs.set('fam', params.fam)
  if (params.cat) qs.set('cat', params.cat)
  for (const s of params.searched || []) qs.append('searched', s)
  if (params.used?.length) qs.set('used', params.used.join(','))
  // Keyed by URL: two visitors in the same town with no history share the
  // cached answer; anything personal makes a different URL.
  const res = await fetch(`${apiUrl}/v1/public/discover?${qs.toString()}`, {
    next: { revalidate: 60 },
  })
  if (!res.ok) throw new Error('Discover failed')
  const json = (await res.json()) as { data: DiscoverResponse }
  return json.data
}

export async function fetchCategories(): Promise<TaxonomyFamily[]> {
  const res = await fetch(`${apiUrl}/v1/public/categories`, { next: { revalidate: 300 } })
  if (!res.ok) throw new Error('Categories failed')
  const json = (await res.json()) as { data: { families: TaxonomyFamily[] } }
  return json.data.families
}

export async function fetchPlaces(params: { q?: string; near?: string }) {
  const qs = new URLSearchParams()
  if (params.q) qs.set('q', params.q)
  if (params.near) qs.set('near', params.near)
  const res = await fetch(`${apiUrl}/v1/public/places?${qs.toString()}`, {
    next: { revalidate: 3600 },
  })
  if (!res.ok) throw new Error('Places failed')
  const json = (await res.json()) as {
    data: {
      resolved: { label: string; lat: number; lng: number; precision: string } | null
      suggestions: Array<{ city: string; state: string; lat: number; lng: number }>
    }
  }
  return json.data
}

export async function fetchMarketplaceProfile(slug: string, place?: PlaceParam): Promise<Profile | null> {
  const qs = new URLSearchParams()
  placeParams(qs, place)
  const suffix = qs.toString() ? `?${qs.toString()}` : ''
  const res = await fetch(`${apiUrl}/v1/public/businesses/${encodeURIComponent(slug)}${suffix}`, {
    next: { revalidate: 60, tags: [`marketplace:${slug}`] },
  })
  if (!res.ok) return null
  const json = await res.json()
  return json.data as Profile
}
