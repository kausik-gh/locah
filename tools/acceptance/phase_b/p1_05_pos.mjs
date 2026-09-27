// P1-05 counter billing in the browser (Capability Universe §14.1–§14.3, §14.5, §14.6).
//  The owner opens a shift, scans a barcode and a scale label, takes cash and
//  gives change; the network is cut and two more bills are rung up and
//  numbered from the register's block, then sync when it returns; a bill is
//  held and recalled; a bill is voided with a manager's PIN; goods come back
//  as a credit note; a petty expense leaves the drawer; the shift closes
//  counted vs expected. Desktop and 390 px.
//
//   CHROME_PATH=/opt/pw-browsers/chromium CHROME_NO_SANDBOX=1 node tools/acceptance/phase_b/p1_05_pos.mjs
import { mkdirSync, writeFileSync } from 'node:fs'
import { OUT, WS, api, browser, check, newBusiness, realErrors } from './common.mjs'

const results = []
const shots = `${OUT}/phase_b/p1_05`
mkdirSync(shots, { recursive: true })
const wait = (ms) => new Promise((r) => setTimeout(r, ms))
const C = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
function gstin(state, pan) {
  const body = `${state}${pan}1Z`
  let t = 0
  for (let i = 0; i < 14; i++) { const v = C.indexOf(body[i]) * (i % 2 ? 2 : 1); t += Math.floor(v / 36) + (v % 36) }
  return body + C[(36 - (t % 36)) % 36]
}
const ean = (body) => body + String((10 - body.split('').reverse().reduce((s, d, i) => s + Number(d) * (i % 2 === 0 ? 3 : 1), 0) % 10) % 10)
const now = new Date()
const fyStart = now.getMonth() >= 3 ? now.getFullYear() : now.getFullYear() - 1
const FY = `${String(fyStart % 100).padStart(2, '0')}-${String((fyStart + 1) % 100).padStart(2, '0')}`
const tag = Math.random().toString(36).slice(2, 6).toUpperCase()

const biz = await newBusiness({ name: 'Murugan Provisions', category: 'fresh_grocery', sub: 'grocery', type: 'retail',
  modules: ['offerings-catalog', 'orders', 'payments', 'inventory', 'invoicing', 'pos'] })
const base = `/v1/platform/businesses/${biz.id}`
await api(`${base}/invoicing/profile`, { method: 'PUT', body: { prices_include_tax: true, round_off: true, issue_on: 'manual' } })
const reg = (await api(`${base}/invoicing/registrations`, { method: 'POST', body: { scheme: 'regular', legal_name: 'Murugan Provisions', gstin: gstin('33', `AA${tag}M1234K`.slice(0, 10)) } })).data
const loc = (await api(`${base}/locations`)).data.find((l) => l.is_primary).id
await api(`${base}/invoicing/registers`, { method: 'POST', body: { location_id: loc, registration_id: reg.id, code: 'CHN1', name: 'Front counter' } })
const item = async (body) => (await api(`${base}/products`, { method: 'POST', body: { status: 'active', offering_type: 'product', ...body } })).data
const dal = await item({ title: 'Toor dal 1 kg', price_amount: 149, hsn_sac: '0713', tax_rate: 5, barcode: '8901234567890', track_inventory: true })
const soap = await item({ title: 'Neem soap', price_amount: 45, hsn_sac: '3401', tax_rate: 18 })
const cashews = await item({ title: 'Cashews', offering_type: 'weighed_product', price_amount: 960, sku: '00123', hsn_sac: '0801', tax_rate: 5,
  attributes: { price_per: 'kg' }, sell_units: [{ label: '250 g', qty: 250 }] })
await api(`${base}/inventory/opening-stock`, { method: 'POST', body: { offering_id: dal.id, location_id: loc, quantity: 40 } })
await api(`${base}/pos/settings`, { method: 'PUT', body: { upi_vpa: 'murugan@okbank', return_window_days: 7, discount_caps: { cashier: 5 },
  weighed_label: { prefix: '21', item_digits: 5, value: 'weight', value_digits: 5, value_decimals: 3 }, receipt_footer: 'Thank you — visit again' } })
await api(`${base}/pos/pin`, { method: 'PUT', body: { pin: '4826' } })

