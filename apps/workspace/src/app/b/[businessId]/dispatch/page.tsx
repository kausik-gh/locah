import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import { GateNotice, PageHeader, StatusPill } from '@/components/ui'
import { DISPATCH_COLUMNS } from '@platform/contracts'

export const dynamic = 'force-dynamic'

type Job = {
  id: string
  order_number: string
  kind: string
  status: string
  assignee_name: string | null
  pickup: { label: string | null }
  customer: { name: string | null }
}

/**
 * Owner / dispatcher board. Columns match the shared dispatch contract:
 * Unassigned, Assigned, Out now, Delivered, Failed / attention.
 */
export default async function DispatchBoardPage({ params }: { params: { businessId: string } }) {
  const token = await getAccessToken()
  if (!token) redirect('/login')
  const res = await apiTry<{ data: { columns: { key: string; label: string; jobs: Job[] }[] } }>(
    `/v1/b/${params.businessId}/dispatch/board`,
    token,
  )
  if (!res.ok) {
    return (
      <div>
        <PageHeader title="Dispatch" />
        <GateNotice error={res.error} businessId={params.businessId} moduleLabel="Dispatch" />
      </div>
    )
  }
  const byKey = new Map(res.data.data.columns.map((column) => [column.key, column]))

  return (
    <div>
      <PageHeader
        title="Dispatch"
        subtitle="Who is carrying each order. Live location appears only when a device is sharing it."
      />
      <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'flex-start', overflowX: 'auto' }}>
        {DISPATCH_COLUMNS.map((column) => {
          const jobs = byKey.get(column.key)?.jobs ?? []
          return (
            <section key={column.key} style={{ minWidth: '14rem', flex: '1 1 14rem' }}>
              <h2 style={{ fontSize: '0.95rem' }}>
                {column.label} <span style={{ color: 'var(--color-muted)' }}>{jobs.length}</span>
              </h2>
              {jobs.length === 0 ? (
                <p style={{ color: 'var(--color-muted)' }}>None</p>
              ) : (
                jobs.map((job) => (
                  <article key={job.id} style={{ border: '1px solid var(--color-border, #ddd)', borderRadius: '8px', padding: '0.75rem', marginBottom: '0.5rem' }}>
                    <Link href={`/b/${params.businessId}/dispatch/${job.id}`}>
                      <strong>{job.order_number}</strong>
                    </Link>
                    <p style={{ margin: '0.35rem 0' }}>
                      <StatusPill value={job.status} />
                    </p>
                    <p style={{ margin: 0 }}>{job.customer.name || 'Customer'}</p>
                    <p style={{ margin: '0.2rem 0 0', color: 'var(--color-muted)' }}>
                      {job.kind === 'pickup' ? 'Pickup' : 'Drop-off'} · {job.pickup.label || 'Shop'}
                      {job.assignee_name ? ` · ${job.assignee_name}` : ''}
                    </p>
                  </article>
                ))
              )}
            </section>
          )
        })}
      </div>
    </div>
  )
}
