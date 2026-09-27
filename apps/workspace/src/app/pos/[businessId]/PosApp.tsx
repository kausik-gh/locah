'use client'

import Link from 'next/link'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { compute, rupees, toPaise, type Scheme } from '@/lib/pos/engine'
import { canPrintDirect, pad, printDirect, receiptBytes } from '@/lib/pos/escpos'
import { resolveCode, type PosItem, type PosPack, type PosVariant, type WeighedFormat } from '@/lib/pos/scan'
import { deviceId, load, numbersLeft, save, takeNumber, type Block, type Held, type Queued } from '@/lib/pos/store'
import { posToken } from './actions'

// ------------------------------------------------------------------ types
type Seller = { legal_name: string; trade_name: string | null; gstin: string | null; address: string | null; declaration: string | null }
type Register = { id: string; name: string; code: string; location_id: string; location_name: string; scheme: Scheme; state_code: string; seller: Seller; open_shift: Shift | null }
type Shift = { id: string; register_id: string; location_id: string; status: string; opened_at: string; opening_cash: number; summary?: Summary }
type Summary = { bills: number; voided: number; returns: number; sales_total: number; cash_sales: number; upi: number; upi_to_verify: number; card: number; refunds: number; petty_expenses: number; cash_in: number; cash_out: number; opening_cash: number; expected_cash: number; khata_given?: number; khata_received?: number; khata_cash?: number }
export type PosSetup = {
  profile: { prices_include_tax: boolean; round_off: boolean } | null
  registers: Register[]
  settings: { upi_vpa: string | null; return_window_days: number; weighed_label: WeighedFormat | null; receipt_footer: string | null; discount_caps: Record<string, number> }
  discount_cap: number | null
  me: string
  approvers: { identity_id: string; name: string }[]
  cash_kinds: Record<string, string>
  khata?: boolean
}
type Catalogue = { version: string; items: PosItem[]; today: string }
type CartLine = { key: string; item: PosItem; variant?: PosVariant; pack?: PosPack; quantity: number; unitPrice: number; discount: number }
type Customer = { name: string; phone: string; gstin: string }
type Cart = { lines: CartLine[]; customer: Customer; billDiscount: number; approval?: string; creditApproval?: string }
type Tender = { method: 'cash' | 'upi' | 'card' | 'khata'; amount: number; reference?: string; to_verify?: boolean }
type KhataAccount = { id: string; display_name: string; balance: number; credit_limit: number | null; over_limit: boolean }
type Receipt = {
  clientId: string; number: string | null; at: string; kind: string; seller: Seller; register: string
  lines: { title: string; qty: string; total: number }[]; taxable: number; cgst: number; sgst: number; roundOff: number
  total: number; tenders: Tender[]; change: number; gst: boolean; footer: string | null; phone: string
}
type Panel = null | 'pay' | 'approve' | 'receipt' | 'drawer' | 'bills' | 'return' | 'close' | 'holds' | 'choose' | 'khata'
const TENDER_LABEL: Record<Tender['method'], string> = { cash: 'Cash', upi: 'UPI', card: 'Card', khata: 'Khata' }

const emptyCart = (): Cart => ({ lines: [], customer: { name: '', phone: '', gstin: '' }, billDiscount: 0 })
const uid = () => crypto.randomUUID()
const qtyText = (l: CartLine) => (l.item.price_per && !l.pack ? `${l.quantity} ${l.item.price_per}` : String(l.quantity))

