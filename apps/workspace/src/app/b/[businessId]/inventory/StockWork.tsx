'use client'

import { useMemo, useState, useTransition } from 'react'
import { useRouter } from 'next/navigation'
import {
  configureItem, cutAndPortion, decideCount, lookupSerial, receiveStock, recordWastage, saveCount,
  setReorder, setYield, startCount, submitCount, writeOffBatch, type SerialInfo,
} from './stock-actions'
import { UNIT, toStock, type Location, type StockItem, type StockRow, type YieldRow } from './types'

type Msg = { text: string; bad?: boolean } | null

function useAction() {
  const router = useRouter()
  const [pending, start] = useTransition()
  const [msg, setMsg] = useState<Msg>(null)
  const run = (fn: () => Promise<{ ok: boolean; message?: string } & Record<string, unknown>>, done: (r: never) => string, after?: () => void) => {
    setMsg(null)
    start(async () => {
      const r = await fn()
      if (r.ok) {
        setMsg({ text: done(r as never) })
        after?.()
        router.refresh()
      } else setMsg({ text: r.message || 'That did not save. Try again.', bad: true })
    })
  }
  return { pending, msg, run, setMsg }
}

function Status({ msg }: { msg: Msg }) {
  return <p className={msg?.bad ? 'bos-status bos-error' : 'bos-status'} role="status" aria-live="polite">{msg?.text ?? ''}</p>
}

const unitWord = (u: StockItem['stock_unit']) => UNIT[u].word

