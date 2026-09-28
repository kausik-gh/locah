import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import { GateNotice, PageHeader } from '@/components/ui'
import { CountSheet, type CountLine } from '../../StockWork'
import type { StockProfile } from '../../types'

export const dynamic = 'force-dynamic'

type Count = { id: string; label: string; status: string; lines: CountLine[]; counted: number; variances: number; decision_note: string | null }

const WORDS: Record<string, string> = {
  open: 'Count what is on the shelf. The system figure stays hidden until you submit.',
  submitted: 'Submitted — stock changes only when a manager approves the differences.',
  approved: 'Approved: the differences were applied to stock.',
  cancelled: 'Sent back for a recount. Start a new count.',
}

export default async function CountPage({ params }: { params: { businessId: string; countId: string } }) {
  const token = await getAccessToken()
  if (!token) redirect('/login')
  const b = params.businessId
  const [res, profRes] = await Promise.all([
    apiTry<{ data: Count }>(`/v1/platform/businesses/${b}/stock/counts/${params.countId}`, token),
    apiTry<{ data: StockProfile }>(`/v1/platform/businesses/${b}/stock/profile`, token),
  ])
  if (!res.ok) return <div className="bos-page"><PageHeader title="Stock count" /><GateNotice error={res.error} businessId={b} moduleLabel="Stock" /></div>
  const c = res.data.data
  const can = profRes.ok ? profRes.data.data.can : { adjust: false, approve: false, cost: false, setup: false }
  return (
    <div className="bos-page bos-stock">
      <p><Link href={`/b/${b}/inventory?view=counts`}>← Counts</Link></p>
      <PageHeader title={c.label} subtitle={WORDS[c.status] ?? ''} />
      <div className="bos-review-summary">
        <div><span>Counted</span><strong>{c.counted} of {c.lines.length}</strong><small>Items on this count</small></div>
        {c.status !== 'open' || can.approve ? <div><span>Differences</span><strong>{c.variances}</strong><small>Against the figure when the count began</small></div> : null}
      </div>
      {c.decision_note ? <p className="bos-hint">Note: {c.decision_note}</p> : null}
      <CountSheet businessId={b} countId={c.id} status={c.status} lines={c.lines} canApprove={can.approve} canCount={can.adjust} />
    </div>
  )
}
