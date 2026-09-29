import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import { GateNotice, PageHeader, StatusPill } from '@/components/ui'
import {
  CutPanel, ItemSetup, ReceivePanel, ReorderEditor, SerialLookup, StartCount, WastagePanel, WriteOffButton, YieldEditor,
} from './StockWork'
import {
  UNIT, rupees, type Batch, type Conversion, type CountSummary, type Lens, type Location, type StockItem,
  type StockOverview, type StockProfile, type StockRow, type Wastage, type YieldRow,
} from './types'

export const dynamic = 'force-dynamic'

type View = Lens['key'] | 'counts' | 'wastage' | 'all' | 'setup'

const EXTRA_VIEWS: { key: View; label: string }[] = [
  { key: 'counts', label: 'Counts' }, { key: 'wastage', label: 'Wastage' }, { key: 'all', label: 'All stock' },
  { key: 'setup', label: 'Item settings' },
]
const date = (s: string) => new Date(`${s}T00:00:00`).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })

/** Capability Universe §15.1 — one inventory domain; the view follows how this business keeps stock. */
export default async function StockPage({ params, searchParams }: {
  params: { businessId: string }; searchParams?: { view?: string; q?: string; location?: string }
}) {
  const token = await getAccessToken()
  if (!token) redirect('/login')
  const b = params.businessId
  const api = `/v1/platform/businesses/${b}/stock`
  const [profRes, locRes] = await Promise.all([
    apiTry<{ data: StockProfile }>(`${api}/profile`, token),
    apiTry<{ data: Location[] }>(`/v1/platform/businesses/${b}/locations`, token),
  ])
  if (!profRes.ok) {
    return <div className="bos-page"><PageHeader title="Stock" /><GateNotice error={profRes.error} businessId={b} moduleLabel="Stock" /></div>
  }
  const prof = profRes.data.data
  const locations = locRes.ok ? locRes.data.data : []
  const lensKeys = prof.lenses.map((l) => l.key)
  const requested = (searchParams?.view ?? '') as View
  const view: View = [...lensKeys, ...EXTRA_VIEWS.map((v) => v.key)].includes(requested) ? requested : prof.primary
  const location = searchParams?.location && locations.some((l) => l.id === searchParams.location) ? searchParams.location : undefined
  const qs = new URLSearchParams()
  if (location) qs.set('location_id', location)
  if (searchParams?.q) qs.set('q', searchParams.q)
  const [ovRes, itemsRes] = await Promise.all([
    apiTry<{ data: StockOverview }>(`${api}?${qs}`, token),
    apiTry<{ data: StockItem[] }>(`${api}/items`, token),
  ])
  const overview = ovRes.ok ? ovRes.data.data : { items: [], totals: { items: 0, low: 0, out: 0, expiring_30d: 0, expired: 0 } }
  const items = itemsRes.ok ? itemsRes.data.data : []
  const defaultLocation = location ?? locations.find((l) => l.is_primary)?.id ?? locations[0]?.id ?? ''
  const lens = prof.lenses.find((l) => l.key === view)
  const href = (v: View) => `/b/${b}/inventory?view=${v}${location ? `&location=${location}` : ''}`
  const tracked = items.filter((i) => i.track_inventory)
  const rows = overview.items

  const header = (
    <PageHeader
      title={lens?.title ?? EXTRA_VIEWS.find((v) => v.key === view)?.label ?? 'Stock'}
      subtitle={lensSubtitle(view)}
    />
  )
  const tabs = (
    <nav className="bos-stock-tabs" aria-label="Stock views">
      {prof.lenses.map((l) => <Link key={l.key} href={href(l.key)} aria-current={view === l.key ? 'page' : undefined}>{TAB_LABEL[l.key]}</Link>)}
      {EXTRA_VIEWS.filter((v) => v.key !== 'setup' || prof.can.setup).map((v) => <Link key={v.key} href={href(v.key)} aria-current={view === v.key ? 'page' : undefined}>{v.label}</Link>)}
      <Link href={`/b/${b}/inventory/transfers`}>Transfers</Link>
      <Link href={`/b/${b}/inventory/vans`}>Van stock</Link>
      {locations.length > 1 ? <form className="bos-stock-tabs__where" action={`/b/${b}/inventory`}>
        <input type="hidden" name="view" value={view} />
        <label className="sr-only" htmlFor="stock-loc">Location</label>
        <select id="stock-loc" name="location" defaultValue={location ?? ''}><option value="">All locations</option>{locations.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}</select>
        <button type="submit" className="btn-quiet">Show</button>
      </form> : null}
    </nav>
  )
  const totals = (
    <div className="bos-review-summary">
      <div><span>Items tracked</span><strong>{overview.totals.items}</strong><small>{locations.length > 1 && !location ? 'Across locations' : 'Here'}</small></div>
      <div><span>Low or out</span><strong>{overview.totals.low + overview.totals.out}</strong><small>At or below the reorder level</small></div>
      {lensKeys.includes('batches') ? <div><span>Expiring in 30 days</span><strong>{overview.totals.expiring_30d}</strong><small>{overview.totals.expired ? `${overview.totals.expired} with expired stock` : 'No expired stock'}</small></div> : null}
      {prof.can.cost && overview.totals.value_paise !== undefined ? <div><span>Stock value</span><strong>{rupees(overview.totals.value_paise)}</strong><small>{overview.totals.not_valued ? `${overview.totals.not_valued} item(s) without a cost` : 'At average cost'}</small></div> : null}
    </div>
  )
  const noStock = !tracked.length
  const empty = noStock ? (
    <div className="bos-empty bos-stock-empty">
      <p><strong>{prof.lenses[0].empty}</strong></p>
      {prof.can.setup ? <p>Open <Link href={href('setup')}>Item settings</Link> to choose which items you keep stock of{lensKeys.includes('batches') ? ', which keep batches and expiry' : ''}{lensKeys.includes('serials') ? ', which keep serial numbers' : ''}.</p>
        : <p>Ask the owner to turn on stock for the items you handle.</p>}
      <p className="bos-hint">Set up this way because this business is {describe(prof)}.</p>
    </div>
  ) : null

  let body: React.ReactNode = null
  if (view === 'weighed') body = await weighedView()
  else if (view === 'batches') body = await batchesView()
  else if (view === 'serials') body = serialsView()
  else if (view === 'variants') body = variantsView()
  else if (view === 'ingredients') body = ingredientsView()
  else if (view === 'counter') body = counterView()
  else if (view === 'counts') body = await countsView()
  else if (view === 'wastage') body = await wastageView()
  else if (view === 'setup') body = setupView()
  else body = allView()

  return (
    <div className="bos-page bos-stock">
      {header}
      {tabs}
      {view !== 'setup' ? totals : null}
      {empty && view !== 'setup' ? empty : body}
    </div>
  )

  // ---------------------------------------------------------------- views
  async function weighedView() {
    const [yRes, cRes, wRes] = await Promise.all([
      apiTry<{ data: YieldRow[] }>(`${api}/yields`, token!),
      apiTry<{ data: Conversion[] }>(`${api}/conversions`, token!),
      apiTry<{ data: Wastage }>(`${api}/wastage?days=30`, token!),
    ])
    const yields = yRes.ok ? yRes.data.data : []
    const runs = cRes.ok ? cRes.data.data : []
    const wastage = wRes.ok ? wRes.data.data : null
    const weighed = rows.filter((r) => r.stock_unit !== 'piece')
    return (
      <>
        <section className="bos-section" aria-labelledby="counter-now">
          <h2 id="counter-now">On the counter now</h2>
          <ul className="bos-stock-cards">
            {weighed.map((r) => (
              <li key={r.id} className={`bos-stock-card is-${r.stock_status}`}>
                <Link href={`/b/${b}/inventory/${r.id}`} className="bos-stock-card__title">{r.title}</Link>
                <strong className="bos-stock-card__qty">{r.on_hand_text}</strong>
                <span className="bos-hint">{r.quantity_reserved ? `${r.available_text} free · rest held for orders` : 'All free to sell'}</span>
                {r.stock_status !== 'available' ? <StatusPill value={r.stock_status} /> : null}
              </li>
            ))}
          </ul>
          {!weighed.length ? <p className="bos-hint">Nothing sold by weight is in stock yet.</p> : null}
        </section>
        {prof.can.adjust ? <div className="bos-stock-work">
          <section className="bos-card" aria-labelledby="receive-h"><h2 id="receive-h">{prof.lenses[0].primary_action}</h2>
            <ReceivePanel businessId={b} items={items} locations={locations} defaultLocation={defaultLocation} only="weighed" title="Record arrival" canCost={prof.can.cost} /></section>
          {prof.yield_offered ? <section className="bos-card" aria-labelledby="cut-h"><h2 id="cut-h">Cut and portion</h2>
            <p className="bos-hint">Weigh what you cut and what came out; the difference is trim. The cost of the whole moves into the cuts.</p>
            <CutPanel businessId={b} items={items} yields={yields} rows={rows} locationId={defaultLocation} /></section> : null}
          <section className="bos-card" aria-labelledby="waste-h"><h2 id="waste-h">Record wastage</h2>
            <WastagePanel businessId={b} rows={weighed.length ? weighed : rows} reasons={prof.wastage_reasons} title="Record wastage" /></section>
        </div> : null}
        {prof.yield_offered ? <section className="bos-section" aria-labelledby="yields-h">
          <h2 id="yields-h">Yields</h2>
          {yields.length ? <ul className="bos-stock-lines">{yields.map((y) => (
            <li key={y.id}><strong>{y.source_title} → {y.output_title}</strong> · usually {y.yield_percent}%
              {y.actual_percent_of_expected !== null ? <span className={y.actual_percent_of_expected < 95 ? ' bos-error' : ''}> · last {y.runs} cut{y.runs === 1 ? '' : 's'} gave {y.actual_percent_of_expected}% of that</span> : <span className="bos-hint"> · no cuts recorded yet</span>}</li>
          ))}</ul> : <p className="bos-hint">No yields yet. Enter your own figure — LOCAH does not guess it.</p>}
          {prof.can.adjust ? <details className="bos-stock-more"><summary>Set a yield</summary><YieldEditor businessId={b} items={items} /></details> : null}
          {runs.length ? <><h3>Recent cuts</h3><ul className="bos-stock-lines">{runs.slice(0, 8).map((c) => (
            <li key={c.id}>{c.source_text} {c.source_title} → {c.outputs.map((o) => `${o.actual_text} ${o.title}`).join(', ')} · trim {c.trim_text} ({c.trim_percent}%)</li>
          ))}</ul></> : null}
          {wastage?.cutting.trim_percent !== null && wastage ? <p className="bos-hint">Trim over the last {wastage.days} days: {wastage.cutting.trim_percent}% across {wastage.cutting.runs} cut{wastage.cutting.runs === 1 ? '' : 's'}.</p> : null}
        </section> : null}
      </>
    )
  }

  async function batchesView() {
    const eRes = await apiTry<{ data: Batch[] }>(`${api}/expiring?days=30${location ? `&location_id=${location}` : ''}`, token!)
    const batches = eRes.ok ? eRes.data.data : []
    const groups: [string, Batch[]][] = [
      ['Expired — do not sell', batches.filter((x) => x.state === 'expired')],
      ['Expires within 7 days', batches.filter((x) => x.state !== 'expired' && (x.days_left ?? 99) <= 7)],
      ['Expires within 30 days', batches.filter((x) => (x.days_left ?? 99) > 7)],
    ]
    const batchRows = rows.filter((r) => r.batch_tracked)
    return (
      <>
        <section className="bos-section" aria-labelledby="exp-h">
          <h2 id="exp-h">Expiry</h2>
          {batches.length ? groups.filter(([, list]) => list.length).map(([label, list]) => (
            <div key={label} className="bos-stock-expiry">
              <h3>{label}</h3>
              <ul className="bos-mini-list">{list.map((x) => (
                <li key={x.id} className={`bos-stock-batch is-${x.state}`}>
                  <span><strong>{x.title}</strong> · batch {x.batch_code} · {x.quantity_text}</span>
                  <span>{x.expires_on ? (x.state === 'expired' ? `expired ${date(x.expires_on)}` : `${date(x.expires_on)} · ${x.days_left} day${x.days_left === 1 ? '' : 's'}`) : ''}</span>
                  {prof.can.adjust ? <WriteOffButton businessId={b} batchId={x.id} label={x.state === 'expired' ? 'Write off' : 'Write off early'} /> : null}
                </li>
              ))}</ul>
            </div>
          )) : <p className="bos-hint">Nothing expires in the next 30 days.</p>}
        </section>
        <section className="bos-section" aria-labelledby="bystock-h">
          <h2 id="bystock-h">Stock by item</h2>
          <table className="bos-stock-table">
            <thead><tr><th scope="col">Item</th><th scope="col">On hand</th><th scope="col">Batches</th><th scope="col">Next expiry</th><th scope="col">State</th></tr></thead>
            <tbody>{batchRows.map((r) => (
              <tr key={r.id}><th scope="row"><Link href={`/b/${b}/inventory/${r.id}`}>{r.title}{r.variant ? ` — ${r.variant}` : ''}</Link></th>
                <td>{r.on_hand_text}</td><td>{r.batches}</td><td>{r.next_expiry ? date(r.next_expiry) : '—'}</td><td><StatusPill value={r.stock_status} /></td></tr>
            ))}</tbody>
          </table>
          {!batchRows.length ? <p className="bos-hint">No item keeps batches yet. Turn it on in Item settings for medicines and anything with a use-by date.</p> : null}
        </section>
        {prof.can.adjust ? <section className="bos-card" aria-labelledby="rcv-h"><h2 id="rcv-h">Receive a batch</h2>
          <ReceivePanel businessId={b} items={items} locations={locations} defaultLocation={defaultLocation} only="batch" title="Receive batch" canCost={prof.can.cost} /></section> : null}
      </>
    )
  }

  function serialsView() {
    const serialRows = rows.filter((r) => r.serial_tracked)
    return (
      <>
        <section className="bos-section" aria-labelledby="warranty-h">
          <h2 id="warranty-h">Warranty lookup</h2>
          <p className="bos-hint">Scan the serial or IMEI a customer brings back to see when it was sold and whether it is still in warranty.</p>
          <SerialLookup businessId={b} />
        </section>
        <section className="bos-section" aria-labelledby="units-h">
          <h2 id="units-h">Units in stock</h2>
          <table className="bos-stock-table">
            <thead><tr><th scope="col">Item</th><th scope="col">Units by serial</th><th scope="col">Warranty</th><th scope="col">State</th></tr></thead>
            <tbody>{serialRows.map((r) => (
              <tr key={r.id}><th scope="row"><Link href={`/b/${b}/inventory/${r.id}`}>{r.title}{r.variant ? ` — ${r.variant}` : ''}</Link></th>
                <td>{r.serials_in_stock}{r.serials_in_stock !== r.quantity_on_hand ? <span className="bos-error"> (record says {r.quantity_on_hand})</span> : null}</td>
                <td>{r.warranty_months ? `${r.warranty_months} months` : '—'}</td><td><StatusPill value={r.stock_status} /></td></tr>
            ))}</tbody>
          </table>
          {!serialRows.length ? <p className="bos-hint">No item keeps serial numbers yet. Turn it on in Item settings for phones, appliances and anything with a warranty.</p> : null}
        </section>
        {prof.can.adjust ? <section className="bos-card" aria-labelledby="rcvs-h"><h2 id="rcvs-h">Receive with serial numbers</h2>
          <ReceivePanel businessId={b} items={items} locations={locations} defaultLocation={defaultLocation} only="serial" title="Receive units" canCost={prof.can.cost} /></section> : null}
      </>
    )
  }

  function variantsView() {
    const products = tracked.filter((i) => i.variants.length)
    return (
      <>
        {products.map((p) => {
          const opts = p.variant_options
          const [a, c] = [opts[0], opts[1]]
          const cell = (va: string, vc?: string) => {
            const v = p.variants.find((x) => x.attributes[a.name] === va && (!c || x.attributes[c.name] === vc))
            const r = v ? rows.find((x) => x.variant_id === v.id) : undefined
            return r ? <td key={`${va}-${vc}`} className={`bos-grid-cell is-${r.stock_status}`}><Link href={`/b/${b}/inventory/${r.id}`}>{r.quantity_available}</Link></td>
              : <td key={`${va}-${vc}`} className="bos-grid-cell is-none">{v ? '0' : '—'}</td>
          }
          return (
            <section key={p.id} className="bos-section" aria-label={p.title}>
              <h2>{p.title}</h2>
              {a ? <div className="bos-grid-wrap"><table className="bos-variant-grid">
                <thead><tr><th scope="col">{a.name}{c ? ` \\ ${c.name}` : ''}</th>{(c ? c.values : ['In stock']).map((vc) => <th key={vc} scope="col">{vc}</th>)}</tr></thead>
                <tbody>{a.values.map((va) => <tr key={va}><th scope="row">{va}</th>{c ? c.values.map((vc) => cell(va, vc)) : cell(va)}</tr>)}</tbody>
              </table></div> : null}
            </section>
          )
        })}
        {!products.length ? <p className="bos-hint">No product with sizes or colours keeps stock yet. Give a product its sizes and colours in Products & services.</p> : null}
        {prof.can.adjust ? <section className="bos-card" aria-labelledby="rcvv-h"><h2 id="rcvv-h">Receive stock</h2>
          <ReceivePanel businessId={b} items={items} locations={locations} defaultLocation={defaultLocation} title="Receive" canCost={prof.can.cost} /></section> : null}
      </>
    )
  }

  function ingredientsView() {
    return (
      <>
        <p className="bos-hint">Ingredients you buy and use. Recipes that use them up as dishes are sold arrive with Recipes &amp; BOM; until then record what arrives and what is wasted.</p>
        {stockTable(rows, false)}
        {prof.can.adjust ? <div className="bos-stock-work">
          <section className="bos-card"><h2>Record what came in</h2><ReceivePanel businessId={b} items={items} locations={locations} defaultLocation={defaultLocation} title="Record arrival" canCost={prof.can.cost} /></section>
          <section className="bos-card"><h2>Record wastage</h2><WastagePanel businessId={b} rows={rows} reasons={prof.wastage_reasons} title="Record wastage" /></section>
        </div> : null}
      </>
    )
  }

  function counterView() {
    const reorder = rows.filter((r) => r.stock_status !== 'available')
    return (
      <>
        <section className="bos-section" aria-labelledby="reorder-h">
          <h2 id="reorder-h">To reorder</h2>
          {reorder.length ? <table className="bos-stock-table">
            <thead><tr><th scope="col">Item</th><th scope="col">Free now</th><th scope="col">Reorder at</th><th scope="col">Suggested</th></tr></thead>
            <tbody>{reorder.map((r) => (
              <tr key={r.id}><th scope="row"><Link href={`/b/${b}/inventory/${r.id}`}>{r.title}{r.variant ? ` — ${r.variant}` : ''}</Link></th>
                <td>{r.available_text}</td><td>{r.reorder_min !== null ? `${r.reorder_min / UNIT[r.stock_unit].per} ${UNIT[r.stock_unit].word}` : '—'}</td>
                <td>{r.reorder_suggest_text ?? (r.reorder_max === null ? 'Set a “fill up to” level' : '—')}</td></tr>
            ))}</tbody>
          </table> : <p className="bos-hint">Nothing is at its reorder level.</p>}
        </section>
        {stockTable(rows, true)}
        {prof.can.adjust ? <section className="bos-card" aria-labelledby="rcvc-h"><h2 id="rcvc-h">Receive stock</h2>
          <ReceivePanel businessId={b} items={items} locations={locations} defaultLocation={defaultLocation} title="Receive" canCost={prof.can.cost} /></section> : null}
      </>
    )
  }

  async function countsView() {
    const cRes = await apiTry<{ data: CountSummary[] }>(`${api}/counts`, token!)
    const counts = cRes.ok ? cRes.data.data : []
    const words: Record<CountSummary['status'], string> = { open: 'Counting', submitted: 'Waiting for approval', approved: 'Approved', cancelled: 'Sent back' }
    return (
      <>
        <p className="bos-hint">Count a shelf without looking at the system figure. Differences change stock only when a manager approves them.</p>
        {prof.can.adjust ? <section className="bos-card"><h2>Start a count</h2><StartCount businessId={b} locations={locations} defaultLocation={defaultLocation} /></section> : null}
        <ul className="bos-mini-list bos-section">{counts.map((c) => (
          <li key={c.id}><Link href={`/b/${b}/inventory/counts/${c.id}`}><strong>{c.label}</strong></Link> · {words[c.status]}{c.created_at ? ` · ${new Date(c.created_at).toLocaleDateString('en-IN', { dateStyle: 'medium' })}` : ''}</li>
        ))}</ul>
        {!counts.length ? <p className="bos-hint">No counts yet.</p> : null}
      </>
    )
  }

  async function wastageView() {
    const wRes = await apiTry<{ data: Wastage }>(`${api}/wastage?days=30`, token!)
    const w = wRes.ok ? wRes.data.data : null
    return (
      <>
        <section className="bos-section" aria-labelledby="w30-h">
          <h2 id="w30-h">Last 30 days</h2>
          {w && w.reasons.length ? <table className="bos-stock-table">
            <thead><tr><th scope="col">Why</th><th scope="col">Times</th><th scope="col">How much</th>{prof.can.cost ? <th scope="col">Cost</th> : null}</tr></thead>
            <tbody>{w.reasons.map((r) => <tr key={r.reason}><th scope="row">{r.label}</th><td>{r.entries}</td><td>{r.quantities.join(' + ')}</td>{prof.can.cost ? <td>{rupees(r.value_paise ?? 0)}</td> : null}</tr>)}</tbody>
          </table> : <p className="bos-hint">No wastage recorded in the last 30 days.</p>}
          {w?.cutting.runs ? <p className="bos-hint">Cutting trim: {w.cutting.trim_percent}% over {w.cutting.runs} cut{w.cutting.runs === 1 ? '' : 's'}.</p> : null}
        </section>
        {prof.can.adjust ? <section className="bos-card"><h2>Record wastage</h2><WastagePanel businessId={b} rows={rows} reasons={prof.wastage_reasons} title="Record wastage" /></section> : null}
      </>
    )
  }

  function setupView() {
    const goods = items
    return (
      <>
        <p className="bos-hint">Choose which items you keep stock of and how: batches and expiry, serial numbers, how you buy them. This business shows {prof.lenses.map((l) => TAB_LABEL[l.key].toLowerCase()).join(', ')} because it is {describe(prof)}.</p>
        <ul className="bos-stock-setup">{goods.map((i) => (
          <li key={i.id} className="bos-card"><details><summary><strong>{i.title}</strong> <span className="bos-hint">{i.track_inventory ? [i.batch_tracked && 'batches', i.serial_tracked && 'serials', 'stock kept'].filter(Boolean).join(' · ') : 'no stock kept'}</span></summary>
            <ItemSetup businessId={b} item={i} /></details></li>
        ))}</ul>
        {!goods.length ? <p className="bos-hint">Add products in Products &amp; services first.</p> : null}
      </>
    )
  }

  function allView() {
    return stockTable(rows, true)
  }

  function stockTable(list: StockRow[], editable: boolean) {
    return (
      <section className="bos-section" aria-labelledby="all-h">
        <h2 id="all-h">Everything in stock</h2>
        <form className="bos-stock-search" action={`/b/${b}/inventory`}><input type="hidden" name="view" value={view} />
          <label className="sr-only" htmlFor="stock-q">Find an item</label><input id="stock-q" name="q" defaultValue={searchParams?.q ?? ''} placeholder="Find by name, code or barcode" /><button type="submit" className="btn-quiet">Find</button></form>
        <table className="bos-stock-table">
          <thead><tr><th scope="col">Item</th><th scope="col">On hand</th><th scope="col">Free</th>{prof.can.cost ? <th scope="col">Value</th> : null}<th scope="col">State</th>{editable && prof.can.adjust ? <th scope="col">Reorder</th> : null}</tr></thead>
          <tbody>{list.map((r) => (
            <tr key={r.id}><th scope="row"><Link href={`/b/${b}/inventory/${r.id}`}>{r.title}{r.variant ? ` — ${r.variant}` : ''}</Link>{r.sku ? <span className="bos-hint"> {r.sku}</span> : null}</th>
              <td>{r.on_hand_text}</td><td>{r.available_text}</td>{prof.can.cost ? <td>{r.value_paise ? rupees(r.value_paise) : '—'}</td> : null}
              <td><StatusPill value={r.stock_status} /></td>
              {editable && prof.can.adjust ? <td><ReorderEditor businessId={b} row={r} /></td> : null}</tr>
          ))}</tbody>
        </table>
        {!list.length ? <p className="bos-hint">{searchParams?.q ? 'Nothing matches that.' : 'No stock recorded yet.'}</p> : null}
      </section>
    )
  }
}

