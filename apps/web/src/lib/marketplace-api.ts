const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000'

export type SearchResponse = {
  state: 'results' | 'no_results' | 'sparse_market'
  query: { q: string | null; location: string | null; type: string | null }
  businesses: Array<{
    business_id: string
    slug: string
    display_name: string
    description?: string | null
    business_type?: string | null
    city?: string | null
    capability_flags?: Record<string, boolean>
  }>
  offerings: Array<{
    id: string
    business_id: string
    business_slug?: string | null
    title: string
    offering_type: string
    description?: string | null
    price_from?: number | null
    currency?: string | null
  }>
  counts: { businesses: number; offerings: number; indexed_businesses: number }
}

export async function fetchSearch(params: {
  q?: string
  location?: string
  type?: string
}): Promise<SearchResponse> {
  const qs = new URLSearchParams()
  if (params.q) qs.set('q', params.q)
  if (params.location) qs.set('location', params.location)
  if (params.type) qs.set('type', params.type)
  const res = await fetch(`${apiUrl}/v1/public/search?${qs.toString()}`, {
    next: { revalidate: 30 },
  })
  if (!res.ok) throw new Error('Search failed')
  const json = (await res.json()) as { data: SearchResponse }
  return json.data
}

export async function fetchMarketplaceProfile(slug: string) {
  const res = await fetch(`${apiUrl}/v1/public/businesses/${slug}`, {
    next: { revalidate: 60, tags: [`marketplace:${slug}`] },
  })
  if (!res.ok) return null
  const json = await res.json()
  return json.data
}
