// P1-03 offering kinds in the browser (Capability Universe §6.3; §26.3 P1-03
// "new kinds render on the tenant site").
//  Workspace: the owner picks "Sold by weight", fills packs and cuts in words,
//  and it shows grouped by kind with what the others still need.
//  Tenant site: a meat shop's chicken is bought as a 500 g pack, boneless —
//  priced by the server; a dealer's car opens "Book a test drive", which lands
//  as a lead; a developer's projects sit under status tabs; a cause takes a
//  gift. Desktop and 390 px.
//
//   CHROME_PATH=/opt/pw-browsers/chromium CHROME_NO_SANDBOX=1 node tools/acceptance/phase_b/p1_03_kinds.mjs
import { mkdirSync, writeFileSync } from 'node:fs'
import { launch } from '../cdp.mjs'
import { OUT, WEB, WS, api, browser, check, clickUntil, newBusiness, realErrors } from './common.mjs'

const results = []
const shots = `${OUT}/phase_b/p1_03`
mkdirSync(shots, { recursive: true })
const wait = (ms) => new Promise((r) => setTimeout(r, ms))

const biz = await newBusiness({
  name: 'Anna Fresh Meats', category: 'fresh_grocery', sub: 'meat_shop', type: 'retail',
  modules: ['offerings-catalog', 'orders', 'payments', 'inventory', 'fulfilment', 'leads'],
})
const base = `/v1/platform/businesses/${biz.id}`
await api(`/v1/b/${biz.id}/marketplace/visibility`, { method: 'POST', body: { visibility: 'unlisted' } })
await api(`/v1/b/${biz.id}/fulfilment/settings`, { method: 'PATCH', body: { pickup_enabled: true } })
const loc = (await api(`${base}/locations`)).data.find((l) => l.is_primary).id

