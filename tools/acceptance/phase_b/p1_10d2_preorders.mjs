// P1-10D2 — dated pre-orders (MD §6.1, §21.1; Business OS Guide p.22; Founder
// refinement — Orders & Customer Transactions, "Pre-orders / scheduled orders").
//
//  The bakery's owner makes the custom cake "made to order" in the Workspace:
//  a box for the message, a day's notice, ready at 11 am or 5 pm, three a day,
//  30% advance, cancel up to 24 h before. A signed-in customer picks Black
//  forest · 2 kg · "Happy birthday Asha" on the bakery's own site; the checkout
//  (priced by the server) asks the day, shows the ₹750 advance and the balance;
//  a full day cannot be picked. Placing the order leads to the advance link; the
//  customer pays by UPI, the owner confirms it. The owner's Orders open on the
//  board by the day wanted (overdue / prepare now / today / tomorrow / later)
//  with the message on the card; Accept → Start preparing; the production list
//  for that day adds it up. The bill from the order shows the advance; the
//  customer's account and tracking show the day. Desktop and 390 px.
//
//   node tools/acceptance/phase_b/p1_10d2_preorders.mjs
import { API, WEB, WS, caller, closeAll, fits, load, must, open, recorder, sql, wait } from './pw.mjs'

const { check, shot, finish } = recorder('p1_10d2')
const OUT = process.env.LOCAH_ACCEPT_OUT || 'acceptance-out'
const owner = load(process.env.LOCAH_ACCEPT_OWNER || `${OUT}/owner2.json`)
const customer = load(process.env.LOCAH_ACCEPT_SESSION || `${OUT}/session.json`)
const as = must(owner.token)
const guestApi = caller(null)

// ------------------------------------------------------------------ the bakery
const created = (await as('/v1/platform/businesses', { method: 'POST', body: {
  display_name: 'Anjali Bakes', business_type: 'other', category_key: 'food_service', subcategory_key: 'bakery' } })).data.business
const bid = created.id
const base = `/v1/platform/businesses/${bid}`
for (const m of ['offerings-catalog', 'inventory', 'orders', 'payments', 'fulfilment', 'invoicing', 'pos',
  'customer-relationships', 'messaging']) await as(`/v1/b/${bid}/modules/${m}/enable`, { method: 'POST' })
const slug = (await as(`/v1/b/${bid}`)).data.slug
await as(`/v1/b/${bid}/fulfilment/settings`, { method: 'PATCH', body: { pickup_enabled: true } })
await as(`/v1/b/${bid}/marketplace/visibility`, { method: 'POST', body: { visibility: 'unlisted' } })
await as(`${base}/invoicing/profile`, { method: 'PUT', body: { prices_include_tax: true, round_off: false, issue_on: 'manual' } })
const reg = (await as(`${base}/invoicing/registrations`, { method: 'POST', body: { scheme: 'unregistered', legal_name: 'Anjali Bakes', state_code: '33' } })).data
const loc = (await as(`${base}/locations`)).data.find((l) => l.is_primary).id
await as(`${base}/invoicing/registers`, { method: 'POST', body: { location_id: loc, registration_id: reg.id, code: 'ANJ1' } })
await as(`${base}/pos/settings`, { method: 'PUT', body: { upi_vpa: 'anjali@okicici', upi_payee_name: 'Anjali Bakes' } })
const cake = (await as(`${base}/products`, { method: 'POST', body: {
  status: 'active', offering_type: 'menu_item', title: 'Custom cake', price_amount: 1200, visibility: 'public',
  option_groups: [
    { name: 'Flavour', required: true, max: 1, choices: [{ label: 'Chocolate', price_delta: 0 }, { label: 'Black forest', price_delta: 200 }] },
    { name: 'Weight', required: true, max: 1, choices: [{ label: '1 kg', price_delta: 0 }, { label: '2 kg', price_delta: 1100 }] },
  ] } })).data
const buns = (await as(`${base}/products`, { method: 'POST', body: {
  status: 'active', offering_type: 'menu_item', title: 'Cinnamon buns (6)', price_amount: 240, visibility: 'public' } })).data
const site = (await as(`/v1/b/${bid}/website`)).data
const home = (site.draft?.pages || site.pages || []).find((p) => p.slug === 'home') || (site.draft?.pages || site.pages)[0]
await as(`/v1/b/${bid}/website/pages/${home.id}/sections`, { method: 'POST', body: { section_type_id: 'offerings_list', content: { title: 'Cakes & bakes' } } })
check((await caller(owner.token)(`/v1/b/${bid}/website/publish`, { method: 'POST' })).ok, 'website published')

