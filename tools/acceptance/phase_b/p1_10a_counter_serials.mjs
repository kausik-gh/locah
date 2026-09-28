// P1-10A serial / IMEI captured at the counter (Capability Universe §15.1; §21.2 electronics, mobile stores).
//  A phone added by tapping its tile cannot be paid for until its IMEI is scanned; scanning the IMEI on
//  the box adds the phone with that IMEI; the sale marks both units sold with their warranty.
//
//   node tools/acceptance/phase_b/p1_10a_counter_serials.mjs      (local stack only)
import { mkdirSync, writeFileSync } from 'node:fs'
import { OUT, WS, api, browser, check, newBusiness, realErrors } from './common.mjs'

const results = []
const shots = `${OUT}/phase_b/p1_10a`
mkdirSync(shots, { recursive: true })
const wait = (ms) => new Promise((r) => setTimeout(r, ms))
const C = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
function gstin(state, pan) {
  const body = `${state}${pan}1Z`
  let t = 0
  for (let i = 0; i < 14; i++) { const v = C.indexOf(body[i]) * (i % 2 ? 2 : 1); t += Math.floor(v / 36) + (v % 36) }
  return body + C[(36 - (t % 36)) % 36]
}
const tag = Math.random().toString(36).slice(2, 6).toUpperCase()

const biz = await newBusiness({ name: 'Galaxy Mobiles Counter', category: 'retail', sub: 'mobile_store',
  modules: ['offerings-catalog', 'orders', 'payments', 'inventory', 'invoicing', 'pos'] })
const base = `/v1/platform/businesses/${biz.id}`
await api(`${base}/invoicing/profile`, { method: 'PUT', body: { prices_include_tax: true, round_off: true, issue_on: 'manual' } })
const reg = (await api(`${base}/invoicing/registrations`, { method: 'POST', body: { scheme: 'regular', legal_name: 'Galaxy Mobiles', gstin: gstin('33', `AA${tag}G1234K`.slice(0, 10)) } })).data
const loc = (await api(`${base}/locations`)).data.find((l) => l.is_primary).id
await api(`${base}/invoicing/registers`, { method: 'POST', body: { location_id: loc, registration_id: reg.id, code: 'GM1', name: 'Counter' } })
const phone = (await api(`${base}/products`, { method: 'POST', body: { status: 'active', offering_type: 'product', title: 'Redmi Note 14', price_amount: 17999, hsn_sac: '8517', tax_rate: 18, track_inventory: true } })).data
await api(`${base}/stock/items/${phone.id}`, { method: 'PATCH', body: { serial_tracked: true, warranty_months: 12 } })
const imeiA = `35${String(Date.now()).slice(-13)}`
const imeiB = `${imeiA.slice(0, -1)}${(Number(imeiA.slice(-1)) + 1) % 10}`
await api(`${base}/stock/receipts`, { method: 'POST', body: { location_id: loc, offering_id: phone.id, quantity: 2, serials: [imeiA, imeiB] } })

const page = await browser()
const scan = async (code) => {
  await page.type('#pos-q', code)
  await page.eval(`document.querySelector('.pos-search').requestSubmit()`)
  await wait(300)
}
try {
  await page.goto(`${WS}/pos/${biz.id}`)
  await page.waitFor('Open the counter', { text: true })
  await page.type('.pos-form input[inputmode=decimal]', '0')
  await page.click('Open shift', { byText: true })
  await page.waitFor('.pos-tile')
  // 1. tapped, not scanned: the bill cannot be paid until the IMEI is on it
  await page.eval(`[...document.querySelectorAll('.pos-tile')].find(t => t.innerText.includes('Redmi Note 14')).click()`)
  await page.waitFor('Scan the serial / IMEI of each', { text: true })
  check(await page.eval(`document.querySelector('.pos-pay').disabled`), 'Pay is disabled until each phone has its IMEI', results)
  await page.shot(`${shots}/12-counter-needs-imei.png`)
  await page.type('.pos-serial-add input', imeiB)
  await page.eval(`document.querySelector('.pos-serial-add').requestSubmit()`)
  await wait(300)
  // 2. scanning the IMEI on a box adds that phone with its IMEI
  await scan(imeiA)
  const chips = await page.eval(`[...document.querySelectorAll('.pos-serial')].map(c => c.innerText.replace(' ×', ''))`)
  check(chips.length === 2 && chips.includes(imeiA) && chips.includes(imeiB), `both IMEIs on the line (${chips.join(', ')})`, results)
  const qty = await page.eval(`document.querySelector('.pos-qty span')?.innerText`)
  check(qty === '2', `scanning the second box made it 2 phones (${qty})`, results)
  check(!(await page.eval(`document.querySelector('.pos-pay').disabled`)), 'Pay is enabled once every unit has its IMEI', results)
  await page.shot(`${shots}/13-counter-imeis.png`)
  await page.click('.pos-pay')
  await page.waitFor('Take cash', { text: true })
  await page.click('Take cash', { byText: true })
  await page.waitFor('Complete sale', { text: true })
  await page.click('Complete sale', { byText: true })
  await page.waitFor('.pos-receipt-head')
  await page.waitFor('Saved to LOCAH.', { text: true, timeout: 20000 })
  for (const imei of [imeiA, imeiB]) {
    const s = (await api(`${base}/stock/serials/${imei}`)).data
    check(s.status === 'sold' && s.in_warranty && s.bill_number, `${imei} sold on bill ${s.bill_number}, in warranty until ${s.warranty_until}`, results)
  }
  const left = (await api(`${base}/stock`)).data.items.find((i) => i.offering_id === phone.id)
  check(left.quantity_on_hand === 0 && left.serials_in_stock === 0, 'no phones left on record or by serial', results)
  check(realErrors(page).length === 0, `no console errors (${realErrors(page).join(' | ').slice(0, 300)})`, results)
} finally {
  await page.close()
}

writeFileSync(`${shots}/results-counter.json`, JSON.stringify(results, null, 2))
const failed = results.filter((r) => !r.ok)
console.log(`\n${results.length - failed.length}/${results.length} checks passed`)
