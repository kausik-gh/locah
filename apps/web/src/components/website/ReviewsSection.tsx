import Link from 'next/link'
import { fetchPublicReviews } from '@/lib/public-reviews'
import { ReviewCard } from './ReviewCard'

/** Live verified reviews only. Structured section content controls the heading,
 * never the rating or customer words. */
export async function ReviewsSection({ slug, title, subtitle, alt }: { slug: string; title: string; subtitle?: string; alt: boolean }) {
  const data = await fetchPublicReviews(slug, { featured: true, limit: 3 })
  // A fresh business has no testimonial to show; don't invent one or leave an empty frame.
  if (!data?.count || !data.reviews.length) return null
  return (
    <section className={`ls-section ls-reviews-section ${alt ? 'ls-section--alt' : ''}`}>
      <div className="ls-inner">
        <div className="ls-reviews-section__head">
          <div><p className="ls-eyebrow">From customers</p><h2 className="ls-title">{title}</h2>{subtitle ? <p className="ls-sub">{subtitle}</p> : null}</div>
          <p className="ls-reviews-score"><span aria-hidden="true">★</span> {data.average?.toFixed(1)} <small>from {data.count} verified reviews</small></p>
        </div>
        <div className="ls-reviews-list">{data.reviews.map((review) => <ReviewCard key={review.id} review={review} slug={slug} />)}</div>
        <Link className="ls-reviews-section__all" href={`/${slug}/reviews`}>See all reviews →</Link>
      </div>
    </section>
  )
}