// ------------------------------------------------------------------ app
export function PosApp({ businessId, businessName, initialToken, apiUrl, billBase, setup: initialSetup }: {
  businessId: string; businessName: string; initialToken: string; apiUrl: string; billBase: string; setup: PosSetup
}) {
  const setup = initialSetup
  const [device, setDevice] = useState('')
  const [online, setOnline] = useState(true)
  const [shift, setShift] = useState<Shift | null>(null)
  const [block, setBlock] = useState<Block | null>(null)
  const [catalogue, setCatalogue] = useState<Catalogue | null>(null)
  const [queue, setQueue] = useState<Queued[]>([])
  const [done, setDone] = useState<Record<string, { number: string; document_id: string; share_token?: string }>>({})
  const [holds, setHolds] = useState<Held[]>([])
  const [cart, setCart] = useState<Cart>(emptyCart())
  const [panel, setPanel] = useState<Panel>(null)
  const [query, setQuery] = useState('')
  const [notice, setNotice] = useState<{ text: string; bad?: boolean } | null>(null)
  const [receipt, setReceipt] = useState<Receipt | null>(null)
  const [choose, setChoose] = useState<PosItem | null>(null)
  const [approveFor, setApproveFor] = useState<{ action: 'discount' | 'void' | 'return'; maxPct?: number; documentId?: string; then: (token: string) => void } | null>(null)
  const token = useRef(initialToken)
  const syncing = useRef(false)
  const searchRef = useRef<HTMLInputElement>(null)

  // ---------------------------------------------------------------- persistence
  useEffect(() => {
    setDevice(deviceId())
    const saved = load<{ shift: Shift | null; block: Block | null }>(businessId, 'shift', { shift: null, block: null })
    setShift(saved.shift)
    setBlock(saved.block)
    setQueue(load<Queued[]>(businessId, 'queue', []))
    setDone(load(businessId, 'done', {}))
    setHolds(load<Held[]>(businessId, 'holds', []))
    setCart(load<Cart>(businessId, 'cart', emptyCart()))
    if (saved.shift) setCatalogue(load<Catalogue | null>(businessId, `catalogue.${saved.shift.location_id}`, null))
    const on = () => setOnline(true)
    const off = () => setOnline(false)
    window.addEventListener('online', on)
    window.addEventListener('offline', off)
    setOnline(navigator.onLine)
    return () => { window.removeEventListener('online', on); window.removeEventListener('offline', off) }
  }, [businessId])
  useEffect(() => { if (device) save(businessId, 'shift', { shift, block }) }, [businessId, device, shift, block])
  useEffect(() => { if (device) save(businessId, 'queue', queue) }, [businessId, device, queue])
  useEffect(() => { if (device) save(businessId, 'done', done) }, [businessId, device, done])
  useEffect(() => { if (device) save(businessId, 'holds', holds) }, [businessId, device, holds])
  useEffect(() => { if (device) save(businessId, 'cart', cart) }, [businessId, device, cart])

  // ---------------------------------------------------------------- API
  const api = useCallback(async <T,>(path: string, init?: { method?: string; body?: unknown; raw?: boolean }): Promise<
    { ok: true; data: T } | { ok: false; status: number; message: string; offline?: boolean }> => {
    const go = (t: string) => fetch(`${apiUrl}/v1/platform/businesses/${businessId}${path}`, {
      method: init?.method ?? 'GET',
      headers: { Authorization: `Bearer ${t}`, 'Content-Type': 'application/json' },
      body: init?.body === undefined ? undefined : JSON.stringify(init.body),
      cache: 'no-store',
    })
    try {
      let res = await go(token.current)
      if (res.status === 401) {
        const fresh = await posToken().catch(() => null)
        if (fresh) { token.current = fresh; res = await go(fresh) }
      }
      setOnline(true)
      if (init?.raw) return res.ok ? { ok: true, data: (await res.text()) as unknown as T } : { ok: false, status: res.status, message: 'Not available' }
      const body = await res.json().catch(() => ({}))
      if (!res.ok) return { ok: false, status: res.status, message: body?.error?.message ?? 'That did not work' }
      return { ok: true, data: body.data as T }
    } catch {
      setOnline(false)
      return { ok: false, status: 0, message: 'No connection', offline: true }
    }
  }, [apiUrl, businessId])

  const register = setup.registers.find((r) => r.id === shift?.register_id) ?? null
  const scheme: Scheme = register?.scheme ?? 'regular'
  const ctx = useMemo(() => ({ scheme, inclusive: setup.profile?.prices_include_tax ?? false, intraState: true, roundOff: setup.profile?.round_off ?? false }), [scheme, setup.profile])
  const items = catalogue?.items ?? []

  const refreshCatalogue = useCallback(async (locationId: string) => {
    const r = await api<Catalogue>(`/pos/catalogue?location_id=${locationId}`)
    if (r.ok) { setCatalogue(r.data); save(businessId, `catalogue.${locationId}`, r.data) }
  }, [api, businessId])

  // ---------------------------------------------------------------- sync (§14.2)
  const syncNow = useCallback(async () => {
    if (syncing.current || !device) return
    const waiting = queue.filter((q) => q.status !== 'rejected')
    if (!waiting.length) return
    syncing.current = true
    try {
      const r = await api<{ results: { client_mutation_id: string; status: string; reason?: string; number?: string; document_id?: string; share_token?: string }[] }>(
        '/sync', { method: 'POST', body: { device_id: device, mutations: waiting.map(({ client_mutation_id, kind, payload, client_created_at }) => ({ client_mutation_id, kind, payload, client_created_at })) } })
      if (!r.ok) return
      const byId = new Map(r.data.results.map((x) => [x.client_mutation_id, x]))
      setDone((d) => {
        const next = { ...d }
        for (const x of r.data.results) if (x.status === 'applied' && x.document_id) next[x.client_mutation_id] = { number: x.number ?? '', document_id: x.document_id, share_token: x.share_token }
        return next
      })
      setQueue((q) => q.flatMap((m) => {
        const res = byId.get(m.client_mutation_id)
        if (!res) return [m]
        if (res.status === 'applied') return []
        return [{ ...m, status: 'rejected' as const, reason: res.reason }]
      }))
      const rejected = r.data.results.filter((x) => x.status === 'rejected')
      if (rejected.length) setNotice({ text: `${rejected.length} not accepted: ${rejected[0].reason}`, bad: true })
    } finally {
      syncing.current = false
    }
  }, [api, device, queue])

  useEffect(() => {
    const t = setInterval(() => { if (navigator.onLine) void syncNow() }, 4000)
    return () => clearInterval(t)
  }, [syncNow])

  // Top up the register's numbers once everything has synced.
  useEffect(() => {
    if (!shift || !online || queue.some((q) => q.status !== 'rejected') || numbersLeft(block) >= 10) return
    void api<Block>(`/pos/shifts/${shift.id}/block`, { method: 'POST' }).then((r) => { if (r.ok) setBlock(r.data) })
  }, [api, block, online, queue, shift])

  // ---------------------------------------------------------------- shift
  const [openForm, setOpenForm] = useState({ register: initialSetup.registers.find((r) => !r.open_shift || r.open_shift)?.id ?? '', cash: '' })
  const openShift = async () => {
    const r = await api<{ shift: Shift; block: Block }>('/pos/shifts', { method: 'POST', body: { register_id: openForm.register, device_id: device, opening_cash: Number(openForm.cash || 0) } })
    if (!r.ok) return setNotice({ text: r.message, bad: true })
    setShift(r.data.shift)
    setBlock(r.data.block)
    await refreshCatalogue(r.data.shift.location_id)
    setNotice({ text: 'Shift open' })
  }

  // ---------------------------------------------------------------- cart
  const add = (item: PosItem, opts: { variant?: PosVariant; pack?: PosPack; quantity?: number } = {}) => {
    if (!opts.variant && !opts.pack && (item.variants.length || item.packs.length) && opts.quantity === undefined) {
      setChoose(item)
      setPanel('choose')
      return
    }
    const unitPrice = opts.pack?.price ?? opts.variant?.price ?? item.price
    setCart((c) => {
      const same = c.lines.find((l) => l.item.id === item.id && l.variant?.id === opts.variant?.id && l.pack?.label === opts.pack?.label && !item.price_per)
      if (same && opts.quantity === undefined) return { ...c, lines: c.lines.map((l) => (l === same ? { ...l, quantity: l.quantity + 1 } : l)) }
      return { ...c, lines: [...c.lines, { key: uid(), item, variant: opts.variant, pack: opts.pack, quantity: opts.quantity ?? 1, unitPrice, discount: 0 }] }
    })
    setPanel(null)
    setQuery('')
    searchRef.current?.focus()
  }
  const setLine = (key: string, patch: Partial<CartLine>) => setCart((c) => ({ ...c, lines: c.lines.map((l) => (l.key === key ? { ...l, ...patch } : l)).filter((l) => l.quantity > 0) }))

  const bill = useMemo(() => compute(cart.lines.map((l) => ({ quantity: l.quantity, unitPrice: l.unitPrice, rate: l.item.rate, discount: l.discount })), ctx, cart.billDiscount), [cart, ctx])
  const grossPaise = cart.lines.reduce((s, l) => s + Math.round(toPaise(l.unitPrice) * l.quantity), 0)
  const discountPct = grossPaise > 0 ? ((cart.lines.reduce((s, l) => s + toPaise(l.discount), 0) + toPaise(cart.billDiscount)) * 100) / grossPaise : 0
  const needsApproval = setup.discount_cap !== null && discountPct > (setup.discount_cap ?? 0) + 1e-9 && !cart.approval
  const noRate = scheme === 'regular' ? cart.lines.filter((l) => l.item.rate === null).map((l) => l.item.title) : []

  const onScan = (e: React.FormEvent) => {
    e.preventDefault()
    const hit = resolveCode(query, items, setup.settings.weighed_label)
    if (hit) return add(hit.item, { variant: hit.variant, quantity: hit.quantity })
    const matches = items.filter((i) => i.title.toLowerCase().includes(query.toLowerCase()))
    if (matches.length === 1) return add(matches[0])
    if (!matches.length) setNotice({ text: `Nothing matches “${query}”`, bad: true })
  }
  const shown = query ? items.filter((i) => i.title.toLowerCase().includes(query.toLowerCase()) || i.sku === query || i.barcode === query) : items

  const hold = () => {
    if (!cart.lines.length) return
    setHolds((h) => [...h, { id: uid(), label: cart.customer.name || `Bill ${h.length + 1}`, at: new Date().toISOString(), cart }])
    setCart(emptyCart())
    setNotice({ text: 'Bill held' })
  }
  const recall = (h: Held) => {
    if (cart.lines.length) setHolds((x) => [...x.filter((y) => y.id !== h.id), { id: uid(), label: cart.customer.name || 'Current bill', at: new Date().toISOString(), cart }])
    else setHolds((x) => x.filter((y) => y.id !== h.id))
    setCart(h.cart as Cart)
    setPanel(null)
  }

  // ---------------------------------------------------------------- pay
  const [tenders, setTenders] = useState<Tender[]>([])
  const [tab, setTab] = useState<Tender['method']>('cash')
  const [amount, setAmount] = useState('')
  const [ref, setRef] = useState('')
  const [qr, setQr] = useState<string | null>(null)
  const paid = tenders.reduce((s, t) => s + toPaise(t.amount), 0)
  const remaining = Math.max(0, bill.total - paid)
  const cashGiven = tenders.filter((t) => t.method === 'cash').reduce((s, t) => s + toPaise(t.amount), 0)
  const change = Math.max(0, paid - bill.total)
  const canComplete = paid >= bill.total && change <= cashGiven && cart.lines.length > 0

  const startPay = () => {
    setTenders([])
    setAmount((bill.total / 100).toFixed(2))
    setTab('cash')
    setQr(null)
    setPanel('pay')
  }
  useEffect(() => {
    if (panel !== 'pay' || tab !== 'upi' || !online || !setup.settings.upi_vpa || remaining <= 0) { setQr(null); return }
    let url: string | null = null
    void api<string>(`/pos/upi-qr?amount=${(remaining / 100).toFixed(2)}&note=Bill`, { raw: true }).then((r) => {
      if (r.ok) { url = URL.createObjectURL(new Blob([r.data], { type: 'image/svg+xml' })); setQr(url) }
    })
    return () => { if (url) URL.revokeObjectURL(url) }
  }, [api, online, panel, remaining, setup.settings.upi_vpa, tab])

  const addTender = (t: Tender) => { setTenders((x) => [...x, t]); setAmount(''); setRef('') }

  const tabs: Tender['method'][] = setup.khata ? ['cash', 'upi', 'card', 'khata'] : ['cash', 'upi', 'card']
  const requestApproval: Approve = async (action, approver, pin, extra) => {
    const r = await api<{ token: string }>('/pos/approve', { method: 'POST', body: { approver_id: approver, pin, action, ...extra } })
    return r.ok ? { token: r.data.token } : { error: r.message }
  }

  const complete = () => {
    if (!shift || !register) return
    const { block: nextBlock, used } = takeNumber(block)
    const clientId = uid()
    const now = new Date().toISOString()
    const payload = {
      shift_id: shift.id, client_bill_id: clientId, catalogue_version: catalogue?.version, sold_at: now, sold_offline: !online,
      lines: cart.lines.map((l) => ({ offering_id: l.item.id, variant_id: l.variant?.id, quantity: l.quantity, unit_price: l.unitPrice, discount: l.discount || undefined, options: l.pack ? { pack: l.pack.label } : undefined })),
      bill_discount: cart.billDiscount || undefined,
      customer: cart.customer.phone || cart.customer.name || cart.customer.gstin ? { name: cart.customer.name || undefined, phone: cart.customer.phone || undefined, gstin: cart.customer.gstin || undefined } : undefined,
      tenders, number: used ? { block_id: used.block_id, value: used.value } : undefined, approval: cart.approval,
      credit_approval: tenders.some((t) => t.method === 'khata') ? cart.creditApproval : undefined,
    }
    setQueue((q) => [...q, { client_mutation_id: clientId, kind: 'pos.sale', payload, client_created_at: now, label: used?.number ?? 'Bill (number on sync)' }])
    setBlock(nextBlock)
    setReceipt({
      clientId, number: used?.number ?? null, at: now, register: `${register.name} · ${register.location_name}`, seller: register.seller,
      kind: scheme === 'regular' ? 'Tax invoice' : scheme === 'composition' ? 'Bill of supply' : 'Bill',
      lines: cart.lines.map((l, i) => ({ title: l.item.title + (l.variant ? ` — ${l.variant.name}` : '') + (l.pack ? ` — ${l.pack.label}` : ''), qty: qtyText(l), total: bill.lines[i].total })),
      taxable: bill.taxable, cgst: bill.cgst, sgst: bill.sgst, roundOff: bill.roundOff, total: bill.total, tenders, change,
      gst: scheme === 'regular', footer: setup.settings.receipt_footer, phone: cart.customer.phone,
    })
    setCart(emptyCart())
    setPanel('receipt')
    setTimeout(() => void syncNow(), 50)
  }

  // ---------------------------------------------------------------- render
  if (!shift) {
    return (
      <div className="pos-shell">
        <header className="pos-top"><strong>{businessName}</strong><span className="pos-top__spacer" /><Link href={`/b/${businessId}`}>Workspace</Link></header>
        <main className="pos-open">
          <h1>Open the counter</h1>
          {setup.registers.length === 0 ? (
            <p>Add a billing register first (Settings → Tax & invoicing).</p>
          ) : (
            <form onSubmit={(e) => { e.preventDefault(); void openShift() }} className="pos-form">
              <label>Register
                <select value={openForm.register} onChange={(e) => setOpenForm({ ...openForm, register: e.target.value })}>
                  {setup.registers.map((r) => <option key={r.id} value={r.id}>{r.name} · {r.location_name}{r.open_shift ? ' (shift open)' : ''}</option>)}
                </select>
              </label>
              <label>Cash in the drawer now
                <input inputMode="decimal" value={openForm.cash} onChange={(e) => setOpenForm({ ...openForm, cash: e.target.value.replace(/[^\d.]/g, '') })} placeholder="0" autoFocus />
              </label>
              <button type="submit" disabled={!online || !device}>Open shift</button>
              {!online ? <p className="pos-warn">Connect to the internet to open a shift.</p> : null}
            </form>
          )}
          {notice ? <p className={notice.bad ? 'pos-bad' : 'pos-ok'} role="status">{notice.text}</p> : null}
        </main>
      </div>
    )
  }

  const waiting = queue.filter((q) => q.status !== 'rejected')
  const rejected = queue.filter((q) => q.status === 'rejected')
  return (
    <div className="pos-shell">
      <header className="pos-top">
        <strong>{businessName}</strong>
        <span className="pos-top__reg">{register ? `${register.name} · ${register.location_name}` : ''}</span>
        <span className={`pos-pill ${online ? 'is-on' : 'is-off'}`} role="status">{online ? 'Online' : 'Offline — bills are kept on this device'}</span>
        {waiting.length ? <button type="button" className="pos-pill is-wait" onClick={() => void syncNow()}>{waiting.length} to sync</button> : null}
        {rejected.length ? <button type="button" className="pos-pill is-bad" onClick={() => setPanel('bills')}>{rejected.length} need attention</button> : null}
        <span className="pos-top__spacer" />
        <span className="pos-top__numbers" title="Bill numbers this register can use without a connection">{numbersLeft(block)} numbers left</span>
        <button type="button" className="btn-ghost" onClick={() => setPanel('holds')}>Held ({holds.length})</button>
        <button type="button" className="btn-ghost" onClick={() => setPanel('bills')}>Bills</button>
        <button type="button" className="btn-ghost" onClick={() => setPanel('return')}>Return</button>
        {setup.khata ? <button type="button" className="btn-ghost" onClick={() => setPanel('khata')}>Khata</button> : null}
        <button type="button" className="btn-ghost" onClick={() => setPanel('drawer')}>Drawer</button>
        <button type="button" className="btn-ghost" onClick={() => setPanel('close')}>Close shift</button>
      </header>

      <main className="pos-main">
        <section className="pos-items" aria-label="Items">
          <form onSubmit={onScan} className="pos-search">
            <label className="sr-only" htmlFor="pos-q">Scan or search</label>
            <input id="pos-q" ref={searchRef} value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Scan a barcode or type a name" autoFocus autoComplete="off" />
          </form>
          <ul className="pos-grid">
            {shown.slice(0, 60).map((i) => (
              <li key={i.id}>
                <button type="button" onClick={() => add(i)} className="pos-tile">
                  <strong>{i.title}</strong>
                  <span>{rupees(toPaise(i.price))}{i.price_per ? ` / ${i.price_per}` : ''}</span>
                  {i.track_inventory && i.available !== null ? <small className={i.available <= 0 ? 'is-out' : ''}>{i.available <= 0 ? 'None on record' : `${i.available} on record`}</small> : null}
                  {scheme === 'regular' && i.rate === null ? <small className="is-out">No GST rate</small> : null}
                </button>
              </li>
            ))}
          </ul>
          {!items.length ? <p className="pos-muted">{catalogue ? 'No items to sell yet.' : 'Loading the catalogue…'}</p> : null}
        </section>

        <section className="pos-cart" aria-label="Bill">
          <ul className="pos-lines">
            {cart.lines.map((l, i) => (
              <li key={l.key}>
                <div className="pos-line__title">
                  <strong>{l.item.title}{l.variant ? ` — ${l.variant.name}` : ''}{l.pack ? ` — ${l.pack.label}` : ''}</strong>
                  <span>{rupees(toPaise(l.unitPrice))}{l.item.price_per && !l.pack ? ` / ${l.item.price_per}` : ''}{l.discount ? ` · −${rupees(toPaise(l.discount))}` : ''}</span>
                </div>
                <div className="pos-qty">
                  {l.item.price_per && !l.pack ? (
                    <input aria-label={`Quantity of ${l.item.title}`} inputMode="decimal" value={l.quantity} onChange={(e) => setLine(l.key, { quantity: Number(e.target.value) || 0 })} />
                  ) : (
                    <>
                      <button type="button" aria-label="One less" onClick={() => setLine(l.key, { quantity: l.quantity - 1 })}>−</button>
                      <span>{l.quantity}</span>
                      <button type="button" aria-label="One more" onClick={() => setLine(l.key, { quantity: l.quantity + 1 })}>+</button>
                    </>
                  )}
                </div>
                <strong className="pos-line__total">{rupees(bill.lines[i]?.total ?? 0)}</strong>
              </li>
            ))}
          </ul>
          {!cart.lines.length ? <p className="pos-muted">Scan or tap an item to start a bill.</p> : null}
          <details className="pos-extra">
            <summary>Customer and discount</summary>
            <div className="pos-form pos-form--row">
              <label>Phone<input inputMode="tel" value={cart.customer.phone} onChange={(e) => setCart({ ...cart, customer: { ...cart.customer, phone: e.target.value } })} /></label>
              <label>Name<input value={cart.customer.name} onChange={(e) => setCart({ ...cart, customer: { ...cart.customer, name: e.target.value } })} /></label>
              {scheme !== 'unregistered' ? <label>Business GSTIN<input value={cart.customer.gstin} maxLength={15} onChange={(e) => setCart({ ...cart, customer: { ...cart.customer, gstin: e.target.value.toUpperCase() } })} /></label> : null}
              <label>Discount on the bill (₹)<input inputMode="decimal" value={cart.billDiscount || ''} onChange={(e) => setCart({ ...cart, billDiscount: Number(e.target.value.replace(/[^\d.]/g, '')) || 0, approval: undefined })} /></label>
            </div>
            <p className="pos-muted">Your discount limit: {setup.discount_cap === null ? 'none' : `${setup.discount_cap}% of the bill`}.</p>
          </details>
          <dl className="pos-totals">
            {scheme === 'regular' && cart.lines.length ? (<><dt>Taxable</dt><dd>{rupees(bill.taxable)}</dd><dt>CGST</dt><dd>{rupees(bill.cgst)}</dd><dt>SGST</dt><dd>{rupees(bill.sgst)}</dd></>) : null}
            {bill.discount ? (<><dt>Discount</dt><dd>−{rupees(bill.discount)}</dd></>) : null}
            {bill.roundOff ? (<><dt>Round-off</dt><dd>{rupees(bill.roundOff)}</dd></>) : null}
            <dt className="is-total">Total</dt><dd className="is-total" data-testid="pos-total">{rupees(bill.total)}</dd>
          </dl>
          {noRate.length ? <p className="pos-bad">No GST rate yet for {noRate.join(', ')} — ask the owner to set it before billing.</p> : null}
          <div className="pos-actions">
            <button type="button" className="btn-ghost" onClick={hold} disabled={!cart.lines.length}>Hold</button>
            <button type="button" className="btn-ghost" onClick={() => setCart(emptyCart())} disabled={!cart.lines.length}>Clear</button>
            {needsApproval ? (
              <button type="button" onClick={() => { setApproveFor({ action: 'discount', maxPct: Math.ceil(discountPct * 10) / 10, then: (t) => setCart((c) => ({ ...c, approval: t })) }); setPanel('approve') }} disabled={!online}>
                Discount {discountPct.toFixed(1)}% — manager’s PIN
              </button>
            ) : (
              <button type="button" className="pos-pay" onClick={startPay} disabled={!cart.lines.length || noRate.length > 0}>Pay {rupees(bill.total)}</button>
            )}
          </div>
          {notice ? <p className={notice.bad ? 'pos-bad' : 'pos-ok'} role="status">{notice.text}</p> : null}
        </section>
      </main>

      {panel ? (
        <div className="pos-overlay" role="dialog" aria-modal="true" onKeyDown={(e) => { if (e.key === 'Escape' && panel !== 'receipt') setPanel(null) }}>
          <div className="pos-dialog">
            {panel === 'choose' && choose ? (
              <>
                <h2>{choose.title}</h2>
                <div className="pos-choices">
                  {choose.packs.map((p) => <button key={p.label} type="button" onClick={() => add(choose, { pack: p })}>{p.label} · {rupees(toPaise(p.price))}</button>)}
                  {choose.variants.map((v) => <button key={v.id} type="button" onClick={() => add(choose, { variant: v })}>{v.name} · {rupees(toPaise(v.price))}</button>)}
                  {choose.price_per ? <button type="button" onClick={() => add(choose, { quantity: 1 })}>By weight · {rupees(toPaise(choose.price))} / {choose.price_per}</button> : null}
                </div>
                <button type="button" className="btn-ghost" onClick={() => setPanel(null)}>Cancel</button>
              </>
            ) : null}

            {panel === 'pay' ? (
              <>
                <h2>Pay {rupees(bill.total)}</h2>
                <div className="pos-tabs" role="tablist">
                  {tabs.map((t) => <button key={t} type="button" role="tab" aria-selected={tab === t} className={tab === t ? 'is-on' : ''} onClick={() => { setTab(t); setAmount((remaining / 100).toFixed(2)) }}>{TENDER_LABEL[t]}</button>)}
                </div>
                {tab === 'cash' ? (
                  <div className="pos-form">
                    <label>Cash received<input inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value.replace(/[^\d.]/g, ''))} autoFocus /></label>
                    <div className="pos-quick">
                      {[remaining, Math.ceil(remaining / 5000) * 5000, Math.ceil(remaining / 10000) * 10000, Math.ceil(remaining / 50000) * 50000].filter((v, i, a) => v > 0 && a.indexOf(v) === i).map((v) => (
                        <button key={v} type="button" className="btn-ghost" onClick={() => addTender({ method: 'cash', amount: v / 100 })}>{rupees(v)}</button>
                      ))}
                    </div>
                    <button type="button" onClick={() => Number(amount) > 0 && addTender({ method: 'cash', amount: Number(amount) })}>Take cash</button>
                  </div>
                ) : null}
                {tab === 'upi' ? (
                  <div className="pos-form">
                    {/* eslint-disable-next-line @next/next/no-img-element -- a QR drawn from an in-memory SVG */}
                    {qr ? <img className="pos-qr" src={qr} alt={`UPI QR for ${rupees(remaining)}`} /> : null}
                    {!setup.settings.upi_vpa ? <p className="pos-muted">Add your UPI ID in Settings → Counter billing to show a QR.</p> : null}
                    {!online ? <p className="pos-warn">UPI cannot be confirmed without a connection. Take cash, or mark it “UPI to verify”.</p> : <p className="pos-muted">Not confirmed automatically: check the payment arrived before you tap “Paid”.</p>}
                    <label>Reference — optional<input value={ref} onChange={(e) => setRef(e.target.value)} placeholder="UPI reference" /></label>
                    <div className="pos-quick">
                      {online ? <button type="button" onClick={() => addTender({ method: 'upi', amount: remaining / 100, reference: ref || undefined })}>Paid {rupees(remaining)}</button> : null}
                      <button type="button" className="btn-ghost" onClick={() => addTender({ method: 'upi', amount: remaining / 100, reference: ref || undefined, to_verify: true })}>UPI to verify</button>
                    </div>
                  </div>
                ) : null}
                {tab === 'card' ? (
                  <div className="pos-form">
                    <p className="pos-muted">Charge the card on your terminal, then record it here.</p>
                    <label>Amount<input inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value.replace(/[^\d.]/g, ''))} /></label>
                    <label>Approval code or last 4 digits<input value={ref} onChange={(e) => setRef(e.target.value)} /></label>
                    <button type="button" onClick={() => Number(amount) > 0 && addTender({ method: 'card', amount: Number(amount), reference: ref || undefined })}>Record card</button>
                  </div>
                ) : null}
                {tab === 'khata' ? (
                  <KhataTender api={api} online={online} customer={cart.customer} remaining={remaining} approvers={setup.approvers} approve={requestApproval}
                    onCustomer={(c) => setCart((x) => ({ ...x, customer: c }))}
                    onAdd={(paise, token) => {
                      if (token) setCart((x) => ({ ...x, creditApproval: token }))
                      addTender({ method: 'khata', amount: paise / 100 })
                    }} />
                ) : null}
                {tenders.length ? (
                  <ul className="pos-tenders">
                    {tenders.map((t, i) => (
                      <li key={i}><span>{t.method === 'upi' && t.to_verify ? 'UPI (to verify)' : TENDER_LABEL[t.method]}</span><strong>{rupees(toPaise(t.amount))}</strong>
                        <button type="button" className="btn-quiet" onClick={() => setTenders(tenders.filter((_, j) => j !== i))}>Remove</button></li>
                    ))}
                  </ul>
                ) : null}
                <dl className="pos-totals">
                  <dt>Still to pay</dt><dd>{rupees(remaining)}</dd>
                  {change ? (<><dt className="is-total">Change</dt><dd className="is-total">{rupees(change)}</dd></>) : null}
                </dl>
                {change > cashGiven ? <p className="pos-bad">Change can only come from cash.</p> : null}
                <div className="pos-actions">
                  <button type="button" className="btn-ghost" onClick={() => setPanel(null)}>Back</button>
                  <button type="button" className="pos-pay" disabled={!canComplete} onClick={complete}>Complete sale</button>
                </div>
              </>
            ) : null}

            {panel === 'receipt' && receipt ? (
              <ReceiptPanel r={receipt} done={done[receipt.clientId]} billBase={billBase} businessName={businessName}
                onNext={() => { setPanel(null); setReceipt(null); searchRef.current?.focus() }} />
            ) : null}

            {panel === 'approve' && approveFor ? (
              <ApprovePanel approvers={setup.approvers} online={online} action={approveFor.action}
                onCancel={() => setPanel(null)}
                onApprove={async (approver, pin) => {
                  const r = await requestApproval(approveFor.action, approver, pin, { max_discount_pct: approveFor.maxPct })
                  if ('error' in r) return r.error
                  approveFor.then(r.token)
                  setPanel(null)
                  setNotice({ text: 'Approved' })
                  return null
                }} />
            ) : null}

            {panel === 'holds' ? (
              <>
                <h2>Held bills</h2>
                {holds.length ? (
                  <ul className="pos-list">
                    {holds.map((h) => <li key={h.id}><span>{h.label} · {new Date(h.at).toLocaleTimeString('en-IN', { hour: 'numeric', minute: '2-digit' })}</span><button type="button" onClick={() => recall(h)}>Recall</button></li>)}
                  </ul>
                ) : <p className="pos-muted">No held bills.</p>}
                <button type="button" className="btn-ghost" onClick={() => setPanel(null)}>Close</button>
              </>
            ) : null}

            {panel === 'khata' ? (
              <KhataPayPanel api={api} online={online} onCancel={() => setPanel(null)} onPay={(account, value, method, reference) => {
                const label = `Khata payment ${rupees(toPaise(value))} — ${account.display_name}`
                setQueue((q) => [...q, { client_mutation_id: uid(), kind: 'pos.khata_payment', payload: { shift_id: shift.id, account_id: account.id, amount: value, method, reference }, client_created_at: new Date().toISOString(), label }])
                setPanel(null)
                setNotice({ text: `${label} recorded` })
                setTimeout(() => void syncNow(), 50)
              }} />
            ) : null}

            {panel === 'drawer' ? (
              <DrawerPanel kinds={setup.cash_kinds} onCancel={() => setPanel(null)} onSave={(kind, value, reason) => {
                const clientId = uid()
                setQueue((q) => [...q, { client_mutation_id: clientId, kind: 'pos.cash', payload: { shift_id: shift.id, kind, amount: value, reason }, client_created_at: new Date().toISOString(), label: `${setup.cash_kinds[kind]} ${rupees(toPaise(value))}` }])
                setPanel(null)
                setNotice({ text: `${setup.cash_kinds[kind]} recorded` })
                setTimeout(() => void syncNow(), 50)
              }} />
            ) : null}

            {panel === 'bills' ? (
              <BillsPanel api={api} shift={shift} queue={queue} onDismiss={(id) => setQueue((q) => q.filter((x) => x.client_mutation_id !== id))}
                onClose={() => setPanel(null)} businessId={businessId} approvers={setup.approvers} online={online} approve={requestApproval}
                onVoid={(documentId, number, reason, approval) => {
                  setQueue((q) => [...q, { client_mutation_id: uid(), kind: 'pos.void', payload: { document_id: documentId, reason, approval }, client_created_at: new Date().toISOString(), label: `Void ${number}` }])
                  setNotice({ text: `Void of ${number} recorded` })
                  setPanel(null)
                  setTimeout(() => void syncNow(), 50)
                }} />
            ) : null}

            {panel === 'return' ? (
              <ReturnPanel api={api} online={online} windowDays={setup.settings.return_window_days} onCancel={() => setPanel(null)}
                approvers={setup.approvers} approve={requestApproval}
                onReturn={(payload) => {
                  setQueue((q) => [...q, { client_mutation_id: uid(), kind: 'pos.return', payload: { ...payload, shift_id: shift.id }, client_created_at: new Date().toISOString(), label: `Return ${payload.number}` }])
                  setPanel(null)
                  setNotice({ text: 'Return recorded — credit note on sync' })
                  setTimeout(() => void syncNow(), 50)
                }} />
            ) : null}

            {panel === 'close' ? (
              <ClosePanel api={api} shift={shift} waiting={waiting.length} online={online} lastUsed={block ? (block.next_block && block.next > block.end ? block.next_block.next - 1 : block.next - 1) : null}
                onSync={() => void syncNow()} onCancel={() => setPanel(null)}
                onClosed={() => { setShift(null); setBlock(null); setPanel(null); setNotice({ text: 'Shift closed' }) }} />
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  )
}

