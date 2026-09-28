import type { Metadata } from 'next'
import Link from 'next/link'
import { notFound } from 'next/navigation'
import { RESERVED_SLUGS } from '@/lib/reserved-slugs'
import { fetchPublicWebsite } from '@/lib/public-website'
import { fetchPublicReviews } from '@/lib/public-reviews'
import { siteThemeVars } from '@/components/website/WebsitePageView'
import { ReviewCard } from '@/components/website/ReviewCard'

export const dynamic = 'force-dynamic'

export async function generateMetadata({ params }: { params: { slug: string } }): Promise<Metadata> {
  const site = await fetchPublicWebsite(params.slug)
  return site ? { title: `Reviews | ${site.business.display_name}` } : {}
}

export default async function ReviewsPage({ params, searchParams }: { params: { slug: string }; searchParams?: { offset?: string } }) {
  if (RESERVED_SLUGS.has(params.slug)) notFound()
  const offset = Math.max(0, Math.min(10000, Number(searchParams?.offset) || 0))
  const [site, data] = await Promise.all([
    fetchPublicWebsite(params.slug),
    fetchPublicReviews(params.slug, { offset, limit: 20 }),
  ])
  if (!site || !data) notFound()
  const theme = siteThemeVars(site)
  return (
    <div data-locah-site="" data-palette={theme.paletteMode} style={theme.styleVars}>
      <main className="ls-section ls-reviews-page">
        <div className="ls-inner">
          <Link className="ls-reviews-back" href={`/${params.slug}`}>← {site.business.display_name}</Link>
          <header className="ls-reviews-header">
            <p className="ls-eyebrow">Customer experiences</p>
            <h1>Reviews</h1>
            {data.count ? <p className="ls-reviews-score"><span aria-hidden="true">★</span> {data.average?.toFixed(1)} <small>from {data.count} verified {data.count === 1 ? 'review' : 'reviews'}</small></p> : <p>No reviews yet.</p>}
            {data.count ? <p className="ls-meta">Reviews come from completed customer interactions. The business cannot change a customer’s rating or words.</p> : null}
          </header>
          <div className="ls-reviews-list">{data.reviews.map((review) => <ReviewCard key={review.id} review={review} slug={params.slug} />)}</div>
          <nav className="ls-reviews-pages" aria-label="Review pages">
            {offset > 0 ? <Link href={`/${params.slug}/reviews?offset=${Math.max(0, offset - 20)}`}>← Newer</Link> : null}
            {data.reviews.length === 20 ? <Link href={`/${params.slug}/reviews?offset=${offset + 20}`}>Older →</Link> : null}
          </nav>
        </div>
      </main>
    </div>
  )
}
