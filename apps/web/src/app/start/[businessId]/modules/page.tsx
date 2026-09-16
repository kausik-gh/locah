import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/platform-api'
import { OnboardingError, OnboardingShell, Steps } from '@/components/onboarding/Shell'
import { ClaimForm, type CatalogEntry, type Recommendation } from './ClaimForm'

export const dynamic = 'force-dynamic'

type Business = { id: string; display_name: string; business_type?: string | null }
type ModuleSeed = { module_id: string; rationale: string; rank: number }
type CatalogModule = { module_id: string; display_name: string; module_class: string }
type ModuleState = { module_id: string; activation_state: string }

const OPERATIONAL = new Set(['active', 'ready'])

/** Onboarding steps 3 + 4 — recommendations for this business type, and claiming them. */
export default async function ModulesStepPage({
  params,
}: {
  params: { businessId: string }
}) {
  const token = await getAccessToken()
  if (!token) redirect(`/login?destination=/start/${params.businessId}/modules`)

  const bizRes = await apiTry<{ data: Business[] }>('/v1/platform/businesses', token)
  if (!bizRes.ok) {
    return (
      <OnboardingShell>
        <Steps current={3} />
        <OnboardingError
          title="Could not load your business"
          code={bizRes.error.code}
          message={bizRes.error.message}
        />
      </OnboardingShell>
    )
  }
  const business = (bizRes.data.data || []).find((b) => b.id === params.businessId)
  const businessType = business?.business_type || 'not_sure'

  const [profileRes, catalogRes, statesRes] = await Promise.all([
    apiTry<{ data: { module_seeds: ModuleSeed[] } }>(
      `/v1/platform/business-types/${encodeURIComponent(businessType)}/profile`,
      token
    ),
    apiTry<{ data: CatalogModule[] }>('/v1/platform/modules', token),
    apiTry<{ data: ModuleState[] }>(`/v1/b/${params.businessId}/modules`, token),
  ])

  if (!profileRes.ok) {
    return (
      <OnboardingShell>
        <Steps current={3} />
        <OnboardingError
          title="Could not load recommendations"
          code={profileRes.error.code}
          message={profileRes.error.message}
        >
          <Link href={`/start/${params.businessId}/modules`}>Try again</Link>
        </OnboardingError>
      </OnboardingShell>
    )
  }

  const catalog = catalogRes.ok ? catalogRes.data.data || [] : []
  const byId = new Map(catalog.map((m) => [m.module_id, m]))
  const states = new Map(
    (statesRes.ok ? statesRes.data.data || [] : []).map((s) => [s.module_id, s.activation_state])
  )

  const seeds = [...(profileRes.data.data.module_seeds || [])].sort((a, b) => a.rank - b.rank)

  // Only recommend modules the owner can actually claim: a seed naming a
  // module the catalog doesn't have is a data bug, not something to render.
  const recommendations: Recommendation[] = seeds
    .filter((s) => byId.has(s.module_id))
    .map((s) => ({
      module_id: s.module_id,
      rationale: s.rationale,
      rank: s.rank,
      display_name: byId.get(s.module_id)?.display_name || s.module_id,
      already_active: OPERATIONAL.has(states.get(s.module_id) || ''),
    }))

  const recommendedIds = new Set(recommendations.map((r) => r.module_id))
  const others: CatalogEntry[] = catalog
    .filter(
      (m) =>
        m.module_class !== 'platform_core' &&
        !recommendedIds.has(m.module_id) &&
        !OPERATIONAL.has(states.get(m.module_id) || '')
    )
    .map((m) => ({ module_id: m.module_id, display_name: m.display_name }))
    .sort((a, b) => a.display_name.localeCompare(b.display_name))

  return (
    <OnboardingShell>
      <Steps current={3} />
      <h1 style={{ fontSize: '2rem', margin: '0 0 0.6rem' }}>What {business?.display_name || 'your business'} needs</h1>
      <p style={{ color: '#3c4855', lineHeight: 1.65, margin: '0 0 2rem', maxWidth: '36rem' }}>
        Based on running a{' '}
        <strong>{businessType.replace(/_/g, ' ')}</strong> business. These are pre-selected —
        uncheck anything you don&apos;t want. You can change all of this later.
      </p>

      {recommendations.length === 0 ? (
        <OnboardingError
          title="No recommendations available"
          message="We couldn't match any tools to this business type. You can still open your Workspace and turn things on from the module catalog."
        />
      ) : (
        <ClaimForm
          businessId={params.businessId}
          recommendations={recommendations}
          others={others}
        />
      )}
    </OnboardingShell>
  )
}