// ------------------------------------------------------------------ receipt
function ReceiptPanel({ r, done, billBase, businessName, onNext }: {
  r: Receipt; done?: { number: string; document_id: string; share_token?: string }; billBase: string; businessName: string; onNext: () => void
}) {
  const number = done?.number || r.number
  const name = r.seller.trade_name || r.seller.legal_name || businessName
  const link = done?.share_token && billBase ? `${billBase}${done.share_token}` : null
  const printText = () => {
    const w = 32 as const
    const lines = [
      { text: name, bold: true, center: true },
      ...(r.seller.gstin && r.gst ? [{ text: `GSTIN ${r.seller.gstin}`, center: true }] : []),
      { text: `${r.kind} ${number ?? ''}`, center: true },
      { text: new Date(r.at).toLocaleString('en-IN'), center: true },
      { text: '-'.repeat(w) },
      ...r.lines.map((l) => ({ text: pad(`${l.title.slice(0, 18)} x${l.qty}`, rupees(l.total), w) })),
      { text: '-'.repeat(w) },
      ...(r.gst ? [{ text: pad('Taxable', rupees(r.taxable), w) }, { text: pad('CGST', rupees(r.cgst), w) }, { text: pad('SGST', rupees(r.sgst), w) }] : []),
      ...(r.roundOff ? [{ text: pad('Round-off', rupees(r.roundOff), w) }] : []),
      { text: pad('TOTAL', rupees(r.total), w), bold: true },
      ...r.tenders.filter((t) => t.method === 'khata').map((t) => ({ text: pad('On khata', rupees(toPaise(t.amount)), w) })),
      ...(r.change ? [{ text: pad('Change', rupees(r.change), w) }] : []),
      ...(r.seller.declaration && !r.gst ? [{ text: r.seller.declaration }] : []),
      ...(r.footer ? [{ text: r.footer, center: true }] : []),
    ]
    return receiptBytes({ width: w, lines }, { kick: r.tenders.some((t) => t.method === 'cash') })
  }
  return (
    <>
      <div className="pos-receipt-head">
        <h2>{r.change ? `Change ${rupees(r.change)}` : r.tenders.some((t) => t.method === 'khata') ? 'On khata' : 'Paid'}</h2>
        <p>{r.kind} {number ?? '— number given when this bill syncs'} · {rupees(r.total)}</p>
        <p className="pos-muted">{done ? 'Saved to LOCAH.' : 'Kept on this device until it syncs.'}</p>
      </div>
      <div className="pos-actions">
        <button type="button" className="btn-ghost" onClick={() => window.print()}>Print receipt</button>
        {canPrintDirect() ? <button type="button" className="btn-ghost" onClick={() => void printDirect(printText()).catch(() => undefined)}>Receipt printer</button> : null}
        {link ? (
          <a className="btn btn-ghost" target="_blank" rel="noreferrer"
            href={`https://wa.me/${r.phone.replace(/[^\d]/g, '')}?text=${encodeURIComponent(`Your bill from ${name}: ${r.kind} ${number} for ${rupees(r.total)}. ${link}`)}`}>
            Send on WhatsApp
          </a>
        ) : <span className="pos-muted">WhatsApp link once synced</span>}
        <button type="button" className="pos-pay" onClick={onNext} autoFocus>New sale</button>
      </div>
      <div className="pos-receipt-print" aria-hidden="true">
        <p className="c b">{name}</p>
        {r.seller.address ? <p className="c">{r.seller.address}</p> : null}
        {r.seller.gstin && r.gst ? <p className="c">GSTIN {r.seller.gstin}</p> : null}
        <p className="c b">{r.kind} {number ?? ''}</p>
        <p className="c">{new Date(r.at).toLocaleString('en-IN')} · {r.register}</p>
        <hr />
        {r.lines.map((l, i) => <p key={i} className="row"><span>{l.title} × {l.qty}</span><span>{rupees(l.total)}</span></p>)}
        <hr />
        {r.gst ? (<><p className="row"><span>Taxable</span><span>{rupees(r.taxable)}</span></p><p className="row"><span>CGST</span><span>{rupees(r.cgst)}</span></p><p className="row"><span>SGST</span><span>{rupees(r.sgst)}</span></p></>) : null}
        {r.roundOff ? <p className="row"><span>Round-off</span><span>{rupees(r.roundOff)}</span></p> : null}
        <p className="row b"><span>Total</span><span>{rupees(r.total)}</span></p>
        {r.tenders.map((t, i) => <p key={i} className="row"><span>{t.method === 'khata' ? 'On khata' : TENDER_LABEL[t.method]}</span><span>{rupees(toPaise(t.amount))}</span></p>)}
        {r.change ? <p className="row"><span>Change</span><span>{rupees(r.change)}</span></p> : null}
        {!r.gst && r.seller.declaration ? <p>{r.seller.declaration}</p> : null}
        {r.footer ? <p className="c">{r.footer}</p> : null}
      </div>
    </>
  )
}

