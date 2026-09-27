// P1-04 GST invoicing in the browser (Capability Universe §14, §14.4, §14.6).
//  Workspace: the owner answers how they bill, adds their GSTIN and a register,
//  enters a dated rate for an HSN code, bills a website order (CGST + SGST,
//  round-off line), raises a B2B bill to another state (IGST), a return credit
//  note that restocks, records money received, cancels a bill (it keeps its
//  number) and opens the CA's reports and CSV.
//  Tenant site: the customer opens "Your bill from <business>" from the link,
//  in the business's colours, with its PDF. A composition business's bill of
//  supply shows no tax line. Desktop and 390 px.
//
//   CHROME_PATH=/opt/pw-browsers/chromium CHROME_NO_SANDBOX=1 node tools/acceptance/phase_b/p1_04_invoicing.mjs
import { mkdirSync, writeFileSync } from 'node:fs'
import { launch } from '../cdp.mjs'
import { OUT, WEB, WS, api, browser, check, clickUntil, newBusiness, realErrors } from './common.mjs'

const results = []
const shots = `${OUT}/phase_b/p1_04`
mkdirSync(shots, { recursive: true })
const wait = (ms) => new Promise((r) => setTimeout(r, ms))
const C = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
function gstin(state, pan) {
  const body = `${state}${pan}1Z`
  let total = 0
  for (let i = 0; i < 14; i++) {
    const v = C.indexOf(body[i]) * (i % 2 ? 2 : 1)
    total += Math.floor(v / 36) + (v % 36)
  }
  return body + C[(36 - (total % 36)) % 36]
}
const now = new Date()
const fyStart = now.getMonth() >= 3 ? now.getFullYear() : now.getFullYear() - 1
const FY = `${String(fyStart % 100).padStart(2, '0')}-${String((fyStart + 1) % 100).padStart(2, '0')}`
const today = now.toISOString().slice(0, 10)
const tag = Math.random().toString(36).slice(2, 6).toUpperCase()

const biz = await newBusiness({
  name: 'Lakshmi Stores', category: 'fresh_grocery', sub: 'grocery', type: 'retail',
  modules: ['offerings-catalog', 'orders', 'payments', 'inventory', 'fulfilment', 'invoicing'],
})
const base = `/v1/platform/businesses/${biz.id}`
await api(`/v1/b/${biz.id}/marketplace/visibility`, { method: 'POST', body: { visibility: 'unlisted' } })
await api(`/v1/b/${biz.id}/fulfilment/settings`, { method: 'PATCH', body: { pickup_enabled: true } })
const loc = (await api(`${base}/locations`)).data.find((l) => l.is_primary).id
const item = async (body) => (await api(`${base}/products`, { method: 'POST', body: { status: 'active', offering_type: 'product', ...body } })).data
const rice = await item({ title: 'Ponni rice 5 kg', price_amount: 420, hsn_sac: '1006' })
const oil = await item({ title: 'Groundnut oil 1 l', price_amount: 199, hsn_sac: '1508', tax_rate: 18 })
const fan = await item({ title: 'Ceiling fan', price_amount: 2360, hsn_sac: '8414', tax_rate: 18, track_inventory: true })
await api(`${base}/inventory/opening-stock`, { method: 'POST', body: { offering_id: fan.id, location_id: loc, quantity: 6 } })