const page = await browser()
const total = async () => page.eval(`document.querySelector('[data-testid=pos-total]').innerText`)
const scan = async (code) => {
  await page.type('#pos-q', code)
  await page.eval(`document.querySelector('.pos-search').requestSubmit()`)
  await wait(250)
}
const rupeeNum = (s) => Number(String(s).replace(/[^\d.]/g, ''))
try {
  // ---- entry points
  await page.goto(`${WS}/b/${biz.id}`)
  await page.waitFor('Counter (POS)', { text: true })
  const posHref = await page.eval(`[...document.querySelectorAll('a')].find(a => a.innerText.trim() === 'Counter (POS)')?.getAttribute('href')`)
  check(posHref === `/pos/${biz.id}`, `Sell area opens the full-screen counter (${posHref})`, results)
  await page.goto(`${WS}/b/${biz.id}/settings/counter`)
  await page.waitFor('Counter rules', { text: true })
  check(await page.eval(`document.body.innerText.includes('Your approval PIN') && document.body.innerText.includes('UPI to verify')`), 'counter settings: rules, approval PIN, UPI to verify', results)
  await page.shot(`${shots}/01-counter-settings.png`, { full: true })

  // ---- 1. open the shift
  await page.goto(`${WS}/pos/${biz.id}`)
  await page.waitFor('Open the counter', { text: true })
  await page.shot(`${shots}/02-open-shift.png`)
  await page.type('.pos-form input[inputmode=decimal]', '1000')
  await page.click('Open shift', { byText: true })
  await page.waitFor('#pos-q')
  await page.waitFor('.pos-tile')
  check((await page.text('.pos-top__numbers')).startsWith('50'), `register holds 50 bill numbers for offline use (${await page.text('.pos-top__numbers')})`, results)

  // ---- 2. scan, scale label, tap; cash with change
  await scan('8901234567890')
  await scan(ean('2100123' + '00500'))
  await page.eval(`[...document.querySelectorAll('.pos-tile')].find(t => t.innerText.includes('Neem soap')).click()`)
  await page.eval(`[...document.querySelectorAll('.pos-tile')].find(t => t.innerText.includes('Neem soap')).click()`)
  const lines = await page.eval(`[...document.querySelectorAll('.pos-line__title strong')].map(s => s.innerText)`)
  check(lines.join('|') === 'Toor dal 1 kg|Cashews|Neem soap', `barcode, scale label and taps build the bill (${lines.join(', ')})`, results)
  const qtys = await page.eval(`[...document.querySelectorAll('.pos-qty')].map(q => q.querySelector('input')?.value ?? q.innerText.replace(/[^\\d.]/g, ''))`)
  check(qtys[1] === '0.5' && qtys[2] === '2', `scale label gives 0.5 kg; two taps give 2 (${qtys.join(', ')})`, results)
  const shown = await total()
  check(shown === '₹719.00', `prices include GST, total rounded: 149 + 480 + 90 = ${shown}`, results)
  await page.shot(`${shots}/03-bill.png`)
  await page.click('.pos-pay')
  await page.waitFor('Take cash', { text: true })
  await page.type('.pos-dialog input[inputmode=decimal]', '1000')
  await page.click('Take cash', { byText: true })
  await page.waitFor('Change', { text: true })
  await page.shot(`${shots}/04-pay-cash.png`)
  await page.click('Complete sale', { byText: true })
  await page.waitFor('.pos-receipt-head')
  const head = await page.text('.pos-receipt-head')
  check(head.includes('Change ₹281.00') && head.includes(`CHN1/${FY}/00001`), `receipt: number from the block, change ₹281 (${head.replace(/\s+/g, ' ')})`, results)
  await page.waitFor('Saved to LOCAH.', { text: true, timeout: 20000 })
  const bills = (await api(`${base}/invoices?kind=invoices`)).data
  const first = bills.find((b) => b.number === `CHN1/${FY}/00001`)
  check(first && first.amount_due === 719 && first.source === 'pos', `server bill equals the counter's total (${first?.amount_due})`, results)
  await page.media('print')
  await page.shot(`${shots}/05-receipt-print-80mm.png`)
  const printed = await page.eval(`getComputedStyle(document.querySelector('.pos-receipt-print')).display`)
  await page.media('')
  check(printed === 'block', 'receipt has its own 80 mm print layout', results)
  await page.click('New sale', { byText: true })

  // ---- 3. network cut: two bills numbered from the block, kept on the device
  await page.offline(true)
  await scan('8901234567890')
  await scan('8901234567890')
  await page.click('.pos-pay')
  await page.waitFor('Take cash', { text: true })
  await page.click('UPI', { byText: true })
  await page.waitFor('UPI cannot be confirmed without a connection', { text: true })
  await page.click('UPI to verify', { byText: true })
  await page.click('Complete sale', { byText: true })
  await page.waitFor('.pos-receipt-head')
  const off1 = await page.text('.pos-receipt-head')
  check(off1.includes(`CHN1/${FY}/00002`) && off1.includes('Kept on this device'), `offline bill numbered CHN1/${FY}/00002 and kept on the device`, results)
  await page.click('New sale', { byText: true })
  await page.eval(`[...document.querySelectorAll('.pos-tile')].find(t => t.innerText.includes('Neem soap')).click()`)
  await page.click('.pos-pay')
  await page.waitFor('Take cash', { text: true })
  await page.click('Take cash', { byText: true })
  await page.click('Complete sale', { byText: true })
  await page.waitFor(`CHN1/${FY}/00003`, { text: true })
  await page.click('New sale', { byText: true })
  const pill = await page.eval(`document.querySelector('.pos-pill.is-off')?.innerText || ''`)
  const toSync = await page.eval(`document.querySelector('.pos-pill.is-wait')?.innerText || ''`)
  check(pill.startsWith('Offline') && toSync === '2 to sync', `offline shown; ${toSync}`, results)
  await page.shot(`${shots}/06-offline.png`)
  check((await api(`${base}/invoices?kind=invoices`)).data.length === 1, 'nothing reached the server while offline', results)

  // ---- 4. network back: the queue syncs by itself
  await page.offline(false)
  for (let i = 0; i < 40 && (await page.eval(`!!document.querySelector('.pos-pill.is-wait')`)); i++) await wait(500)
  const synced = (await api(`${base}/invoices?kind=invoices`)).data.map((b) => b.number).sort()
  check(synced.join(',') === [1, 2, 3].map((n) => `CHN1/${FY}/0000${n}`).join(','), `after reconnecting, bills 1–3 are on the server with the device's numbers (${synced.join(', ')})`, results)
  const toVerify = (await api(`${base}/pos/upi-to-verify`)).data
  check(toVerify.length === 1 && toVerify[0].number === `CHN1/${FY}/00002`, 'the offline UPI bill waits to be verified', results)

  // ---- 5. hold and recall
  await scan('8901234567890')
  await page.click('Hold', { byText: true })
  check((await page.eval(`document.querySelectorAll('.pos-lines li').length`)) === 0, 'holding clears the counter for the next customer', results)
  await page.click('Held (1)', { byText: true })
  await page.click('Recall', { byText: true })
  check((await page.eval(`document.querySelectorAll('.pos-lines li').length`)) === 1, 'recalled bill comes back', results)
  await page.click('Clear', { byText: true })

  // ---- 6. void with a manager's PIN
  await page.click('Bills', { byText: true })
  await page.waitFor(`CHN1/${FY}/00003`, { text: true })
  await page.eval(`[...document.querySelectorAll('.pos-list li')].find(l => l.innerText.includes('CHN1/${FY}/00003')).querySelectorAll('button')[1].click()`)
  await page.waitFor('A manager approves cancelling this bill', { text: true })
  await page.type('.pos-dialog input[type=password]', '0000')
  await page.click('Approve', { byText: true })
  await page.waitFor('That PIN is not right', { text: true })
  await page.type('.pos-dialog input[type=password]', '4826')
  await page.click('Approve', { byText: true })
  await page.waitFor(`Void of CHN1/${FY}/00003 recorded`, { text: true })
  for (let i = 0; i < 20; i++) { if ((await api(`${base}/invoices?status=cancelled`)).data.length) break; await wait(500) }
  const cancelled = (await api(`${base}/invoices?status=cancelled`)).data
  check(cancelled.length === 1 && cancelled[0].number === `CHN1/${FY}/00003`, 'voided bill is cancelled and keeps its number', results)

  // ---- 7. a return becomes a credit note, cash back from the drawer
  await page.click('Return', { byText: true })
  await page.type('.pos-dialog input', `CHN1/${FY}/00001`)
  await page.click('Find', { byText: true })
  await page.waitFor('Refund in', { text: true })
  await page.eval(`(() => { const i = [...document.querySelectorAll('.pos-dialog .pos-list input')][0]; Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(i, '1'); i.dispatchEvent(new Event('input', { bubbles: true })); return true })()`)
  await page.shot(`${shots}/07-return.png`)
  await page.click('Take the return', { byText: true })
  await page.waitFor('Return recorded', { text: true })
  for (let i = 0; i < 20; i++) { if ((await api(`${base}/invoices?kind=credit_note`)).data.length) break; await wait(500) }
  const cn = (await api(`${base}/invoices?kind=credit_note`)).data
  check(cn.length === 1 && cn[0].number === `CN/${FY}/00001` && cn[0].amount_due === 149, `return issued credit note ${cn[0]?.number} for ₹${cn[0]?.amount_due}`, results)

  // ---- 8. petty expense and closing the drawer
  await page.click('Drawer', { byText: true })
  await page.type('.pos-dialog input[inputmode=decimal]', '50')
  await page.type('.pos-dialog input[maxlength="300"]', 'Tea for staff')
  await page.click('Record', { byText: true })
  await page.waitFor('Petty expense recorded', { text: true })
  for (let i = 0; i < 20 && (await page.eval(`!!document.querySelector('.pos-pill.is-wait')`)); i++) await wait(500)
  await page.click('Close shift', { byText: true })
  await page.waitFor('Expected in the drawer', { text: true })
  const expectedText = await page.eval(`[...document.querySelectorAll('.pos-dialog dt')].find(d => d.innerText.startsWith('Expected'))?.nextElementSibling.innerText`)
  // 1000 opening + 719 (bill 1) + 45 (bill 3 was voided: no) ... bill 3 voided; bill 2 UPI → cash 719; − 149 refund − 50 petty
  check(rupeeNum(expectedText) === 1000 + 719 - 149 - 50, `drawer should hold opening + cash sales − refunds − petty = ${expectedText}`, results)
  await page.shot(`${shots}/08-close.png`, { full: true })
  await page.type('.pos-dialog input[inputmode=decimal]', String(1000 + 719 - 149 - 50 - 10))
  await page.click('.pos-dialog button[type=submit]')
  await page.waitFor('Short by', { text: true })
  check((await page.text('.pos-dialog')).includes('₹10.00'), 'closing shows the drawer short by ₹10', results)
  await page.shot(`${shots}/09-closed.png`)
  await page.click('Done', { byText: true })
  await page.waitFor('Open the counter', { text: true })
  const shifts = (await api(`${base}/pos/shifts`)).data
  check(shifts[0].status === 'closed' && shifts[0].variance === -10, 'shift closed with its variance recorded', results)

  // ---- 9. Workspace views
  await page.goto(`${WS}/b/${biz.id}/pos/shifts`)
  await page.waitFor('Short', { text: true })
  await page.shot(`${shots}/10-shifts.png`, { full: true })
  await page.goto(`${WS}/b/${biz.id}/offerings/${cashews.id}`)
  await page.waitFor('Barcode and labels', { text: true })
  await page.click('Give an in-store code', { byText: true })
  await page.waitFor('Print on A4 sheet', { text: true })
  const labelHref = await page.eval(`[...document.querySelectorAll('a')].find(a => a.innerText === 'Print on A4 sheet').getAttribute('href')`)
  const pdf = await page.eval(`fetch(${JSON.stringify(labelHref)}).then(r => r.headers.get('content-type') + '|' + r.status)`)
  check(pdf === 'application/pdf|200', `in-store code given and labels print as PDF (${pdf})`, results)
  await page.shot(`${shots}/11-labels.png`)
  check(realErrors(page).length === 0, `no console errors (${realErrors(page).join(' | ').slice(0, 300)})`, results)
} finally {
  await page.close()
}

// ---- 10. 390 px counter
const phone = await browser({ mobile: true })
try {
  await phone.goto(`${WS}/pos/${biz.id}`)
  await phone.waitFor('Open the counter', { text: true })
  await phone.type('.pos-form input[inputmode=decimal]', '500')
  await phone.click('Open shift', { byText: true })
  await phone.waitFor('.pos-tile')
  await phone.eval(`[...document.querySelectorAll('.pos-tile')].find(t => t.innerText.includes('Neem soap')).click()`)
  check(await phone.eval('document.documentElement.scrollWidth <= window.innerWidth + 1'), 'counter fits 390 px', results)
  await phone.shot(`${shots}/12-counter-390.png`, { full: true })
  check(realErrors(phone).length === 0, `no console errors at 390 px (${realErrors(phone).join(' | ').slice(0, 200)})`, results)
} finally {
  await phone.close()
}

writeFileSync(`${shots}/results.json`, JSON.stringify(results, null, 2))
const failed = results.filter((r) => !r.ok)
console.log(`\n${results.length - failed.length}/${results.length} checks passed`)