const ownerCtx = await open({ who: owner })
const op = ownerCtx.page
let orderId = ''
let orderNumber = ''
let chosenDay = ''
try {
  // ---------------------------------------------------------------- 1. the owner makes it "made to order"
  await op.goto(`${WS}/b/${bid}/offerings/${cake.id}`)
  await op.getByRole('heading', { name: 'Order ahead' }).waitFor()
  await op.getByRole('button', { name: 'Add a box the customer writes in' }).click()
  await op.getByLabel('What the customer writes').fill('Message on the cake')
  await op.getByLabel('Most letters').fill('30')
  await op.getByLabel('Made to order — needs a day').check()
  await op.getByLabel('Notice needed').fill('1')
  await op.getByLabel('Notice unit').selectOption('days')
  await op.getByLabel('Ready at').fill('11:00, 17:00')
  await op.getByLabel('How many a day').fill('3')
  await op.getByLabel('Advance type').selectOption('percent')
  await op.getByLabel('Advance amount').fill('30')
  await op.getByLabel('Cancel until').fill('24')
  await shot(op, '01-owner-order-ahead.png')
  await op.getByRole('button', { name: 'Save', exact: true }).click()
  await op.getByText('Saved. It is live.').waitFor()
  const saved = (await as(`${base}/products/${cake.id}`)).data
  check(saved.preorder?.mode === 'required' && saved.preorder.lead_hours === 24 && saved.preorder.daily_limit === 3
    && saved.preorder.advance?.value === '30.00' && saved.preorder.cancel_hours === 24
    && JSON.stringify(saved.preorder.ready_times) === '["11:00","17:00"]',
    `rules saved from the Workspace (${JSON.stringify(saved.preorder).slice(0, 160)})`)
  check(saved.option_groups.some((g) => g.text && g.name === 'Message on the cake' && g.max_length === 30), 'message box saved on the item')

  // three cakes already promised for one day → that day is full
  const priced = (await guestApi(`/v1/public/websites/${slug}/checkout/price`, { method: 'POST', body: {
    items: [{ offering_id: cake.id, quantity: 1, options: { choices: { Flavour: ['Chocolate'], Weight: ['1 kg'] } } }] } })).data.data
  const open_ = priced.preorder.dates.filter((d) => !d.full)
  const fullDay = open_[1].date
  chosenDay = open_[3].date
  const placeFor = async (email, date) => guestApi(`/v1/public/websites/${slug}/checkout`, { method: 'POST', body: {
    items: [{ offering_id: cake.id, quantity: 1, options: { choices: { Flavour: ['Chocolate'], Weight: ['1 kg'] } } }],
    fulfilment_mode: 'pickup', payment_method: 'cod', guest: { name: 'Earlier customer', email }, due: { date, time: '11:00' } } })
  for (const n of [1, 2, 3]) await placeFor(`early${n}-${Date.now()}@example.com`, fullDay)
  const fourth = await placeFor(`late-${Date.now()}@example.com`, fullDay)
  check(fourth.status === 422 && JSON.stringify(fourth.data).includes('full'), `a fourth cake for ${fullDay} is refused (${fourth.status})`)

  // ---------------------------------------------------------------- 2. the customer orders it on the bakery's site
  const cust = await open({ who: customer })
  const cp = cust.page
  await cp.goto(`${WEB}/${slug}`)
  const card = cp.locator('.ls-offer', { hasText: 'Custom cake' })
  await card.waitFor()
  const hint = await card.locator('.ls-offer__ahead').innerText()
  check(hint.includes('Made to order') && hint.includes('ready from') && hint.includes('30% advance'), `card says made to order (${hint})`)
  await card.getByRole('button', { name: /^Black forest/ }).click()
  await card.getByRole('button', { name: /^2 kg/ }).click()
  await card.getByLabel(/Message on the cake/).fill('Happy birthday Asha')
  await shot(cp, '02-customer-chooses-cake.png')
  await card.getByRole('button', { name: 'Add' }).click()
  await card.getByText(/Added/).waitFor()
  await cp.goto(`${WEB}/${slug}/checkout`)
  await cp.getByRole('heading', { name: 'When do you need it?' }).waitFor()
  await cp.getByText('₹2,500').first().waitFor()
  let body = await cp.locator('main').innerText()
  check(body.includes('Custom cake — Black forest · 2 kg · “Happy birthday Asha”') && body.includes('₹2,500'),
    'basket line priced by the server with the choices and the message')
  check(body.includes('Made to order — the earliest is'), 'checkout names the earliest day')
  const dayOptions = await cp.getByLabel('Day').locator('option').evaluateAll((os) => os.map((o) => ({ v: o.value, t: o.textContent, d: o.disabled })))
  const full = dayOptions.find((o) => o.v === fullDay)
  check(full && full.d && full.t.includes('full'), `the full day cannot be picked (${full?.t})`)
  await cp.getByLabel('Day').selectOption(chosenDay)
  await cp.getByLabel('Ready at').selectOption('17:00')
  await wait(800)
  body = await cp.locator('main').innerText()
  check(body.includes('Advance now') && body.includes('₹750') && body.includes('Balance at pickup') && body.includes('₹1,750'),
    'total ₹2,500 with ₹750 advance now and ₹1,750 at pickup')
  check(body.includes('You can cancel up to 24 hours before it is due'), 'cancel window shown before placing')
  const btnBg = await cp.locator('.ls-checkout__place').evaluate((e) => getComputedStyle(e).backgroundColor)
  check(!['rgb(37, 99, 235)', 'rgb(194, 70, 26)'].includes(btnBg), `checkout uses the bakery's colours (${btnBg})`)
  await shot(cp, '03-checkout-day-and-advance.png')
  await cp.getByRole('button', { name: /Place order · pay ₹750 advance/ }).click()
  await cp.getByRole('heading', { name: 'Order confirmed' }).waitFor()
  body = await cp.locator('main').innerText()
  check(body.includes('ready') && body.includes('5 pm') && body.includes('₹750'), `confirmation names the day and the advance (${body.replace(/\s+/g, ' ').slice(0, 140)})`)
  await shot(cp, '04-confirmed-pay-advance.png')
  const mine = (await as(`${base}/orders?channel=web`)).data.find((o) => o.due_at && o.due_at.startsWith(chosenDay))
  orderId = mine.id
  orderNumber = mine.order_number
  check(mine.preorder && mine.advance_amount === 750, `order ${orderNumber} is a pre-order asking ₹750`)
  await cp.getByRole('link', { name: 'Pay ₹750 advance' }).click()
  await cp.getByText('Payment to Anjali Bakes').waitFor()
  body = await cp.locator('main').innerText()
  check(body.includes('Advance for') && body.includes('Advance — paying now') && body.includes('₹750'), 'the advance link opens on the same order')
  await cp.getByRole('button', { name: /I have paid ₹750/ }).click()
  await cp.getByText('Payment still being confirmed').waitFor()

  // ---------------------------------------------------------------- 3. the owner's day
  await op.goto(`${WS}/b/${bid}/payments`)
  const waiting = op.locator('section[aria-labelledby=pay-confirm] li').filter({ hasText: `Order ${orderNumber}` })
  await waiting.getByRole('button', { name: 'It arrived' }).click()
  await waiting.waitFor({ state: 'detached' })
  // one earlier order is now late (the clock moved on for it)
  const earlier = (await as(`${base}/orders`)).data.find((o) => o.due_at && o.due_at.startsWith(fullDay))
  sql(`update orders_orders set due_at = now() - interval '1 hour' where id = '${earlier.id}'`)
  await op.goto(`${WS}/b/${bid}/orders`)
  await op.getByRole('heading', { name: 'Overdue' }).waitFor()
  const cols = await op.locator('.bos-board__h').allInnerTexts()
  check(cols.map((c) => c.replace(/\s*\d+$/, '').trim()).join('|') === 'Overdue|Prepare now|Today|Tomorrow|Later',
    `board columns: ${cols.map((c) => c.replace(/\s+/g, ' ')).join(' · ')}`)
  const ours = op.locator('.bos-ordercard', { hasText: orderNumber })
  const cardText = await ours.innerText()
  check(cardText.includes('Message on the cake: “Happy birthday Asha”') && cardText.includes('Advance paid') && cardText.includes('Website'),
    `the card shows the message, advance paid and where it came from (${cardText.replace(/\s+/g, ' ').slice(0, 160)})`)
  const lateCol = await op.locator('.bos-board__col--overdue').innerText()
  check(lateCol.includes(earlier.order_number), `the late order sits under Overdue (${earlier.order_number})`)
  await shot(op, '05-board-by-day.png')
  await ours.getByRole('button', { name: 'Accept' }).click()
  await op.locator('.bos-ordercard', { hasText: orderNumber }).getByRole('button', { name: 'Start preparing' }).click()
  await op.locator('.bos-ordercard', { hasText: orderNumber }).getByText('Preparing', { exact: true }).waitFor()
  check((await as(`${base}/orders/${orderId}`)).data.status === 'preparing', 'Accept → Start preparing from the board')
  await op.goto(`${WS}/b/${bid}/orders/production?date=${chosenDay}`)
  await op.getByRole('heading', { name: /Production/ }).waitFor()
  const prod = await op.locator('.bos-prodlist').innerText()
  check(prod.includes('1 ×') && prod.includes('Custom cake — Black forest · 2 kg') && prod.includes('“Happy birthday Asha”') && prod.includes(orderNumber),
    `production list for the day adds it up with the message (${prod.replace(/\s+/g, ' ').slice(0, 160)})`)
  await shot(op, '06-production-list.png')
  await op.goto(`${WS}/b/${bid}/orders/production?date=${fullDay}`)
  const prodFull = await op.locator('.bos-prodlist').innerText()
  check(/2 ×\s*Custom cake — Chocolate · 1 kg/.test(prodFull.replace(/\n/g, ' ')), `the full day still due lists the other cakes (${prodFull.replace(/\s+/g, ' ').slice(0, 90)})`)

  // the order page, the bill, the customer's view
  await op.goto(`${WS}/b/${bid}/orders/${orderId}`)
  const header = (await op.locator('main').first().innerText()).toLowerCase()
  check(header.includes('wanted for') && header.includes('advance asked') && header.includes('part paid'), `order page: wanted for, advance asked, part paid (${header.replace(/\s+/g, ' ').slice(0, 200)})`)
  check(await op.getByRole('button', { name: 'Mark ready' }).isVisible(), 'the next step reads "Mark ready", not a stored state')
  await op.getByRole('button', { name: 'Issue bill' }).click()
  await op.waitForURL(/\/invoices\//, { timeout: 8000 }).catch(() => undefined)
  if (!op.url().includes('/invoices/')) await op.getByRole('link', { name: /Open bill|ANJ1/ }).first().click()
  await op.getByText('already paid on the order').waitFor()
  check((await op.locator('.bos-inv-side').innerText()).includes('₹750.00 already paid on the order'), 'the bill knows the ₹750 advance')
  await shot(op, '07-bill-with-advance.png')
  await wait(2000)
  await cp.goto(`${WEB}/${slug}/account`)
  await cp.getByText(`Order ${orderNumber}`).waitFor()
  const acct = await cp.locator('main').innerText()
  check(acct.includes('Wanted for') && acct.includes('5 pm'), 'customer account shows the day it is wanted')
  await shot(cp, '08-customer-account-day.png')
  check(op.realErrors().length === 0, `owner pages: no console errors (${op.realErrors().join(' | ').slice(0, 300)})`)
  check(cp.realErrors().length === 0, `customer pages: no console errors (${cp.realErrors().join(' | ').slice(0, 300)})`)
  await cust.context.close()
} finally {
  await ownerCtx.context.close()
}

// ---------------------------------------------------------------- 390 px
{
  const phone = await open({ who: customer, mobile: true })
  const p = phone.page
  await p.goto(`${WEB}/${slug}`)
  await p.evaluate(([s, id]) => localStorage.setItem(`platform.cart.${s}`, JSON.stringify([{ offering_id: id, title: 'Custom cake', quantity: 1, unit_price: 1200, currency: 'INR',
    options: { choices: { Flavour: ['Chocolate'], Weight: ['1 kg'] } } }])), [slug, cake.id])
  await p.goto(`${WEB}/${slug}/checkout`)
  await p.getByRole('heading', { name: 'When do you need it?' }).waitFor()
  await wait(800)
  check(await fits(p), 'checkout with the day picker fits 390 px')
  await shot(p, '09-checkout-390.png')
  const phoneOwner = await open({ who: owner, mobile: true })
  await phoneOwner.page.goto(`${WS}/b/${bid}/orders`)
  await phoneOwner.page.getByRole('heading', { name: 'Overdue' }).waitFor()
  check(await fits(phoneOwner.page), 'the board fits 390 px (columns stack)')
  await shot(phoneOwner.page, '10-board-390.png')
  await phoneOwner.page.goto(`${WS}/b/${bid}/orders/production?date=${chosenDay}`)
  check(await fits(phoneOwner.page), 'production list fits 390 px')
  await shot(phoneOwner.page, '11-production-390.png')
  check(p.realErrors().length === 0 && phoneOwner.page.realErrors().length === 0, '390 px: no console errors')
  await phone.context.close()
  await phoneOwner.context.close()
}

// ---------------------------------------------------------------- a business without dated items keeps the plain list
{
  const ctx = await open({ who: owner })
  await as(`${base}/products/${cake.id}`, { method: 'PATCH', body: { preorder: null, version: (await as(`${base}/products/${cake.id}`)).data.version } })
  sql(`update orders_orders set status = 'completed' where business_id = '${bid}'`)
  await ctx.page.goto(`${WS}/b/${bid}/orders`)
  await ctx.page.getByRole('heading', { name: 'Orders' }).waitFor()
  check(await ctx.page.locator('.bos-board').count() === 0, 'with nothing made for a day, Orders is the plain list (no empty board forced on the business)')
  void buns
  await ctx.context.close()
}

await closeAll()
finish()