// ------------------------------------------------------------------ receive
export function ReceivePanel({ businessId, items, locations, defaultLocation, only, title, canCost }: {
  businessId: string; items: StockItem[]; locations: Location[]; defaultLocation: string
  only?: 'batch' | 'serial' | 'weighed'; title: string; canCost: boolean
}) {
  const pool = useMemo(() => items.filter((i) => i.track_inventory && (only === 'batch' ? i.batch_tracked
    : only === 'serial' ? i.serial_tracked : only === 'weighed' ? i.stock_unit !== 'piece' : true)), [items, only])
  const [itemId, setItemId] = useState(pool[0]?.id ?? '')
  const item = pool.find((i) => i.id === itemId)
  const [variantId, setVariantId] = useState('')
  const [location, setLocation] = useState(defaultLocation)
  const [qty, setQty] = useState('')
  const [buyUnit, setBuyUnit] = useState('')
  const [cost, setCost] = useState('')
  const [batch, setBatch] = useState('')
  const [expiry, setExpiry] = useState('')
  const [serials, setSerials] = useState('')
  const [note, setNote] = useState('')
  const { pending, msg, run } = useAction()
  const serialList = serials.split(/[\n,]/).map((s) => s.trim()).filter(Boolean)
  if (!pool.length) return <p className="bos-hint">No items are set up for this yet. Turn on stock tracking for an item below.</p>
  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!item) return
    const body: Record<string, unknown> = { location_id: location, offering_id: item.id, variant_id: variantId || null, note: note || null }
    if (item.serial_tracked) body.quantity = serialList.length
    else if (buyUnit) { body.buy_unit = buyUnit; body.buy_quantity = Number(qty) }
    else body.quantity = toStock(qty, item.stock_unit)
    if (cost) body.total_cost_paise = Math.round(Number(cost) * 100)
    if (item.batch_tracked) { body.batch_code = batch; body.expires_on = expiry || null }
    if (item.serial_tracked) body.serials = serialList
    run(() => receiveStock(businessId, body), (r: { data?: { quantity_text: string; on_hand_text: string } }) =>
      `Received ${r.data?.quantity_text ?? ''} of ${item.title}. Now ${r.data?.on_hand_text ?? ''} on hand.`,
      () => { setQty(''); setCost(''); setBatch(''); setExpiry(''); setSerials(''); setNote('') })
  }
  return (
    <form className="bos-stock-form" onSubmit={submit} aria-label={title}>
      <div className="bos-form-grid">
        <label>Item<select value={itemId} onChange={(e) => { setItemId(e.target.value); setVariantId(''); setBuyUnit('') }} required>
          {pool.map((i) => <option key={i.id} value={i.id}>{i.title}</option>)}
        </select></label>
        {item?.variants.length ? <label>Size / colour<select value={variantId} onChange={(e) => setVariantId(e.target.value)} required>
          <option value="">Choose…</option>{item.variants.map((v) => <option key={v.id} value={v.id}>{v.name}</option>)}
        </select></label> : null}
        {locations.length > 1 ? <label>At<select value={location} onChange={(e) => setLocation(e.target.value)}>
          {locations.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}</select></label> : null}
        {item && !item.serial_tracked ? <label>How much{item.buy_units.length ? '' : ` (${unitWord(item.stock_unit)})`}
          <span className="bos-stock-qty">
            <input inputMode="decimal" value={qty} onChange={(e) => setQty(e.target.value.replace(/[^\d.]/g, ''))} required placeholder={buyUnit ? 'e.g. 2' : item.stock_unit === 'piece' ? 'e.g. 24' : 'e.g. 12.5'} />
            {item.buy_units.length ? <select aria-label="Unit" value={buyUnit} onChange={(e) => setBuyUnit(e.target.value)}>
              <option value="">{unitWord(item.stock_unit)}</option>
              {item.buy_units.map((u) => <option key={u.label} value={u.label}>{u.label} ({u.quantity / UNIT[item.stock_unit].per} {unitWord(item.stock_unit)})</option>)}
            </select> : null}
          </span></label> : null}
        {item?.batch_tracked ? <>
          <label>Batch number<input value={batch} onChange={(e) => setBatch(e.target.value)} required maxLength={60} placeholder="As printed on the pack" /></label>
          <label>Expiry date<input type="date" value={expiry} onChange={(e) => setExpiry(e.target.value)} /></label>
        </> : null}
        <label>What it cost in total (₹) — optional<input inputMode="decimal" value={cost} onChange={(e) => setCost(e.target.value.replace(/[^\d.]/g, ''))} placeholder="From the supplier's bill" />
          {!canCost ? <span className="bos-fieldhelp">You can enter it from the bill; stock value stays visible to the owner.</span> : null}</label>
        {item?.serial_tracked ? <label className="bos-form-wide">Serial / IMEI numbers — one per line, one per unit
          <textarea rows={4} value={serials} onChange={(e) => setSerials(e.target.value)} placeholder={'Scan each box’s serial or IMEI'} required />
          <span className="bos-fieldhelp">{serialList.length} unit{serialList.length === 1 ? '' : 's'}{item.warranty_months ? ` · ${item.warranty_months}-month warranty starts at sale` : ''}</span></label> : null}
        <label className="bos-form-wide">Note — optional<input value={note} onChange={(e) => setNote(e.target.value)} maxLength={200} placeholder="Supplier, invoice number…" /></label>
      </div>
      <button type="submit" className="btn" disabled={pending}>{pending ? 'Saving…' : title}</button>
      <Status msg={msg} />
    </form>
  )
}

