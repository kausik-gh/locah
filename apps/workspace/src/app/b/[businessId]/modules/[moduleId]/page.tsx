import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import { GateNotice, PageHeader, StatusPill } from '@/components/ModuleState'
import { setModuleState } from '../actions'

export const dynamic = 'force-dynamic'

type ModuleDetail = {
  module_id: string
  display_name: string
  module_class: string
  description: string | null
  dependencies: string[]
  default_state: string
  features: Array<{ feature_id: string; display_name?: string }>
}

type ModuleState = { module_id: string; activation_state: string }

/** Doc 09 CORE-014 Module Detail & Management. */
export default async function ModuleDetailPage({
  params,
}: {
  params: { businessId: string; moduleId: string }
}) {
  const token = await getAccessToken()
  if (!token) redirect('/login')

  const res = await apiTry<{ data: ModuleDetail }>(
    `/v1/platform/modules/${params.moduleId}`,
    token
  )
  if (!res.ok) {
    return (
      <div>
        <Link href={`/b/${params.businessId}/modules`}>← Modules</Link>
        <PageHeader title="Module" />
        <GateNotice error={res.error} businessId={params.businessId} moduleLabel="This module" />
      </div>
    )
  }
  const moduleDetail = res.data.data

  const statesRes = await apiTry<{ data: ModuleState[] }>(
    `/v1/b/${params.businessId}/modules`,
    token
  )
  const state = statesRes.ok
    ? statesRes.data.data?.find((row) => row.module_id === params.moduleId)?.activation_state
    : undefined
  const operational = state === 'active' || state === 'ready'
  const isCore = moduleDetail.module_class === 'platform_core'

  return (
    <div>
      <Link href={`/b/${params.businessId}/modules`}>← Modules</Link>
      <PageHeader title={moduleDetail.display_name} subtitle={moduleDetail.description ?? undefined} />

      <p>
        {state ? (
          <>
            Status: <StatusPill value={state} />
          </>
        ) : (
          <span style={{ opacity: 0.8 }}>Not enabled for this Business.</span>
        )}
      </p>

      {moduleDetail.dependencies.length > 0 ? (
        <p style={{ opacity: 0.85 }}>
          Needs: {moduleDetail.dependencies.join(', ')}. Turning this on without them will not work.
        </p>
      ) : null}

      {isCore ? (
        <p style={{ opacity: 0.8, marginTop: '1.25rem' }}>
          This is part of every Business and is always on.
        </p>
      ) : (
        <section style={{ marginTop: '1.5rem' }}>
          <form action={setModuleState}>
            <input type="hidden" name="businessId" value={params.businessId} />
            <input type="hidden" name="moduleId" value={params.moduleId} />
            <input type="hidden" name="action" value={operational ? 'deactivate' : 'enable'} />
            <button type="submit" style={BUTTON}>
              {operational ? 'Turn off this module' : 'Turn on this module'}
            </button>
          </form>
          {operational ? (
            <p style={{ opacity: 0.8, marginTop: '0.6rem' }}>
              Turning a module off hides its pages. Your data stays exactly where it is and comes
              back if you turn it on again.
            </p>
          ) : null}
        </section>
      )}

      {moduleDetail.features.length > 0 ? (
        <section style={{ marginTop: '2rem' }}>
          <h2 >What it includes</h2>
          <ul style={{ paddingLeft: '1.1rem' }}>
            {moduleDetail.features.map((feature) => (
              <li key={feature.feature_id}>{feature.display_name || feature.feature_id}</li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  )
}

const BUTTON: React.CSSProperties = {
  justifySelf: 'start',
}
