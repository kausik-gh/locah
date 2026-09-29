// P2-01 — the stage engine and assignment scope (Capability Universe §24 #10,
// #11; §7.2–§7.3).
//
//  A grocer opens Settings › Stages and adds her own steps inside Preparing —
//  "Picking", then "Packed" (which needs a note). A phone order for this
//  evening is accepted; on its page the steps show, she taps Picking (the order
//  moves to Preparing through the order rules), then Packed, which asks for a
//  note. The order board card shows "Packed", and the stage history lists each
//  move.
//
//  A salon gives Anbu the Provider role. Anbu's Home is "My day" with only his
//  appointment; Bookings lists only his; the other stylist's appointment is not
//  found, even by its address. Desktop and 390 px.
//
//   node tools/acceptance/phase_b/p2_01_stages_and_assignment.mjs
import { execFileSync } from 'node:child_process'
import { WS, DB, OUT, caller, closeAll, fits, load, must, open, recorder, sql } from './pw.mjs'

const { check, shot, finish } = recorder('p2_01_stages_and_assignment')
const owner = load(process.env.LOCAH_ACCEPT_OWNER || `${OUT}/owner2.json`)
const as = must(owner.token)
const ist = new Date(Date.now() + 5.5 * 3600e3)
const today = ist.toISOString().slice(0, 10)

// ---------------------------------------------------------------- a grocer's own steps
const shop = (await as('/v1/platform/businesses', { method: 'POST', body: {
  display_name: 'Meenakshi Stores', business_type: 'retail', category_key: 'fresh_grocery', subcategory_key: 'grocery' } })).data.business
const bid = shop.id
const base = `/v1/platform/businesses/${bid}`
for (const m of ['offerings-catalog', 'orders', 'payments', 'fulfilment', 'customer-relationships'])
  await as(`/v1/b/${bid}/modules/${m}/enable`, { method: 'POST' })
await as(`/v1/b/${bid}/fulfilment/settings`, { method: 'PATCH', body: { pickup_enabled: true } })
const dal = (await as(`${base}/products`, { method: 'POST', body: { status: 'active', offering_type: 'product', title: 'Toor dal 1 kg', price_amount: 168 } })).data
const order = (await as(`${base}/orders/phone`, { method: 'POST', body: { customer: { name: 'Lakshmi', phone: '98400 12121' },
  items: [{ offering_id: dal.id, quantity: 2 }], fulfilment_mode: 'pickup', payment_method: 'cod', due: { date: today, time: '20:00' } } })).data
const orderId = order.order?.id ?? order.id
await as(`${base}/orders/${orderId}/status`, { method: 'POST', body: { status: 'accepted' } })

