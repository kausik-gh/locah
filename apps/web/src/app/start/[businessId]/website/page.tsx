import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/platform-api'
import { OnboardingError, OnboardingShell, Steps } from '@/components/onboarding/Shell'

export const dynamic = 'force-dynamic'

type Section = { id: string; section_type_id: string; is_visible: boolean }
type Page = { id: string; title: string; slug: string; page_type: string; sections: Section[] }
type WebsiteAggregate = {
  website: { id: string; status: string; slug?: string | null }
  draft: {
    id: string
    generated_by: string | null
    generation_job_id: string | null
    pages: Page[]
  } | null
}
type Business = { id: string; slug: string; display_name: string }

const BTN: React.CSSProperties = {
  display: 'inline-block',
  padding: '0.7rem 1.4rem',
  borderRadius: '8px',
  background: '#1c5f57',
  color: '#fff',
  textDecoration: 'none',
  fontWeight: 600,
  fontFamily: 'system-ui, sans-serif',
  fontSize: '0.95rem',
}
const GHOST: React.CSSProperties = {
  ...BTN,
  background: 'transparent',
  color: '#1c5f57',
  border: '1px solid #1c5f57',
}

/**
 * Onboarding step 2 — the generated website, made visible.
 *
 * Generation is enqueued server-side by business creation. In practice the
 * deterministic draft is written during creation, so by the time this page
 * renders there are usually already real pages; the "still building" branch
 * exists for the case where the async job hasn't landed a draft yet.
 */
export default async function WebsiteStepPage({
  params,
}: {
  params: { businessId: string }
}) {
  const token = await getAccessToken()
  if (!token) redirect(`/login?destination=/start/${params.businessId}/website`)

  const [siteRes, bizRes, genRes] = await Promise.all([
    apiTry<{ data: WebsiteAggregate }>(`/v1/b/${params.businessId}/website`, token),
    apiTry<{ data: Business[] }>('/v1/platform/businesses', token),
    apiTry<{ data: { status: string; generated_by?: string | null } | null }>(
      `/v1/b/${params.businessId}/website/generation`,
      token
    ),
  ])

  const genStatus = genRes.ok ? genRes.data.data?.status : undefined
  const regenerating = genStatus === 'pending' || genStatus === 'running'

  if (!siteRes.ok) {
    return (
      <OnboardingShell>
        <Steps current={2} />
        <OnboardingError
          title="Could not load your website"
          code={siteRes.error.code}
          message={siteRes.error.message}
        >
          <Link href={`/start/${params.businessId}/website`} style={GHOST}>
            Try again
          </Link>
        </OnboardingError>
      </OnboardingShell>
    )
  }

  const site = siteRes.data.data
  const pages = site.draft?.pages || []
  const business = bizRes.ok
    ? (bizRes.data.data || []).find((b) => b.id === params.businessId)
    : undefined

  // Still building: no draft pages yet, or a questionnaire-driven regeneration
  // is in flight. Refresh on a timer rather than an indefinite spinner.
  if (pages.length === 0 || regenerating) {
    return (
      <OnboardingShell>
        <meta httpEquiv="refresh" content="3" />
        <Steps current={2} />
        <h1 style={{ fontSize: '2rem', margin: '0 0 0.6rem' }}>Building your website…</h1>
        <p style={{ color: '#3c4855', lineHeight: 1.65, maxWidth: '34rem' }}>
          {regenerating
            ? "We're writing your site from your answers now. This screen refreshes on its own."
            : "We're generating your pages now. This screen refreshes every few seconds and will show your site as soon as it's ready."}
        </p>
        <p
          style={{
            fontFamily: 'system-ui, sans-serif',
            fontSize: '0.85rem',
            color: '#4c5967',
            marginTop: '1.5rem',
          }}
        >
          Taking too long?{' '}
          <Link href={`/start/${params.businessId}/modules`}>Skip ahead to your tools</Link> — the
          website will finish on its own.
        </p>
      </OnboardingShell>
    )
  }

  const totalSections = pages.reduce((n, p) => n + (p.sections?.length || 0), 0)
  const previewRes = await apiTry<{ data: { token?: string; preview_token?: string } }>(
    `/v1/b/${params.businessId}/website/preview-token`,
    token
  )
  const previewToken = previewRes.ok
    ? previewRes.data.data?.token || previewRes.data.data?.preview_token
    : undefined
  const previewHref =
    business && previewToken
      ? `/${business.slug}?preview_token=${encodeURIComponent(previewToken)}`
      : undefined

  return (
    <OnboardingShell>
      <Steps current={2} />
      <h1 style={{ fontSize: '2rem', margin: '0 0 0.6rem' }}>Your website is ready</h1>
      <p style={{ color: '#3c4855', lineHeight: 1.65, margin: '0 0 2rem', maxWidth: '36rem' }}>
        We built {pages.length} {pages.length === 1 ? 'page' : 'pages'} with {totalSections}{' '}
        {totalSections === 1 ? 'section' : 'sections'} for{' '}
        <strong>{business?.display_name || 'your business'}</strong>. It&apos;s a draft — only
        you can see it until you publish.
      </p>

      <div style={{ display: 'grid', gap: '0.7rem', marginBottom: '2rem' }}>
        {pages.map((p) => (
          <div
            key={p.id}
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              gap: '1rem',
              flexWrap: 'wrap',
              padding: '0.85rem 1.1rem',
              borderRadius: '10px',
              border: '1px solid rgba(28,36,48,0.14)',
              background: 'rgba(255,255,255,0.7)',
            }}
          >
            <div>
              <div style={{ fontWeight: 600 }}>{p.title}</div>
              <div
                style={{
                  fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
                  fontSize: '0.8rem',
                  color: '#4c5967',
                  marginTop: '0.15rem',
                }}
              >
                /{business?.slug || '…'}
                {p.slug && p.slug !== 'home' ? `/${p.slug}` : ''}
              </div>
            </div>
            <span
              style={{
                fontFamily: 'system-ui, sans-serif',
                fontSize: '0.82rem',
                color: '#4c5967',
              }}
            >
              {p.sections?.length || 0} sections
            </span>
          </div>
        ))}
      </div>

      <div style={{ display: 'flex', gap: '0.8rem', flexWrap: 'wrap', alignItems: 'center' }}>
        <Link href={`/start/${params.businessId}/modules`} style={BTN}>
          Next: choose your tools →
        </Link>
        {previewHref ? (
          <a href={previewHref} target="_blank" rel="noreferrer" style={GHOST}>
            Preview the live site ↗
          </a>
        ) : null}
      </div>

      {site.draft?.generated_by === 'deterministic_fallback' ? (
        <p
          style={{
            marginTop: '2rem',
            fontFamily: 'system-ui, sans-serif',
            fontSize: '0.85rem',
            color: '#4c5967',
            lineHeight: 1.6,
            maxWidth: '36rem',
          }}
        >
          Built from your business details using the standard layout for your industry — no AI
          writing provider is configured on this environment. You can edit every page and
          section in your Workspace.
        </p>
      ) : null}
    </OnboardingShell>
  )
}
