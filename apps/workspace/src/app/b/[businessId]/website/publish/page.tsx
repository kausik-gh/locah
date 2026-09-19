import Link from 'next/link'
import { redirect } from 'next/navigation'
import { businessSiteUrl } from '@platform/config'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import { GateNotice, PageHeader } from '@/components/ModuleState'
import { publishWebsite, generatePreviewToken } from './actions'

export const dynamic = 'force-dynamic'

type WebsiteResponse = {
  data: {
    website: { status: string }
    draft: { pages: { slug: string; title: string }[]; generated_by?: string | null }
  }
}

type BusinessSummary = {
  id: string
  slug: string
  display_name: string
  state?: string | null
  visibility?: string | null
}

export default async function WebsitePublishPage({
  params,
}: {
  params: { businessId: string }
}) {
  const token = await getAccessToken()
  if (!token) redirect('/login')

  const [res, bizRes] = await Promise.all([
    apiTry<WebsiteResponse>(`/v1/b/${params.businessId}/website`, token),
    apiTry<{ data: BusinessSummary[] }>('/v1/platform/businesses', token),
  ])

  if (!res.ok) {
    return (
      <div>
        <PageHeader title="Preview & Publish" />
        <GateNotice error={res.error} businessId={params.businessId} moduleLabel="Website" />
      </div>
    )
  }

  const published = res.data.data.website.status === 'published'
  const business = bizRes.ok
    ? (bizRes.data.data || []).find((b) => b.id === params.businessId)
    : undefined

  // Publishing the website and the business being reachable are two different
  // things, and conflating them is how someone publishes, is told "Published",
  // and still finds their address returning nothing. A business that is still a
  // draft, or set to private, is not served to the public whatever its website
  // says — so that is stated here rather than discovered.
  const businessIsLive = business?.state === 'active'
  const publiclyVisible =
    business?.visibility === 'discoverable' || business?.visibility === 'unlisted'
  const reachable = published && businessIsLive && publiclyVisible
  const liveUrl = business ? businessSiteUrl(business.slug) : undefined

  return (
    <div>
      <h1 style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>Preview & Publish</h1>
      <p style={{ marginBottom: '1rem', maxWidth: '42rem' }}>
        Preview gives you a private link to check your site before customers see it. Publishing
        makes your current draft live. Nothing goes live until you publish.
      </p>
      <p>
        Current status:{' '}
        <strong>{published ? 'Published' : 'Draft — not yet live'}</strong>
      </p>

      {published && !reachable ? (
        <div
          role="status"
          style={{
            marginTop: '0.9rem',
            padding: '0.9rem 1.1rem',
            border: '1px solid var(--color-border)',
            borderRadius: '10px',
            background: 'var(--color-surface)',
            maxWidth: '42rem',
            lineHeight: 1.55,
          }}
        >
          <strong>Your site is published, but nobody can reach it yet.</strong>
          <p style={{ margin: '0.4rem 0 0' }}>
            {!businessIsLive
              ? 'This business is still a draft. Until it goes live, its address returns nothing to the public.'
              : 'This business is set to private, so its address is not served to the public.'}
          </p>
          <p style={{ margin: '0.6rem 0 0' }}>
            <Link href={`/b/${params.businessId}/marketplace`}>
              Open Marketplace Presence to change this →
            </Link>
          </p>
        </div>
      ) : null}

      {reachable && liveUrl ? (
        <p style={{ marginTop: '0.9rem' }}>
          Live at{' '}
          <a href={liveUrl} target="_blank" rel="noreferrer">
            {liveUrl.replace(/^https?:\/\//, '')}
          </a>
        </p>
      ) : null}

      <ul>
        {res.data.data.draft.pages.map((p) => (
          <li key={p.slug}>
            {p.title} /{p.slug}
          </li>
        ))}
      </ul>
      <div style={{ display: 'flex', gap: '0.75rem', marginTop: '1rem' }}>
        <form action={generatePreviewToken}>
          <input type="hidden" name="businessId" value={params.businessId} />
          <button type="submit">Get preview link</button>
        </form>
        <form action={publishWebsite}>
          <input type="hidden" name="businessId" value={params.businessId} />
          <button type="submit">{published ? 'Publish latest draft' : 'Publish'}</button>
        </form>
        <Link href={`/b/${params.businessId}/website`}>Back to overview</Link>
      </div>
    </div>
  )
}
