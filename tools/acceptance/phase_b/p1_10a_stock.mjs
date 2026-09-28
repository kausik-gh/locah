// P1-10A stock depth in the browser (Capability Universe §15.1; Business OS Guide §11).
//  One inventory domain, four different jobs:
//   - a meat shop sees its counter in kilos, cuts whole chicken into cuts and sees the trim live;
//   - a pharmacy sees batches by expiry and writes off one that is about to expire;
//   - a mobile store looks up a phone by IMEI;
//   - a clothing store sees a size × colour grid.
//  A store count is started, counted blind, submitted and approved. Desktop and 390 px.
//
//   node tools/acceptance/phase_b/p1_10a_stock.mjs      (local stack only)
import { mkdirSync, writeFileSync } from 'node:fs'
import { OUT, WS, api, browser, check, newBusiness, realErrors } from './common.mjs'

const results = []
const shots = `${OUT}/phase_b/p1_10a`
mkdirSync(shots, { recursive: true })
const iso = (days) => new Date(Date.now() + days * 864e5).toISOString().slice(0, 10)

async function shop(name, category, sub) {
  const biz = await newBusiness({ name, category, sub, modules: ['offerings-catalog', 'orders', 'payments', 'inventory'] })
  const base = `/v1/platform/businesses/${biz.id}`
  const loc = (await api(`${base}/locations`)).data.find((l) => l.is_primary).id
  const item = async (body) => (await api(`${base}/products`, { method: 'POST', body: { status: 'active', offering_type: 'product', track_inventory: true, ...body } })).data
  return { ...biz, base, loc, item }
}

// ---- seed: four businesses, each set up the way its own business works
const meat = await shop('Ishant Chicken Centre', 'fresh_grocery', 'meat_shop')
const weighed = (title, price) => meat.item({ title, offering_type: 'weighed_product', price_amount: price, attributes: { price_per: 'kg' }, sell_units: [{ label: '1 kg', qty: 1000 }] })
const whole = await weighed('Whole chicken', 180)
const curry = await weighed('Chicken curry cut', 260)
const boneless = await weighed('Chicken boneless', 340)
await api(`${meat.base}/stock/receipts`, { method: 'POST', body: { location_id: meat.loc, offering_id: whole.id, quantity: 10000, total_cost_paise: 180000 } })
await api(`${meat.base}/stock/yields`, { method: 'PUT', body: { source_offering_id: whole.id, output_offering_id: curry.id, yield_percent: 80 } })
await api(`${meat.base}/stock/yields`, { method: 'PUT', body: { source_offering_id: whole.id, output_offering_id: boneless.id, yield_percent: 10 } })

const pharma = await shop('Sri Sai Medicals', 'healthcare', 'pharmacy')
const para = await pharma.item({ title: 'Paracetamol 500 mg strip', price_amount: 30 })
await api(`${pharma.base}/stock/items/${para.id}`, { method: 'PATCH', body: { batch_tracked: true } })
await api(`${pharma.base}/stock/receipts`, { method: 'POST', body: { location_id: pharma.loc, offering_id: para.id, quantity: 40, batch_code: 'PCM-2411', expires_on: iso(5), total_cost_paise: 60000 } })
const lateBatch = await api(`${pharma.base}/stock/receipts`, { method: 'POST', body: { location_id: pharma.loc, offering_id: para.id, quantity: 120, batch_code: 'PCM-2503', expires_on: iso(210) } })

const mobile = await shop('Galaxy Mobiles', 'retail', 'mobile_store')
const phoneItem = await mobile.item({ title: 'Redmi Note 14', price_amount: 17999 })
await api(`${mobile.base}/stock/items/${phoneItem.id}`, { method: 'PATCH', body: { serial_tracked: true, warranty_months: 12 } })
const imei = `86${String(Date.now()).slice(-13)}`
await api(`${mobile.base}/stock/receipts`, { method: 'POST', body: { location_id: mobile.loc, offering_id: phoneItem.id, quantity: 2, serials: [imei, `${imei.slice(0, -1)}9`] } })