// ------------------------------------------------------------------ wastage
export function WastagePanel({ businessId, rows, reasons, title }: {
  businessId: string; rows: StockRow[]; reasons: { key: string; label: string }[]; title: string
}) {
  const pool = rows.filter((r) => r.quantity_available > 0)
  const [recordId, setRecordId] = useState(pool[0]?.id ?? '')
  const row = pool.find((r) => r.id === recordId)
  const [qty, setQty] = useState('')
  const [reason, setReason] = useState(reasons[0]?.key ?? 'other')
  const [serials, setSerials] = useState('')
  const [note, setNote] = useState('')
  const { pending, msg, run } = useAction()
  if (!pool.length) return <p className="bos-hint">Nothing in stock to write off.</p>
  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!row) return
    const body: Record<string, unknown> = { inventory_record_id: row.id, reason_code: reason, note: note || null }
    if (row.serial_tracked) body.serials = serials.split(/[\n,]/).map((s) => s.trim()).filter(Boolean)
    else body.quantity = toStock(qty, row.stock_unit)
    run(() => recordWastage(businessId, body), (r: { data?: { quantity_text: string; on_hand_text: string } }) =>
      `Wrote off ${r.data?.quantity_text ?? ''}. ${r.data?.on_hand_text ?? ''} left.`, () => { setQty(''); setSerials(''); setNote('') })
  }
  return (
    <form className="bos-stock-form" onSubmit={submit} aria-label={title}>
      <fieldset className="bos-stock-reasons"><legend>Why</legend>
        {reasons.map((r) => <label key={r.key} className={`bos-choice${reason === r.key ? ' is-on' : ''}`}>
          <input type="radio" name="reason" value={r.key} checked={reason === r.key} onChange={() => setReason(r.key)} />{r.label}</label>)}
      </fieldset>
      <div className="bos-form-grid">
        <label>Item<select value={recordId} onChange={(e) => setRecordId(e.target.value)}>
          {pool.map((r) => <option key={r.id} value={r.id}>{r.title}{r.variant ? ` — ${r.variant}` : ''} ({r.available_text})</option>)}</select></label>
        {row?.serial_tracked ? <label>Serial numbers<textarea rows={2} value={serials} onChange={(e) => setSerials(e.target.value)} required /></label>
          : <label>How much ({row ? unitWord(row.stock_unit) : ''})<input inputMode="decimal" value={qty} onChange={(e) => setQty(e.target.value.replace(/[^\d.]/g, ''))} required /></label>}
        <label>Note — optional<input value={note} onChange={(e) => setNote(e.target.value)} maxLength={200} /></label>
      </div>
      <button type="submit" className="btn-ghost" disabled={pending}>{pending ? 'Saving…' : title}</button>
      <Status msg={msg} />
    </form>
  )
}