// ---- Workspace: add a weighed product through the editor
const owner = await browser()
let chickenId = ''
try {
  await owner.goto(`${WS}/b/${biz.id}/offerings/new`)
  await owner.waitFor('What are you adding?', { text: true })
  const kinds = await owner.eval(`[...document.querySelectorAll('.bos-kindcard strong')].map(s => s.innerText)`)
  check(kinds.includes('Sold by weight') && kinds.includes('Vehicle') && kinds.includes('Cause'), `kind picker lists the source kinds (${kinds.length})`, results)
  const fit = await owner.eval(`[...document.querySelectorAll('#fit-h ~ .bos-kindgrid strong')].map(s => s.innerText)`)
  check(fit.includes('Sold by weight') && fit.includes('Product'), `kinds for the tools in use come first (${fit.join(', ')})`, results)
  await owner.shot(`${shots}/01-kind-picker.png`, { full: true })
  await owner.goto(`${WS}/b/${biz.id}/offerings/new?kind=weighed_product`)
  await owner.waitFor('Pack sizes', { text: true })
  await owner.type('#basics-h ~ .bos-form-grid label:first-child input', 'Country chicken')
  await owner.eval(`(() => { const l = [...document.querySelectorAll('#price-h ~ .bos-form-grid label')].find(x => x.innerText.startsWith('Price per kg')); const i = l.querySelector('input'); Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(i, '320'); i.dispatchEvent(new Event('input', { bubbles: true })); return true })()`)
  await clickUntil(owner, 'Add a group of choices', '.bos-group')
  await owner.type('.bos-group .bos-rowedit input', 'Cut')
  await owner.eval(`document.querySelector('.bos-group .bos-toggle input').click()`)
  await owner.type('.bos-group .bos-rowedit--choice input', 'Curry cut')
  await owner.click('+ Add a choice', { byText: true })
  await owner.eval(`(() => { const rows = document.querySelectorAll('.bos-group .bos-rowedit--choice'); const r = rows[rows.length - 1]; const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; const [label, delta] = r.querySelectorAll('input'); set.call(label, 'Boneless'); label.dispatchEvent(new Event('input', { bubbles: true })); set.call(delta, '80'); delta.dispatchEvent(new Event('input', { bubbles: true })); return true })()`)
  await owner.eval(`document.querySelector('.bos-savebar input[type=checkbox]').click()`)
  const packPreview = await owner.eval(`[...document.querySelectorAll('.bos-rowedit__price')].map(s => s.innerText)`)
  check(packPreview.join(',') === '₹160,₹320', `pack prices preview from price per kg (${packPreview.join(', ')})`, results)
  await owner.shot(`${shots}/02-weighed-editor.png`, { full: true })
  await owner.click('Add', { byText: true })
  for (let i = 0; i < 40 && !/\/offerings\/[0-9a-f-]{36}/.test(await owner.eval('location.pathname')); i++) await wait(250)
  chickenId = (await owner.eval('location.pathname')).split('/').pop()
  const saved = (await api(`${base}/products/${chickenId}`)).data
  check(saved.offering_type === 'weighed_product' && saved.stock_unit === 'g' && saved.sell_units.length === 2
    && saved.option_groups[0].choices[1].price_delta === '80.00' && saved.status === 'active', 'weighed product saved with packs, cut and live status', results)
  await api(`${base}/inventory/opening-stock`, { method: 'POST', body: { offering_id: chickenId, location_id: loc, quantity: 8000 } })
  // A few more kinds, made through the API, for the website.
  const post = (body) => api(`${base}/products`, { method: 'POST', body: { status: 'active', ...body } })
  await post({ title: 'Swift VXi 2022', offering_type: 'vehicle', price_amount: 610000,
    attributes: { make: 'Maruti Suzuki', model: 'Swift', year: 2022, fuel: 'Petrol', transmission: 'Manual', km_driven: 21000, ownership: '1st owner' } })
  await post({ title: 'Palm Grove', offering_type: 'property_project', price_type: 'starting_from', price_amount: 8200000,
    attributes: { project_status: 'Live', location: 'OMR, Chennai', rera_number: 'TN/29/Building/0001/2026', unit_types: '2 BHK · 1,050 sq ft\n3 BHK · 1,420 sq ft' } })
  await post({ title: 'Lake View', offering_type: 'property_project', price_type: 'enquiry',
    attributes: { project_status: 'Upcoming', location: 'Tambaram, Chennai' } })
  await post({ title: 'Meals for the shelter', offering_type: 'cause', description: 'Hot lunch for 40 people every Sunday.',
    attributes: { min_amount: 200, goal_amount: 50000, suggested_amounts: '500\n1000' } })
  await post({ title: 'Haircut', offering_type: 'service', price_amount: 300 })
  await owner.goto(`${WS}/b/${biz.id}/offerings`)
  await owner.waitFor('Products & services', { text: true })
  const groups = await owner.eval(`[...document.querySelectorAll('.bos-section__title')].map(h => h.childNodes[0].textContent.trim())`)
  check(['Sold by weight', 'Vehicle', 'Property project', 'Cause', 'Service'].every((g) => groups.includes(g)), `catalogue grouped by kind (${groups.join(', ')})`, results)
  const needs = await owner.eval('document.body.innerText')
  check(needs.includes('Needs: How long it takes'), 'the service shows what it still needs', results)
  await owner.shot(`${shots}/03-catalogue.png`, { full: true })
  check(realErrors(owner).length === 0, `no console errors in Workspace (${realErrors(owner).slice(0, 2).join(' | ')})`, results)
} finally {
  await owner.close()
}

// ---- A website with an offerings section and an enquiry form, published
const site = (await api(`/v1/b/${biz.id}/website`)).data
const home = (site.draft?.pages || site.pages || []).find((p) => p.slug === 'home') || (site.draft?.pages || site.pages)[0]
await api(`/v1/b/${biz.id}/website/pages/${home.id}/sections`, { method: 'POST', body: { section_type_id: 'offerings_list', content: { title: 'Shop, book or ask' } } })
const pub = await api(`/v1/b/${biz.id}/website/publish`, { method: 'POST' }).catch((e) => ({ error: String(e) }))
check(!pub.error, `website published (${pub.error ?? 'ok'})`, results)

