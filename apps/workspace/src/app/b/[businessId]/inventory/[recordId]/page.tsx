import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import { GateNotice, PageHeader, StatusPill } from '@/components/ui'
import { ItemSetup, ReorderEditor, WastagePanel, WriteOffButton } from '../StockWork'
import { rupees, type Batch, type StockItem, type StockProfile, type StockRow } from '../types'

export const dynamic = 'force-dynamic'

type Detail = StockRow & {
  batches: Batch[]
  serials: { serial: string; status: string; received_at: string }[]
  movements: { type: string; delta: number; after: number; delta_text: string; reason: string | null; reason_code: string | null; at: string; value_delta_paise?: number }[]
}

const MOVE: Record<string, string> = {
  opening_stock: 'Opening stock', receipt: 'Received', deduction: 'Sold', reversal: 'Returned / cancelled',
  adjustment: 'Adjusted', wastage: 'Wasted', count_variance: 'Count difference', conversion_out: 'Cut',
  conversion_in: 'Cut from', reservation: 'Held for an order',
}

export default async function StockLinePage({ params }: { params: { businessId: string; recordId: string } }) {
  const token = await getAccessToken()
  if (!token) redirect('/login')
  const b = params.businessId
  const api = `/v1/platform/businesses/${b}/stock`
  const [res, profRes, itemsRes] = await Promise.all([
    apiTry<{ data: Detail }>(`${api}/records/${params.recordId}`, token),
    apiTry<{ data: StockProfile }>(`${api}/profile`, token),
    apiTry<{ data: StockItem[] }>(`${api}/items`, token),
  ])
  if (!res.ok || !profRes.ok) {
    return <div className="bos-page"><PageHeader title="Stock line" /><GateNotice error={!res.ok ? res.error : (profRes as { ok: false; error: never }).error} businessId={b} moduleLabel="Stock" /></div>
  }
  const d = res.data.data
  const prof = profRes.data.data
  const item = itemsRes.ok ? itemsRes.data.data.find((i) => i.id === d.offering_id) : undefined
  const at = (s: string) => new Date(s).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })
  const day = (s: string) => new Date(`${s}T00:00:00`).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
  return (
    <div className="bos-page bos-stock">
      <p><Link href={`/b/${b}/inventory`}>← Stock</Link></p>
      <PageHeader title={d.title} subtitle={`${d.on_hand_text} on hand${d.quantity_reserved ? ` · some held for orders` : ''}`} />
      <div className="bos-review-summary">
        <div><span>On hand</span><strong>{d.on_hand_text}</strong><small><StatusPill value={d.stock_status} /></small></div>
        {prof.can.cost && d.value_paise !== undefined ? <div><span>Value</span><strong>{rupees(d.value_paise)}</strong><small>At average cost</small></div> : null}
        {d.batch_tracked ? <div><span>Batches</span><strong>{d.batches.filter((x) => x.status === 'active').length}</strong><small>Earliest expiry sells first</small></div> : null}
        {d.serial_tracked ? <div><span>Units by serial</span><strong>{d.serials.length}</strong><small>In stock here</small></div> : null}
      </div>
      {d.batch_tracked ? <section className="bos-section" aria-labelledby="b-h"><h2 id="b-h">Batches</h2>
        <table className="bos-stock-table"><thead><tr><th scope="col">Batch</th><th scope="col">Expiry</th><th scope="col">Left</th><th scope="col">Received</th><th scope="col">State</th><th scope="col"><span className="sr-only">Action</span></th></tr></thead>
          <tbody>{d.batches.map((x) => <tr key={x.id}><th scope="row">{x.batch_code}</th><td>{x.expires_on ? day(x.expires_on) : '—'}</td><td>{x.quantity_text}</td>
            <td>{day(x.received_on)}</td><td>{x.status === 'active' ? 'In stock' : x.status === 'depleted' ? 'Sold out' : 'Written off'}</td>
            <td>{x.status === 'active' && prof.can.adjust ? <WriteOffButton businessId={b} batchId={x.id} label="Write off" /> : null}</td></tr>)}</tbody></table>
        {!d.batches.length ? <p className="bos-hint">No batches received yet.</p> : null}</section> : null}
      {d.serial_tracked ? <section className="bos-section" aria-labelledby="s-h"><h2 id="s-h">Serial numbers in stock</h2>
        <ul className="bos-pills">{d.serials.map((s) => <li key={s.serial} className="bos-pill">{s.serial}</li>)}</ul>
        {!d.serials.length ? <p className="bos-hint">No units in stock.</p> : null}</section> : null}
      {prof.can.adjust ? <div className="bos-stock-work">
        <section className="bos-card"><h2>Reorder level</h2><ReorderEditor businessId={b} row={d} /></section>
        <section className="bos-card"><h2>Record wastage</h2><WastagePanel businessId={b} rows={[d]} reasons={prof.wastage_reasons} title="Record wastage" /></section>
      </div> : null}
      {prof.can.setup && item ? <section className="bos-card bos-section"><h2>How {d.title} keeps stock</h2><ItemSetup businessId={b} item={item} /></section> : null}
      <section className="bos-section" aria-labelledby="m-h"><h2 id="m-h">History</h2>
        <ol className="bos-log">{d.movements.map((m, i) => <li key={`${m.at}-${i}`}><strong>{MOVE[m.type] ?? m.type}</strong> {m.delta > 0 ? '+' : m.delta < 0 ? '−' : ''}{m.delta_text}
          {m.reason ? <span className="bos-hint"> · {m.reason}</span> : null}{m.value_delta_paise ? <span className="bos-hint"> · {m.value_delta_paise > 0 ? '+' : '−'}{rupees(Math.abs(m.value_delta_paise))}</span> : null}
          <span className="bos-hint"> · {at(m.at)}</span></li>)}</ol>
        {!d.movements.length ? <p className="bos-hint">No movements yet.</p> : null}</section>
    </div>
  )
}
