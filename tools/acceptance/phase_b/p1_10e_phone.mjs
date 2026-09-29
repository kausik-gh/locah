// P1-10E5 — a phone order taken by staff, then changed (FR-OR-13, FR-OR-18;
// Founder: Orders — "Human phone order: staff creates the same Order using
// current catalogue, stock, pricing, tax, delivery and payment rules";
// "Order edits must revalidate price, stock, tax, delivery, payment difference
// and preserve audit history").
//
//  A bakery owner takes a call: buns, and a custom cake (flavour, weight, a
//  message) for delivery. The screen prices it as the website would — delivery
//  charge for the address, the day the cake can be ready, the 30% advance — and
//  places it; the advance link is ready to send. The customer calls back: one
//  more box of buns and a plum cake. "Change order" shows the new total and what
//  is still to collect before saving; saving needs their agreement, and asking
//  for more plum cake than is in stock is refused. Desktop and 390 px.
//
//   node tools/acceptance/phase_b/p1_10e_phone.mjs
import { WS, closeAll, load, must, open, recorder, sql } from './pw.mjs'

const { check, shot, finish } = recorder('p1_10e_phone')
const OUT = process.env.LOCAH_ACCEPT_OUT || 'acceptance-out'
const owner = load(process.env.LOCAH_ACCEPT_OWNER || `${OUT}/owner2.json`)
const as = must(owner.token)

const created = (await as('/v1/platform/businesses', { method: 'POST', body: {
  display_name: 'Madhuram Bakes', business_type: 'other', category_key: 'food_service', subcategory_key: 'bakery' } })).data.business
const bid = created.id
const base = `/v1/platform/businesses/${bid}`
for (const m of ['offerings-catalog', 'inventory', 'orders', 'payments', 'fulfilment', 'customer-relationships'])
  await as(`/v1/b/${bid}/modules/${m}/enable`, { method: 'POST' })
await as(`/v1/b/${bid}/fulfilment/settings`, { method: 'PATCH', body: { pickup_enabled: true, delivery_enabled: true } })
await as(`/v1/b/${bid}/fulfilment/zones`, { method: 'POST', body: { name: 'Chennai', match_type: 'city', city: 'Chennai', charge_amount: 40 } })
const loc = (await as(`${base}/locations`)).data.find((l) => l.is_primary).id
const buns = (await as(`${base}/products`, { method: 'POST', body: { status: 'active', offering_type: 'menu_item', title: 'Cinnamon buns (6)', price_amount: 240 } })).data
await as(`${base}/products`, { method: 'POST', body: {
  status: 'active', offering_type: 'menu_item', title: 'Custom cake', price_amount: 1200,
  option_groups: [
    { name: 'Flavour', required: true, max: 1, choices: [{ label: 'Chocolate', price_delta: 0 }, { label: 'Black forest', price_delta: 200 }] },
    { name: 'Weight', required: true, max: 1, choices: [{ label: '1 kg', price_delta: 0 }, { label: '2 kg', price_delta: 1100 }] },
    { name: 'Message on the cake', text: true, required: false, max_length: 30 }],
  preorder: { mode: 'required', lead_hours: 24, ready_times: ['11:00', '17:00'], max_days: 30, advance: { type: 'percent', value: 30 } } } })
const plum = (await as(`${base}/products`, { method: 'POST', body: { status: 'active', offering_type: 'product', title: 'Plum cake 500 g', price_amount: 450, track_inventory: true } })).data
await as(`${base}/inventory/opening-stock`, { method: 'POST', body: { offering_id: plum.id, location_id: loc, quantity: 3 } })

