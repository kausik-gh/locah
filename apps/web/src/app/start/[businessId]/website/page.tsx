import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/platform-api'
import { OnboardingError, OnboardingShell, Steps } from '@/components/onboarding/Shell'
import { LivePreview } from './LivePreview'
import './preview.css'

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

/**
 * Onboarding step 2 — the website, shown rather than described.
 *
 * The interview's "build" writes a real deterministic draft synchronously
 * before this page is ever requested, so by the time it renders there is an
 * actual site to put on screen. It goes on screen. A progress screen here
 * would be inventing a wait that the architecture already removed.
 *
 * The "still building" branch below is kept for the genuine case where no
 * draft exists at all — a direct visit before building, or a generation that
 * failed outright. It is a real empty state, not a default.
 */
export default async function WebsiteStepPage({ params }: { params: { businessId: string } }) {
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

  if (!siteRes.ok) {
    return (
      <OnboardingShell>
        <Steps current={2} />
        <OnboardingError
          title="Could not load your website"
          code={siteRes.error.code}
          message={siteRes.error.message}
        >
          <Link href={`/start/${params.businessId}/website`} className="lc-btn">
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
  const genStatus = genRes.ok ? (genRes.data.data?.status ?? null) : null

  if (pages.length === 0) {
    return (
      <OnboardingShell>
        <Steps current={2} />
        <h1 className="lp-title">No website yet</h1>
        <p className="lp-lede">
          Your website is built from your interview answers. Finish the conversation and choose
          <strong> Build my website</strong> — the first version appears straight away.
        </p>
        <Link href={`/start/${params.businessId}/interview`} className="lc-btn lc-btn--primary">
          Back to your interview →
        </Link>
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
  const nextStep = site.draft?.generated_by?.startsWith('interview') ? 'done' : 'modules'

  return (
    <OnboardingShell wide>
      <Steps current={2} />
      <div className="lp-head">
        <div>
          <h1 className="lp-title">Here is your website</h1>
          <p className="lp-lede">
            {pages.length} {pages.length === 1 ? 'page' : 'pages'}, {totalSections}{' '}
            {totalSections === 1 ? 'section' : 'sections'}, built from what you told us. It is a
            draft — only you can see it until you publish.
          </p>
        </div>
        <div className="lp-actions">
          <Link href={`/start/${params.businessId}/${nextStep}`} className="lc-btn lc-btn--primary">
            Continue →
          </Link>
          {previewHref ? (
            <a href={previewHref} target="_blank" rel="noreferrer" className="lc-btn lc-btn--ghost">
              Open full size ↗
            </a>
          ) : null}
        </div>
      </div>

      {previewHref ? (
        <LivePreview businessId={params.businessId} src={previewHref} initialStatus={genStatus} />
      ) : (
        <p className="lp-lede" role="status">
          Your draft is saved with {pages.length} {pages.length === 1 ? 'page' : 'pages'}, but the
          secure preview link could not be created just now. You can open and edit every page in
          your Workspace.
        </p>
      )}

      <ul className="lp-pages">
        {pages.map((p) => (
          <li key={p.id}>
            <strong>{p.title}</strong>
            <code>
              /{business?.slug || '…'}
              {p.slug && p.slug !== 'home' ? `/${p.slug}` : ''}
            </code>
            <span>
              {p.sections?.length || 0} {p.sections?.length === 1 ? 'section' : 'sections'}
            </span>
          </li>
        ))}
      </ul>
    </OnboardingShell>
  )
}
