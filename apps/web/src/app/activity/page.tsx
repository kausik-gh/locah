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
  occurred_at: string | null
  summary: {
    booking_number?: string
    starts_at?: string
    status?: string
  }
}

const ACTIVITY_LABEL: Record<string, string> = {
  'booking.created': 'Booked',
  'booking.confirmed': 'Confirmed',
  'booking.cancelled': 'Cancelled',
  'booking.completed': 'Completed',
}

/** Maps to the design-system badge tones, not raw hex. */
const STATUS_TONE: Record<string, string> = {
  confirmed: 'good',
  completed: 'good',
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
 * Coverage is Bookings only. Orders and Payments do not write to
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
        Bookings you have made. This is your own record as a customer, kept separate from any
        business you run.
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
                      {ACTIVITY_LABEL[entry.activity_type] ?? entry.activity_type}
                      {entry.summary.booking_number ? ` · ${entry.summary.booking_number}` : ''}
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
          <li>Orders and payments — these are not part of your activity record yet.</li>
          <li>
            Anything you did before signing in. Bookings made as a guest stay with the business
            you booked with and are not attached to this account.
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
