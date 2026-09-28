import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import { FilterTabs, GateNotice, PageHeader } from '@/components/ui'

export const dynamic = 'force-dynamic'

type Table = {
  columns: { key: string; label: string }[]
  rows: Record<string, string | number>[]
  totals: Record<string, number> | null
  note: string | null
}
type Report = Table & { sections?: Record<string, Table>; label: string; from: string; to: string }

const KINDS = [
  { value: 'sales_register', label: 'Sales register' },
  { value: 'hsn_summary', label: 'HSN / SAC summary' },
  { value: 'tax_by_rate', label: 'Tax by rate' },
  { value: 'gstr1', label: 'GSTR-1 worksheet' },
  { value: 'documents', label: 'Documents issued' },
]
const SECTION_LABEL: Record<string, string> = {
  b2b: 'B2B — to registered businesses', b2c: 'B2C — to consumers', b2c_inter_state: 'B2C inter-state invoices',
  notes: 'Credit & debit notes', hsn: 'HSN / SAC summary', documents: 'Documents issued',
}

function iso(d: Date) { return d.toISOString().slice(0, 10) }

function presets(): { label: string; from: string; to: string }[] {
  const now = new Date()
  const y = now.getFullYear()
  const m = now.getMonth()
  const fyStart = m >= 3 ? y : y - 1
  return [
    { label: 'This month', from: iso(new Date(Date.UTC(y, m, 1))), to: iso(now) },
    { label: 'Last month', from: iso(new Date(Date.UTC(y, m - 1, 1))), to: iso(new Date(Date.UTC(y, m, 0))) },
    { label: 'This financial year', from: `${fyStart}-04-01`, to: iso(now) },
  ]
}

function money(v: string | number, key: string): string {
  if (typeof v !== 'number' || ['quantity', 'total', 'cancelled', 'net'].includes(key)) return String(v)
  return new Intl.NumberFormat('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(v)
}

function Grid({ t }: { t: Table }) {
  return (
    <div className="ws-tablewrap bos-inv-report">
      <table>
        <thead><tr>{t.columns.map((c) => <th key={c.key}>{c.label}</th>)}</tr></thead>
        <tbody>
          {t.rows.map((r, i) => (
            <tr key={i}>{t.columns.map((c) => <td key={c.key} data-num={typeof r[c.key] === 'number' || undefined}>{money(r[c.key] ?? '', c.key)}</td>)}</tr>
          ))}
          {!t.rows.length ? <tr><td colSpan={t.columns.length} className="bos-hint">Nothing in this period.</td></tr> : null}
        </tbody>
        {t.totals ? (
          <tfoot><tr>{t.columns.map((c, i) => <td key={c.key} data-num={i > 0 || undefined}>{i === 0 ? 'Total' : t.totals?.[c.key] !== undefined ? money(t.totals[c.key], c.key) : ''}</td>)}</tr></tfoot>
        ) : null}
      </table>
    </div>
  )
}

/**
 * For the CA (Capability Universe §14.4): sales register, HSN summary,
 * tax-by-rate summary and a GSTR-1 worksheet, each downloadable as CSV.
 * Figures are the ones stored on the bills when they were issued.
 */
export default async function ReportsPage({ params, searchParams }: {
  params: { businessId: string }
  searchParams: { kind?: string; from?: string; to?: string }
}) {
  const token = await getAccessToken()
  if (!token) redirect('/login')
  const b = params.businessId
  const kind = KINDS.some((k) => k.value === searchParams.kind) ? (searchParams.kind as string) : 'sales_register'
  const range = new URLSearchParams()
  if (searchParams.from) range.set('from', searchParams.from)
  if (searchParams.to) range.set('to', searchParams.to)
  const res = await apiTry<{ data: Report }>(`/v1/platform/businesses/${b}/invoicing/reports/${kind}?${range}`, token)
  const header = (
    <PageHeader
      title="Reports for your CA"
      breadcrumb={<Link href={`/b/${b}/invoices`}>← Bills & invoices</Link>}
      subtitle="Everything your accountant asks for at filing time, from the bills exactly as issued."
    />
  )
  if (!res.ok) return <div className="bos-page">{header}<GateNotice error={res.error} businessId={b} moduleLabel="Reports for your CA" /></div>
  const r = res.data.data
  const qs = (k: string, from = r.from, to = r.to) => `/b/${b}/invoices/reports?kind=${k}&from=${from}&to=${to}`
  return (
    <div className="bos-page">
      {header}
      <FilterTabs options={KINDS} current={kind} hrefFor={(v) => qs(v)} />
      <form className="bos-inv-period" aria-label="Period">
        <input type="hidden" name="kind" value={kind} />
        <label><span className="bos-label">From</span><input type="date" name="from" defaultValue={r.from} /></label>
        <label><span className="bos-label">To</span><input type="date" name="to" defaultValue={r.to} /></label>
        <button type="submit" className="btn-ghost">Show</button>
        <span className="bos-inv-presets">
          {presets().map((p) => <Link key={p.label} href={qs(kind, p.from, p.to)}>{p.label}</Link>)}
        </span>
        <a className="btn" href={`/b/${b}/invoices/reports/csv?kind=${kind}&from=${r.from}&to=${r.to}`}>Download CSV</a>
      </form>
      {r.note ? <p className="bos-hint">{r.note}</p> : null}
      {r.sections ? (
        Object.entries(r.sections).map(([k, t]) => (
          <section key={k} className="bos-section">
            <h2 className="bos-section__title">{SECTION_LABEL[k] ?? k} <span>{t.rows.length}</span></h2>
            {t.note ? <p className="bos-hint">{t.note}</p> : null}
            <Grid t={t} />
          </section>
        ))
      ) : (
        <Grid t={r} />
      )}
    </div>
  )
}
