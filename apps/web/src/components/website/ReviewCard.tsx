import type { PublicReview } from '@/lib/public-reviews'
import { publicReviewPhoto } from '@/lib/public-reviews'

export function ReviewCard({ review, slug }: { review: PublicReview; slug: string }) {
  const date = review.published_at
    ? new Date(review.published_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
    : null
  return (
    <article className="ls-review-card">
      <div className="ls-review-card__top">
        <div>
          <p className="ls-review-card__stars" aria-label={`${review.rating} out of 5 stars`}>{'★'.repeat(review.rating)}<span aria-hidden="true">{'☆'.repeat(5 - review.rating)}</span></p>
          <h3>{review.reviewer_name}</h3>
        </div>
        {date ? <time dateTime={review.published_at?.slice(0, 10)}>{date}</time> : null}
      </div>
      <p className="ls-review-card__verified">✓ {review.verified}</p>
      {review.body ? <p className="ls-review-card__body">{review.body}</p> : null}
      {review.photos.length ? (
        <div className="ls-review-card__photos">
          {review.photos.map((id) => (
            // eslint-disable-next-line @next/next/no-img-element
            <img key={id} src={publicReviewPhoto(slug, id)} alt={`Photo shared by ${review.reviewer_name}`} loading="lazy" />
          ))}
        </div>
      ) : null}
      {review.reply ? <div className="ls-review-card__reply"><strong>Response from the business</strong><p>{review.reply.body}</p></div> : null}
      {review.updated_by_reviewer ? <p className="ls-review-card__updated">Updated by reviewer</p> : null}
    </article>
  )
}