const ctx = await open({ who: owner })
const p = ctx.page
let orderId = ''
try {
  // ---------------------------------------------------------------- 1. the call
  await p.goto(`${WS}/b/${bid}/orders`)
  await p.getByRole('link', { name: 'Take a phone order' }).first().click()
  await p.getByRole('heading', { name: 'Take a phone order' }).waitFor()
  await p.locator('input[name=caller-name]').fill('Revathi')
  await p.locator('input[name=caller-phone]').fill('98400 12121')
  await p.locator('select[name=pick-item]').selectOption(buns.id)
  await p.locator('input[name=pick-qty]').fill('2')
  await p.getByRole('button', { name: 'Add to order' }).click()
  await p.locator('select[name=pick-item]').selectOption({ label: 'Custom cake' })
  await p.getByRole('button', { name: 'Add to order' }).click()
  await p.getByText('Choose flavour.').waitFor()
  check(true, 'a required choice must be picked before the cake is added')
  await p.locator('select[name="pick-choice-Flavour"]').selectOption('Black forest')
  await p.locator('select[name="pick-choice-Weight"]').selectOption('2 kg')
  await p.locator('input[name="pick-note-Message on the cake"]').fill('Happy birthday Asha')
  await p.getByRole('button', { name: 'Add to order' }).click()
  await p.getByRole('radio', { name: 'Delivery' }).check()
  await p.locator('input[name=addr-line1]').fill('14 Lake View Road')
  await p.locator('input[name=addr-city]').fill('Chennai')
  await p.locator('input[name=addr-pin]').fill('600033')
  await p.locator('.bos-phone__lines li', { hasText: 'Delivery' }).waitFor()
  await p.locator('select[name=due-date]').waitFor()
  const total = await p.locator('section[aria-labelledby=total-h]').innerText()
  check(total.includes('Custom cake — Black forest · 2 kg · “Happy birthday Asha”') && total.includes('₹2,500') && total.includes('₹480'),
    `the server prices the cake with its choices and the buns (${total.replace(/\s+/g, ' ').slice(0, 160)})`)
  check(total.includes('Delivery') && total.includes('₹40') && total.includes('₹3,020'), 'delivery charge for the address and the total')
  check(total.includes('Advance to ask: ₹750'), 'the cake’s 30% advance (₹750 — the buns ask none)')
  const dayOptions = await p.locator('select[name=due-date] option').allInnerTexts()
  check(dayOptions.length > 3, `the day picker offers the days the cake can be ready (${dayOptions.length})`)
  await p.locator('select[name=due-time]').selectOption('17:00')
  await shot(p, '01-phone-order.png')
  await p.getByRole('button', { name: 'Place the order' }).click()
  await p.getByRole('heading', { name: /Order .* placed/ }).waitFor()
  const done = await p.locator('main').innerText()
  check(done.includes('Advance ₹750') && done.includes('/pay/') && done.includes('Send the link on WhatsApp'), 'the advance link is ready to send or read out')
  await shot(p, '02-placed.png')
  await p.getByRole('link', { name: 'Open the order' }).click()
  await p.waitForURL(/\/orders\/[0-9a-f-]{36}/)
  orderId = p.url().split('/orders/')[1].split('?')[0]
  const row = sql(`select o.channel, c.display_name, c.phone, j.mode from orders_orders o join customer_relationships_contacts c on c.id = o.customer_contact_id join fulfilment_jobs j on j.order_id = o.id where o.id = '${orderId}'`)
  check(row === 'phone|Revathi|+919840012121|delivery', `stored as one order: ${row}`)

  // ---------------------------------------------------------------- 2. the call back: change it
  await p.getByRole('button', { name: 'Change order' }).click()
  await p.getByRole('heading', { name: 'Change order' }).waitFor()
  await p.getByLabel('How many Cinnamon buns (6)').fill('3')
  await p.locator('section[aria-labelledby=change-h] select[name=pick-item]').selectOption(plum.id)
  await p.locator('section[aria-labelledby=change-h] input[name=pick-qty]').fill('5')
  await p.locator('section[aria-labelledby=change-h]').getByRole('button', { name: 'Add to order' }).click()
  await p.getByRole('button', { name: 'See the new total' }).click()
  await p.locator('section[aria-labelledby=change-h] .bos-error, section[aria-labelledby=change-h] .bos-status.bos-error').first().waitFor()
  const refusal = await p.locator('section[aria-labelledby=change-h]').innerText()
  check(/stock/i.test(refusal), 'asking for more plum cake than is in stock is refused before saving')
  await p.getByLabel('How many Plum cake 500 g (new)').fill('1').catch(async () => {
    await p.locator('.bos-change__row', { hasText: 'Plum cake' }).locator('input').fill('1')
  })
  await p.getByRole('button', { name: 'See the new total' }).click()
  await p.locator('.bos-change__result').waitFor()
  const res = await p.locator('.bos-change__result').innerText()
  check(res.includes('₹3,020 → ₹3,710') && res.includes('still to collect'), `new total and money difference shown (${res.replace(/\s+/g, ' ').slice(0, 160)})`)
  const save = p.getByRole('button', { name: 'Save the change' })
  check(await save.isDisabled(), 'saving waits for the customer’s agreement')
  await p.getByText('The customer agreed to this change').click()
  await p.locator('input[name=change-reason]').fill('Customer called back')
  await shot(p, '03-change-preview.png')
  await save.click()
  await p.locator('section[aria-labelledby=change-h]').waitFor({ state: 'detached' })
  await p.locator('table').first().getByText('Plum cake 500 g').waitFor()
  const items = await p.locator('table').first().innerText()
  const money = await p.locator('main').innerText()
  check(money.includes('₹3,710') && money.includes('₹3,710 · Cash on delivery'), 'the total and the cash expected follow the change')
  check(items.includes('Plum cake 500 g') && /Cinnamon buns \(6\)\s+3/.test(items), 'the order shows the changed items')
  const hist = sql(`select reason from orders_order_status_history where order_id = '${orderId}' order by created_at desc limit 1`)
  check(hist.startsWith('Changed: ') && hist.includes('Customer called back'), `kept in the order's history (${hist})`)
  const reserved = sql(`select quantity_reserved from inventory_records where offering_id = '${plum.id}'`)
  check(reserved === '1', `plum cake reserved for the change (${reserved})`)
  await shot(p, '04-changed.png')
  check(p.realErrors().length === 0, `no console errors (${p.realErrors().join(' | ').slice(0, 200)})`)
} finally {
  await ctx.context.close()
}

// ---------------------------------------------------------------- 390 px
{
  const phone = await open({ who: owner, mobile: true })
  const q = phone.page
  await q.goto(`${WS}/b/${bid}/orders/new`)
  await q.getByRole('heading', { name: 'Take a phone order' }).waitFor()
  await q.locator('select[name=pick-item]').selectOption({ label: 'Custom cake' })
  const spill = await q.evaluate(() => [...document.querySelectorAll('main input, main select, main button')]
    .filter((e) => e.getBoundingClientRect().right > window.innerWidth + 1).map((e) => e.getAttribute('name') || e.textContent))
  check(spill.length === 0, `the phone order screen fits 390 px (${spill.join(', ') || 'no field spills'})`)
  await shot(q, '05-phone-order-390.png')
  await q.goto(`${WS}/b/${bid}/orders/${orderId}`)
  await q.getByRole('button', { name: 'Change order' }).click()
  const spill2 = await q.evaluate(() => [...document.querySelectorAll('main input, main select, main button')]
    .filter((e) => e.getBoundingClientRect().right > window.innerWidth + 1).length)
  check(spill2 === 0, `change order fits 390 px (${spill2} spill)`)
  await shot(q, '06-change-390.png')
  await phone.context.close()
}

await closeAll()
finish()
