import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import { GateNotice, PageHeader } from '@/components/ui'
import { addSupplier } from '../supply-actions'

export const dynamic = 'force-dynamic'

type Home = { purchase_orders: Record<string, number>; bills_due: number }
type Incoming = { lines: { buyer_label: string; item_label: string; quantity: number }[]; totals: Record<string, number> }

export default async function BuyingPage({ params, searchParams }: {
  params: { businessId: string }
  searchParams?: { view?: string }
}) {
  const token = await getAccessToken()
  if (!token) redirect('/login')
  const b = params.businessId
  const view = searchParams?.view === 'incoming' ? 'incoming' : 'buying'
  const home = await apiTry<{ data: Home }>(`/v1/platform/businesses/${b}/buying`, token)
  if (!home.ok) {
    return <div className="bos-page"><PageHeader title="Buying" /><GateNotice error={home.error} businessId={b} moduleLabel="Buying" /></div>
  }
  const incoming = view === 'incoming'
    ? await apiTry<{ data: Incoming }>(`/v1/platform/businesses/${b}/buying/incoming`, token)
    : null
  const counts = home.data.data.purchase_orders
  const waiting = (counts.sent ?? 0) + (counts.acknowledged ?? 0) + (counts.countered ?? 0)
  const arriving = counts.dispatched ?? 0

  return (
    <div className="bos-page">
      <PageHeader title="Buying" subtitle="What to buy, what is with the supplier, and what has arrived." />
      <nav className="bos-stock-tabs" aria-label="Buying views">
        <Link href={`/b/${b}/buying`} aria-current={view === 'buying' ? 'page' : undefined}>Needs buying</Link>
        <Link href={`/b/${b}/buying?view=incoming`} aria-current={view === 'incoming' ? 'page' : undefined}>Incoming demand</Link>
      </nav>
      {view === 'buying' ? (
        <>
          <div className="bos-review-summary">
            <div><span>Needs approval</span><strong>{counts.draft ?? 0}</strong><small>Draft purchase orders</small></div>
            <div><span>Waiting on supplier</span><strong>{waiting}</strong><small>Sent, countered, or acknowledged</small></div>
            <div><span>Arriving</span><strong>{arriving}</strong><small>Dispatched, not fully received</small></div>
            <div><span>Bills due</span><strong>{home.data.data.bills_due}</strong><small>Open supplier bills</small></div>
          </div>
          <form action={addSupplier} className="bos-form">
            <h2>Supplier</h2>
            <input type="hidden" name="businessId" value={b} />
            <label>Name<input name="name" required maxLength={160} /></label>
            <label>Contact<input name="contact_name" maxLength={160} /></label>
            <label>Phone<input name="phone" maxLength={40} /></label>
            <label>Credit days<input name="credit_days" type="number" min={0} defaultValue={0} /></label>
            <button type="submit" className="btn-primary">Save supplier</button>
          </form>
        </>
      ) : (
        <section>
          <h2>What buyers have asked for</h2>
          {incoming?.ok ? (
            <>
              <ul>
                {Object.entries(incoming.data.data.totals).map(([item, qty]) => (
                  <li key={item}><strong>{item}</strong> — {qty} across buyers</li>
                ))}
              </ul>
              <table>
                <caption>Each buyer</caption>
                <thead><tr><th>Buyer</th><th>Item</th><th>Quantity</th></tr></thead>
                <tbody>
                  {incoming.data.data.lines.map((line, index) => (
                    <tr key={`${line.buyer_label}-${index}`}>
                      <td>{line.buyer_label}</td>
                      <td>{line.item_label}</td>
                      <td>{line.quantity}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {incoming.data.data.lines.length === 0 ? <p>No incoming demand yet.</p> : null}
            </>
          ) : <p>Incoming demand could not be loaded.</p>}
        </section>
      )}
    </div>
  )
}