const owner = await browser()
let orderBillId = ''
let b2bId = ''
try {
  // ---- navigation: Money and Settings carry the invoicing pages
  await owner.goto(`${WS}/b/${biz.id}`)
  await owner.waitFor('Bills & invoices', { text: true })
  const nav = await owner.eval(`document.querySelector('nav, aside').innerText`)
  check(['Bills & invoices', 'Tax rates', 'Reports for your CA', 'Tax & invoicing'].every((x) => nav.includes(x)), 'Money area lists bills, tax rates and CA reports; Settings has Tax & invoicing', results)

  // ---- 1. Tax & invoicing setup
  await owner.goto(`${WS}/b/${biz.id}/settings/invoicing`)
  await owner.waitFor('Still to do', { text: true })
  const needs = await owner.eval(`[...document.querySelectorAll('.bos-inv-needs li')].map(l => l.innerText)`)
  check(needs.length === 3, `setup lists what is still to do (${needs.length})`, results)
  check(await owner.eval(`document.body.innerText.includes('Confirm with your CA')`), 'tax-treatment questions say "Confirm with your CA"', results)
  await owner.shot(`${shots}/01-setup-empty.png`, { full: true })
  await owner.eval(`(() => { const pick = (name, i) => document.querySelectorAll('input[name=' + name + ']')[i].click(); pick('incl', 0); pick('round', 0); pick('issue', 1); return true })()`)
  await owner.click('Save', { byText: true })
  await owner.waitFor('Saved', { text: true })
  const gst = gstin('33', `AA${tag}L1234K`.slice(0, 10))
  await owner.type('.bos-inv-form input[maxlength="15"]', gst)
  await owner.eval(`(() => { const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; const labs = [...document.querySelectorAll('.bos-inv-form label')]; const f = (t, v) => { const i = labs.find(l => l.innerText.startsWith(t)).querySelector('input'); set.call(i, v); i.dispatchEvent(new Event('input', { bubbles: true })) }; f('Legal name', 'Lakshmi Stores Private Limited'); f('Trade name', 'Lakshmi Stores'); return true })()`)
  await owner.click('Add registration', { byText: true })
  await owner.waitFor('Registration added', { text: true })
  await owner.waitFor('.bos-inv-regs li')
  await owner.waitFor('Digits in the number', { text: true })
  await owner.click('Add register', { byText: true })
  await owner.waitFor('Billing is set up', { text: true })
  const sample = await owner.eval(`document.querySelector('.bos-inv-regs code')?.innerText || [...document.querySelectorAll('.bos-inv-regs code')].map(c=>c.innerText).join()`)
  const registers = (await api(`${base}/invoicing/setup`)).data.registers
  check(registers.length === 1 && registers[0].sample_number.endsWith(`/${FY}/00001`), `register added; next number ${registers[0]?.sample_number} (page shows ${sample})`, results)
  await owner.shot(`${shots}/02-setup-done.png`, { full: true })

  // ---- 2. Tax rates: rice has no rate until the owner enters one
  await owner.goto(`${WS}/b/${biz.id}/invoices/tax-rates`)
  await owner.waitFor('no GST rate yet', { text: true })
  check(await owner.eval(`document.querySelector('.bos-inv-needs').innerText.includes('Ponni rice')`), 'items without a rate are named', results)
  await owner.type('.bos-inv-form input[inputmode="numeric"]', '1006')
  await owner.eval(`(() => { const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; const l = [...document.querySelectorAll('.bos-inv-form label')].find(x => x.innerText.startsWith('GST %')); const i = l.querySelector('input'); set.call(i, '5'); i.dispatchEvent(new Event('input', { bubbles: true })); return true })()`)
  await owner.click('Add rate', { byText: true })
  await owner.waitFor('Rate added', { text: true })
  await owner.waitFor('In force', { text: true })
  const riceToday = await owner.eval(`[...document.querySelectorAll('tbody tr')].find(r => r.innerText.includes('Ponni rice'))?.innerText`)
  check(/5%/.test(riceToday || '') && !(await owner.eval(`!!document.querySelector('.bos-inv-needs')`)), `rice now charges 5% from the HSN rate (${(riceToday || '').replace(/\s+/g, ' ')})`, results)
  await owner.shot(`${shots}/03-tax-rates.png`, { full: true })

  // ---- 3. A website order, billed from the order page
  const placed = await fetch(`http://localhost:8010/v1/public/websites/${biz.slug}/checkout`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ items: [{ offering_id: rice.id, quantity: 1 }, { offering_id: oil.id, quantity: 2 }],
      fulfilment_mode: 'pickup', payment_method: 'cod', guest: { name: 'Meena', email: `meena-${tag}@example.com`, phone: '+919840000001' } }),
  }).then((r) => r.json())
  const order = placed.data.order
  check(Number(order.total_amount) === 818, `prices include GST: the customer pays the shelf price (${order.total_amount})`, results)
  await owner.goto(`${WS}/b/${biz.id}/orders/${order.id}`)
  await owner.waitFor('Not billed yet', { text: true })
  const orderTax = await owner.text('.bos-inv-ordertax')
  check(orderTax.includes('CGST + SGST') && orderTax.includes('included in prices'), 'order shows its GST split, included in prices', results)
  await clickUntil(owner, 'Issue bill', '.bos-bill')
  await owner.waitFor(`/${FY}/00001`, { text: true })
  orderBillId = (await owner.eval('location.pathname')).split('/').pop()
  const bill = (await api(`${base}/invoices/${orderBillId}`)).data
  check(bill.doc_kind === 'tax_invoice' && bill.amount_due === 818 && bill.cgst_total === bill.sgst_total && bill.igst_total === 0,
    `order billed as a tax invoice: ${bill.number}, CGST ${bill.cgst_total} = SGST ${bill.sgst_total}, total ${bill.amount_due}`, results)
  const heads = await owner.eval(`[...document.querySelectorAll('.bos-bill__lines th')].map(t => t.innerText.toUpperCase())`)
  check(['HSN/SAC', 'TAXABLE', 'GST %', 'CGST', 'SGST'].every((h) => heads.includes(h)) && !heads.includes('IGST'), `same-state bill shows CGST and SGST columns (${heads.join(', ')})`, results)
  const totals = await owner.text('.bos-bill__totals')
  check(totals.includes('Taxable value') && totals.includes('CGST') && totals.includes('SGST'), 'totals list taxable value and each tax', results)
  await owner.shot(`${shots}/04-order-bill.png`, { full: true })

  // ---- 4. The customer's link
  await owner.click('Copy customer link', { byText: true })
  await owner.waitFor('.bos-inv-link')
  const link = await owner.eval(`document.querySelector('.bos-inv-link').value`)
  check(link.startsWith(`${WEB}/${biz.slug}/bill/`), `customer link is on the business's site (${link})`, results)
  const pdf = await owner.eval(`fetch('/b/${biz.id}/invoices/${orderBillId}/pdf?layout=thermal_80').then(r => r.headers.get('content-type') + '|' + r.status)`)
  check(pdf === 'application/pdf|200', `bill PDF (80 mm) downloads from the Workspace (${pdf})`, results)

  const customer = await launch({ width: 390, height: 844, mobile: true })
  try {
    await customer.goto(link)
    await customer.waitFor('Your bill from Lakshmi Stores', { text: true })
    const body = await customer.eval('document.body.innerText')
    check(body.includes(bill.number) && body.includes('CGST') && body.includes('₹818.00'), 'customer sees their bill: number, CGST/SGST, total', results)
    const themed = await customer.eval(`getComputedStyle(document.querySelector('[data-locah-site]')).getPropertyValue('--site-primary').trim()`)
    check(Boolean(themed), `bill page uses the business's own theme (--site-primary ${themed})`, results)
    const dl = await customer.eval(`document.querySelector('.ls-bill__actions a').href`)
    const pdfRes = await fetch(dl)
    check(pdfRes.ok && pdfRes.headers.get('content-type') === 'application/pdf', 'customer can download the PDF', results)
    const overflow = await customer.eval('document.documentElement.scrollWidth <= window.innerWidth + 1')
    check(overflow, 'customer bill fits 390 px without sideways scroll', results)
    await customer.shot(`${shots}/05-customer-bill-390.png`, { full: true })
    await customer.goto(`${WEB}/${biz.slug}/bill/${'x'.repeat(32)}`)
    const wrong = await customer.eval('document.body.innerText')
    check(!wrong.includes('Your bill from') && !wrong.includes('₹'), `a wrong link shows no bill (${wrong.replace(/\s+/g, ' ').slice(0, 80)})`, results)
    check(realErrors(customer).length === 0, `no console errors on the customer page (${realErrors(customer).join(' | ').slice(0, 200)})`, results)
  } finally {
    await customer.close()
  }

  // ---- 5. B2B bill to another state (IGST) with stock, raised by hand
  await owner.goto(`${WS}/b/${biz.id}/invoices/new`)
  await owner.waitFor('What was sold', { text: true })
  await owner.eval(`document.querySelector('#buyer-h ~ .bos-toggle input, .bos-card .bos-toggle input').click()`)
  await owner.waitFor('Buyer GSTIN', { text: true })
  await owner.type('input[placeholder="15 characters"]', gstin('29', 'AABCK1234Q'))
  await owner.eval(`(() => { const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; const l = [...document.querySelectorAll('#buyer-h ~ .bos-form-grid label')].find(x => x.innerText.startsWith('Name')); const i = l.querySelector('input'); set.call(i, 'Kaveri Builders'); i.dispatchEvent(new Event('input', { bubbles: true })); return true })()`)
  const pos = await owner.eval(`(() => { const s = [...document.querySelectorAll('select')].find(x => x.closest('label')?.innerText.startsWith('Place of supply')); return s.value })()`)
  check(pos === '29', `place of supply follows the buyer's GSTIN (${pos})`, results)
  check(await owner.eval(`document.body.innerText.includes('Another state: IGST.')`), 'form explains the IGST consequence', results)
  await owner.eval(`(() => { const s = document.querySelector('.bos-inv-lines__item select'); const set = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set; set.call(s, '${fan.id}'); s.dispatchEvent(new Event('change', { bubbles: true })); return true })()`)
  await wait(300)
  await owner.eval(`(() => { const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; const l = [...document.querySelectorAll('.bos-inv-lines label')].find(x => x.innerText.startsWith('Qty')); const i = l.querySelector('input'); set.call(i, '2'); i.dispatchEvent(new Event('input', { bubbles: true })); return true })()`)
  await owner.shot(`${shots}/06-new-b2b-bill.png`, { full: true })
  await owner.click('Issue bill', { byText: true })
  for (let i = 0; i < 40 && !/\/invoices\/[0-9a-f-]{36}$/.test(await owner.eval('location.pathname')); i++) await wait(250)
  b2bId = (await owner.eval('location.pathname')).split('/').pop()
  await owner.waitFor('.bos-bill')
  const b2b = (await api(`${base}/invoices/${b2bId}`)).data
  check(b2b.igst_total === 720 && b2b.cgst_total === 0 && b2b.number === `${registers[0].code}/${FY}/00002` && b2b.place_of_supply === '29',
    `B2B bill to Karnataka: ${b2b.number}, IGST ${b2b.igst_total}, total ${b2b.amount_due}`, results)
  const heads2 = await owner.eval(`[...document.querySelectorAll('.bos-bill__lines th')].map(t => t.innerText.toUpperCase())`)
  check(heads2.includes('IGST') && !heads2.includes('CGST'), 'other-state bill shows IGST only', results)
  const stock = (await api(`${base}/inventory`)).data.find((r) => r.offering_id === fan.id)
  check(stock.quantity_on_hand === 4, `stock moved with the bill (6 → ${stock.quantity_on_hand})`, results)
  await owner.shot(`${shots}/07-b2b-igst-bill.png`, { full: true })

  // ---- 6. Return credit note that restocks
  await owner.click('Credit note', { byText: true })
  await owner.waitFor('.bos-inv-notelines')
  await owner.type('.bos-inv-notelines input', '1')
  await owner.click('Issue credit note', { byText: true })
  for (let i = 0; i < 40 && (await owner.eval('location.pathname')).endsWith(b2bId); i++) await wait(250)
  await owner.waitFor(`CN/${FY}/00001`, { text: true })
  const cnText = await owner.eval('document.body.innerText')
  check(cnText.includes('Credit note') && cnText.includes(b2b.number), 'credit note references the original bill', results)
  const stock2 = (await api(`${base}/inventory`)).data.find((r) => r.offering_id === fan.id)
  check(stock2.quantity_on_hand === 5, `returned fan back in stock (${stock2.quantity_on_hand})`, results)
  await owner.shot(`${shots}/08-credit-note.png`, { full: true })

  // ---- 7. Money received on the B2B bill
  await owner.goto(`${WS}/b/${biz.id}/invoices/${b2bId}`)
  await owner.waitFor('.bos-bill')
  const outstanding = (await api(`${base}/invoices/${b2bId}`)).data.outstanding
  check(outstanding === 2360, `credit note reduced what is owed (${outstanding})`, results)
  await clickUntil(owner, 'Record money received', '.bos-inv-form')
  await owner.eval(`(() => { const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; const l = [...document.querySelectorAll('.bos-inv-form label')].find(x => x.innerText.startsWith('Reference')); const i = l.querySelector('input'); set.call(i, 'UTR8842'); i.dispatchEvent(new Event('input', { bubbles: true })); return true })()`)
  await owner.click('Record', { byText: true })
  await owner.waitFor('Money received', { text: true })
  check((await api(`${base}/invoices/${b2bId}`)).data.payment_status === 'paid', 'recording the full amount marks the bill paid', results)

  // ---- 8. Cancel keeps the number
  const extra = (await api(`${base}/invoices`, { method: 'POST', body: { lines: [{ offering_id: oil.id, quantity: 1 }] } })).data
  await owner.goto(`${WS}/b/${biz.id}/invoices/${extra.id}`)
  await owner.waitFor('.bos-bill')
  await clickUntil(owner, 'Cancel bill', '.bos-inv-form')
  await owner.type('.bos-inv-form input', 'Entered twice')
  await owner.click('Cancel it', { byText: true })
  await owner.waitFor('The number stays in the series', { text: true })
  check(await owner.eval(`document.body.innerText.includes('${extra.number}')`), `cancelled bill still shows ${extra.number}`, results)
  await owner.shot(`${shots}/09-cancelled.png`, { full: true })

  // ---- 9. List and reports
  await owner.goto(`${WS}/b/${biz.id}/invoices`)
  await owner.waitFor('.bos-inv-summary')
  const rows = await owner.eval(`[...document.querySelectorAll('.bos-inv-num strong')].map(s => s.innerText)`)
  check(rows.includes(extra.number) && rows.includes(`CN/${FY}/00001`) && rows.includes(b2b.number), `list shows bills, notes and cancelled ones (${rows.join(', ')})`, results)
  await owner.shot(`${shots}/10-list.png`, { full: true })
  await owner.goto(`${WS}/b/${biz.id}/invoices/reports`)
  await owner.waitFor('Sales register', { text: true })
  const reg = await owner.eval(`document.querySelector('.bos-inv-report tbody').innerText`)
  check(reg.includes('Cancelled') && reg.includes('Credit note') && reg.includes('Kaveri Builders'), 'sales register lists every document, cancelled marked', results)
  await owner.shot(`${shots}/11-sales-register.png`, { full: true })
  await owner.goto(`${WS}/b/${biz.id}/invoices/reports?kind=gstr1`)
  await owner.waitFor('B2B — to registered businesses', { text: true })
  const sections = await owner.eval(`[...document.querySelectorAll('.bos-section__title')].map(h => h.innerText)`)
  check(sections.length === 6, `GSTR-1 worksheet sections (${sections.join(' / ').replace(/\n/g, ' ')})`, results)
  await owner.shot(`${shots}/12-gstr1.png`, { full: true })
  const csv = await owner.eval(`fetch('/b/${biz.id}/invoices/reports/csv?kind=hsn_summary&from=${today.slice(0, 8)}01&to=${today}').then(async r => r.headers.get('content-type') + '|' + (await r.text()).split('\\n')[0])`)
  check(csv.startsWith('text/csv') && csv.includes('HSN / SAC'), `HSN summary downloads as CSV (${csv})`, results)
  writeFileSync(`${shots}/console-owner.json`, JSON.stringify(owner.consoleErrors, null, 2))
  check(realErrors(owner).length === 0, `no console errors in the Workspace (${realErrors(owner).join(' | ').slice(0, 300)})`, results)
} finally {
  await owner.close()
}