const TAB_LABEL: Record<Lens['key'], string> = {
  weighed: 'Counter by weight', batches: 'Batches & expiry', serials: 'Serials & warranty',
  variants: 'Sizes & colours', ingredients: 'Ingredients', counter: 'Reorder',
}

function lensSubtitle(view: View): string {
  return ({
    weighed: 'Kilos on hand for each item and cut. Record the morning arrival, cut whole into cuts, and see the trim.',
    batches: 'Every batch with its expiry. The earliest expiry sells first, and you are told before anything expires.',
    serials: 'Every unit by its serial or IMEI, captured at sale so its warranty can be looked up.',
    variants: 'Each product as a size × colour grid — what is free to sell in every combination.',
    ingredients: 'What you buy to cook with, what arrives and what is wasted.',
    counter: 'What is low, what to reorder, and everything on the shelf.',
    counts: 'Shelf counts and the differences waiting for approval.',
    wastage: 'What was thrown away and why.',
    all: 'Every stock line, with its free quantity and reorder level.',
    setup: 'How each item keeps stock.',
  } as Record<View, string>)[view]
}

function describe(p: StockProfile): string {
  const words: Record<string, string> = {
    weight_based: 'sold by weight', perishable: 'perishable', serialised: 'sold with serial numbers',
    variant_based: 'sold in sizes or colours', ingredient_based: 'cooked from ingredients', stock_tracked: 'stock-keeping',
  }
  const said = p.because.traits.map((t) => words[t]).filter(Boolean)
  const hints = p.because.playbook_hints.length ? [`a business whose stock needs ${p.because.playbook_hints.join(', ')}`] : []
  return [...said, ...hints].join(', ') || 'set up with stock'
}
