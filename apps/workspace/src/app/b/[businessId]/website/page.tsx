import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import { GateNotice, PageHeader } from '@/components/ModuleState'
import { businessSiteUrl, platformUrl } from '@platform/config'

export const dynamic = 'force-dynamic'

type WebsiteResponse = {
  data: {
    website: { status: string; published_version_id: string | null }
    draft: {
      generated_by?: string | null
      pages: { id: string; title: string; slug: string; sections?: unknown[] }[]
      navigation: { label: string; path: string }[]
    } | null
  }
}

type Business = { slug: string; display_name: string; visibility: string }

export default async function WebsiteOverviewPage({
  params,
}: {
  params: { businessId: string }
}) {
  const token = await getAccessToken()
  if (!token) redirect('/login')

  const [res, bizRes] = await Promise.all([
    apiTry<WebsiteResponse>(`/v1/b/${params.businessId}/website`, token),
    apiTry<{ data: Business }>(`/v1/b/${params.businessId}`, token),
  ])

  if (!res.ok) {
    return (
      <div>
        <PageHeader title="Your website" />
        <GateNotice error={res.error} businessId={params.businessId} moduleLabel="Website" />
      </div>
    )
  }

  const { website, draft } = res.data.data
  const business = bizRes.ok ? bizRes.data.data : null
  const base = `/b/${params.businessId}/website`
  const webUrl = platformUrl('web')
  const isPublished = website.status === 'published'
  const pages = draft?.pages || []

  const builtBy =
    draft?.generated_by === 'ai_generation'
      ? 'Written for you from what you told us about the business.'
      : draft?.generated_by === 'deterministic_fallback'
        ? 'Built from your business details.'
        : null

  return (
    <div className="ws-website-overview">
      <PageHeader
        title="Your website"
        subtitle={
          isPublished
            ? 'Your site is live. Changes you make stay in your draft until you publish them.'
            : 'Your site is not live yet. Publish it when it reads the way you want.'
        }
      />

      <div className="ws-stats" style={{ marginBottom: '1.5rem' }}>
        <div className="ws-stat">
          <p className="ws-stat__label">Status</p>
          <p className="ws-stat__value" style={{ fontSize: '1.15rem' }}>
            {isPublished ? 'Live' : 'Not published'}
          </p>
          {business && isPublished ? (
            <p className="ws-stat__note">
              <a href={`${webUrl}/${business.slug}`} target="_blank" rel="noreferrer">
                {businessSiteUrl(business.slug).replace(/^https?:\/\//, '')} ↗
              </a>
            </p>
          ) : (
            <p className="ws-stat__note">Only you can see it right now</p>
          )}
        </div>
        <div className="ws-stat">
          <p className="ws-stat__label">Pages</p>
          <p className="ws-stat__value" style={{ fontSize: '1.15rem' }}>
            {pages.length}
          </p>
          <p className="ws-stat__note">{pages.map((p) => p.title).join(' · ') || '—'}</p>
        </div>
        <div className="ws-stat">
          <p className="ws-stat__label">Findable in the Marketplace</p>
          <p className="ws-stat__value" style={{ fontSize: '1.15rem' }}>
            {business?.visibility === 'discoverable' ? 'Yes' : 'No'}
          </p>
          <p className="ws-stat__note">
            {business?.visibility === 'discoverable' ? (
              'Customers can find you by searching'
            ) : (
              <Link href={`/b/${params.businessId}/marketplace`}>Set this up →</Link>
            )}
          </p>
        </div>
      </div>

      {builtBy ? (
        <p style={{ color: 'var(--color-muted)', marginBottom: '1.25rem' }}>{builtBy}</p>
      ) : null}

      <h2 className="ws-section-title">Make it yours <span>Manage your website</span></h2>
      <div className="ws-actions">
        <Link className="ws-action" href={`${base}/templates`}>
          <span className="ws-action__title">Starting point</span>
          <span className="ws-action__body">
            Pick the layout your site is built on. See what each one looks like before you choose.
          </span>
        </Link>
        <Link className="ws-action" href={`${base}/preview`}>
          <span className="ws-action__title">Edit your website</span>
          <span className="ws-action__body">
            Change the words and pictures on any page and watch it update as you go.
          </span>
        </Link>
        <Link className="ws-action" href={`${base}/theme`}>
          <span className="ws-action__title">Colours &amp; menu</span>
          <span className="ws-action__body">
            Your brand colours and which pages appear in your site&apos;s menu.
          </span>
        </Link>
        <Link className="ws-action" href={`${base}/pages`}>
          <span className="ws-action__title">Pages &amp; sections</span>
          <span className="ws-action__body">
            Add or remove a page, reorder the sections on it, or hide one for now.
          </span>
        </Link>
        <Link className="ws-action ws-action--primary" href={`${base}/publish`}>
          <span className="ws-action__title">
            {isPublished ? 'Publish your changes' : 'Publish your site'}
          </span>
          <span className="ws-action__body">
            {isPublished
              ? 'Push what is in your draft out to the live site.'
              : 'Make your site public so customers can find it.'}
          </span>
        </Link>
      </div>
    </div>
  )
}
