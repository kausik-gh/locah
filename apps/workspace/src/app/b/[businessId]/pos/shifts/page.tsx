import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import { DataTable, GateNotice, PageHeader, StatusPill } from '@/components/ui'

export const dynamic = 'force-dynamic'

type Row = {
  id: string; register: string; location_name: string; opened_by_name: string | null; status: string; opened_at: string
  closed_at: string | null; opening_cash: number; expected_cash: number | null; counted_cash: number | null; variance: number | null
  summary: { bills: number; voided: number; returns: number; sales_total: number; cash_sales: number; upi: number; upi_to_verify: number; card: number; expected_cash: number }
}

const money = (v: number | null | undefined) => (v === null || v === undefined ? '—' : new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', minimumFractionDigits: 2 }).format(v))
const when = (v: string | null) => (v ? new Date(v).toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' }) : '—')

/** Counter shifts (Capability Universe §14.5): what each drawer should hold, what was counted, the difference. */
export default async function ShiftsPage({ params }: { params: { businessId: string } }) {
  const token = await getAccessToken()
  if (!token) redirect('/login')
  const b = params.businessId
  const res = await apiTry<{ data: Row[] }>(`/v1/platform/businesses/${b}/pos/shifts`, token)
  const header = (
    <PageHeader title="Counter shifts" subtitle="Each cash drawer shift: sales by tender, what the drawer should hold and what was counted."
      actions={<a className="btn" href={`/pos/${b}`}>Open the counter</a>} />
  )
  if (!res.ok) return <div className="bos-page">{header}<GateNotice error={res.error} businessId={b} moduleLabel="Counter billing" /></div>
  return (
    <div className="bos-page">
      {header}
      <DataTable
        rows={res.data.data}
        rowKey={(r) => r.id}
        empty={<p className="bos-hint" style={{ margin: 0 }}>No shifts yet. Open the counter to start one.</p>}
        columns={[
          { key: 'reg', header: 'Register', render: (r) => (<span className="bos-inv-buyer">{r.register}<small>{r.location_name} · {r.opened_by_name ?? ''}</small></span>) },
          { key: 'when', header: 'Opened → closed', render: (r) => `${when(r.opened_at)} → ${r.status === 'open' ? 'open' : when(r.closed_at)}` },
          { key: 'sales', header: 'Sales', align: 'num', render: (r) => (<span className="bos-inv-buyer">{money(r.summary.sales_total)}<small>{r.summary.bills} bills{r.summary.voided ? ` · ${r.summary.voided} voided` : ''}{r.summary.returns ? ` · ${r.summary.returns} returns` : ''}</small></span>) },
          { key: 'tenders', header: 'Cash · UPI · Card', align: 'num', render: (r) => (<span className="bos-inv-buyer">{money(r.summary.cash_sales)} · {money(r.summary.upi)} · {money(r.summary.card)}{r.summary.upi_to_verify ? <small>{money(r.summary.upi_to_verify)} UPI to verify</small> : null}</span>) },
          { key: 'expected', header: 'Drawer expected', align: 'num', render: (r) => money(r.status === 'open' ? r.summary.expected_cash : r.expected_cash) },
          { key: 'counted', header: 'Counted', align: 'num', render: (r) => money(r.counted_cash) },
          { key: 'var', header: 'Difference', render: (r) => (r.status === 'open' ? <StatusPill value="open" tone="info" /> : r.variance === 0 ? <StatusPill value="Balanced" tone="good" /> : <StatusPill value={`${(r.variance ?? 0) < 0 ? 'Short' : 'Over'} ${money(Math.abs(r.variance ?? 0))}`} tone="bad" />) },
        ]}
      />
      <p className="bos-hint" style={{ marginTop: '1rem' }}>UPI taken without confirmation is checked in <Link href={`/b/${b}/settings/counter`}>Settings → Counter billing</Link>.</p>
    </div>
  )
}
