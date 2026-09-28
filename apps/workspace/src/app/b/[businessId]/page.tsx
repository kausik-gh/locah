import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import { Card, PageHeader } from '@/components/ui'

export const dynamic = 'force-dynamic'

type Business = { display_name: string; state: string; status: string; visibility: string }

type Item = { label: string; count: number; href: string; detail: string; tone: string }
type Stat = { label: string; value: string; href: string; note: string }
type Band = { key: string; title: string; items?: Item[]; stats?: Stat[]; empty: string }
type Home = {
  role: { key: string; label: string; question: string }
  location_scoped: boolean
  bands: Band[]
}

/**
 * Workspace Home (Business OS Guide §3: "Home should answer a question, not
 * display random cards"; Build Spec §8). The API composes the bands for the
 * viewer's role from real records within their permissions and locations;
 * this page lays them out and links every row to the records behind it.
 */
export default async function WorkspaceHomePage({ params }: { params: { businessId: string } }) {
  const token = await getAccessToken()
  if (!token) redirect('/login')
  const base = `/b/${params.businessId}`
  const [homeRes, businessRes] = await Promise.all([
    apiTry<{ data: Home }>(`/v1/platform/businesses/${params.businessId}/home`, token),
    apiTry<{ data: Business }>(`/v1/b/${params.businessId}`, token),
  ])
  const business = businessRes.ok ? businessRes.data.data : null

  if (business && business.status && business.status !== 'in_good_standing') {
    const suspended = business.status === 'suspended'
    return (
      <div>
        <PageHeader title={business.display_name} />
        <Card tone="danger" style={{ maxWidth: '46rem' }}>
          <h2 style={{ marginBottom: '0.4rem' }}>
            {suspended ? 'This business is suspended' : 'This business is under review'}
          </h2>
          <p style={{ color: 'var(--status-bad-fg)' }}>
            {suspended
              ? 'New orders, bookings and payments are not being accepted right now. Your data is safe and nothing has been deleted.'
              : 'Your account is being reviewed. Everything keeps working normally while that happens.'}
          </p>
          <p style={{ color: 'var(--color-muted)' }}>Contact support to resolve this. They can tell you exactly what is needed.</p>
        </Card>
      </div>
    )
  }

  if (!homeRes.ok) {
    return (
      <div>
        <PageHeader title={business?.display_name ?? 'Workspace'} />
        <Card style={{ maxWidth: '40rem' }}>
          <p>Your home could not load just now. Refresh the page to try again.</p>
        </Card>
      </div>
    )
  }

  const home = homeRes.data.data
  const isOwner = home.role.key === 'owner'
  const attention = home.bands.find((b) => b.key === 'now' || b.key === 'late')
  const waiting = attention?.items?.reduce((n, i) => n + (i.count || 0), 0) ?? 0
  const subtitle = isOwner
    ? waiting > 0
      ? `${waiting} thing${waiting === 1 ? '' : 's'} need you.`
      : 'Nothing needs you right now.'
    : `${home.role.label} · ${home.role.question}`

  return (
    <div className="bos-home">
      <PageHeader title={business?.display_name ?? 'Workspace'} subtitle={subtitle} />
      {home.location_scoped ? (
        <p className="bos-hint">Showing your locations only.</p>
      ) : null}
      {home.bands.map((band) => (
        <section key={band.key} className={`bos-band bos-band--${band.key}`} aria-labelledby={`band-${band.key}`}>
          <h2 className="bos-section__title" id={`band-${band.key}`}>{band.title}</h2>
          {band.stats ? (
            <div className="ws-stats">
              {band.stats.map((s) => (
                <Link key={s.label} href={s.href.startsWith('~') ? `${s.href.slice(1)}/${params.businessId}` : `${base}${s.href}`} className="ws-stat bos-stat-link">
                  <p className="ws-stat__label">{s.label}</p>
                  <p className="ws-stat__value">{s.value}</p>
                  {s.note ? <p className="ws-stat__note">{s.note}</p> : null}
                </Link>
              ))}
            </div>
          ) : band.items && band.items.length > 0 ? (
            <ul className="bos-attention">
              {band.items.map((i) => (
                <li key={`${i.label}-${i.href}`}>
                  <Link href={i.href.startsWith('~') ? `${i.href.slice(1)}/${params.businessId}` : `${base}${i.href}`} className={`bos-attention__row is-${i.tone}`}>
                    {band.key === 'business' ? (
                      <span className="bos-attention__dot" aria-hidden />
                    ) : (
                      <span className="bos-attention__count">{i.count}</span>
                    )}
                    <span className="bos-attention__text">
                      <strong>{i.label}</strong>
                      {i.detail ? <span>{i.detail}</span> : null}
                    </span>
                    <span className="bos-attention__go" aria-hidden>→</span>
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <div className="bos-empty">{band.empty}</div>
          )}
        </section>
      ))}
    </div>
  )
}