// ------------------------------------------------------------------ approval
function ApprovePanel({ approvers, online, action, onApprove, onCancel }: {
  approvers: { identity_id: string; name: string }[]; online: boolean; action: string
  onApprove: (approver: string, pin: string) => Promise<string | null>; onCancel: () => void
}) {
  const [who, setWho] = useState(approvers[0]?.identity_id ?? '')
  const [pin, setPin] = useState('')
  const [error, setError] = useState<string | null>(null)
  const what = action === 'discount' ? 'this discount' : action === 'void' ? 'cancelling this bill'
    : action === 'credit' ? 'credit above their khata limit' : 'this late return'
  return (
    <form className="pos-form" onSubmit={async (e) => { e.preventDefault(); setError(await onApprove(who, pin)); setPin('') }}>
      <h2>A manager approves {what}</h2>
      {!online ? <p className="pos-warn">Approvals need a connection.</p> : null}
      {!approvers.length ? <p className="pos-warn">No manager has set an approval PIN yet (Settings → Counter billing).</p> : (
        <>
          <label>Manager<select value={who} onChange={(e) => setWho(e.target.value)}>{approvers.map((a) => <option key={a.identity_id} value={a.identity_id}>{a.name}</option>)}</select></label>
          <label>PIN<input type="password" inputMode="numeric" autoComplete="off" maxLength={6} value={pin} onChange={(e) => setPin(e.target.value.replace(/\D/g, ''))} autoFocus /></label>
        </>
      )}
      {error ? <p className="pos-bad" role="alert">{error}</p> : null}
      <div className="pos-actions">
        <button type="button" className="btn-ghost" onClick={onCancel}>Cancel</button>
        <button type="submit" disabled={!online || pin.length < 4 || !who}>Approve</button>
      </div>
    </form>
  )
}