const visitor = await launch({ width: 1440, height: 900 })
try {
  await visitor.goto(`${WEB}/${biz.slug}`)
  await visitor.waitFor('Shop, book or ask', { text: true })
  await visitor.waitFor('.ls-offer')
  const card = `[...document.querySelectorAll('.ls-offer')].find(a => a.querySelector('.ls-item__title').innerText === 'Country chicken')`
  const chips = await visitor.eval(`[...${card}.querySelectorAll('.ls-chip')].map(c => c.innerText)`)
  check(chips.includes('500 g · ₹160') && chips.includes('Boneless +₹80'), `chicken shows packs and cuts with prices (${chips.join(' | ')})`, results)
  await visitor.eval(`[...${card}.querySelectorAll('.ls-chip')].find(c => c.innerText === 'Boneless +₹80').click()`)
  await wait(200)
  const shown = await visitor.eval(`${card}.querySelector('.ls-price').innerText`)
  check(shown === '₹240', `price follows the choice (${shown})`, results)
  await visitor.eval(`${card}.querySelector('.ls-item__foot .ls-btn').click()`)
  await visitor.waitFor('Added — 500 g · Boneless', { text: true })
  const specs = await visitor.eval(`[...document.querySelectorAll('.ls-offer')].find(a => a.innerText.includes('Swift VXi')).innerText`)
  check(specs.includes('Fuel') && specs.includes('Petrol') && specs.includes('21000 km') && specs.includes('Book a test drive'), 'vehicle shows its specs and a test-drive action', results)
  const tabs = await visitor.eval(`[...document.querySelectorAll('.ls-tab')].map(t => t.innerText)`)
  // Projects are mixed with other kinds on this page, so they show as cards;
  // the tabbed Projects section is checked on a developer's site below.
  const cause = await visitor.eval(`[...document.querySelectorAll('.ls-offer')].find(a => a.innerText.includes('Meals for the shelter')).innerText`)
  check(cause.includes('₹0 given of ₹50,000') && cause.includes('₹500') && cause.includes('Give'), 'cause shows real progress and suggested gifts', results)
  const service = await visitor.eval(`[...document.querySelectorAll('.ls-offer')].find(a => a.innerText.includes('Haircut')).innerText`)
  check(!service.includes('Add to cart'), 'a service is never put in a cart', results)
  await visitor.shot(`${shots}/04-site-cards.png`, { full: true })

  // Buy the chicken
  await visitor.goto(`${WEB}/${biz.slug}/checkout`)
  await visitor.waitFor('Cart', { text: true })
  const cart = await visitor.eval('document.body.innerText')
  check(cart.includes('500 g · Boneless'), 'basket keeps the choice', results)
  await visitor.type('input[name="name"], #name', 'Kumar').catch(() => {})
  await visitor.eval(`(() => { const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; for (const i of document.querySelectorAll('form input')) { const t = (i.name || i.placeholder || i.type || '').toLowerCase(); let v = null; if (t.includes('mail')) v = 'kumar@example.com'; else if (t.includes('name')) v = 'Kumar'; else if (t.includes('phone') || i.type === 'tel') v = '+919876500001'; if (v) { set.call(i, v); i.dispatchEvent(new Event('input', { bubbles: true })) } } return true })()`)
  await visitor.shot(`${shots}/05-checkout.png`, { full: true })
  await visitor.eval(`[...document.querySelectorAll('form button[type=submit]')].pop().click()`)
  await wait(2500)
  const orders = (await api(`${base}/orders`)).data
  check(orders.length === 1, `order placed from the site (${orders.length})`, results)
  if (orders.length) {
    const detail = (await api(`${base}/orders/${orders[0].id}`)).data
    const line = detail.items.find((i) => i.offering_id === chickenId)
    check(line && line.title === 'Country chicken — 500 g · Boneless' && Number(line.unit_price) === 240 && line.stock_quantity === 500,
      `order line priced by the server with 500 g of stock (${line?.title}, ₹${line?.unit_price})`, results)
  }

  // Test drive request → lead
  const car = (await api(`/v1/public/websites/${biz.slug}/offerings`)).data.offerings.find((o) => o.title.startsWith('Swift'))
  await visitor.goto(`${WEB}/${biz.slug}/enquire?offering_id=${car.id}&purpose=test_drive`)
  await visitor.waitFor('Book a test drive', { text: true })
  await visitor.type('.ls-enquiry input[name=name]', 'Ravi')
  await visitor.type('.ls-enquiry input[name=phone]', '+919000011111')
  const day = new Date(Date.now() + 3 * 864e5).toISOString().slice(0, 10)
  await visitor.type('.ls-enquiry input[name=preferred_date]', day)
  await visitor.shot(`${shots}/06-test-drive-form.png`, { full: true })
  await visitor.eval(`document.querySelector('.ls-enquiry button[type=submit]').click()`)
  await visitor.waitFor('Sent', { text: true })
  const leads = (await api(`${base}/leads`)).data
  check(leads.length === 1 && leads[0].origin_context.purpose_label === 'Test drive request' && leads[0].origin_context.preferred_date === day,
    'test drive request became a lead with the date', results)
  check(realErrors(visitor).length === 0, `no console errors on the site (${realErrors(visitor).slice(0, 2).join(' | ')})`, results)
  await visitor.viewport(390, 844, true)
  await visitor.goto(`${WEB}/${biz.slug}`)
  await visitor.waitFor('.ls-offer')
  check(!(await visitor.eval('document.documentElement.scrollWidth > window.innerWidth + 1')), 'site with offering cards fits 390 px', results)
  await visitor.shot(`${shots}/07-site-phone.png`, { full: true })
} finally {
  await visitor.close()
}

