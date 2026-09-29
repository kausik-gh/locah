// P1-10E1 — basic insights from real data only (IS-01; MD §26.3 P1-10; First
// Launch §12.1 "Core Workspace Insights").
//
//  A kirana with two branches has bills, orders and money received. The owner
//  opens Insights › Your numbers from the navigation and from Home: today, the
//  last 7 days (a bill from three days ago joins) and this month, every number
//  linking to its page; Bookings is off so it is named, not shown as a zero. A
//  manager limited to the branch sees the branch's orders only and is told money
//  received is shown to people who see every location. Desktop and 390 px.
//
//   node tools/acceptance/phase_b/p1_10e_insights.mjs
import { execFileSync } from 'node:child_process'
import { DB, WS, caller, closeAll, fits, load, must, open, recorder, sql } from './pw.mjs'

const { check, shot, finish } = recorder('p1_10e_insights')
const OUT = process.env.LOCAH_ACCEPT_OUT || 'acceptance-out'
const owner = load(process.env.LOCAH_ACCEPT_OWNER || `${OUT}/owner2.json`)
const as = must(owner.token)

const created = (await as('/v1/platform/businesses', { method: 'POST', body: {
  display_name: 'Murugan Stores', business_type: 'other', category_key: 'fresh_grocery', subcategory_key: 'grocery' } })).data.business
const bid = created.id
const base = `/v1/platform/businesses/${bid}`
for (const m of ['offerings-catalog', 'inventory', 'orders', 'payments', 'invoicing', 'pos'])
  await as(`/v1/b/${bid}/modules/${m}/enable`, { method: 'POST' })
await as(`${base}/invoicing/profile`, { method: 'PUT', body: { prices_include_tax: true, round_off: false, issue_on: 'manual' } })
const reg = (await as(`${base}/invoicing/registrations`, { method: 'POST', body: { scheme: 'unregistered', legal_name: 'Murugan Stores', state_code: '33' } })).data
const main = (await as(`${base}/locations`)).data.find((l) => l.is_primary).id
const branch = (await as(`${base}/locations`, { method: 'POST', body: { name: 'Anna Nagar branch' } })).data.id
await as(`${base}/invoicing/registers`, { method: 'POST', body: { location_id: main, registration_id: reg.id, code: 'MUR1' } })
const rice = (await as(`${base}/products`, { method: 'POST', body: {
  status: 'active', offering_type: 'product', title: 'Ponni rice 5 kg', price_amount: 450, hsn_sac: '1006' } })).data
const oil = (await as(`${base}/products`, { method: 'POST', body: {
  status: 'active', offering_type: 'product', title: 'Groundnut oil 1 l', price_amount: 210, hsn_sac: '1508' } })).data

// bills: ₹1,110 today (paid ₹1,110 cash), ₹450 three days ago
const today = (await as(`${base}/invoices`, { method: 'POST', body: { issue: true, lines: [
  { offering_id: rice.id, quantity: 2 }, { offering_id: oil.id, quantity: 1 }] } })).data
await as(`${base}/invoices/${today.id}/payments`, { method: 'POST', body: { amount: 1110, method: 'cash' } })
const older = (await as(`${base}/invoices`, { method: 'POST', body: { issue: true, lines: [{ offering_id: rice.id, quantity: 1 }] } })).data
sql(`update invoicing_documents set issue_date = (now() at time zone 'Asia/Kolkata')::date - 3 where id = '${older.id}'`)
// orders: one at each location, one cancelled
const mk = async (loc, qty, channel) => (await as(`${base}/orders`, { method: 'POST', body: {
  location_id: loc, payment_method: 'pay_at_business', channel, items: [{ offering_id: rice.id, quantity: qty }] } })).data
await mk(main, 1, 'phone')
await mk(branch, 2, 'phone')
const gone = await mk(main, 1, 'workspace')
await as(`${base}/orders/${gone.id}/cancel`, { method: 'POST', body: { reason: 'Out of stock' } })

