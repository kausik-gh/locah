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
  description?: string | null
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
    <div className="ws-modules-page">
      <PageHeader
        title="The tools that fit your business."
        subtitle="Explore what is available, what is running and what is included in your plan."
      />

      <section>
        <h2 className="ws-section-title">Available modules <span>{optional.length} to explore</span></h2>
        <div className="ws-module-grid">
          {optional.map((item, index) => {
            const state = states.get(item.module_id)
            const isEntitled = entitled.size === 0 || entitled.has(item.module_id)
            const operational = state === 'active' || state === 'ready'
            return (
              <article
                key={item.module_id}
                className="ws-module-card"
              >
                <div className="ws-module-card__head"><span className="ws-module-card__number">{String(index + 1).padStart(2, '0')}</span>{state ? <StatusPill value={state} /> : <span className="ws-module-card__state">{isEntitled ? 'Not enabled' : 'Not in plan'}</span>}</div>
                <div className="ws-module-card__body">
                  <Link href={`/b/${params.businessId}/modules/${item.module_id}`} className="ws-module-card__title">
                    {item.display_name} <span aria-hidden="true">↗</span>
                  </Link>
                  {item.description ? <p>{item.description}</p> : <p>Explore what this module does and how it fits your business.</p>}
                </div>
                <div className="ws-module-card__foot">
                  <Link href={`/b/${params.businessId}/modules/${item.module_id}`}>View details</Link>
                  {isEntitled ? (
                    <form action={setModuleState}>
                      <input type="hidden" name="businessId" value={params.businessId} />
                      <input type="hidden" name="moduleId" value={item.module_id} />
                      <input
                        type="hidden"
                        name="action"
                        value={operational ? 'deactivate' : 'enable'}
                      />
                      <button type="submit" className="btn-quiet">
                        {operational ? 'Turn off' : 'Turn on'}
                      </button>
                    </form>
                  ) : null}
                </div>
              </article>
            )
          })}
        </div>
        {optional.length === 0 ? <EmptyState>No modules in the catalog.</EmptyState> : null}
      </section>

      {core.length > 0 ? (
        <section style={{ marginTop: '2rem' }}>
          <h2 className="ws-section-title">Always included <span>The foundation</span></h2>
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
