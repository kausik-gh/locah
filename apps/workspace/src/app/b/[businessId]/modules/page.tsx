import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import { EmptyState, GateNotice, PageHeader, StatusPill } from '@/components/ModuleState'
import { setModuleState } from './actions'

export const dynamic = 'force-dynamic'

type CatalogModule = {
  module_id: string
  display_name: string
  module_class: string
}

type ModuleState = {
  module_id: string
  activation_state: string
}

type Entitlements = {
  entitled_modules?: string[]
}

/** Doc 09 CORE-013 Module Catalog. */
export default async function ModuleCatalogPage({ params }: { params: { businessId: string } }) {
  const token = await getAccessToken()
  if (!token) redirect('/login')

  const statesRes = await apiTry<{ data: ModuleState[] }>(
    `/v1/b/${params.businessId}/modules`,
    token
  )
  if (!statesRes.ok) {
    return (
      <div>
        <PageHeader title="Modules" />
        <GateNotice error={statesRes.error} businessId={params.businessId} moduleLabel="Modules" />
      </div>
    )
  }
  const states = new Map(
    (statesRes.data.data || []).map((state) => [state.module_id, state.activation_state])
  )

  const [catalogRes, entitlementsRes] = await Promise.all([
    apiTry<{ data: CatalogModule[] }>(`/v1/platform/modules`, token),
    apiTry<{ data: Entitlements }>(
      `/v1/platform/businesses/${params.businessId}/entitlements`,
      token
    ),
  ])
  const catalog = catalogRes.ok ? catalogRes.data.data || [] : []
  const entitled = new Set(
    entitlementsRes.ok ? entitlementsRes.data.data?.entitled_modules || [] : []
  )

  const optional = catalog.filter((item) => item.module_class !== 'platform_core')
  const core = catalog.filter((item) => item.module_class === 'platform_core')

  return (
    <div>
      <PageHeader
        title="Modules"
        subtitle="What this Business can turn on, and what is already running."
      />

      <section>
        <h2 >Available modules</h2>
        <div style={{ display: 'grid', gap: '0.75rem', marginTop: '0.75rem' }}>
          {optional.map((item) => {
            const state = states.get(item.module_id)
            const isEntitled = entitled.size === 0 || entitled.has(item.module_id)
            const operational = state === 'active' || state === 'ready'
            return (
              <div
                key={item.module_id}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  gap: '1rem',
                  flexWrap: 'wrap',
                  padding: '0.9rem 1.1rem',
                  borderRadius: '10px',
                  border: '1px solid var(--color-border)',
                  background: 'var(--color-surface)',
                }}
              >
                <div>
                  <Link href={`/b/${params.businessId}/modules/${item.module_id}`}>
                    <strong>{item.display_name}</strong>
                  </Link>
                  {/*
                    The raw module id used to be printed here. It is a developer
                    identifier — `offerings-catalog`, `customer-relationships` —
                    and this page was the one place an owner saw the platform's
                    internal vocabulary instead of its own. The display name is
                    the whole of what they need; the id still addresses the
                    detail page through the link above.
                  */}
                </div>
                <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
                  {state ? (
                    <StatusPill value={state} />
                  ) : (
                    <span style={{ opacity: 0.7, fontSize: '0.9rem' }}>
                      {isEntitled ? 'not enabled' : 'not in plan'}
                    </span>
                  )}
                  {isEntitled ? (
                    <form action={setModuleState}>
                      <input type="hidden" name="businessId" value={params.businessId} />
                      <input type="hidden" name="moduleId" value={item.module_id} />
                      <input
                        type="hidden"
                        name="action"
                        value={operational ? 'deactivate' : 'enable'}
                      />
                      <button type="submit" style={BUTTON}>
                        {operational ? 'Turn off' : 'Turn on'}
                      </button>
                    </form>
                  ) : null}
                </div>
              </div>
            )
          })}
        </div>
        {optional.length === 0 ? <EmptyState>No modules in the catalog.</EmptyState> : null}
      </section>

      {core.length > 0 ? (
        <section style={{ marginTop: '2rem' }}>
          <h2 >Always included</h2>
          <p style={{ opacity: 0.8 }}>
            These are part of every Business and cannot be turned off.
          </p>
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            {core.map((item) => (
              <span
                key={item.module_id}
                style={{
                  padding: '0.3rem 0.7rem',
                  borderRadius: '999px',
                  border: '1px solid var(--color-border)',
                  background: 'var(--color-surface)',
                }}
              >
                {item.display_name}
              </span>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  )
}

const BUTTON: React.CSSProperties = {
  justifySelf: 'start',
}
