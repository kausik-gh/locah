// P1-10E2 — customer tags and rule-built segments (CR-03, CR-04; MD §6.1; §18.2
// Audiences "rule-built segments … shows counts; only consented contacts for
// WhatsApp").
//
//  A sweet shop's customers come from real orders, a counter bill and khata.
//  The owner tags a customer on their page (adds "diwali box", removes "vip"),
//  filters the customer list by a tag, then builds a segment in the Workspace —
//  "bought Mysore pak 2+ times in the last 60 days" and "tagged regular" — sees
//  who is in it and how many said yes to WhatsApp offers, saves it, opens it,
//  and after another customer's orders the segment includes them the next time
//  it is opened. Desktop and 390 px.
//
//   node tools/acceptance/phase_b/p1_10e_segments.mjs
import { WS, closeAll, fits, load, must, open, recorder } from './pw.mjs'

const { check, shot, finish } = recorder('p1_10e_segments')
const OUT = process.env.LOCAH_ACCEPT_OUT || 'acceptance-out'
const owner = load(process.env.LOCAH_ACCEPT_OWNER || `${OUT}/owner2.json`)
const as = must(owner.token)

const created = (await as('/v1/platform/businesses', { method: 'POST', body: {
  display_name: 'Sri Krishna Sweets', business_type: 'other', category_key: 'food_service', subcategory_key: 'bakery' } })).data.business
const bid = created.id
const base = `/v1/platform/businesses/${bid}`
for (const m of ['offerings-catalog', 'orders', 'payments', 'invoicing', 'customer-relationships', 'ledger'])
  await as(`/v1/b/${bid}/modules/${m}/enable`, { method: 'POST' })
await as(`${base}/invoicing/profile`, { method: 'PUT', body: { prices_include_tax: true, round_off: false, issue_on: 'manual' } })
const reg = (await as(`${base}/invoicing/registrations`, { method: 'POST', body: { scheme: 'unregistered', legal_name: 'Sri Krishna Sweets', state_code: '33' } })).data
const loc = (await as(`${base}/locations`)).data.find((l) => l.is_primary).id
await as(`${base}/invoicing/registers`, { method: 'POST', body: { location_id: loc, registration_id: reg.id, code: 'SKS1' } })
const pak = (await as(`${base}/products`, { method: 'POST', body: { status: 'active', offering_type: 'product', title: 'Mysore pak 500 g', price_amount: 380, hsn_sac: '1704' } })).data
const murukku = (await as(`${base}/products`, { method: 'POST', body: { status: 'active', offering_type: 'product', title: 'Murukku 250 g', price_amount: 120, hsn_sac: '1905' } })).data
const cust = async (display_name, phone, tags = []) => (await as(`${base}/customers`, { method: 'POST', body: { display_name, phone, tags } })).data.id
const asha = await cust('Asha Raman', '+919840011001', ['regular', 'vip'])
const ravi = await cust('Ravi Kumar', '+919840011002', ['regular'])
const meena = await cust('Meena S', '+919840011003')
const order = (contact, item, quantity = 1) => as(`${base}/orders`, { method: 'POST', body: {
  location_id: loc, payment_method: 'pay_at_business', channel: 'phone', customer_contact_id: contact, items: [{ offering_id: item, quantity }] } })
await order(asha, pak.id)
await order(asha, pak.id, 2)
await order(ravi, murukku.id)
await as(`${base}/invoices`, { method: 'POST', body: { issue: true, customer_contact_id: meena, lines: [{ offering_id: pak.id, quantity: 3 }] } })
await as(`${base}/ledger/accounts`, { method: 'POST', body: { party_type: 'customer', customer_contact_id: ravi, opening_balance: 240 } })
await as(`${base}/customers/${asha}/consents`, { method: 'POST', body: { purpose: 'marketing', channel: 'whatsapp', granted: true, source: 'staff_recorded' } })