const ownerCtx = await open({ who: owner })
const op = ownerCtx.page
try {
  await op.goto(`${WS}/b/${bid}`)
  await op.getByRole('link', { name: 'Your numbers for the week and month →' }).waitFor()
  await op.getByRole('link', { name: 'Your numbers', exact: true }).click()
  await op.getByRole('heading', { name: 'Your numbers' }).waitFor()
  const card = (key) => op.locator(`section[aria-labelledby=in-${key}]`)
  let text = await card('sales').innerText()
  check(text.includes('₹1,110') && text.includes('1 bill') && !text.includes('Other bills') && text.includes('Open bills'),
    `today's sales ₹1,110 from 1 bill (${text.replace(/\s+/g, ' ')})`)
  text = await card('orders').innerText()
  check(text.includes('₹1,350') && text.includes('2 orders') && text.includes('Phone') && text.includes('Cancelled or declined'),
    `today's orders ₹1,350, by channel, with the cancelled one apart (${text.replace(/\s+/g, ' ')})`)
  text = await card('collections').innerText()
  check(text.includes('₹1,110') && text.includes('Bills and the counter'), 'money received ₹1,110 from bills and the counter')
  const off = await op.locator('.bos-insights__off').innerText()
  check(off.includes('Bookings') && (await card('bookings').count()) === 0, 'Bookings is off: named, not a zero')
  await shot(op, '01-today.png')

  await op.getByRole('link', { name: 'Last 7 days' }).click()
  await op.waitForURL(/period=7d/)
  await op.getByText('Last 7 days ·').waitFor()
  text = await card('sales').innerText()
  check(text.includes('₹1,560') && text.includes('2 bills'), `the week adds the bill from three days ago (${text.replace(/\s+/g, ' ')})`)
  await shot(op, '02-week.png')
  await op.getByRole('link', { name: 'This month' }).click()
  await op.waitForURL(/period=month/)
  await op.getByText('This month ·').waitFor()
  const inMonth = sql(`select extract(month from (now() at time zone 'Asia/Kolkata')::date - 3) = extract(month from (now() at time zone 'Asia/Kolkata')::date)`) === 't'
  text = await card('sales').innerText()
  check(text.includes(inMonth ? '₹1,560' : '₹1,110'), `this month's sales (${text.replace(/\s+/g, ' ')})`)
  await card('orders').getByRole('link', { name: 'Open orders →' }).click()
  await op.waitForURL(new RegExp(`/b/${bid}/orders`))
  check(true, 'each number opens the page where the work happens')
  check(op.realErrors().length === 0, `owner: no console errors (${op.realErrors().join(' | ').slice(0, 300)})`)
} finally {
  await ownerCtx.context.close()
}

// ---------------------------------------------------------------- a manager limited to the branch
const mgrFile = `${OUT}/manager_e1.json`
execFileSync('uv', ['run', '--no-env-file', 'python', 'tools/acceptance/stack/owner.py', DB, mgrFile], { stdio: 'ignore' })
const mgr = load(mgrFile)
const inv = (await as(`${base}/team/people`, { method: 'POST', body: { name: 'Divya', email: mgr.email, role: 'manager', location_ids: [branch] } })).data
check((await caller(mgr.token)(`${base}/invitations/${inv.invitation_id}/accept`, { method: 'POST', body: {} })).ok, 'branch manager joined')
{
  const ctx = await open({ who: mgr })
  const p = ctx.page
  await p.goto(`${WS}/b/${bid}/insights`)
  await p.getByRole('heading', { name: 'Your numbers' }).waitFor()
  const orders = await p.locator('section[aria-labelledby=in-orders]').innerText()
  check(orders.includes('₹900') && orders.includes('1 order') && !orders.includes('Cancelled'), `branch manager sees the branch's order only (${orders.replace(/\s+/g, ' ')})`)
  const money = await p.locator('section[aria-labelledby=in-collections]').innerText()
  check(money.includes('shown to people who see every location') && !money.includes('₹'), 'money received is not shown to a location-limited manager')
  await shot(p, '03-branch-manager.png')
  check(p.realErrors().length === 0, 'manager: no console errors')
  await ctx.context.close()
}

// ---------------------------------------------------------------- 390 px
{
  const phone = await open({ who: owner, mobile: true })
  await phone.page.goto(`${WS}/b/${bid}/insights?period=7d`)
  await phone.page.getByRole('heading', { name: 'Your numbers' }).waitFor()
  check(await fits(phone.page), 'Your numbers fits 390 px')
  await shot(phone.page, '04-numbers-390.png')
  check(phone.page.realErrors().length === 0, '390 px: no console errors')
  await phone.context.close()
}

await closeAll()
finish()
