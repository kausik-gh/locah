import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import { Card, PageHeader } from '@/components/ui'

export const dynamic = 'force-dynamic'

type InsightCard = {
  key: string
  title: string
  state: 'ok' | 'no_data' | 'no_permission' | 'whole_business_only'
  value: string | null
  note: string
  detail: { label: string; value: string }[]
  href: string
  go?: string
}
type Insights = {
  period: { key: string; label: string; from: string; to: string }
  periods: { key: string; label: string }[]
  cards: InsightCard[]
  not_switched_on: { key: string; title: string; tool: string }[]
}

function range(p: Insights['period']) {
  const f = (d: string) => new Date(`${d}T00:00:00`).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })
  return p.from === p.to ? f(p.from) : `${f(p.from)} – ${f(p.to)}`
}

/**
 * Your numbers (IS-01; First Launch §12.1 "Core Workspace Insights"): sales,
 * orders, bookings and money received for a period, counted from the records
 * behind them and linked to where the work happens. Trends and comparisons are
 * the later Analytics module.
 */
export default async function InsightsPage({
  params,
  searchParams,
}: {
  params: { businessId: string }
  searchParams: { period?: string }
}) {
  const token = await getAccessToken()
  if (!token) redirect('/login')
  const period = ['today', '7d', 'month'].includes(searchParams.period ?? '') ? searchParams.period! : 'today'
  const base = `/b/${params.businessId}`
  const res = await apiTry<{ data: Insights }>(`/v1/platform/businesses/${params.businessId}/insights?period=${period}`, token)
  const header = <PageHeader title="Your numbers" subtitle="Counted from your bills, orders, bookings and payments — nothing estimated." />
  if (!res.ok) {
    return (
      <div className="bos-page">
        {header}
        <Card style={{ maxWidth: '40rem' }}>
          <p>Your numbers could not load just now. Refresh the page to try again.</p>
        </Card>
      </div>
    )
  }
  const d = res.data.data
  return (
    <div className="bos-page bos-insights">
      {header}
      <nav className="bos-stock-tabs" aria-label="Period">
        {d.periods.map((p) => (
          <Link key={p.key} href={`${base}/insights?period=${p.key}`} className={p.key === d.period.key ? 'is-on' : undefined}
            aria-current={p.key === d.period.key ? 'page' : undefined}>
            {p.label}
          </Link>
        ))}
      </nav>
      <p className="bos-hint">{d.period.label} · {range(d.period)}</p>
      {d.cards.length === 0 ? (
        <div className="bos-empty">
          Nothing to count yet — switch on Orders, Bookings, Bills or Payments in <Link href={`${base}/modules`}>Tools</Link>.
        </div>
      ) : (
        <div className="bos-insight-grid">
          {d.cards.map((c) => (
            <section key={c.key} className={`bos-insight is-${c.state}`} aria-labelledby={`in-${c.key}`}>
              <h2 id={`in-${c.key}`} className="bos-insight__title">{c.title}</h2>
              {c.value !== null ? <p className="bos-insight__value">{c.value}</p> : null}
              <p className="bos-insight__note">{c.note}</p>
              {c.detail.length ? (
                <dl className="bos-insight__detail">
                  {c.detail.map((x) => (
                    <div key={x.label}>
                      <dt>{x.label}</dt>
                      <dd>{x.value}</dd>
                    </div>
                  ))}
                </dl>
              ) : null}
              {c.state === 'ok' || c.state === 'no_data' ? (
                <Link className="bos-insight__go" href={`${base}${c.href}`}>{c.go ?? 'Open'} →</Link>
              ) : null}
            </section>
          ))}
        </div>
      )}
      {d.not_switched_on.length ? (
        <p className="bos-hint bos-insights__off">
          Not counted here because the tool is off: {d.not_switched_on.map((m) => m.title).join(', ')}.{' '}
          <Link href={`${base}/modules`}>Tools</Link>
        </p>
      ) : null}
    </div>
  )
}
