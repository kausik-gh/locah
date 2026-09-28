import { platformUrl } from '@platform/config'

const base = `${platformUrl('api')}/v1/public/websites`

export type PublicReview = {
  id: string
  reviewer_name: string
  rating: number
  body: string | null
  verified: string
  published_at: string | null
  updated_by_reviewer: boolean
  reply: { body: string; at: string } | null
  photos: string[]
  redacted: boolean
}

export type PublicReviews = {
  average: number | null
  count: number
  distribution: Record<string, number>
  reviews: PublicReview[]
}

export type ReviewerView = {
  business_name: string
  label: string
  source_type: string
  verified: string
  state: 'open' | 'written' | 'declined' | 'expired'
  expires_at: string
  violations: Record<string, string>
  review: (PublicReview & {
    status: string
    can_appeal: boolean
    appeal: { status: string; note: string } | null
  }) | null
}

export async function fetchPublicReviews(slug: string, options: { featured?: boolean; offset?: number; limit?: number } = {}): Promise<PublicReviews | null> {
  const qs = new URLSearchParams()
  if (options.featured) qs.set('featured', 'true')
  if (options.offset) qs.set('offset', String(options.offset))
  if (options.limit) qs.set('limit', String(options.limit))
  const res = await fetch(`${base}/${encodeURIComponent(slug)}/reviews?${qs}`, { cache: 'no-store' })
  if (!res.ok) return null
  return ((await res.json()) as { data: PublicReviews }).data
}

export async function fetchReviewerView(slug: string, token: string): Promise<ReviewerView | null> {
  const res = await fetch(`${base}/${encodeURIComponent(slug)}/review/${encodeURIComponent(token)}`, { cache: 'no-store' })
  if (!res.ok) return null
  return ((await res.json()) as { data: ReviewerView }).data
}

export function publicReviewPhoto(slug: string, id: string) {
  return `${base}/${encodeURIComponent(slug)}/reviews/photos/${encodeURIComponent(id)}`
}
