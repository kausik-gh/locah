import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import { Card, DataTable, FilterTabs, GateNotice, PageHeader, StatusPill } from '@/components/ui'
import { PAYMENT_LABEL, day, rupees, type Bill, type Setup } from './types'

export const dynamic = 'force-dynamic'

const TABS = [
  { value: '', label: 'All' },
  { value: 'unpaid', label: 'Unpaid' },
  { value: 'overdue', label: 'Overdue' },
  { value: 'draft', label: 'Drafts' },
  { value: 'notes', label: 'Credit & debit notes' },
  { value: 'cancelled', label: 'Cancelled' },
]

function query(tab: string, q: string | undefined): string {
  const p = new URLSearchParams()
  if (tab === 'unpaid' || tab === 'overdue') p.set('payment', tab)
  if (tab === 'draft' || tab === 'cancelled') p.set('status', tab)
  if (tab === 'notes') p.set('kind', 'notes')
  if (q) p.set('q', q)
  return p.toString()
}

/**
 * Bills & invoices (Capability Universe §14): one list for every bill the
 * business issues — counter, website, WhatsApp and business customers —
 * numbered per GSTIN × financial year × register, cancelled ones kept.
 */
export default async function InvoicesPage({
  params,
  searchParams,
}: {
  params: { businessId: string }
  searchParams: { tab?: string; q?: string }
}) {
  const token = await getAccessToken()
  if (!token) redirect('/login')
  const b = params.businessId
  const base = `/b/${b}/invoices`
  const tab = searchParams.tab ?? ''
  const [list, setup, unpaid] = await Promise.all([
    apiTry<{ data: Bill[] }>(`/v1/platform/businesses/${b}/invoices?${query(tab, searchParams.q)}`, token),
    apiTry<{ data: Setup }>(`/v1/platform/businesses/${b}/invoicing/setup`, token),
    apiTry<{ data: Bill[] }>(`/v1/platform/businesses/${b}/invoices?payment=unpaid&limit=500`, token),
  ])
  const header = (
    <PageHeader
      title="Bills & invoices"
      subtitle="Every bill you issue — at the counter, for website and WhatsApp orders, and for business customers — correctly numbered, with its PDF."
      actions={
        <>
          <Link className="btn" href={`${base}/new`}>New bill</Link>
          <Link className="btn btn-ghost" href={`${base}/tax-rates`}>Tax rates</Link>
        </>
      }
    />
  )
  if (!list.ok) {
    return (
      <div className="bos-page">
        {header}
        <GateNotice error={list.error} businessId={b} moduleLabel="Invoices & GST" />
      </div>
    )
  }
  const bills = list.data.data
  const open = unpaid.ok ? unpaid.data.data : []
  const outstanding = open.reduce((s, x) => s + x.outstanding, 0)
  const overdue = open.filter((x) => x.overdue)

  return (
    <div className="bos-page">
      {header}
      {setup.ok && !setup.data.data.ready ? (
        <Card tone="urgent" style={{ marginBottom: '1.2rem' }}>
          <h2 style={{ marginBottom: '.35rem' }}>Finish setting up billing</h2>
          <ul className="bos-hint" style={{ margin: '0 0 .7rem', paddingLeft: '1.1rem' }}>
            {setup.data.data.needs.map((n) => <li key={n}>{n}</li>)}
          </ul>
          <Link className="btn" href={`/b/${b}/settings/invoicing`}>Open Tax & invoicing</Link>
        </Card>
      ) : null}

      <div className="bos-inv-summary" role="group" aria-label="Money owed to you">
        <div>
          <span>Outstanding</span>
          <strong>{rupees(outstanding)}</strong>
          <small>{open.length} {open.length === 1 ? 'bill' : 'bills'} unpaid</small>
        </div>
        <div className={overdue.length ? 'is-late' : ''}>
          <span>Overdue</span>
          <strong>{rupees(overdue.reduce((s, x) => s + x.outstanding, 0))}</strong>
          <small>{overdue.length ? <Link href={`${base}?tab=overdue`}>{overdue.length} past their due date</Link> : 'Nothing late'}</small>
        </div>
      </div>

      <FilterTabs options={TABS} current={tab} hrefFor={(v) => (v ? `${base}?tab=${v}` : base)} />
      <form className="bos-inv-search" role="search">
        {tab ? <input type="hidden" name="tab" value={tab} /> : null}
        <label className="sr-only" htmlFor="bill-q">Search bills</label>
        <input id="bill-q" name="q" defaultValue={searchParams.q ?? ''} placeholder="Number, customer, GSTIN or order" />
        <button type="submit" className="btn-ghost">Search</button>
      </form>

      <DataTable
        rows={bills}
        rowKey={(r) => r.id}
        empty={
          <p className="bos-hint" style={{ margin: 0 }}>
            {tab || searchParams.q ? 'No bills match.' : 'No bills yet. Bills appear here as orders are billed, or '}
            {!tab && !searchParams.q ? <Link href={`${base}/new`}>raise one yourself</Link> : null}
          </p>
        }
        columns={[
          {
            key: 'number', header: 'Bill', render: (r) => (
              <Link href={`${base}/${r.id}`} className="bos-inv-num">
                <strong>{r.number ?? 'Draft'}</strong>
                <span>{r.kind_label}{r.order_number ? ` · ${r.order_number}` : ''}</span>
              </Link>
            ),
          },
          { key: 'date', header: 'Date', render: (r) => (r.issue_date ? day(r.issue_date) : '—') },
          {
            key: 'buyer', header: 'Customer', render: (r) => (
              <span className="bos-inv-buyer">
                {r.buyer?.name ?? 'Walk-in customer'}
                {r.buyer?.gstin ? <small>{r.buyer.gstin}</small> : null}
              </span>
            ),
          },
          { key: 'amount', header: 'Amount', align: 'num', render: (r) => rupees(r.doc_kind === 'credit_note' ? -r.amount_due : r.amount_due) },
          {
            key: 'state', header: 'Status', render: (r) => (
              <span style={{ display: 'inline-flex', gap: '.35rem', flexWrap: 'wrap' }}>
                {r.status !== 'issued' ? <StatusPill value={r.status} /> : null}
                {r.status === 'issued' && r.overdue ? <StatusPill value="overdue" /> : null}
                {r.status === 'issued' && PAYMENT_LABEL[r.payment_status] && !r.overdue ? (
                  <StatusPill value={PAYMENT_LABEL[r.payment_status]} tone={r.payment_status === 'paid' ? 'good' : 'warn'} />
                ) : null}
              </span>
            ),
          },
        ]}
      />
    </div>
  )
}