// ---- A developer's site: projects under status tabs
const dev = await newBusiness({ name: 'Palm Homes', category: 'real_estate', sub: 'developer', type: 'other', modules: ['offerings-catalog', 'leads'] })
const dbase = `/v1/platform/businesses/${dev.id}`
await api(`/v1/b/${dev.id}/marketplace/visibility`, { method: 'POST', body: { visibility: 'unlisted' } })
for (const [title, status] of [['Palm Grove', 'Live'], ['Lake View', 'Upcoming'], ['Green Acres', 'Completed']]) {
  await api(`${dbase}/products`, { method: 'POST', body: { status: 'active', title, offering_type: 'property_project', price_type: 'enquiry', attributes: { project_status: status, location: 'Chennai' } } })
}
const dsite = (await api(`/v1/b/${dev.id}/website`)).data
const dhome = (dsite.draft?.pages || dsite.pages || []).find((p) => p.slug === 'home') || (dsite.draft?.pages || dsite.pages)[0]
await api(`/v1/b/${dev.id}/website/pages/${dhome.id}/sections`, { method: 'POST', body: { section_type_id: 'offerings_list', content: { title: 'Our projects' } } })
await api(`/v1/b/${dev.id}/website/publish`, { method: 'POST' }).catch(() => null)
const devPage = await launch({ width: 1440, height: 900 })
try {
  await devPage.goto(`${WEB}/${dev.slug}`)
  await devPage.waitFor('.ls-tab')
  const tabs = await devPage.eval(`[...document.querySelectorAll('.ls-tab')].map(t => t.innerText)`)
  check(JSON.stringify(tabs) === JSON.stringify(['Upcoming', 'Live', 'Completed']), `projects under status tabs (${tabs.join(' · ')})`, results)
  const visible = await devPage.eval(`[...document.querySelectorAll('.ls-offer .ls-item__title')].map(t => t.innerText)`)
  check(JSON.stringify(visible) === JSON.stringify(['Palm Grove']), `Live tab shows live projects (${visible.join(', ')})`, results)
  const actions = await devPage.eval(`[...document.querySelectorAll('.ls-offer .ls-btn')].map(b => b.innerText)`)
  check(actions.includes('Book a site visit') && actions.includes('Enquire'), `project offers site visit and enquiry (${actions.join(', ')})`, results)
  await devPage.eval(`[...document.querySelectorAll('.ls-tab')].find(t => t.innerText === 'Upcoming').click()`)
  await wait(200)
  const upcoming = await devPage.eval(`[...document.querySelectorAll('.ls-offer .ls-item__title')].map(t => t.innerText)`)
  check(JSON.stringify(upcoming) === JSON.stringify(['Lake View']), 'Upcoming tab switches the list', results)
  await devPage.shot(`${shots}/08-projects-tabs.png`, { full: true })
} finally {
  await devPage.close()
  writeFileSync(`${shots}/results.json`, JSON.stringify({ business: biz, results }, null, 1))
}