const ctx = await open({ who: owner })
const p = ctx.page
try {
  // ---------------------------------------------------------------- 1. tags on a customer
  await p.goto(`${WS}/b/${bid}/customers/${asha}`)
  await p.getByRole('heading', { name: 'Tags' }).waitFor()
  await p.getByLabel('New tag').fill('Diwali  Box')
  await p.getByRole('button', { name: 'Add tag' }).click()
  await p.locator('.bos-tag', { hasText: 'diwali box' }).waitFor()
  await p.getByRole('button', { name: 'Remove tag vip' }).click()
  await p.locator('.bos-tag', { hasText: 'vip' }).waitFor({ state: 'detached' })
  const saved = (await as(`${base}/customers/${asha}`)).data.tags
  check(JSON.stringify(saved) === '["regular","diwali box"]', `tags saved as the owner left them (${JSON.stringify(saved)})`)
  await shot(p, '01-customer-tags.png')

  // ---------------------------------------------------------------- 2. the list by tag
  await p.goto(`${WS}/b/${bid}/customers`)
  await p.locator('.bos-tagbar').waitFor()
  const bar = await p.locator('.bos-tagbar').innerText()
  check(bar.includes('regular · 2') && bar.includes('diwali box · 1') && !bar.includes('vip'), `tag bar with counts (${bar.replace(/\s+/g, ' ')})`)
  await p.locator('.bos-tagbar a', { hasText: 'regular · 2' }).click()
  await p.waitForURL(/tag=regular/)
  const rows = await p.locator('table tbody tr').allInnerTexts()
  check(rows.length === 2 && rows.some((r) => r.includes('Asha Raman')) && rows.some((r) => r.includes('Ravi Kumar')), `filtered to the two regulars (${rows.length})`)
  await shot(p, '02-customers-by-tag.png')

  // ---------------------------------------------------------------- 3. build a segment
  await p.getByRole('link', { name: 'Segments' }).click()
  await p.getByRole('heading', { name: 'Build a segment' }).waitFor()
  check((await p.locator('main').innerText()).includes('No segments yet'), 'no segments yet, with what to do')
  const kinds = await p.locator('select[name=rule-0-kind] option').allInnerTexts()
  check(kinds.includes('Owes on khata') && !kinds.includes('Booked') && !kinds.includes('Membership ended and not renewed'),
    `rules offered follow the tools that are on (${kinds.join(', ')})`)
  await p.locator('select[name=rule-0-kind]').selectOption('bought')
  await p.locator('select[name=rule-0-offering_id]').selectOption(pak.id)
  await p.locator('input[name=rule-0-times]').fill('2')
  await p.locator('input[name=rule-0-days]').fill('60')
  await p.getByRole('button', { name: 'See who is in it' }).click()
  await p.locator('.bos-seg-count').waitFor()
  let text = await p.locator('section[aria-labelledby=seg-new-h]').innerText()
  check(text.includes('1 customer') && text.includes('Asha Raman') && !text.includes('Meena'),
    'bought Mysore pak 2+ times: Asha (two orders); Meena bought once at the counter')
  await p.getByRole('button', { name: 'Add a rule' }).click()
  await p.locator('select[name=rule-1-kind]').selectOption('tag')
  await p.locator('input[name=rule-1-tag]').fill('regular')
  await p.getByRole('button', { name: 'See who is in it' }).click()
  await p.getByText('Tagged “regular”').waitFor()
  text = await p.locator('section[aria-labelledby=seg-new-h]').innerText()
  check(text.includes('1 customer') && text.includes('1 said yes to offers on WhatsApp'), 'both rules: 1 customer, 1 can be sent a WhatsApp offer')
  await shot(p, '03-builder-preview.png')
  await p.locator('input[name=segment-name]').fill('Mysore pak regulars')
  await p.getByRole('button', { name: 'Save segment' }).click()
  await p.getByText('Saved “Mysore pak regulars”.').waitFor()
  await p.locator('.bos-catalogue li', { hasText: 'Mysore pak regulars' }).waitFor()
  text = await p.locator('.bos-catalogue li', { hasText: 'Mysore pak regulars' }).innerText()
  check(text.includes('1 customer') && text.includes('Bought Mysore pak 500 g 2+ times in the last 60 days'), 'the saved segment lists its count and rules in words')

  // ---------------------------------------------------------------- 4. members are worked out each time
  await order(ravi, pak.id)
  await order(ravi, pak.id)
  await p.locator('.bos-catalogue li', { hasText: 'Mysore pak regulars' }).getByRole('link').click()
  await p.getByRole('heading', { name: 'Mysore pak regulars' }).waitFor()
  text = await p.locator('main').innerText()
  check(text.includes('2 customers') && text.includes('Asha Raman') && text.includes('Ravi Kumar'), 'Ravi joins after his two orders — nobody re-saved the segment')
  await shot(p, '04-segment-members.png')
  check(p.realErrors().length === 0, `owner: no console errors (${p.realErrors().join(' | ').slice(0, 300)})`)
} finally {
  await ctx.context.close()
}

// ---------------------------------------------------------------- 390 px
{
  const phone = await open({ who: owner, mobile: true })
  const q = phone.page
  await q.goto(`${WS}/b/${bid}/customers/segments`)
  await q.getByRole('heading', { name: 'Build a segment' }).waitFor()
  const spill = await q.evaluate(() => [...document.querySelectorAll('main input, main select, main button')]
    .filter((e) => e.getBoundingClientRect().right > window.innerWidth + 1).map((e) => e.getAttribute('name') || e.textContent))
  check(await fits(q) && spill.length === 0, `segments and the builder fit 390 px (${spill.join(', ') || 'no field spills'})`)
  await shot(q, '05-segments-390.png')
  await q.goto(`${WS}/b/${bid}/customers/${asha}`)
  await q.getByRole('heading', { name: 'Tags' }).waitFor()
  check(await fits(q), 'a customer with tags fits 390 px')
  await shot(q, '06-customer-390.png')
  check(q.realErrors().length === 0, '390 px: no console errors')
  await phone.context.close()
}

await closeAll()
finish()