// ------------------------------------------------------------------ cut and portion (yield)
export function CutPanel({ businessId, items, yields, rows, locationId }: {
  businessId: string; items: StockItem[]; yields: YieldRow[]; rows: StockRow[]; locationId: string
}) {
  const weighed = items.filter((i) => i.track_inventory && i.stock_unit !== 'piece' && !i.variants.length)
  const sources = weighed.filter((i) => yields.some((y) => y.source_offering_id === i.id))
  const [sourceId, setSourceId] = useState(sources[0]?.id ?? weighed[0]?.id ?? '')
  const source = weighed.find((i) => i.id === sourceId)
  const [cut, setCut] = useState('')
  const suggested = yields.filter((y) => y.source_offering_id === sourceId)
  const [outs, setOuts] = useState<Record<string, string>>({})
  const [extra, setExtra] = useState('')
  const { pending, msg, run } = useAction()
  if (!source) return <p className="bos-hint">Add the items you cut (for example Whole chicken) and the cuts you sell, then set how much each cut usually yields.</p>
  const onHand = rows.find((r) => r.offering_id === source.id && r.location_id === locationId)
  const outputIds = [...suggested.map((y) => y.output_offering_id), ...(extra ? [extra] : [])]
  const cutG = toStock(cut, source.stock_unit)
  const outG = outputIds.reduce((s, id) => s + toStock(outs[id] || '', source.stock_unit), 0)
  const trim = cutG - outG
  const title = (id: string) => weighed.find((i) => i.id === id)?.title ?? 'Item'
  const fmt = (g: number) => `${(g / UNIT[source.stock_unit].per).toFixed(3).replace(/\.?0+$/, '') || '0'} ${unitWord(source.stock_unit)}`
  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    run(() => cutAndPortion(businessId, {
      location_id: locationId, source_offering_id: source.id, source_quantity: cutG, idempotency_key: crypto.randomUUID(),
      outputs: outputIds.map((id) => ({ offering_id: id, quantity: toStock(outs[id] || '', source.stock_unit) })),
    }), (r: { data?: { trim_text: string; trim_percent: number } }) => `Cut recorded. Trim ${r.data?.trim_text ?? ''} (${r.data?.trim_percent ?? 0}%).`,
    () => { setCut(''); setOuts({}) })
  }
  return (
    <form className="bos-stock-form bos-cut" onSubmit={submit} aria-label="Cut and portion">
      <div className="bos-form-grid">
        <label>What was cut<select value={sourceId} onChange={(e) => { setSourceId(e.target.value); setOuts({}) }}>
          {weighed.map((i) => <option key={i.id} value={i.id}>{i.title}</option>)}</select>
          <span className="bos-fieldhelp">{onHand ? `${onHand.available_text} free here` : 'None on record here'}</span></label>
        <label>How much was cut ({unitWord(source.stock_unit)})<input inputMode="decimal" value={cut} onChange={(e) => setCut(e.target.value.replace(/[^\d.]/g, ''))} required /></label>
      </div>
      <table className="bos-cut__table">
        <thead><tr><th scope="col">Cut</th><th scope="col">Usual yield</th><th scope="col">Expected</th><th scope="col">Weighed out</th></tr></thead>
        <tbody>
          {outputIds.map((id) => {
            const y = suggested.find((s) => s.output_offering_id === id)
            return <tr key={id}><th scope="row">{title(id)}</th><td>{y ? `${y.yield_percent}%` : '—'}</td>
              <td>{y && cutG ? fmt(Math.round((cutG * y.yield_bp) / 10000)) : '—'}</td>
              <td><input aria-label={`Weighed out: ${title(id)}`} inputMode="decimal" value={outs[id] || ''} onChange={(e) => setOuts((o) => ({ ...o, [id]: e.target.value.replace(/[^\d.]/g, '') }))} /></td></tr>
          })}
        </tbody>
      </table>
      <label className="bos-cut__add">Another cut from this<select value={extra} onChange={(e) => setExtra(e.target.value)}>
        <option value="">—</option>{weighed.filter((i) => i.id !== source.id && !suggested.some((s) => s.output_offering_id === i.id)).map((i) => <option key={i.id} value={i.id}>{i.title}</option>)}</select></label>
      <p className={`bos-cut__trim${trim < 0 ? ' is-bad' : ''}`} aria-live="polite">
        {cutG ? (trim < 0 ? `The cuts weigh ${fmt(-trim)} more than what was cut` : `Trim ${fmt(trim)} · ${Math.round((trim * 1000) / cutG) / 10}%`) : 'Enter what was cut to see the trim'}
      </p>
      <button type="submit" className="btn" disabled={pending || !cutG || trim < 0 || outG <= 0}>{pending ? 'Saving…' : 'Record the cut'}</button>
      <Status msg={msg} />
    </form>
  )
}

export function YieldEditor({ businessId, items }: { businessId: string; items: StockItem[] }) {
  const weighed = items.filter((i) => i.track_inventory && !i.variants.length)
  const [src, setSrc] = useState('')
  const [out, setOut] = useState('')
  const [pct, setPct] = useState('')
  const { pending, msg, run } = useAction()
  return (
    <form className="bos-stock-form" onSubmit={(e) => { e.preventDefault(); run(() => setYield(businessId, { source_offering_id: src, output_offering_id: out, yield_percent: Number(pct) }), () => 'Yield saved', () => setPct('')) }}>
      <div className="bos-form-grid">
        <label>From<select value={src} onChange={(e) => setSrc(e.target.value)} required><option value="">Choose…</option>{weighed.map((i) => <option key={i.id} value={i.id}>{i.title}</option>)}</select></label>
        <label>Gives<select value={out} onChange={(e) => setOut(e.target.value)} required><option value="">Choose…</option>{weighed.filter((i) => i.id !== src).map((i) => <option key={i.id} value={i.id}>{i.title}</option>)}</select></label>
        <label>Usual yield (%)<input inputMode="decimal" value={pct} onChange={(e) => setPct(e.target.value.replace(/[^\d.]/g, ''))} required placeholder="e.g. 80" /></label>
      </div>
      <p className="bos-fieldhelp">Your own figure — for example 1 kg of whole chicken gives about 800 g of curry cut. LOCAH compares every cut with it.</p>
      <button type="submit" className="btn-ghost" disabled={pending}>Save yield</button>
      <Status msg={msg} />
    </form>
  )
}

