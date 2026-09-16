import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import { GateNotice, PageHeader } from '@/components/ModuleState'
import { updateJobStatus } from '../actions'

export const dynamic = 'force-dynamic'

export default async function FulfilmentJobDetailPage({
  params,
}: {
  params: { businessId: string; jobId: string }
}) {
  const token = await getAccessToken()
  if (!token) redirect('/login')
  const res = await apiTry<{
    data: {
      id: string
      order_id: string
      mode: string
      status: string
      delivery_charge: number
      currency: string
      delivery_address?: Record<string, unknown> | null
      outcome_reason?: string | null
      tracking_token: string
    }
  }>(`/v1/b/${params.businessId}/fulfilment/jobs/${params.jobId}`, token)
  if (!res.ok) {
    return (
      <div>
        <Link href={`/b/${params.businessId}/fulfilment`}>← Fulfilment</Link>
        <PageHeader title="Fulfilment job" />
        <GateNotice error={res.error} businessId={params.businessId} moduleLabel="Fulfilment" />
      </div>
    )
  }
  const job = res.data.data
  const transitions: Record<string, string[]> = {
    pending: ['preparing', 'cancelled', 'failed'],
    preparing: ['ready', 'cancelled', 'failed'],
    ready:
      job.mode === 'delivery'
        ? ['out_for_delivery', 'cancelled', 'failed']
        : ['delivered', 'cancelled', 'failed'],
    out_for_delivery: ['delivered', 'failed', 'cancelled'],
  }
  const next = transitions[job.status] || []

  return (
    <div>
      <Link href={`/b/${params.businessId}/fulfilment`}>← Fulfilment</Link>
      <h1 style={{ fontSize: '1.75rem', marginTop: '0.75rem' }}>Job {job.id.slice(0, 8)}</h1>
      <p>
        Mode: <strong>{job.mode}</strong> · Status: <strong>{job.status}</strong>
      </p>
      <p>
        Order:{' '}
        <Link href={`/b/${params.businessId}/orders/${job.order_id}`}>{job.order_id}</Link>
      </p>
      <p>
        Charge: {job.currency} {job.delivery_charge}
      </p>
      {job.delivery_address ? (
        <pre style={{ background: 'var(--color-surface)', padding: '0.75rem' }}>
          {JSON.stringify(job.delivery_address, null, 2)}
        </pre>
      ) : null}
      {job.outcome_reason ? <p>Reason: {job.outcome_reason}</p> : null}
      <section style={{ marginTop: '1.25rem', display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
        {next.map((status) => (
          <form key={status} action={updateJobStatus}>
            <input type="hidden" name="businessId" value={params.businessId} />
            <input type="hidden" name="jobId" value={params.jobId} />
            <input type="hidden" name="status" value={status} />
            {status === 'failed' || status === 'cancelled' ? (
              <input type="hidden" name="reason" value={`${status} from Workspace`} />
            ) : null}
            <button type="submit">{status}</button>
          </form>
        ))}
      </section>
    </div>
  )
}
