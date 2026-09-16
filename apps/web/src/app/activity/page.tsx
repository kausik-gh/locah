import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'

export const dynamic = 'force-dynamic'

const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000'

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

const STATUS_TONE: Record<string, string> = {
  confirmed: '#1f7a4d',
  completed: '#1f7a4d',
  pending: '#8a6d1f',
  cancelled: '#a33',
  no_show: '#a33',
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
        <h1 style={H1}>My activity</h1>
        <div style={CARD}>
          <p style={{ margin: 0, lineHeight: 1.6 }}>
            We could not load your activity just now. Please try again in a moment.
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
      <h1 style={H1}>My activity</h1>
      <p style={{ opacity: 0.8, lineHeight: 1.6, maxWidth: '38rem' }}>
        Bookings you have made. This is your own record as a customer — it is separate from any
        business you run.
      </p>

      {entries.length === 0 ? (
        <div style={CARD}>
          <h2 style={{ marginTop: 0, fontSize: '1.15rem' }}>Nothing here yet</h2>
          <p style={{ lineHeight: 1.6 }}>
            When you book something, it will show up here so you can find it again.
          </p>
          <Link href="/marketplace">Find a business →</Link>
        </div>
      ) : (
        <div style={{ display: 'grid', gap: '0.75rem', maxWidth: '38rem' }}>
          {entries.map((entry) => {
            const status = entry.summary.status
            const startsAt = entry.summary.starts_at
            return (
              <article key={entry.id} style={CARD}>
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    gap: '1rem',
                    flexWrap: 'wrap',
                  }}
                >
                  <div>
                    <div style={{ fontWeight: 600 }}>
                      {entry.business_name ?? 'A business'}
                    </div>
                    <div style={{ opacity: 0.85, marginTop: '0.2rem' }}>
                      {ACTIVITY_LABEL[entry.activity_type] ?? entry.activity_type}
                      {entry.summary.booking_number ? ` · ${entry.summary.booking_number}` : ''}
                    </div>
                    {startsAt ? (
                      <div style={{ opacity: 0.7, fontSize: '0.9rem', marginTop: '0.2rem' }}>
                        {new Date(startsAt).toLocaleString()}
                      </div>
                    ) : null}
                  </div>
                  {status ? (
                    <span
                      style={{
                        color: STATUS_TONE[status] ?? '#1a2229',
                        border: `1px solid ${STATUS_TONE[status] ?? '#1a2229'}33`,
                        background: `${STATUS_TONE[status] ?? '#1a2229'}14`,
                        borderRadius: '999px',
                        padding: '0.15rem 0.6rem',
                        fontSize: '0.85rem',
                        alignSelf: 'flex-start',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {status}
                    </span>
                  ) : null}
                </div>
              </article>
            )
          })}
        </div>
      )}

      <section style={{ marginTop: '2rem', maxWidth: '38rem' }}>
        <h2 style={{ fontSize: '1.05rem' }}>What is not here yet</h2>
        <ul style={{ paddingLeft: '1.1rem', lineHeight: 1.8, opacity: 0.85 }}>
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
    <div
      style={{
        minHeight: '100vh',
        fontFamily: 'Georgia, "Iowan Old Style", serif',
        background: 'linear-gradient(165deg, #f4f7f2, #e6eef5)',
        color: '#1a2229',
        padding: '2.5rem 1.5rem',
      }}
    >
      <div style={{ maxWidth: '48rem', margin: '0 auto' }}>{children}</div>
    </div>
  )
}

const H1: React.CSSProperties = { fontSize: '2rem', marginBottom: '0.5rem' }
const CARD: React.CSSProperties = {
  padding: '1.1rem 1.25rem',
  borderRadius: '10px',
  border: '1px solid rgba(26,34,41,0.12)',
  background: 'rgba(255,255,255,0.65)',
}