// ------------------------------------------------------------------ drawer
function DrawerPanel({ kinds, onSave, onCancel }: { kinds: Record<string, string>; onSave: (k: string, v: number, reason: string) => void; onCancel: () => void }) {
  const [kind, setKind] = useState(Object.keys(kinds)[0] ?? 'petty_expense')
  const [value, setValue] = useState('')
  const [reason, setReason] = useState('')
  return (
    <form className="pos-form" onSubmit={(e) => { e.preventDefault(); if (Number(value) > 0 && reason.trim()) onSave(kind, Number(value), reason.trim()) }}>
      <h2>Cash in or out of the drawer</h2>
      <label>What<select value={kind} onChange={(e) => setKind(e.target.value)}>{Object.entries(kinds).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
      <label>Amount<input inputMode="decimal" value={value} onChange={(e) => setValue(e.target.value.replace(/[^\d.]/g, ''))} autoFocus /></label>
      <label>For<input value={reason} onChange={(e) => setReason(e.target.value)} maxLength={300} placeholder="e.g. milk for tea" /></label>
      <div className="pos-actions"><button type="button" className="btn-ghost" onClick={onCancel}>Cancel</button><button type="submit">Record</button></div>
    </form>
  )
}

// ------------------------------------------------------------------ bills this shift
type Approve = (action: 'discount' | 'void' | 'return' | 'credit', approver: string, pin: string, extra?: Record<string, unknown>) => Promise<{ token: string } | { error: string }>
type ApiFn = <T>(path: string, init?: { method?: string; body?: unknown; raw?: boolean }) => Promise<{ ok: true; data: T } | { ok: false; status: number; message: string; offline?: boolean }>

function BillsPanel({ api, shift, queue, onVoid, onDismiss, onClose, businessId, approvers, online, approve }: {
  api: ApiFn; shift: Shift; queue: Queued[]; onVoid: (id: string, number: string, reason: string, approval?: string) => void
  onDismiss: (id: string) => void; onClose: () => void; businessId: string
  approvers: { identity_id: string; name: string }[]; online: boolean; approve: Approve
}) {
  const [bills, setBills] = useState<{ id: string; number: string; kind: string; status: string; amount_due: number }[] | null>(null)
  const [pinFor, setPinFor] = useState<{ id: string; number: string } | null>(null)
  useEffect(() => { void api<typeof bills>(`/pos/shifts/${shift.id}/bills`).then((r) => { if (r.ok) setBills(r.data) }) }, [api, shift.id])
  if (pinFor) {
    return (
      <ApprovePanel approvers={approvers} online={online} action="void" onCancel={() => setPinFor(null)}
        onApprove={async (who, pin) => {
          const r = await approve('void', who, pin, { document_id: pinFor.id })
          if ('error' in r) return r.error
          onVoid(pinFor.id, pinFor.number, 'Voided with a manager\'s approval', r.token)
          return null
        }} />
    )
  }
  return (
    <>
      <h2>This shift’s bills</h2>
      {queue.length ? (
        <ul className="pos-list">
          {queue.map((q) => (
            <li key={q.client_mutation_id} className={q.status === 'rejected' ? 'is-bad' : ''}>
              <span>{q.label}{q.status === 'rejected' ? ` — not accepted: ${q.reason}` : ' — waiting to sync'}</span>
              {q.status === 'rejected' ? <button type="button" className="btn-quiet" onClick={() => onDismiss(q.client_mutation_id)}>Dismiss</button> : null}
            </li>
          ))}
        </ul>
      ) : null}
      {bills === null ? <p className="pos-muted">Bills appear here when online.</p> : (
        <ul className="pos-list">
          {bills.map((b) => (
            <li key={b.id}>
              <span>{b.number} · {rupees(toPaise(b.amount_due))}{b.status === 'cancelled' ? ' · cancelled' : ''}{b.kind === 'credit_note' ? ' · return' : ''}</span>
              <span className="pos-list__acts">
                <a className="btn-quiet" href={`/b/${businessId}/invoices/${b.id}/pdf?layout=thermal_80`} target="_blank" rel="noreferrer">Reprint</a>
                {b.status === 'issued' && b.kind !== 'credit_note' ? <button type="button" className="btn-quiet" onClick={() => onVoid(b.id, b.number, 'Voided at the counter')}>Void</button> : null}
                {b.status === 'issued' && b.kind !== 'credit_note' ? <button type="button" className="btn-quiet" onClick={() => setPinFor({ id: b.id, number: b.number })}>Void with PIN</button> : null}
              </span>
            </li>
          ))}
        </ul>
      )}
      <button type="button" className="btn-ghost" onClick={onClose}>Close</button>
    </>
  )
}

// ------------------------------------------------------------------ returns
function ReturnPanel({ api, online, windowDays, onReturn, approvers, approve, onCancel }: {
  api: ApiFn; online: boolean; windowDays: number; onReturn: (p: Record<string, unknown> & { number: string }) => void
  approvers: { identity_id: string; name: string }[]; approve: Approve; onCancel: () => void
}) {
  const [asking, setAsking] = useState(false)
  const [number, setNumber] = useState('')
  const [bill, setBill] = useState<{ id: string; number: string; issue_date: string; on_account?: boolean; lines: { id: string; title: string; returnable_quantity: number; line_total: number; quantity: number }[] } | null>(null)
  const [qty, setQty] = useState<Record<string, string>>({})
  const [method, setMethod] = useState('cash')
  const [restock, setRestock] = useState(true)
  const [approval, setApproval] = useState<string | undefined>()
  const [error, setError] = useState<string | null>(null)
  const find = async () => {
    setError(null)
    const r = await api<{ id: string }[]>(`/invoices?q=${encodeURIComponent(number.trim())}&kind=invoices&status=issued`)
    if (!r.ok) return setError(r.message)
    if (!r.data.length) return setError('No issued bill with that number')
    const d = await api<NonNullable<typeof bill>>(`/invoices/${r.data[0].id}`)
    if (d.ok) {
      setBill(d.data)
      if (d.data.on_account) setMethod('khata')
    }
  }
  const late = bill ? (Date.now() - new Date(`${bill.issue_date}T00:00:00`).getTime()) / 86400000 > windowDays : false
  const chosen = bill ? bill.lines.filter((l) => Number(qty[l.id] || 0) > 0) : []
  if (asking) {
    return (
      <ApprovePanel approvers={approvers} online={online} action="return" onCancel={() => setAsking(false)}
        onApprove={async (who, pin) => {
          const r = await approve('return', who, pin)
          if ('error' in r) return r.error
          setApproval(r.token)
          setAsking(false)
          return null
        }} />
    )
  }
  return (
    <div className="pos-form">
      <h2>Return</h2>
      {!bill ? (
        <form onSubmit={(e) => { e.preventDefault(); void find() }} className="pos-form">
          <label>Bill number<input value={number} onChange={(e) => setNumber(e.target.value)} autoFocus placeholder="e.g. CHN1/26-27/00012" /></label>
          {!online ? <p className="pos-warn">Finding a bill needs a connection.</p> : null}
          <div className="pos-actions"><button type="button" className="btn-ghost" onClick={onCancel}>Cancel</button><button type="submit" disabled={!online || !number.trim()}>Find</button></div>
        </form>
      ) : (
        <>
          <p>{bill.number}{late ? ` · past the ${windowDays}-day return window` : ''}</p>
          <ul className="pos-list">
            {bill.lines.map((l) => (
              <li key={l.id}><span>{l.title} (up to {l.returnable_quantity})</span>
                <input aria-label={`Return quantity for ${l.title}`} inputMode="decimal" value={qty[l.id] ?? ''} onChange={(e) => setQty({ ...qty, [l.id]: e.target.value.replace(/[^\d.]/g, '') })} placeholder="0" /></li>
            ))}
          </ul>
          <label>Refund in<select value={method} onChange={(e) => setMethod(e.target.value)}>
            {bill.on_account ? <option value="khata">Back to their khata</option> : null}
            <option value="cash">Cash from the drawer</option><option value="upi">UPI</option><option value="card">Card</option>
          </select></label>
          <label className="pos-check"><input type="checkbox" checked={restock} onChange={(e) => setRestock(e.target.checked)} /> Put the items back in stock</label>
          {error ? <p className="pos-bad">{error}</p> : null}
          <div className="pos-actions">
            <button type="button" className="btn-ghost" onClick={onCancel}>Cancel</button>
            {late && !approval ? <button type="button" onClick={() => setAsking(true)}>Manager’s PIN</button> : (
              <button type="button" disabled={!chosen.length} onClick={() => onReturn({ number: bill.number, document_id: bill.id, refund_method: method, restock, approval,
                lines: chosen.map((l) => ({ original_line_id: l.id, quantity: Number(qty[l.id]) })) })}>Take the return</button>
            )}
          </div>
        </>
      )}
    </div>
  )
}

// ------------------------------------------------------------------ close
function ClosePanel({ api, shift, waiting, online, lastUsed, onSync, onCancel, onClosed }: {
  api: ApiFn; shift: Shift; waiting: number; online: boolean; lastUsed: number | null; onSync: () => void; onCancel: () => void; onClosed: () => void
}) {
  const [s, setS] = useState<Summary | null>(null)
  const [counted, setCounted] = useState('')
  const [note, setNote] = useState('')
  const [result, setResult] = useState<{ expected: number; counted: number; variance: number } | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => { void api<Shift>(`/pos/shifts/${shift.id}`).then((r) => { if (r.ok) setS(r.data.summary ?? null) }) }, [api, shift.id, waiting])
  if (result) {
    return (
      <div className="pos-form">
        <h2>Shift closed</h2>
        <dl className="pos-totals">
          <dt>Expected in the drawer</dt><dd>{rupees(toPaise(result.expected))}</dd>
          <dt>Counted</dt><dd>{rupees(toPaise(result.counted))}</dd>
          <dt className="is-total">{result.variance === 0 ? 'Drawer balances' : result.variance < 0 ? 'Short by' : 'Over by'}</dt>
          <dd className="is-total">{rupees(toPaise(Math.abs(result.variance)))}</dd>
        </dl>
        <button type="button" onClick={onClosed}>Done</button>
      </div>
    )
  }
  return (
    <form className="pos-form" onSubmit={async (e) => {
      e.preventDefault()
      const r = await api<{ expected_cash: number; counted_cash: number; variance: number }>(`/pos/shifts/${shift.id}/close`, { method: 'POST', body: { counted_cash: Number(counted || 0), note: note || undefined, last_used: lastUsed ?? undefined } })
      if (!r.ok) return setError(r.message)
      setResult({ expected: r.data.expected_cash, counted: r.data.counted_cash, variance: r.data.variance })
    }}>
      <h2>Close the shift</h2>
      {waiting ? <p className="pos-warn">{waiting} bills on this device have not synced yet. <button type="button" className="btn-quiet" onClick={onSync}>Sync now</button></p> : null}
      {s ? (
        <dl className="pos-totals">
          <dt>Opening cash</dt><dd>{rupees(toPaise(s.opening_cash))}</dd>
          <dt>Cash sales</dt><dd>{rupees(toPaise(s.cash_sales))}</dd>
          {s.khata_cash ? (<><dt>Khata paid in cash</dt><dd>{rupees(toPaise(s.khata_cash))}</dd></>) : null}
          {s.cash_in ? (<><dt>Cash put in</dt><dd>{rupees(toPaise(s.cash_in))}</dd></>) : null}
          {s.refunds ? (<><dt>Cash refunds</dt><dd>−{rupees(toPaise(s.refunds))}</dd></>) : null}
          {s.petty_expenses ? (<><dt>Petty expenses</dt><dd>−{rupees(toPaise(s.petty_expenses))}</dd></>) : null}
          {s.cash_out ? (<><dt>Cash taken out</dt><dd>−{rupees(toPaise(s.cash_out))}</dd></>) : null}
          <dt className="is-total">Expected in the drawer</dt><dd className="is-total">{rupees(toPaise(s.expected_cash))}</dd>
          <dt>UPI</dt><dd>{rupees(toPaise(s.upi))}{s.upi_to_verify ? ` (${rupees(toPaise(s.upi_to_verify))} to verify)` : ''}</dd>
          <dt>Card</dt><dd>{rupees(toPaise(s.card))}</dd>
          {s.khata_given || s.khata_received ? (<><dt>Khata</dt><dd>{rupees(toPaise(s.khata_given ?? 0))} given · {rupees(toPaise(s.khata_received ?? 0))} received</dd></>) : null}
          <dt>Bills</dt><dd>{s.bills}{s.voided ? ` · ${s.voided} voided` : ''}{s.returns ? ` · ${s.returns} returns` : ''}</dd>
        </dl>
      ) : null}
      <label>Cash counted in the drawer<input inputMode="decimal" value={counted} onChange={(e) => setCounted(e.target.value.replace(/[^\d.]/g, ''))} autoFocus /></label>
      <label>Note — optional<input value={note} onChange={(e) => setNote(e.target.value)} maxLength={500} /></label>
      {error ? <p className="pos-bad" role="alert">{error}</p> : null}
      <div className="pos-actions">
        <button type="button" className="btn-ghost" onClick={onCancel}>Back</button>
        <button type="submit" disabled={!online || waiting > 0 || counted === ''}>Close shift</button>
      </div>
    </form>
  )
}