const ctx = await open({ who: owner })
const p = ctx.page
try {
  await p.goto(`${WS}/b/${bid}/settings`)
  await p.getByRole('link', { name: 'Open stages →' }).click()
  await p.getByRole('heading', { name: 'Stages', exact: true }).waitFor()
  const card = p.locator('section.bos-stages', { has: p.getByRole('heading', { name: 'Orders' }) })
  await card.getByLabel('New step inside Preparing').fill('Picking')
  await card.getByRole('button', { name: 'Add step' }).nth(2).click()
  await card.getByLabel('New step inside Preparing').fill('Packed')
  await card.getByLabel('New step inside Preparing').press('Enter')
  const packedRow = card.locator('.bos-stages__steps li', { has: p.locator('input[value="Packed"]') })
  await packedRow.getByLabel('Needs a note').check()
  check((await card.getByLabel('New step inside Completed').count()) === 0, 'no steps can be added inside an ending (Completed)')
  await shot(p, '01-stages-editing.png')
  await card.getByRole('button', { name: 'Save stages' }).click()
  await card.getByText('Saved. New steps show on each record from now.').waitFor()
  const saved = sql(`select string_agg(s->>'key' || ':' || (s->>'needs_note'), ',' order by n) from platform_stage_sets, jsonb_array_elements(stages) with ordinality as t(s, n) where business_id = '${bid}' and entity = 'orders' and (s->>'custom')::boolean`)
  check(saved === 's_picking:false,s_packed:true', `the steps are saved in order, Packed needing a note (${saved})`)
  await shot(p, '02-stages-saved.png')

  await p.goto(`${WS}/b/${bid}/orders/${orderId}`)
  await p.waitForLoadState('networkidle')
  const steps = p.locator('.bos-stagetrack')
  await steps.waitFor()
  check((await steps.locator('.bos-stagepath li').allInnerTexts()).join(' / ') === 'Accepted', 'the order is at Accepted')
  await steps.getByRole('button', { name: 'Picking' }).click()
  await steps.getByText('Moved to “Picking”.').waitFor()
  const row1 = sql(`select status || ':' || stage from orders_orders where id = '${orderId}'`)
  check(row1 === 'preparing:s_picking', `Picking moves the order into Preparing through the order rules (${row1})`)
  await steps.locator('.bos-stagepath li.is-now', { hasText: 'Picking' }).waitFor()
  await steps.getByRole('button', { name: 'Packed' }).click()
  const note = steps.getByLabel('Note for “Packed”')
  await note.waitFor()
  check(await steps.getByRole('button', { name: 'Move to “Packed”' }).isDisabled(), 'Packed cannot be chosen without a note')
  await note.fill('2 bags, sealed')
  await shot(p, '03-order-packed-note.png')
  await steps.getByRole('button', { name: 'Move to “Packed”' }).click()
  await steps.getByText('Moved to “Packed”.').waitFor()
  const row2 = sql(`select stage from orders_orders where id = '${orderId}'`)
  const events = sql(`select count(*) from platform_stage_events where record_id = '${orderId}'`)
  check(row2 === 's_packed' && events === '2', `Packed is recorded with its note (${row2}, ${events} moves)`)
  await steps.locator('.bos-stagepath li.is-now', { hasText: 'Packed' }).waitFor()
  await steps.locator('summary', { hasText: '(2)' }).click()
  const hist = await steps.locator('.bos-stagetrack__history').innerText()
  check(hist.includes('Picking → Packed') && hist.includes('2 bags, sealed'), `the stage history lists the move and its note (${hist.replace(/\s+/g, ' ').slice(0, 140)})`)
  await shot(p, '04-order-steps-history.png')

  await p.goto(`${WS}/b/${bid}/orders?view=board`)
  // Let React finish hydrating before the screenshot touches the page.
  await p.waitForLoadState('networkidle')
  const cardText = await p.locator('.bos-ordercard').first().innerText()
  check(cardText.includes('Packed'), `the order board card shows the step (${cardText.replace(/\s+/g, ' ').slice(0, 140)})`)
  await shot(p, '05-board-card-step.png')
  check(p.realErrors().length === 0, `no console errors (${p.realErrors().join(' | ').slice(0, 200)})`)
} finally {
  await ctx.context.close()
}

// ---------------------------------------------------------------- a provider sees only their own
const salon = (await as('/v1/platform/businesses', { method: 'POST', body: { display_name: 'Anbu Hair Studio', business_type: 'salon' } })).data.business
const sid = salon.id
const sbase = `/v1/platform/businesses/${sid}`
for (const m of ['workforce', 'bookings', 'offerings-catalog', 'payments', 'customer-relationships'])
  await as(`/v1/b/${sid}/modules/${m}/enable`, { method: 'POST' })
const loc = (await as(`${sbase}/locations`)).data.find((l) => l.is_primary).id
const anbuFile = `${OUT}/provider_p2_01.json`
execFileSync('uv', ['run', '--no-env-file', 'python', 'tools/acceptance/stack/owner.py', DB, anbuFile], { stdio: 'ignore' })
const anbu = load(anbuFile)
const inv = (await as(`/v1/b/${sid}/team/invitations`, { method: 'POST', body: { identity_id: anbu.user_id, role: 'member' } })).data
await as(`/v1/b/${sid}/team/members/${inv.id}/activate`, { method: 'POST' })
const role = await caller(owner.token)(`${sbase}/members/${inv.id}/role`, { method: 'PUT', body: { role: 'provider' } })
check(role.ok, 'Anbu is given the Provider role')
const anbuMember = (await as(`${sbase}/workforce/members`, { method: 'POST', body: { display_name: 'Anbu', identity_id: anbu.user_id, location_ids: [loc], primary_location_id: loc } })).data.id
const bala = (await as(`${sbase}/workforce/members`, { method: 'POST', body: { display_name: 'Bala', location_ids: [loc], primary_location_id: loc } })).data.id
const person = async (name, phone) => (await as(`${sbase}/customers`, { method: 'POST', body: { display_name: name, phone } })).data.id
const [meena, ravi] = [await person('Meena', '98400 31313'), await person('Ravi', '98400 41414')]
const soon = (h) => { const d = new Date(Date.now() + h * 3600e3); d.setUTCMinutes(0, 0, 0); return d }
const book = async (provider, customer, title, h) => (await as(`${sbase}/bookings`, { method: 'POST', body: {
  location_id: loc, provider_id: provider, customer_contact_id: customer, title, reservation_mode: 'appointment',
  starts_at: soon(h).toISOString(), ends_at: new Date(soon(h).getTime() + 45 * 60e3).toISOString() } })).data.id
