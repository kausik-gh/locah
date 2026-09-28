import type { Metadata } from 'next'
import Link from 'next/link'
import { notFound } from 'next/navigation'
import { RESERVED_SLUGS } from '@/lib/reserved-slugs'
import { fetchPublicWebsite } from '@/lib/public-website'
import { fetchReviewerView } from '@/lib/public-reviews'
import { siteThemeVars } from '@/components/website/WebsitePageView'
import { ReviewForm } from './ReviewForm'

export const dynamic = 'force-dynamic'
export const metadata: Metadata = { robots: { index: false, follow: false }, referrer: 'no-referrer' }

export default async function CustomerReviewPage({ params }: { params: { slug: string; token: string } }) {
  if (RESERVED_SLUGS.has(params.slug)) notFound()
  const view = await fetchReviewerView(params.slug, params.token)
  if (!view) notFound()
  const site = await fetchPublicWebsite(params.slug)
  const theme = site ? siteThemeVars(site) : { styleVars: {}, paletteMode: 'light' }
  return (
    <div data-locah-site="" data-palette={theme.paletteMode} style={theme.styleVars}>
      <main className="ls-section ls-review-page">
        <div className="ls-inner">
          {site ? <Link className="ls-reviews-back" href={`/${params.slug}`}>← {view.business_name}</Link> : null}
          <header className="ls-reviews-header">
            <p className="ls-eyebrow">Your experience</p>
            <h1>Review {view.business_name}</h1>
            <p>For {view.label}. Only someone who completed this interaction can use this link.</p>
          </header>
          <ReviewForm initial={view} slug={params.slug} token={params.token} />
        </div>
      </main>
    </div>
  )
}
