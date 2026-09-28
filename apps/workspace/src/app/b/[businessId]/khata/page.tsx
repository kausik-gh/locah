import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry, businessHeaders } from '@/lib/api'
import { DataTable, FilterTabs, GateNotice, PageHeader, StatusPill } from '@/components/ui'
import { OpenAccount } from './OpenAccount'
import { day, owes, rupees, type AccountList } from './types'

export const dynamic = 'force-dynamic'

const TABS = [
  { value: '', label: 'Customers' },
  { value: 'due', label: 'Past due' },
  { value: 'suppliers', label: 'Suppliers' },
]

/**
 * Khata / credit book (Capability Universe §6.2 `ledger`, §14.5; §23 #3):
 * who owes the business and whom it owes — the udhaar notebook, kept by
 * LOCAH. Credit is given by billing on a customer's khata (at the counter or
 * on a bill); money received settles their oldest bills first.
 */
export default async function KhataPage({
  params,
  searchParams,
}: {
  params: { businessId: string }
  searchParams: { tab?: string; q?: string; due?: string }
}) {
  const token = await getAccessToken()
  if (!token) redirect('/login')
  const b = params.businessId
  const base = `/b/${b}/khata`
  const tab = searchParams.tab ?? (searchParams.due ? 'due' : '')
  const q = new URLSearchParams({ party: tab === 'suppliers' ? 'supplier' : 'customer' })
  if (tab === 'due') q.set('due', 'true')
  if (searchParams.q) q.set('q', searchParams.q)
  const [list, all, me] = await Promise.all([
    apiTry<{ data: AccountList }>(`/v1/platform/businesses/${b}/ledger/accounts?${q}`, token),
    apiTry<{ data: AccountList }>(`/v1/platform/businesses/${b}/ledger/accounts`, token),
    apiTry<{ data: { permissions: string[] } }>('/v1/me/context', token, businessHeaders(b)),
  ])
  const perms = new Set(me.ok ? me.data.data.permissions ?? [] : [])
  const header = (
    <PageHeader
      title="Khata"
      subtitle="Who owes you and whom you owe — credit given at the counter or on a bill, money received, limits and statements."
    />
  )
  if (!list.ok) {
    return (
      <div className="bos-page">
        {header}
        <GateNotice error={list.error} businessId={b} moduleLabel="Khata / credit book" />
      </div>
    )
  }
  const rows = list.data.data.accounts
  const totals = all.ok ? all.data.data.totals : list.data.data.totals
  const late = all.ok ? all.data.data.accounts.filter((a) => a.party_type === 'customer' && (a.ageing?.overdue ?? 0) > 0).length : 0

  return (
    <div className="bos-page">
      {header}
      <div className="bos-inv-summary" role="group" aria-label="Khata totals">
        <div>
          <span>Customers owe you</span>
          <strong>{rupees(totals.receivable)}</strong>
          <small>Across every customer&apos;s khata</small>
        </div>
        <div className={totals.overdue > 0 ? 'is-late' : ''}>
          <span>Past due</span>
          <strong>{rupees(totals.overdue)}</strong>
          <small>{late ? <Link href={`${base}?tab=due`}>{late} {late === 1 ? 'customer' : 'customers'} late</Link> : 'Nobody is late'}</small>
        </div>
        <div>
          <span>You owe suppliers</span>
          <strong>{rupees(totals.payable)}</strong>
          <small><Link href={`${base}?tab=suppliers`}>Supplier accounts</Link></small>
        </div>
      </div>

      {perms.has('ledger.manage') ? <OpenAccount businessId={b} party={tab === 'suppliers' ? 'supplier' : 'customer'} /> : null}

      <FilterTabs options={TABS} current={tab} hrefFor={(v) => (v ? `${base}?tab=${v}` : base)} />
      <form className="bos-inv-search" role="search">
        {tab ? <input type="hidden" name="tab" value={tab} /> : null}
        <label className="sr-only" htmlFor="khata-q">Search accounts</label>
        <input id="khata-q" name="q" defaultValue={searchParams.q ?? ''} placeholder="Name or phone" />
        <button type="submit" className="btn-ghost">Search</button>
      </form>

      <DataTable
        rows={rows}
        rowKey={(r) => r.id}
        empty={
          <p className="bos-hint" style={{ margin: 0 }}>
            {searchParams.q ? 'No account matches.' : tab === 'due' ? 'Nobody is past due.'
              : tab === 'suppliers' ? 'No supplier accounts yet. Open one to keep track of what you buy on credit.'
                : 'No khata yet. A customer’s khata opens the first time you bill them on credit — at the counter or on a bill.'}
          </p>
        }
        columns={[
          {
            key: 'name', header: tab === 'suppliers' ? 'Supplier' : 'Customer', render: (r) => (
              <Link href={`${base}/${r.id}`} className="bos-inv-num">
                <strong>{r.display_name}</strong>
                <span>{[r.phone, r.gstin].filter(Boolean).join(' · ') || (r.status === 'closed' ? 'Closed' : '')}</span>
              </Link>
            ),
          },
          {
            key: 'balance', header: 'Balance', align: 'num', render: (r) => (
              <span className={`bos-khata-bal${r.balance > 0 ? ' is-owed' : r.balance < 0 ? ' is-ahead' : ''}`}>{owes(r)}</span>
            ),
          },
          {
            key: 'due', header: 'Past due', align: 'num', render: (r) =>
              (r.ageing?.overdue ?? 0) > 0 ? <span className="bos-khata-late">{rupees(r.ageing!.overdue)}</span> : '—',
          },
          {
            key: 'limit', header: 'Limit', render: (r) =>
              r.credit_limit === null ? <span className="bos-hint">No limit</span> : (
                <span className="bos-khata-limit">
                  <span className="bos-khata-meter" aria-hidden>
                    <span style={{ width: `${Math.min(100, Math.max(0, r.limit_used_pct ?? 0))}%` }} className={r.over_limit ? 'is-over' : ''} />
                  </span>
                  <small>{rupees(r.credit_limit)}{r.over_limit ? ' · over' : ''}</small>
                </span>
              ),
          },
          {
            key: 'last', header: 'Last entry', render: (r) => (
              <span style={{ display: 'inline-flex', gap: '.35rem', alignItems: 'center', flexWrap: 'wrap' }}>
                {r.last_entry_at ? day(r.last_entry_at) : '—'}
                {r.over_limit ? <StatusPill value="over limit" tone="bad" /> : null}
              </span>
            ),
          },
        ]}
      />
    </div>
  )
}