// ------------------------------------------------------------------ khata (§14.5)
function useKhataLookup(api: ApiFn, phone: string) {
  const [account, setAccount] = useState<KhataAccount | null | undefined>(undefined)
  const [name, setName] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  useEffect(() => { setAccount(undefined); setName(null); setError(null) }, [phone])
  const lookup = async () => {
    setBusy(true)
    setError(null)
    const r = await api<{ name: string; account: KhataAccount | null } | null>(`/ledger/lookup?phone=${encodeURIComponent(phone.trim())}`)
    setBusy(false)
    if (!r.ok) return setError(r.message)
    setAccount(r.data?.account ?? null)
    setName(r.data?.name ?? null)
  }
  return { account, name, error, busy, lookup }
}

function KhataTender({ api, online, customer, remaining, approvers, approve, onCustomer, onAdd }: {
  api: ApiFn; online: boolean; customer: Customer; remaining: number
  approvers: { identity_id: string; name: string }[]; approve: Approve
  onCustomer: (c: Customer) => void; onAdd: (paise: number, approval?: string) => void
}) {
  const k = useKhataLookup(api, customer.phone)
  const [asking, setAsking] = useState(false)
  useEffect(() => { if (k.name && !customer.name) onCustomer({ ...customer, name: k.name }) }, [k.name, customer, onCustomer])
  const room = k.account && k.account.credit_limit !== null ? toPaise(k.account.credit_limit - k.account.balance) : null
  const over = room !== null && remaining > room
  if (asking) {
    return (
      <ApprovePanel approvers={approvers} online={online} action="credit" onCancel={() => setAsking(false)}
        onApprove={async (who, pin) => {
          const r = await approve('credit', who, pin)
          if ('error' in r) return r.error
          setAsking(false)
          onAdd(remaining, r.token)
          return null
        }} />
    )
  }
  return (
    <div className="pos-form">
      {!online ? <p className="pos-warn">Khata needs a connection, to check what they owe.</p> : null}
      <div className="pos-form pos-form--row" style={{ marginTop: 0 }}>
        <label>Customer’s phone<input inputMode="tel" value={customer.phone} onChange={(e) => onCustomer({ ...customer, phone: e.target.value })} autoFocus /></label>
        <label>Name<input value={customer.name} onChange={(e) => onCustomer({ ...customer, name: e.target.value })} /></label>
      </div>
      {k.account === undefined ? (
        <button type="button" className="btn-ghost" disabled={!online || customer.phone.replace(/\D/g, '').length < 8 || k.busy} onClick={() => void k.lookup()}>
          {k.busy ? 'Checking…' : 'Check their khata'}
        </button>
      ) : (
        <p className="pos-muted" role="status">
          {k.account
            ? `${k.account.display_name} owes ${rupees(toPaise(k.account.balance))}${k.account.credit_limit !== null ? ` · limit ${rupees(toPaise(k.account.credit_limit))}` : ' · no limit set'}.`
            : 'No khata yet — this sale opens one.'}
        </p>
      )}
      {over ? <p className="pos-warn">This takes them over their limit ({rupees(Math.max(0, room ?? 0))} left).</p> : null}
      {k.error ? <p className="pos-bad" role="alert">{k.error}</p> : null}
      {k.account !== undefined && remaining > 0 ? (
        <div className="pos-quick">
          {over ? <button type="button" onClick={() => setAsking(true)} disabled={!online}>Over the limit — manager’s PIN</button>
            : <button type="button" disabled={!online} onClick={() => onAdd(remaining)}>Put {rupees(remaining)} on khata</button>}
        </div>
      ) : null}
    </div>
  )
}

