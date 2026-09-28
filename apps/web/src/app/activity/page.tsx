import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { PublicNav } from '@/components/public/PublicNav'
import { PublicFooter } from '@/components/public/PublicFooter'
import { platformUrl } from '@platform/config'

export const dynamic = 'force-dynamic'

const apiUrl = platformUrl('api')

type Activity = {
  id: string
  business_id: string
  business_name: string | null
  activity_type: string
  resource_type: string
  resource_id: string
  action_url?: string
  account_url?: string
  occurred_at: string | null
  summary: {
    booking_number?: string
    order_number?: string
    number?: string
    starts_at?: string
    ends_at?: string | null
    status?: string
    label?: string | null
    total?: number
    items?: number
    amount_due?: number
  }
}

const ACTIVITY_LABEL: Record<string, string> = {
  'booking.created': 'Booked',
  'booking.confirmed': 'Confirmed',
  'booking.cancelled': 'Cancelled',
  'booking.completed': 'Completed',
  'review.requested': 'Review invited',
  'review.written': 'Review posted',
  'review.declined': 'Review declined',
}

/** Words for records other than bookings and reviews: the kind of record, then its state. */
const KIND_LABEL: Record<string, string> = { order: 'Order', bill: 'Bill', quote: 'Quote', membership: 'Membership' }

function label(a: Activity): string {
  if (ACTIVITY_LABEL[a.activity_type]) return ACTIVITY_LABEL[a.activity_type]
  const kind = KIND_LABEL[a.resource_type]
  return kind ?? a.activity_type
}

const ACTION_WORD: Record<string, string> = { review_invitation: 'Write your review', order: 'Track', bill: 'Open the bill' }

/** Maps to the design-system badge tones, not raw hex. */
const STATUS_TONE: Record<string, string> = {
  confirmed: 'good',
  completed: 'good',
  active: 'good',
  accepted: 'good',
  issued: 'ink',
  ready: 'good',
  pending: 'warn',
  cancelled: 'bad',
  no_show: 'bad',
}

/**
 * Doc 09 ACC-011 — My Activity.
 *
 * The consumer surface, deliberately separate from the Business Workspace
 * (Doc 11 §17.7 exit: "My Activity remains separate from Workspace"). It shows
 * this person's own activity as a customer, never anything they manage as a
 * Business.
 *
 * Coverage is bookings and review invitations. Orders and Payments do not write to
 * `consumer_activity_projections` yet, and activity from before signing in is
 * not linked to an account pending FL-DEC-024. The page states both limits
 * rather than letting an incomplete feed read as a complete one.
 */
export default async function MyActivityPage() {
  const token = await getAccessToken()
  if (!token) redirect('/login')

  const res = await fetch(`${apiUrl}/v1/me/activity`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: 'no-store',
  })

  if (!res.ok) {
    return (
      <Shell>
        <h1>My activity</h1>
        <div className="lc-empty" style={{ marginTop: 'var(--sp-6)' }}>
          <p className="lc-empty__title">We could not load your activity</p>
          <p className="lc-empty__body">
            Nothing is lost — please try again in a moment.
          </p>
        </div>
      </Shell>
    )
  }

  const body = (await res.json()) as { data: Activity[] }
  const activities = body.data || []

  // Collapse the per-event projection into one entry per booking, keeping the
  // latest event — a person thinks in bookings, not state transitions.
  const latestByResource = new Map<string, Activity>()
  for (const activity of activities) {
    const key = `${activity.resource_type}:${activity.resource_id}`
    const existing = latestByResource.get(key)
    if (
      !existing ||
      (activity.occurred_at ?? '') > (existing.occurred_at ?? '')
    ) {
      latestByResource.set(key, activity)
    }
  }
  const entries = [...latestByResource.values()].sort((a, b) =>
    (b.occurred_at ?? '').localeCompare(a.occurred_at ?? '')
  )

  return (
    <Shell>
      <p className="lc-eyebrow">Your record</p>
      <h1>My activity</h1>
      <p className="lc-lead" style={{ marginTop: 'var(--sp-3)' }}>
        Your orders, bookings, bills, quotes, memberships and review invitations with businesses on LOCAH. This is
        your own record as a customer, kept separate from any business you run.
      </p>

      {entries.length === 0 ? (
        <div className="lc-empty" style={{ marginTop: 'var(--sp-7)' }}>
          <p className="lc-empty__title">Nothing here yet</p>
          <p className="lc-empty__body">
            When you book something through LOCAH it appears here, so you can find it again
            without digging through your email.
          </p>
          <Link className="lc-btn lc-btn--primary" href="/marketplace">
            Find a business
          </Link>
        </div>
      ) : (
        <div className="lc-stack" style={{ marginTop: 'var(--sp-7)', maxWidth: '42rem' }}>
          {entries.map((entry) => {
            const status = entry.summary.status
            const startsAt = entry.summary.starts_at
            return (
              <article key={entry.id} className="lc-card">
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    gap: '1rem',
                    flexWrap: 'wrap',
                  }}
                >
                  <div>
                    <h2 className="lc-card__title" style={{ fontSize: '1.05rem' }}>
                      {entry.business_name ?? 'A business'}
                    </h2>
                    <p className="lc-card__body" style={{ margin: 0 }}>
                      {label(entry)}
                      {entry.summary.booking_number ? ` · ${entry.summary.booking_number}` : ''}
                      {entry.summary.order_number ? ` ${entry.summary.order_number}` : ''}
                      {entry.summary.number ? ` ${entry.summary.number}` : ''}
                      {entry.summary.label ? ` · ${entry.summary.label}` : ''}
                      {typeof entry.summary.total === 'number' ? ` · ${new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' }).format(entry.summary.total)}` : ''}
                    </p>
                    <p style={{ display: 'flex', gap: '.5rem', flexWrap: 'wrap', margin: '.65rem 0 0' }}>
                      {entry.action_url ? <Link className="lc-btn lc-btn--primary" href={entry.action_url}>{ACTION_WORD[entry.resource_type] ?? 'Open'}</Link> : null}
                      {entry.account_url ? <Link className="lc-btn lc-btn--ghost" href={entry.account_url}>Everything with {entry.business_name ?? 'this business'}</Link> : null}
                    </p>
                    {startsAt ? (
                      <p className="lc-small lc-muted" style={{ margin: '0.25rem 0 0' }}>
                        {new Date(startsAt).toLocaleString()}
                      </p>
                    ) : null}
                  </div>
                  {status ? (
                    <span
                      className={`lc-badge lc-badge--${STATUS_TONE[status] ?? 'ink'}`}
                      style={{ alignSelf: 'flex-start' }}
                    >
                      {status.replace(/_/g, ' ')}
                    </span>
                  ) : null}
                </div>
              </article>
            )
          })}
        </div>
      )}

      <section style={{ marginTop: 'var(--sp-9)', maxWidth: '42rem' }}>
        <h2 style={{ fontSize: '1.05rem', marginBottom: 'var(--sp-3)' }}>What is not here yet</h2>
        <ul className="lc-muted lc-small" style={{ paddingLeft: '1.1rem', lineHeight: 1.9 }}>
          <li>
            Things you did as a guest with a different email. Guest orders and bookings join this account only when
            they carry the email you signed in with — LOCAH never matches on a name or an unverified phone.
          </li>
        </ul>
      </section>
    </Shell>
  )
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="locah-public">
      <PublicNav signedIn audience="consumer" />
      <main className="lc-section lc-container" style={{ maxWidth: '52rem' }}>
        {children}
      </main>
      <PublicFooter />
    </div>
  )
}