const fashion = await shop('Trendz Menswear', 'retail', 'clothing')
const shirt = await fashion.item({ title: 'Linen shirt', price_amount: 1299, variant_options: [{ name: 'Size', values: ['M', 'L', 'XL'] }, { name: 'Colour', values: ['White', 'Blue'] }] })
await api(`${fashion.base}/products/${shirt.id}/variants/matrix`, { method: 'POST', body: {} })
const shirtVariants = (await api(`${fashion.base}/stock/items`)).data.find((i) => i.id === shirt.id).variants
for (const [i, v] of shirtVariants.entries()) {
  if (i === 5) continue // XL Blue never arrived
  await api(`${fashion.base}/stock/receipts`, { method: 'POST', body: { location_id: fashion.loc, offering_id: shirt.id, variant_id: v.id, quantity: i === 1 ? 1 : 6 } })
}

const page = await browser()
const fill = (label, value, scope = 'document') => page.eval(`(() => {
  const l = [...${scope}.querySelectorAll('label')].filter(x => x.offsetParent !== null).find(x => x.innerText.trim().startsWith(${JSON.stringify(label)}));
  if (!l) throw new Error('no label ' + ${JSON.stringify(label)});
  const el = l.querySelector('input, select, textarea');
  const proto = el.tagName === 'SELECT' ? HTMLSelectElement.prototype : el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
  Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, ${JSON.stringify(value)});
  el.dispatchEvent(new Event(el.tagName === 'SELECT' ? 'change' : 'input', { bubbles: true }));
  return true })()`)
const setByAria = (aria, value) => page.eval(`(() => { const el = document.querySelector('[aria-label=${JSON.stringify(aria)}]');
  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(el, ${JSON.stringify(value)});
  el.dispatchEvent(new Event('input', { bubbles: true })); return true })()`)