function KhataPayPanel({ api, online, onPay, onCancel }: {
  api: ApiFn; online: boolean; onPay: (a: KhataAccount, value: number, method: string, reference?: string) => void; onCancel: () => void
}) {
  const [phone, setPhone] = useState('')
  const k = useKhataLookup(api, phone)
  const [value, setValue] = useState('')
  const [method, setMethod] = useState('cash')
  const [reference, setReference] = useState('')
  useEffect(() => { if (k.account && k.account.balance > 0) setValue(k.account.balance.toFixed(2)) }, [k.account])
  return (
    <form className="pos-form" onSubmit={(e) => {
      e.preventDefault()
      if (k.account && Number(value) > 0) onPay(k.account, Number(value), method, reference || undefined)
    }}>
      <h2>Khata payment</h2>
      <p className="pos-muted">A customer pays off what they owe. Cash goes into this drawer.</p>
      {!online ? <p className="pos-warn">Looking up a khata needs a connection.</p> : null}
      <label>Customer’s phone<input inputMode="tel" value={phone} onChange={(e) => setPhone(e.target.value)} autoFocus /></label>
      {k.account === undefined ? (
        <button type="button" className="btn-ghost" disabled={!online || phone.replace(/\D/g, '').length < 8 || k.busy} onClick={() => void k.lookup()}>
          {k.busy ? 'Checking…' : 'Find their khata'}
        </button>
      ) : k.account ? (
        <>
          <p role="status"><strong>{k.account.display_name}</strong> owes {rupees(toPaise(k.account.balance))}</p>
          <label>Amount paid<input inputMode="decimal" value={value} onChange={(e) => setValue(e.target.value.replace(/[^\d.]/g, ''))} /></label>
          <label>How<select value={method} onChange={(e) => setMethod(e.target.value)}><option value="cash">Cash</option><option value="upi">UPI</option><option value="card">Card</option></select></label>
          {method !== 'cash' ? <label>Reference — optional<input value={reference} onChange={(e) => setReference(e.target.value)} maxLength={120} /></label> : null}
        </>
      ) : <p className="pos-warn" role="status">No khata for this phone number.</p>}
      {k.error ? <p className="pos-bad" role="alert">{k.error}</p> : null}
      <div className="pos-actions">
        <button type="button" className="btn-ghost" onClick={onCancel}>Cancel</button>
        <button type="submit" disabled={!k.account || !(Number(value) > 0)}>Record payment</button>
      </div>
    </form>
  )
}