// ------------------------------------------------------------------ serials
export function SerialLookup({ businessId }: { businessId: string }) {
  const [value, setValue] = useState('')
  const [found, setFound] = useState<SerialInfo | null>(null)
  const [pending, start] = useTransition()
  const [msg, setMsg] = useState<Msg>(null)
  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    setMsg(null)
    setFound(null)
    start(async () => {
      const r = await lookupSerial(businessId, value)
      if (r.ok && r.data) setFound(r.data)
      else setMsg({ text: r.ok ? 'Not found' : r.message, bad: true })
    })
  }
  const d = (s: string | null) => (s ? new Date(s).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }) : '—')
  return (
    <div className="bos-serial-lookup">
      <form onSubmit={submit} className="bos-serial-lookup__form" role="search" aria-label="Warranty lookup">
        <label htmlFor="serial-q">Serial or IMEI</label>
        <input id="serial-q" value={value} onChange={(e) => setValue(e.target.value)} placeholder="Scan or type" autoComplete="off" required />
        <button type="submit" className="btn" disabled={pending}>Look up</button>
      </form>
      <Status msg={msg} />
      {found ? (
        <div className={`bos-serial-card ${found.in_warranty ? 'is-good' : found.status === 'sold' ? 'is-bad' : ''}`}>
          <p className="bos-serial-card__head"><strong>{found.title}</strong> <span className="bos-tag">{found.serial}</span></p>
          {found.status === 'sold' ? (
            <p>{found.in_warranty ? 'In warranty' : 'Out of warranty'} · sold {d(found.sold_at)}{found.bill_number ? ` on bill ${found.bill_number}` : ''} · warranty until {d(found.warranty_until)}</p>
          ) : <p>{found.status === 'in_stock' ? 'In stock, not sold yet' : 'Written off'}</p>}
          {found.customer ? <p className="bos-hint">Bought by {found.customer.name}{found.customer.phone ? ` · ${found.customer.phone}` : ''}</p> : null}
        </div>
      ) : null}
    </div>
  )
}

// ------------------------------------------------------------------ small actions
export function WriteOffButton({ businessId, batchId, label }: { businessId: string; batchId: string; label: string }) {
  const [confirm, setConfirm] = useState(false)
  const { pending, msg, run } = useAction()
  if (!confirm) return <button type="button" className="btn-quiet" onClick={() => setConfirm(true)}>{label}</button>
  return (
    <span className="bos-stock-confirm">
      <button type="button" className="btn-ghost" disabled={pending} onClick={() => run(() => writeOffBatch(businessId, batchId), () => 'Written off')}>Yes, write off</button>
      <button type="button" className="btn-quiet" onClick={() => setConfirm(false)}>Keep</button>
      <Status msg={msg} />
    </span>
  )
}

export function ReorderEditor({ businessId, row }: { businessId: string; row: StockRow }) {
  const per = UNIT[row.stock_unit].per
  const [min, setMin] = useState(row.reorder_min === null ? '' : String(row.reorder_min / per))
  const [max, setMax] = useState(row.reorder_max === null ? '' : String(row.reorder_max / per))
  const { pending, msg, run } = useAction()
  return (
    <form className="bos-reorder" onSubmit={(e) => { e.preventDefault(); run(() => setReorder(businessId, row.id, {
      reorder_min: min === '' ? null : toStock(min, row.stock_unit), reorder_max: max === '' ? null : toStock(max, row.stock_unit) }), () => 'Saved') }}>
      <label>Reorder at<input inputMode="decimal" value={min} onChange={(e) => setMin(e.target.value.replace(/[^\d.]/g, ''))} /></label>
      <label>Fill up to<input inputMode="decimal" value={max} onChange={(e) => setMax(e.target.value.replace(/[^\d.]/g, ''))} /></label>
      <span className="bos-fieldhelp">{unitWord(row.stock_unit)}</span>
      <button type="submit" className="btn-quiet" disabled={pending}>Save</button>
      <Status msg={msg} />
    </form>
  )
}