// ---- 10. Composition business: a bill of supply carries no tax line
const comp = await newBusiness({ name: 'Sri Sweets', category: 'food_service', sub: 'bakery', type: 'restaurant',
  modules: ['offerings-catalog', 'orders', 'invoicing'] })
const cbase = `/v1/platform/businesses/${comp.id}`
await api(`${cbase}/invoicing/profile`, { method: 'PUT', body: { prices_include_tax: true, round_off: true, issue_on: 'manual' } })
const creg = (await api(`${cbase}/invoicing/registrations`, { method: 'POST', body: {
  scheme: 'composition', legal_name: 'Sri Sweets', gstin: gstin('33', `AB${tag}S1234K`.slice(0, 10)),
  composition_declaration: 'Declaration text entered by the owner as advised by their CA' } })).data
const cloc = (await api(`${cbase}/locations`)).data.find((l) => l.is_primary).id
await api(`${cbase}/invoicing/registers`, { method: 'POST', body: { location_id: cloc, registration_id: creg.id, code: 'SS1' } })
const sweet = (await api(`${cbase}/products`, { method: 'POST', body: { status: 'active', title: 'Mysore pak 250 g', price_amount: 180.5, tax_rate: 5 } })).data
const bos = (await api(`${cbase}/invoices`, { method: 'POST', body: { lines: [{ offering_id: sweet.id, quantity: 1 }] } })).data
const mobile = await browser({ mobile: true })
try {
  await mobile.goto(`${WS}/b/${comp.id}/invoices/${bos.id}`)
  await mobile.waitFor('.bos-bill')
  const paper = await mobile.text('.bos-bill')
  check(paper.includes('Bill of supply') && !/CGST|SGST|IGST|GST %|Taxable/.test(paper) && paper.includes('Declaration text entered'),
    'composition bill of supply shows no tax line and prints the declaration', results)
  check(paper.includes('Round-off') && paper.includes('₹181.00'), 'round-off is its own line (₹180.50 → ₹181.00)', results)
  check(await mobile.eval('document.documentElement.scrollWidth <= window.innerWidth + 1'), 'bill page fits 390 px', results)
  await mobile.shot(`${shots}/13-bill-of-supply-390.png`, { full: true })
  await mobile.goto(`${WS}/b/${comp.id}/invoices`)
  await mobile.waitFor('.bos-inv-summary')
  check(await mobile.eval('document.documentElement.scrollWidth <= window.innerWidth + 1'), 'bill list fits 390 px', results)
  await mobile.shot(`${shots}/14-list-390.png`, { full: true })
  check(realErrors(mobile).length === 0, `no console errors at 390 px (${realErrors(mobile).join(' | ').slice(0, 200)})`, results)
} finally {
  await mobile.close()
}

writeFileSync(`${shots}/results.json`, JSON.stringify(results, null, 2))
const failed = results.filter((r) => !r.ok)
console.log(`\n${results.length - failed.length}/${results.length} checks passed`)
