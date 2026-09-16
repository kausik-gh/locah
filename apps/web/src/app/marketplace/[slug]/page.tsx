import type { Metadata } from 'next'
import Link from 'next/link'
import { notFound } from 'next/navigation'
import { fetchMarketplaceProfile } from '@/lib/marketplace-api'
import { fetchPublicOfferings } from '@/lib/checkout-api'
import { PublicNav } from '@/components/public/PublicNav'
import { PublicFooter } from '@/components/public/PublicFooter'
import { typeLabel } from '@/components/public/BusinessCard'

export const revalidate = 60

type Business = {
  id: string
  slug: string
  display_name: string
  business_type?: string | null
  city?: string | null
  description?: string | null
}
type Action = { action: string; label: string; href: string }
type Offering = {
  id: string
  title: string
  offering_type: string
  description?: string | null
  price_from?: number | null
  currency?: string | null
  handoff: { href: string }
}

export async function generateMetadata({
  params,
}: {
  params: { slug: string }
}): Promise<Metadata> {
  const data = await fetchMarketplaceProfile(params.slug)
  if (!data) return {}
  const b = data.business as Business
  return {
    title: `${b.display_name} — on LOCAH`,
    description: b.description || undefined,
  }
}

function money(amount?: number | null, currency?: string | null) {
  if (amount === null || amount === undefined) return null
  try {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: currency || 'INR',
      maximumFractionDigits: Number.isInteger(amount) ? 0 : 2,
    }).format(amount)
  } catch {
    return `${currency || 'INR'} ${amount}`
  }
}

/** MKT-007 Marketplace Business Profile + MKT-008 offering handoff.
 *
 *  This is LOCAH's page about the Business, deliberately separate from the
 *  Business's own Website. Every action here is an explicit handoff across
 *  that boundary rather than an attempt to reproduce their site. */
export default async function MarketplaceBusinessProfilePage({
  params,
  searchParams,
}: {
  params: { slug: string }
  searchParams?: { offering_id?: string; intent?: string; location_id?: string }
}) {
  // The Marketplace projection carries no imagery, so the public offerings
  // payload is merged in for pictures only. Both are already public.
  const [data, live] = await Promise.all([
    fetchMarketplaceProfile(params.slug),
    fetchPublicOfferings(params.slug).catch(() => ({ offerings: [] })),
  ])
  if (!data) notFound()

  const business = data.business as Business
  const actions = (data.actions || []) as Action[]
  const offerings = (data.offerings || []) as Offering[]

  const imageByTitle = new Map<string, string>()
  for (const o of (live.offerings || []) as Array<Record<string, unknown>>) {
    if (typeof o.title === 'string' && typeof o.image_url === 'string') {
      imageByTitle.set(o.title, o.image_url)
    }
  }

  const selected = searchParams?.offering_id
    ? offerings.find((o) => o.id === searchParams.offering_id)
    : null

  const primary = actions.find((a) => a.action !== 'visit_website') || actions[0]
  const visit = actions.find((a) => a.action === 'visit_website')

  function actionHref(a: Action) {
    if (a.action === 'visit_website') return a.href
    const qs = new URLSearchParams()
    if (searchParams?.offering_id) qs.set('offering_id', searchParams.offering_id)
    if (searchParams?.location_id) qs.set('location_id', searchParams.location_id)
    qs.set('intent', searchParams?.intent || a.action)
    return `${a.href}${a.href.includes('?') ? '&' : '?'}${qs.toString()}`
  }

  return (
    <div className="locah-public">
      <PublicNav active="marketplace" />
      <main>
        <section className="lc-section lc-section--tight lc-ground-paper">
          <div className="lc-container lc-container--wide">
            <p className="lc-eyebrow">
              <Link className="lc-link" href="/marketplace">
                Marketplace
              </Link>
            </p>
            <div className="mkp-head">
              <div>
                <h1>{business.display_name}</h1>
                <p className="lc-muted" style={{ marginBottom: 'var(--sp-4)' }}>
                  {typeLabel(business.business_type)}
                  {business.city ? ` · ${business.city}` : ''}
                </p>
                {business.description ? (
                  <p className="lc-lead">{business.description}</p>
                ) : null}
                <div className="lc-row" style={{ marginTop: 'var(--sp-5)' }}>
                  {primary ? (
                    <Link className="lc-btn lc-btn--primary lc-btn--lg" href={actionHref(primary)}>
                      {primary.label}
                    </Link>
                  ) : null}
                  {visit && visit !== primary ? (
                    <Link className="lc-btn lc-btn--ghost lc-btn--lg" href={visit.href}>
                      {visit.label}
                    </Link>
                  ) : null}
                </div>
                <p className="lc-small lc-muted" style={{ marginTop: 'var(--sp-3)' }}>
                  You will continue on {business.display_name}&rsquo;s own website.
                </p>
              </div>
            </div>
          </div>
        </section>

        {selected ? (
          <section className="lc-section lc-section--tight">
            <div className="lc-container lc-container--wide">
              <div className="lc-card" style={{ borderColor: 'var(--locah-accent)' }}>
                <p className="lc-eyebrow">You were looking at</p>
                <h2 className="lc-card__title">{selected.title}</h2>
                {selected.description ? (
                  <p className="lc-card__body">{selected.description}</p>
                ) : null}
                <Link
                  className="lc-btn lc-btn--primary"
                  href={selected.handoff.href}
                  style={{ marginTop: 'var(--sp-4)' }}
                >
                  Continue on their website
                </Link>
              </div>
            </div>
          </section>
        ) : null}

        <section className="lc-section">
          <div className="lc-container lc-container--wide">
            {offerings.length === 0 ? (
              <div className="lc-empty">
                <p className="lc-empty__title">Nothing listed yet</p>
                <p className="lc-empty__body">
                  This business has not published anything to the Marketplace yet. Their website
                  may still have more.
                </p>
                {visit ? (
                  <Link className="lc-btn lc-btn--ghost" href={visit.href}>
                    {visit.label}
                  </Link>
                ) : null}
              </div>
            ) : (
              <>
                <h2 style={{ marginBottom: 'var(--sp-6)' }}>
                  What {business.display_name} offers
                </h2>
                <div className="lc-grid lc-grid--3">
                  {offerings.map((o) => {
                    const img = imageByTitle.get(o.title)
                    return (
                      <Link className="lc-mediacard" key={o.id} href={o.handoff.href}>
                        <div className="lc-mediacard__media">
                          {img ? (
                            // eslint-disable-next-line @next/next/no-img-element
                            <img src={img} alt="" loading="lazy" />
                          ) : (
                            <div
                              className="lc-mediacard__fallback"
                              data-type={business.business_type || 'other'}
                              aria-hidden="true"
                            >
                              {o.title.slice(0, 1).toUpperCase()}
                            </div>
                          )}
                        </div>
                        <div className="lc-mediacard__body">
                          <h3 className="lc-mediacard__title">{o.title}</h3>
                          {o.description ? (
                            <p className="lc-muted lc-small mk-clamp">{o.description}</p>
                          ) : null}
                          {o.price_from !== null && o.price_from !== undefined ? (
                            <p className="lc-mediacard__foot lc-stat__value" style={{ fontSize: '1.1rem' }}>
                              {money(o.price_from, o.currency)}
                            </p>
                          ) : null}
                        </div>
                      </Link>
                    )
                  })}
                </div>
              </>
            )}
          </div>
        </section>
      </main>
      <PublicFooter />
    </div>
  )
}