export function ItemSetup({ businessId, item }: { businessId: string; item: StockItem }) {
  const [track, setTrack] = useState(item.track_inventory)
  const [batch, setBatch] = useState(item.batch_tracked)
  const [serial, setSerial] = useState(item.serial_tracked)
  const [warranty, setWarranty] = useState(item.warranty_months === null ? '' : String(item.warranty_months))
  const [units, setUnits] = useState(item.buy_units.map((u) => ({ label: u.label, quantity: String(u.quantity / UNIT[item.stock_unit].per) })))
  const { pending, msg, run } = useAction()
  const save = (e: React.FormEvent) => {
    e.preventDefault()
    run(() => configureItem(businessId, item.id, {
      track_inventory: track, batch_tracked: batch, serial_tracked: serial,
      warranty_months: warranty === '' ? null : Number(warranty),
      buy_units: units.filter((u) => u.label && u.quantity).map((u) => ({ label: u.label, quantity: toStock(u.quantity, item.stock_unit) })),
    }), () => 'Saved')
  }
  return (
    <form className="bos-stock-form" onSubmit={save} aria-label={`Stock settings for ${item.title}`}>
      <label className="bos-compliance__check"><input type="checkbox" checked={track} onChange={(e) => setTrack(e.target.checked)} /> Keep stock of {item.title}</label>
      <label className="bos-compliance__check"><input type="checkbox" checked={batch} onChange={(e) => setBatch(e.target.checked)} /> Batches and expiry dates — sell the earliest expiry first</label>
      {item.stock_unit === 'piece' ? <label className="bos-compliance__check"><input type="checkbox" checked={serial} onChange={(e) => setSerial(e.target.checked)} /> A serial or IMEI number for every unit</label> : null}
      {serial ? <label>Warranty from the sale (months)<input inputMode="numeric" value={warranty} onChange={(e) => setWarranty(e.target.value.replace(/\D/g, ''))} /></label> : null}
      <fieldset className="bos-group"><legend>How you buy it — optional</legend>
        {units.map((u, i) => <div key={i} className="bos-rowedit">
          <input aria-label="Unit name" value={u.label} placeholder="crate, case, box" onChange={(e) => setUnits((x) => x.map((y, j) => (j === i ? { ...y, label: e.target.value } : y)))} />
          <input aria-label={`How many ${unitWord(item.stock_unit)}`} inputMode="decimal" value={u.quantity} placeholder={unitWord(item.stock_unit)} onChange={(e) => setUnits((x) => x.map((y, j) => (j === i ? { ...y, quantity: e.target.value.replace(/[^\d.]/g, '') } : y)))} />
          <span className="bos-fieldhelp">{unitWord(item.stock_unit)} in one</span>
          <button type="button" className="btn-quiet" onClick={() => setUnits((x) => x.filter((_, j) => j !== i))}>Remove</button>
        </div>)}
        {units.length < 6 ? <button type="button" className="btn-quiet" onClick={() => setUnits((x) => [...x, { label: '', quantity: '' }])}>Add a buying unit</button> : null}
      </fieldset>
      <button type="submit" className="btn-ghost" disabled={pending}>Save stock settings</button>
      <Status msg={msg} />
    </form>
  )
}

// ------------------------------------------------------------------ counts
export function StartCount({ businessId, locations, defaultLocation }: { businessId: string; locations: Location[]; defaultLocation: string }) {
  const router = useRouter()
  const [location, setLocation] = useState(defaultLocation)
  const [label, setLabel] = useState('')
  const [pending, start] = useTransition()
  const [msg, setMsg] = useState<Msg>(null)
  return (
    <form className="bos-stock-form" onSubmit={(e) => {
      e.preventDefault()
      start(async () => {
        const r = await startCount(businessId, { location_id: location, label: label || null })
        if (r.ok && r.data) router.push(`/b/${businessId}/inventory/counts/${r.data.id}`)
        else setMsg({ text: r.ok ? 'Could not start' : r.message, bad: true })
      })
    }}>
      <div className="bos-form-grid">
        {locations.length > 1 ? <label>Where<select value={location} onChange={(e) => setLocation(e.target.value)}>{locations.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}</select></label> : null}
        <label>Name — optional<input value={label} onChange={(e) => setLabel(e.target.value)} placeholder="e.g. Monday shelf count" maxLength={120} /></label>
      </div>
      <button type="submit" className="btn" disabled={pending}>Start a count</button>
      <Status msg={msg} />
    </form>
  )
}

