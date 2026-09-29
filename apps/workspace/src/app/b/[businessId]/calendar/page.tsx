import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import { Card, PageHeader } from '@/components/ui'

export const dynamic = 'force-dynamic'

type Item = { kind: string; at: string; time: string; title: string; who: string | null; note: string | null; href: string }
type Agenda = { from: string; days: number; count: number; days_list: { date: string; label: string; items: Item[] }[] }

const KIND_WORD: Record<string, string> = {
  booking: 'Booking',
  order: 'Order',
  follow_up: 'Enquiry',
  membership: 'Membership',
  due: 'Due',
}

/**
 * Calendar (OM-21; MD §22 "Solo professionals … one calendar"): bookings,
 * orders wanted for a day, follow-ups, memberships ending and licences due,
 * in one list for the days ahead — each opening the record behind it.
 */
export default async function CalendarPage({
  params,
  searchParams,
}: {
  params: { businessId: string }
  searchParams: { days?: string }
}) {
  const token = await getAccessToken()
  if (!token) redirect('/login')
  const days = searchParams.days === '30' ? 30 : 7
  const base = `/b/${params.businessId}`
  const res = await apiTry<{ data: Agenda }>(`/v1/platform/businesses/${params.businessId}/calendar?days=${days}`, token)
  const header = <PageHeader title="Calendar" subtitle="Everything with a time on it, in one place." />
  if (!res.ok) {
    return (
      <div className="bos-page">
        {header}
        <Card style={{ maxWidth: '40rem' }}><p>Your calendar could not load just now. Refresh the page to try again.</p></Card>
      </div>
    )
  }
  const a = res.data.data
  return (
    <div className="bos-page bos-calendar">
      {header}
      <nav className="bos-stock-tabs" aria-label="Range">
        <Link href={`${base}/calendar`} aria-current={days === 7 ? 'page' : undefined}>Next 7 days</Link>
        <Link href={`${base}/calendar?days=30`} aria-current={days === 30 ? 'page' : undefined}>Next 30 days</Link>
      </nav>
      {a.count === 0 ? (
        <div className="bos-empty">Nothing scheduled in the next {days} days. Bookings, orders wanted for a day, follow-ups and renewals appear here.</div>
      ) : (
        a.days_list.map((d) => (
          <section key={d.date} className="bos-section" aria-labelledby={`day-${d.date}`}>
            <h2 className="bos-section__title" id={`day-${d.date}`}>{d.label} <span>{d.items.length}</span></h2>
            <ul className="bos-agenda">
              {d.items.map((i, n) => (
                <li key={`${i.href}-${n}`}>
                  <Link href={`${base}${i.href}`} className={`bos-agenda__row is-${i.kind}`}>
                    <span className="bos-agenda__time">{i.time}</span>
                    <span className="bos-agenda__what">
                      <strong>{i.title}</strong>
                      <span>{[KIND_WORD[i.kind], i.who, i.note].filter(Boolean).join(' · ')}</span>
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        ))
      )}
    </div>
  )
}
