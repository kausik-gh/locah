import Link from 'next/link'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import { AdminNotice, EmptyState, PageHeader } from '@/components/AdminNotice'
import { decideAppeal, dismissReport, redactReview, removeReview, removeReviewPhoto } from './actions'

export const dynamic = 'force-dynamic'

type Review = { id: string; reviewer_name: string; rating: number; body: string | null; status: string; photos: string[]; removed: { reason_words: string; note: string | null } | null; appeal: { note: string; status: string } | null }
type Report = { report_id: string; business_name: string; reason: string; reason_words: string; note: string | null; reported_at: string; review: Review }
type Appeal = { business_name: string; review: Review }
type Queue = { reports: Report[]; appeals: Appeal[]; violations: Record<string, string> }

function ReviewDetails({ review }: { review: Review }) {
  return <div><p><strong>{review.reviewer_name}</strong> · {review.rating} / 5 · {review.status}</p><p style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{review.body || 'Star rating only'}</p>{review.photos.length ? <div className="mod-review-photos">{review.photos.map((id) => (
    // eslint-disable-next-line @next/next/no-img-element
    <img key={id} src={`/reviews/photos/${id}`} alt={`Review attachment ${id.slice(0, 8)}`} />
  ))}</div> : null}{review.removed ? <p>Removed: {review.removed.reason_words}{review.removed.note ? ` · ${review.removed.note}` : ''}</p> : null}</div>
}

export default async function ReviewModerationPage() {
  const token = await getAccessToken()
  const header = <><p><Link href="/">← Admin home</Link></p><PageHeader title="Review moderation" subtitle="Decide reports and appeals. Removal and redaction are audited; businesses cannot perform them." /></>
  if (!token) return <div>{header}<AdminNotice error={{ status: 0, code: 'NO_SESSION', message: 'no session' }} /></div>
  const res = await apiTry<{ data: Queue }>('/v1/admin/reviews/queue', token)
  if (!res.ok) return <div>{header}<AdminNotice error={res.error} /></div>
  const { reports, appeals, violations } = res.data.data
  return <div className="mod-reviews">
    {header}
    <section><h2>Reported reviews <small>({reports.length})</small></h2>
      {reports.length ? reports.map((item) => <article key={item.report_id} className="mod-review-card">
        <p><strong>{item.business_name}</strong> · {item.reason_words} · {new Date(item.reported_at).toLocaleDateString('en-IN')}</p>
        {item.note ? <p>Reporter context: {item.note}</p> : null}
        <ReviewDetails review={item.review} />
        <div className="mod-review-actions">
          <form action={dismissReport}><input type="hidden" name="reportId" value={item.report_id} /><label>Decision note<input name="note" maxLength={500} /></label><button type="submit">Dismiss report</button></form>
          <form action={removeReview}><input type="hidden" name="reviewId" value={item.review.id} /><label>Violation<select name="reason" required><option value="">Choose</option>{Object.entries(violations).map(([id, name]) => <option key={id} value={id}>{name}</option>)}</select></label><label>Reason for customer<input name="note" maxLength={500} /></label><button type="submit">Remove review</button></form>
        </div>
        <details><summary>Personal-data redaction</summary><form action={redactReview}><input type="hidden" name="reviewId" value={item.review.id} /><label>Exact text to redact<input name="span" required /></label><button type="submit">Redact text</button></form>{item.review.photos.map((id) => <form action={removeReviewPhoto} key={id}><input type="hidden" name="photoId" value={id} /><button type="submit">Remove photo {id.slice(0, 8)}</button></form>)}</details>
      </article>) : <EmptyState>No open reports.</EmptyState>}
    </section>
    <section><h2>Customer appeals <small>({appeals.length})</small></h2>
      {appeals.length ? appeals.map((item) => <article key={item.review.id} className="mod-review-card"><p><strong>{item.business_name}</strong></p><ReviewDetails review={item.review} /><p>Customer appeal: {item.review.appeal?.note}</p><div className="mod-review-actions">{[true, false].map((restore) => <form action={decideAppeal} key={String(restore)}><input type="hidden" name="reviewId" value={item.review.id} /><input type="hidden" name="restore" value={String(restore)} /><label>Decision note<input name="note" maxLength={500} /></label><button type="submit">{restore ? 'Restore review' : 'Reject appeal'}</button></form>)}</div></article>) : <EmptyState>No open appeals.</EmptyState>}
    </section>
  </div>
}
