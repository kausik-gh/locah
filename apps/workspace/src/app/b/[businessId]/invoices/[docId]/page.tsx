import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import { DetailShell, GateNotice, PageHeader, StatusPill } from '@/components/ui'
import { BillActions } from './BillActions'
import { PAYMENT_LABEL, day, rupees, type Bill } from '../types'

export const dynamic = 'force-dynamic'

/**
 * One bill, shown the way it prints (Capability Universe §14.4): a tax
 * invoice carries GSTINs, HSN/SAC, taxable value, CGST + SGST or IGST and the
 * place of supply; a bill of supply and a bill carry no tax line at all.
 */
export default async function BillPage({ params }: { params: { businessId: string; docId: string } }) {
  const token = await getAccessToken()
  if (!token) redirect('/login')
  const b = params.businessId
  const base = `/b/${b}/invoices`
  const res = await apiTry<{ data: Bill; meta: { note_reasons: Record<string, Record<string, string>>; payment_methods: Record<string, string> } }>(
    `/v1/platform/businesses/${b}/invoices/${params.docId}`, token)
  if (!res.ok) {
    return (
      <div className="bos-page">
        <PageHeader title="Bill" breadcrumb={<Link href={base}>← Bills & invoices</Link>} />
        <GateNotice error={res.error} businessId={b} moduleLabel="Invoices & GST" />
      </div>
    )
  }
  const d = res.data.data
  const gst = d.seller.scheme === 'regular' && d.doc_kind !== 'bill' && d.doc_kind !== 'bill_of_supply'
  const intra = d.intra_state !== false
  const lines = d.lines ?? []
  const pdf = (layout: string, label: string) => (
    <a key={layout} className="btn btn-ghost" href={`${base}/${d.id}/pdf?layout=${layout}`} target="_blank" rel="noreferrer">{label}</a>
  )
  const title = d.number ? `${d.kind_label} ${d.number}` : `Draft ${d.kind_label.toLowerCase()}`

  return (
    <div className="bos-page">
      <DetailShell
        breadcrumb={<Link href={base}>← Bills & invoices</Link>}
        title={title}
        status={
          <span style={{ display: 'inline-flex', gap: '.4rem', flexWrap: 'wrap' }}>
            <StatusPill value={d.status} />
            {d.status === 'issued' && d.overdue ? <StatusPill value="overdue" /> : null}
            {d.on_account ? <StatusPill value="on khata" tone="info" /> : null}
            {d.status === 'issued' && PAYMENT_LABEL[d.payment_status] ? (
              <StatusPill value={PAYMENT_LABEL[d.payment_status]} tone={d.payment_status === 'paid' ? 'good' : 'warn'} />
            ) : null}
          </span>
        }
        meta={[
          ['Date', day(d.issue_date)],
          ...(d.due_date ? [['Due', day(d.due_date)] as [string, string]] : []),
          ['Amount', rupees(d.amount_due)],
          ...(d.status === 'issued' && d.payment_status !== 'not_applicable'
            ? [['Outstanding', rupees(d.outstanding)] as [string, string]] : []),
          ...(d.order_number && d.order_id ? [['Order', <Link key="o" href={`/b/${b}/orders/${d.order_id}`}>{d.order_number}</Link>] as [string, React.ReactNode]] : []),
        ]}
        actions={<>{pdf('a4', 'PDF (A4)')}{pdf('thermal_80', '80 mm')}{pdf('thermal_58', '58 mm')}</>}
      >
        {d.status === 'cancelled' ? (
          <p className="bos-inv-cancelled" role="status">Cancelled{d.cancel_reason ? ` — ${d.cancel_reason}` : ''}. The number stays in the series.</p>
        ) : null}

        <div className="bos-inv-layout">
          <article className="bos-bill" aria-label={title}>
            <header className="bos-bill__head">
              <div>
                <p className="bos-bill__seller">{d.seller.trade_name || d.seller.legal_name}</p>
                {d.seller.trade_name && d.seller.legal_name && d.seller.trade_name !== d.seller.legal_name ? <p>{d.seller.legal_name}</p> : null}
                {d.seller.address ? <p>{d.seller.address}</p> : null}
                {d.seller.gstin && d.seller.scheme !== 'unregistered' ? <p>GSTIN {d.seller.gstin}</p> : null}
              </div>
              <div className="bos-bill__kind">
                <strong>{d.kind_label}</strong>
                <span>{d.number ?? 'Not numbered yet'}</span>
                <span>{day(d.issue_date)}</span>
              </div>
            </header>
            <div className="bos-bill__parties">
              <div>
                <span className="bos-bill__label">{d.doc_kind.endsWith('note') ? 'Customer' : 'Bill to'}</span>
                <p>{d.buyer.name ?? 'Walk-in customer'}</p>
                {d.buyer.address ? <p>{d.buyer.address}</p> : null}
                {d.buyer.gstin && d.seller.scheme !== 'unregistered' ? <p>GSTIN {d.buyer.gstin}</p> : null}
              </div>
              {d.seller.scheme !== 'unregistered' ? (
                <dl>
                  {d.place_of_supply ? (<><dt>Place of supply</dt><dd>{d.place_of_supply_label}</dd></>) : null}
                  {d.doc_kind === 'tax_invoice' ? (<><dt>Reverse charge</dt><dd>{d.reverse_charge ? 'Yes' : 'No'}</dd></>) : null}
                  {(d.related ?? []).length && d.doc_kind.endsWith('note') ? (
                    <><dt>Against</dt><dd><Link href={`${base}/${d.related![0].id}`}>{d.related![0].kind_label} {d.related![0].number}</Link></dd></>
                  ) : null}
                </dl>
              ) : null}
            </div>
            <div className="ws-tablewrap">
              <table className="bos-bill__lines">
                <thead>
                  <tr>
                    <th>Item</th>
                    {gst ? <th>HSN/SAC</th> : null}
                    <th data-num>Qty</th>
                    <th data-num>Rate</th>
                    {gst ? <th data-num>Taxable</th> : null}
                    {gst ? <th data-num>GST %</th> : null}
                    {gst && intra ? <><th data-num>CGST</th><th data-num>SGST</th></> : null}
                    {gst && !intra ? <th data-num>IGST</th> : null}
                    <th data-num>Amount</th>
                  </tr>
                </thead>
                <tbody>
                  {lines.map((l) => (
                    <tr key={l.id}>
                      <td>{l.title}{l.discount > 0 ? <small className="bos-bill__disc">Discount {rupees(l.discount)}</small> : null}</td>
                      {gst ? <td>{l.hsn_sac ?? '—'}</td> : null}
                      <td data-num>{l.quantity}{l.unit_label ? ` ${l.unit_label}` : ''}</td>
                      <td data-num>{rupees(l.unit_price)}</td>
                      {gst ? <td data-num>{rupees(l.taxable_value)}</td> : null}
                      {gst ? <td data-num>{l.tax_rate === null ? 'Not set' : `${l.tax_rate}%`}</td> : null}
                      {gst && intra ? <><td data-num>{rupees(l.cgst)}</td><td data-num>{rupees(l.sgst)}</td></> : null}
                      {gst && !intra ? <td data-num>{rupees(l.igst)}</td> : null}
                      <td data-num>{rupees(l.line_total)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <dl className="bos-bill__totals">
              {gst ? (<><dt>Taxable value</dt><dd>{rupees(d.taxable_total)}</dd></>) : null}
              {gst && intra ? (<><dt>CGST{d.reverse_charge ? ' (payable by recipient)' : ''}</dt><dd>{rupees(d.cgst_total)}</dd>
                <dt>SGST{d.reverse_charge ? ' (payable by recipient)' : ''}</dt><dd>{rupees(d.sgst_total)}</dd></>) : null}
              {gst && !intra ? (<><dt>IGST{d.reverse_charge ? ' (payable by recipient)' : ''}</dt><dd>{rupees(d.igst_total)}</dd></>) : null}
              {d.round_off !== 0 ? (<><dt>Round-off</dt><dd>{rupees(d.round_off)}</dd></>) : null}
              <dt className="is-total">{d.doc_kind === 'credit_note' ? 'Credit' : d.reverse_charge ? 'Amount payable' : 'Total'}</dt>
              <dd className="is-total">{rupees(d.amount_due)}</dd>
            </dl>
            {d.doc_kind === 'bill_of_supply' && d.seller.declaration ? <p className="bos-bill__note">{d.seller.declaration}</p> : null}
            {gst && (d.tax_by_rate ?? []).length > 1 ? (
              <p className="bos-bill__note">
                {(d.tax_by_rate ?? []).map((g) => `GST ${g.rate}%: taxable ${rupees(g.taxable)}, tax ${rupees(g.cgst + g.sgst + g.igst)}`).join(' · ')}
              </p>
            ) : null}
            {d.prices_include_tax && d.doc_kind === 'tax_invoice' ? <p className="bos-bill__note">Prices include GST.</p> : null}
            {d.notes ? <p className="bos-bill__note">{d.notes}</p> : null}
          </article>

          <aside className="bos-inv-side">
            <BillActions businessId={b} bill={d} noteReasons={res.data.meta.note_reasons} methods={res.data.meta.payment_methods} />
            {(d.payments ?? []).length ? (
              <section className="bos-card">
                <h2>Money received</h2>
                <ul className="bos-inv-pay">
                  {(d.payments ?? []).map((p) => (
                    <li key={p.id}><span>{day(p.received_on)} · {p.method_label}{p.reference ? ` · ${p.reference}` : ''}</span><strong>{rupees(p.amount)}</strong></li>
                  ))}
                </ul>
              </section>
            ) : null}
            {d.paid_via_order ? <p className="bos-hint">Paid online with the order.</p> : null}
            {(d.related ?? []).length && !d.doc_kind.endsWith('note') ? (
              <section className="bos-card">
                <h2>Notes against this bill</h2>
                <ul className="bos-inv-pay">
                  {(d.related ?? []).map((r) => (
                    <li key={r.id}>
                      <Link href={`${base}/${r.id}`}>{r.kind_label} {r.number}</Link>
                      <strong>{r.status === 'cancelled' ? 'Cancelled' : rupees(r.amount_due)}</strong>
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}
          </aside>
        </div>
      </DetailShell>
    </div>
  )
}
