import type { Metadata } from 'next'
import Link from 'next/link'
import { notFound } from 'next/navigation'
import { RESERVED_SLUGS } from '@/lib/reserved-slugs'
import { fetchPublicWebsite } from '@/lib/public-website'
import { fetchReviewerView } from '@/lib/public-reviews'
import { SiteFrame } from '@/components/website/SiteFrame'
import { siteLang } from '@/lib/site-lang'
import { siteWords } from '@/lib/site-words'
import { ReviewForm } from './ReviewForm'

export const dynamic = 'force-dynamic'
export const metadata: Metadata = { robots: { index: false, follow: false }, referrer: 'no-referrer' }

export default async function CustomerReviewPage({ params, searchParams }: { params: { slug: string; token: string }; searchParams?: { lang?: string } }) {
  if (RESERVED_SLUGS.has(params.slug)) notFound()
  const view = await fetchReviewerView(params.slug, params.token)
  if (!view) notFound()
  const site = await fetchPublicWebsite(params.slug)
  // The invitation arrives on WhatsApp in the customer's language (?lang=).
  const lang = siteLang(site?.website.languages, searchParams?.lang, true)
  const t = siteWords(lang)
  return (
    <SiteFrame site={site} lang={lang} style={{ minHeight: undefined }}>
      <main className="ls-section ls-review-page">
        <div className="ls-inner">
          {site ? <Link className="ls-reviews-back" href={`/${params.slug}`}>← {view.business_name}</Link> : null}
          <header className="ls-reviews-header">
            <p className="ls-eyebrow">{t('Your experience')}</p>
            <h1>{t('Review {business}', { business: view.business_name })}</h1>
            <p>{t('For {what}. Only someone who completed this interaction can use this link.', { what: view.label })}</p>
          </header>
          <ReviewForm initial={view} slug={params.slug} token={params.token} />
        </div>
      </main>
    </SiteFrame>
  )
}