const mine = await book(anbuMember, meena, 'Haircut — Meena', 1)
const theirs = await book(bala, ravi, 'Facial — Ravi', 2)

{
  const c = await open({ who: anbu })
  const q = c.page
  await q.goto(`${WS}/b/${sid}`)
  await q.getByRole('heading', { name: 'My day' }).waitFor()
  await q.waitForLoadState('networkidle')
  const home = await q.locator('main').innerText()
  const sameDay = sql(`select (starts_at at time zone 'Asia/Kolkata')::date = (now() at time zone 'Asia/Kolkata')::date from bookings_bookings where id = '${mine}'`) === 't'
  check(home.includes('My next appointment and my day'), 'Anbu’s Home asks the provider’s question')
  check(sameDay ? home.includes('Haircut — Meena') && !home.includes('Facial — Ravi') : !home.includes('Facial — Ravi'),
    `My day lists only Anbu’s appointment (${home.replace(/\s+/g, ' ').slice(0, 160)})`)
  await shot(q, '06-provider-my-day.png')
  await q.goto(`${WS}/b/${sid}/bookings`)
  await q.waitForLoadState('networkidle')
  const list = await q.locator('main').innerText()
  check(list.includes('Haircut — Meena') && !list.includes('Facial — Ravi'), 'Bookings lists only Anbu’s appointment')
  check(!list.includes('Booking policy'), 'the business’s booking policy form is not offered to a provider')
  await shot(q, '07-provider-bookings.png')
  await q.goto(`${WS}/b/${sid}/bookings/${theirs}`)
  await q.waitForLoadState('networkidle')
  const other = await q.locator('main').innerText()
  check(!other.includes('Facial — Ravi') && !other.includes('Ravi'), `Bala’s appointment is not shown to Anbu, even by address (${other.replace(/\s+/g, ' ').slice(0, 120)})`)
  await shot(q, '08-provider-other-booking.png')
  const api = await caller(anbu.token)(`${sbase}/customers`)
  check(api.ok && api.data.data.map((x) => x.id).join() === meena, 'of the customer book, Anbu sees only Meena')
  check(q.realErrors().filter((e) => !/404|Not Found/i.test(e)).length === 0, `no console errors (${q.realErrors().join(' | ').slice(0, 200)})`)
  await c.context.close()
}

// ---------------------------------------------------------------- 390 px
{
  const phone = await open({ who: owner, mobile: true })
  const q = phone.page
  await q.goto(`${WS}/b/${bid}/settings/stages`)
  await q.getByRole('heading', { name: 'Stages', exact: true }).waitFor()
  check(await fits(q), 'Settings › Stages fits 390 px')
  await shot(q, '09-stages-390.png')
  await q.goto(`${WS}/b/${bid}/orders/${orderId}`)
  await q.locator('.bos-stagetrack').waitFor()
  check(await fits(q), 'the order’s steps fit 390 px')
  await q.locator('.bos-stagetrack').scrollIntoViewIfNeeded()
  await shot(q, '10-order-steps-390.png')
  await phone.context.close()
}
{
  const phone = await open({ who: anbu, mobile: true })
  await phone.page.goto(`${WS}/b/${sid}`)
  await phone.page.getByRole('heading', { name: 'My day' }).waitFor()
  check(await fits(phone.page), 'Anbu’s Home fits 390 px')
  await shot(phone.page, '11-provider-home-390.png')
  await phone.context.close()
}
await closeAll()
finish()
