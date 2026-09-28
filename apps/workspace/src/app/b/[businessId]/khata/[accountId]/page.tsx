import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry, businessHeaders } from '@/lib/api'
import { DetailShell, GateNotice, PageHeader, StatusPill } from '@/components/ui'
import { AccountActions } from './AccountActions'
import { day, owes, rupees, type AccountDetail } from '../types'

export const dynamic = 'force-dynamic'

/**
 * One khata (Capability Universe §14.5): the running balance, how old what is
 * owed is (money received settles the oldest first), every entry with the
 * balance after it — entries are never edited, a mistake is a correction.
 */
export default async function AccountPage({ params }: { params: { businessId: string; accountId: string } }) {
  const token = await getAccessToken()
  if (!token) redirect('/login')
  const b = params.businessId
  const base = `/b/${b}/khata`
  const [res, me, wa] = await Promise.all([
    apiTry<{ data: AccountDetail }>(`/v1/platform/businesses/${b}/ledger/accounts/${params.accountId}`, token),
    apiTry<{ data: { permissions: string[] } }>('/v1/me/context', token, businessHeaders(b)),
    apiTry<{ data: { channel: { status: string } | null } }>(`/v1/platform/businesses/${b}/messaging/setup`, token),
  ])
  if (!res.ok) {
    return (
      <div className="bos-page">
        <PageHeader title="Khata" breadcrumb={<Link href={base}>← Khata</Link>} />
        <GateNotice error={res.error} businessId={b} moduleLabel="Khata / credit book" />
      </div>
    )
  }
  const a = res.data.data
  const perms = new Set(me.ok ? me.data.data.permissions ?? [] : [])
  const ageing = a.ageing
  const owed = Math.max(0, a.balance)
  const customer = a.party_type === 'customer'

  return (
    <div className="bos-page">
      <DetailShell
        breadcrumb={<Link href={`${base}${customer ? '' : '?tab=suppliers'}`}>← Khata</Link>}
        title={a.display_name}
        status={
          <span style={{ display: 'inline-flex', gap: '.4rem', flexWrap: 'wrap' }}>
            <StatusPill value={customer ? 'customer' : 'supplier'} tone="neutral" />
            {a.status === 'closed' ? <StatusPill value="closed" tone="neutral" /> : null}
            {(ageing?.overdue ?? 0) > 0 ? <StatusPill value="past due" tone="bad" /> : null}
            {a.over_limit ? <StatusPill value="over limit" tone="bad" /> : null}
          </span>
        }
        meta={[
          ['Balance', <strong key="b" className={`bos-khata-bal${a.balance > 0 ? ' is-owed' : a.balance < 0 ? ' is-ahead' : ''}`}>{owes(a)}</strong>],
          ...((ageing?.overdue ?? 0) > 0 ? [['Past due', rupees(ageing!.overdue)] as [string, string]] : []),
          ...(customer ? [['Limit', a.credit_limit === null ? 'No limit' : rupees(a.credit_limit)] as [string, string]] : []),
          ['Days to pay', a.credit_days === null ? '—' : `${a.credit_days} days`],
          ...(a.phone ? [['Phone', a.phone] as [string, string]] : []),
          ...(a.gstin ? [['GSTIN', a.gstin] as [string, string]] : []),
          ...(a.customer_contact_id && perms.has('customers.read')
            ? [['Customer', <Link key="c" href={`/b/${b}/customers/${a.customer_contact_id}`}>Open profile</Link>] as [string, React.ReactNode]] : []),
        ]}
        actions={<a className="btn btn-ghost" href={`${base}/${a.id}/statement`} target="_blank" rel="noreferrer">Statement PDF</a>}
      >
        <div className="bos-inv-layout">
          <div style={{ display: 'grid', gap: '1rem', minWidth: 0 }}>
            {ageing && owed > 0 ? (
              <section className="bos-card" aria-labelledby="age-h">
                <h2 id="age-h">How old is what {customer ? 'they owe' : 'you owe'}</h2>
                <div className="bos-khata-age" role="list">
                  {ageing.buckets.map((bk) => (
                    <div key={bk.key} role="listitem" className={bk.amount > 0 && bk.key !== 'current' ? 'is-late' : ''}>
                      <span>{bk.label}</span>
                      <strong>{rupees(bk.amount)}</strong>
                    </div>
                  ))}
                </div>
                <p className="bos-hint" style={{ marginBottom: 0 }}>
                  Money {customer ? 'received' : 'paid'} settles the oldest amounts first.
                  {ageing.oldest_due ? (ageing.overdue > 0 ? ` The oldest was due ${day(ageing.oldest_due)}.` : ` The next is due ${day(ageing.oldest_due)}.`) : ''}
                </p>
              </section>
            ) : null}

            <section className="bos-card" aria-labelledby="entries-h">
              <h2 id="entries-h">Entries</h2>
              {a.entries.length ? (
                <div className="bos-khata-table">
                  <table>
                    <thead>
                      <tr><th scope="col">Date</th><th scope="col">Details</th><th scope="col" className="num">{customer ? 'Owed' : 'Owe'} +</th><th scope="col" className="num">Paid −</th><th scope="col" className="num">Balance</th></tr>
                    </thead>
                    <tbody>
                      {a.entries.map((e) => (
                        <tr key={e.id}>
                          <td>{day(e.entry_date)}</td>
                          <td>
                            <strong>{e.kind_label}</strong>
                            {e.document_id && e.document_number ? <> · <Link href={`/b/${b}/invoices/${e.document_id}`}>{e.document_number}</Link></> : null}
                            {e.method_label ? ` · ${e.method_label}` : ''}
                            {e.reference && e.reference !== e.document_number ? <small>Ref {e.reference}</small> : null}
                            {e.note ? <small>{e.note}</small> : null}
                            {e.due_date && e.amount > 0 ? <small>Due {day(e.due_date)}</small> : null}
                            {e.approved_over_limit ? <small className="bos-khata-late">Allowed over the limit</small> : null}
                          </td>
                          <td className="num">{e.amount > 0 ? rupees(e.amount) : ''}</td>
                          <td className="num">{e.amount < 0 ? rupees(-e.amount) : ''}</td>
                          <td className="num">{rupees(e.balance_after)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : <p className="bos-empty">No entries yet.</p>}
            </section>
          </div>
          <AccountActions businessId={b} account={a} canRecord={perms.has('ledger.record')} canManage={perms.has('ledger.manage')}
            whatsapp={perms.has('messaging.reply') && wa.ok && wa.data.data.channel?.status === 'connected'} />
        </div>
      </DetailShell>
    </div>
  )
}