export type CountLine = { id: string; inventory_record_id: string; title: string; variant: string | null; stock_unit: StockItem['stock_unit']; counted_quantity: number | null; expected_quantity?: number; expected_text?: string; variance?: number | null; variance_text?: string | null }

export function CountSheet({ businessId, countId, status, lines, canApprove, canCount }: {
  businessId: string; countId: string; status: string; lines: CountLine[]; canApprove: boolean; canCount: boolean
}) {
  const [values, setValues] = useState<Record<string, string>>(() => Object.fromEntries(lines.map((l) => [l.inventory_record_id, l.counted_quantity === null ? '' : String(l.counted_quantity / UNIT[l.stock_unit].per)])))
  const [note, setNote] = useState('')
  const { pending, msg, run } = useAction()
  const payload = () => lines.map((l) => ({ inventory_record_id: l.inventory_record_id, counted_quantity: values[l.inventory_record_id] === '' ? null : toStock(values[l.inventory_record_id], l.stock_unit) }))
  const open = status === 'open' && canCount
  return (
    <div className="bos-count">
      <table className="bos-count__table">
        <thead><tr><th scope="col">Item</th><th scope="col">Counted</th>{lines[0]?.expected_text !== undefined ? <><th scope="col">On record</th><th scope="col">Difference</th></> : null}</tr></thead>
        <tbody>{lines.map((l) => (
          <tr key={l.id} className={l.variance ? 'is-variance' : ''}>
            <th scope="row">{l.title}{l.variant ? ` — ${l.variant}` : ''}</th>
            <td>{open ? <input aria-label={`Counted: ${l.title}${l.variant ? ` ${l.variant}` : ''}`} inputMode="decimal" value={values[l.inventory_record_id]} onChange={(e) => setValues((v) => ({ ...v, [l.inventory_record_id]: e.target.value.replace(/[^\d.]/g, '') }))} /> : (l.counted_quantity === null ? 'Not counted' : `${l.counted_quantity / UNIT[l.stock_unit].per} ${unitWord(l.stock_unit)}`)}
              {open ? <span className="bos-fieldhelp"> {unitWord(l.stock_unit)}</span> : null}</td>
            {l.expected_text !== undefined ? <><td>{l.expected_text}</td><td>{l.variance_text ?? '—'}</td></> : null}
          </tr>
        ))}</tbody>
      </table>
      {open ? <div className="bos-count__actions">
        <button type="button" className="btn-ghost" disabled={pending} onClick={() => run(() => saveCount(businessId, countId, payload()), () => 'Saved')}>Save progress</button>
        <button type="button" className="btn" disabled={pending} onClick={() => run(async () => { const s = await saveCount(businessId, countId, payload()); return s.ok ? submitCount(businessId, countId) : s }, () => 'Sent for approval')}>Submit count</button>
      </div> : null}
      {status === 'submitted' && canApprove ? <div className="bos-count__actions">
        <label>Note — optional<input value={note} onChange={(e) => setNote(e.target.value)} maxLength={300} /></label>
        <button type="button" className="btn" disabled={pending} onClick={() => run(() => decideCount(businessId, countId, true, note), (r: { data?: { variances_applied?: number } }) => `Approved — ${r.data?.variances_applied ?? 0} stock line(s) corrected`)}>Approve differences</button>
        <button type="button" className="btn-ghost" disabled={pending} onClick={() => run(() => decideCount(businessId, countId, false, note), () => 'Sent back for a recount')}>Send back</button>
      </div> : null}
      {status === 'submitted' && !canApprove ? <p className="bos-hint">Submitted. Stock changes when a manager approves the differences.</p> : null}
      <Status msg={msg} />
    </div>
  )
}
