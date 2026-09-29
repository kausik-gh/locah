import type { Metadata } from 'next'
import { notFound } from 'next/navigation'
import { RESERVED_SLUGS } from '@/lib/reserved-slugs'
import { fetchPublicWebsite } from '@/lib/public-website'
import { fetchDocumentRequest } from '@/lib/public-documents'
import { SiteFrame } from '@/components/website/SiteFrame'
import { siteLang } from '@/lib/site-lang'
import { DocumentRequestPanel } from './DocumentRequestPanel'

export const dynamic = 'force-dynamic'
export const metadata: Metadata = { robots: { index: false, follow: false }, referrer: 'no-referrer' }

export default async function DocumentRequestPage({
  params,
  searchParams,
}: {
  params: { slug: string; token: string }
  searchParams?: { lang?: string }
}) {
  if (RESERVED_SLUGS.has(params.slug)) notFound()
  const view = await fetchDocumentRequest(params.slug, params.token)
  if (!view) notFound()
  const site = await fetchPublicWebsite(params.slug)
  const lang = siteLang(site?.website.languages, searchParams?.lang, true)
  const businessName = site?.business.display_name || 'This business'
  return (
    <SiteFrame site={site} lang={lang} style={{ minHeight: undefined }}>
      <main className="ls-section ls-review-page">
        <div className="ls-inner">
          <header className="ls-reviews-header">
            <p className="ls-eyebrow">Secure request</p>
            <h1>{view.title}</h1>
            <p>For {businessName}. This link works only for this request and expires {new Date(view.expires_at).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })}.</p>
          </header>
          <DocumentRequestPanel initial={view} slug={params.slug} token={params.token} />
        </div>
      </main>
    </SiteFrame>
  )
}