const text = () => page.eval('document.body.innerText')
try {
  // ---- 1. meat shop: the counter in kilos, then cut and portion with live trim
  await page.goto(`${WS}/b/${meat.id}/inventory`)
  await page.waitFor("Today's counter, by weight", { text: true })
  let body = await text()
  check(body.includes('Counter by weight') && body.includes('Cut and portion'), 'meat shop opens on its counter by weight with cutting', results)
  check(/Whole chicken\s+10 kg/.test(body), 'whole chicken shows 10 kg on the counter', results)
  check(!body.includes('Batches & expiry') && !body.includes('Serials & warranty'), 'no pharmacy or electronics views for a meat shop', results)
  await page.shot(`${shots}/01-meat-counter.png`, { full: true })
  await fill('How much was cut', '5')
  await setByAria('Weighed out: Chicken curry cut', '3.6')
  await setByAria('Weighed out: Chicken boneless', '0.4')
  await page.waitFor('Trim 1 kg · 20%', { text: true })
  check(true, 'trim is shown live while weighing (1 kg · 20%)', results)
  await page.shot(`${shots}/02-meat-cutting.png`)
  await page.click('Record the cut', { byText: true })
  await page.waitFor('Cut recorded', { text: true })
  await page.waitFor('last 1 cut gave', { text: true })
  body = await text()
  check(/Chicken curry cut\s+3\.6 kg/.test(body) && /Whole chicken\s+5 kg/.test(body), 'counter now shows 5 kg whole and 3.6 kg curry cut', results)
  check(body.includes('Whole chicken → Chicken curry cut · usually 80% · last 1 cut gave 90% of that'), 'yield accuracy from the real cut (90% of the usual)', results)
  await page.shot(`${shots}/03-meat-after-cut.png`, { full: true })

  // ---- 2. a blind count, submitted and approved
  await page.goto(`${WS}/b/${meat.id}/inventory?view=counts`)
  await page.waitFor('Start a count', { text: true })
  await fill('Name', 'Evening count')
  await page.click('Start a count', { byText: true })
  await page.waitFor('Evening count', { text: true })
  await setByAria('Counted: Chicken curry cut', '3.5')
  await page.shot(`${shots}/04-count-sheet.png`, { full: true })
  await page.click('Submit count', { byText: true })
  await page.waitFor('Approve differences', { text: true })
  body = await text()
  check(body.includes('−0.1 kg'), 'owner sees the 100 g difference on curry cut after submission', results)
  await page.click('Approve differences', { byText: true })
  await page.waitFor('stock line(s) corrected', { text: true })
  const after = (await api(`${meat.base}/stock`)).data.items.find((i) => i.offering_id === curry.id)
  check(after.quantity_on_hand === 3500, `approved count set curry cut to 3.5 kg (${after.on_hand_text})`, results)

  // ---- 3. pharmacy: expiry first, write off a batch about to expire
  await page.goto(`${WS}/b/${pharma.id}/inventory`)
  await page.waitFor('Stock by batch and expiry', { text: true })
  body = await text()
  check(body.includes('Expires within 7 days') && body.includes('PCM-2411') && !body.includes('Cut and portion'), 'pharmacy opens on expiry with the 5-day batch flagged', results)
  await page.shot(`${shots}/05-pharmacy-expiry.png`, { full: true })
  await page.click('Write off early', { byText: true })
  await page.click('Yes, write off', { byText: true })
  await page.waitFor('Nothing expires in the next 30 days', { text: true })
  const para2 = (await api(`${pharma.base}/stock`)).data.items.find((i) => i.offering_id === para.id)
  check(para2.quantity_on_hand === 120 && para2.next_expiry === iso(210), `write-off left only batch PCM-2503 (${para2.on_hand_text})`, results)
  check(lateBatch.data.batch_id, 'second batch recorded with its own id', results)

  // ---- 4. mobile store: warranty lookup by IMEI
  await page.goto(`${WS}/b/${mobile.id}/inventory`)
  await page.waitFor('Units in stock, by serial number', { text: true })
  await page.eval(`(() => { const el = document.querySelector('#serial-q'); Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(el, ${JSON.stringify(imei)}); el.dispatchEvent(new Event('input', { bubbles: true })); return true })()`)
  await page.click('Look up', { byText: true })
  await page.waitFor('In stock, not sold yet', { text: true })
  check(true, 'IMEI lookup finds the unsold phone', results)
  await page.shot(`${shots}/06-mobile-serials.png`, { full: true })

  // ---- 5. clothing: the size × colour grid
  await page.goto(`${WS}/b/${fashion.id}/inventory`)
  await page.waitFor('Stock by size and colour', { text: true })
  const grid = await page.eval(`[...document.querySelectorAll('.bos-variant-grid tbody tr')].map(r => [...r.children].map(c => c.innerText.trim()))`)
  check(JSON.stringify(grid) === JSON.stringify([['M', '6', '1'], ['L', '6', '6'], ['XL', '6', '0']]), `size × colour grid from real stock ${JSON.stringify(grid)}`, results)
  const low = await page.eval(`document.querySelectorAll('.bos-grid-cell.is-out_of_stock, .bos-grid-cell.is-none').length`)
  check(low === 1, 'the combination that never arrived is marked', results)
  await page.shot(`${shots}/07-fashion-grid.png`, { full: true })
  check(realErrors(page).length === 0, `no console errors (${realErrors(page).join(' | ').slice(0, 300)})`, results)
} finally {
  await page.close()
}

// ---- 6. 390 px: each business's stock view fits a phone
const phone = await browser({ mobile: true })
try {
  for (const [biz, want, name] of [[meat, "Today's counter, by weight", '08-meat-390'], [pharma, 'Stock by batch and expiry', '09-pharmacy-390'],
    [mobile, 'Warranty lookup', '10-mobile-390'], [fashion, 'Stock by size and colour', '11-fashion-390']]) {
    await phone.goto(`${WS}/b/${biz.id}/inventory`)
    await phone.waitFor(want, { text: true })
    check(await phone.eval('document.documentElement.scrollWidth <= window.innerWidth + 1'), `${name} fits 390 px`, results)
    await phone.shot(`${shots}/${name}.png`, { full: true })
  }
  check(realErrors(phone).length === 0, `no console errors at 390 px (${realErrors(phone).join(' | ').slice(0, 200)})`, results)
} finally {
  await phone.close()
}

writeFileSync(`${shots}/results.json`, JSON.stringify(results, null, 2))
const failed = results.filter((r) => !r.ok)
console.log(`\n${results.length - failed.length}/${results.length} checks passed`)
