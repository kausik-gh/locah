// P1-10E3 — per-customer export and erasure (CR-08, CO-01; MD §25.1 DPDP
// "access / erasure rights … per-customer export and delete, retention defaults").
//
//  A signed-in customer of a dairy opens "My account" on the dairy's site,
//  downloads their data and asks the dairy to delete their details. The owner
//  sees the request on Home, opens the customer, downloads their data, is told
//  the order still in progress must be finished first, finishes it, and erases —
//  typing the name to confirm, told what stays (the bill, for GST law). The
//  customer's account no longer shows the dairy's records. Desktop and 390 px.
//
//   node tools/acceptance/phase_b/p1_10e_privacy.mjs
import { readFileSync } from 'node:fs'
import { WEB, WS, caller, closeAll, fits, load, must, open, recorder, sql } from './pw.mjs'

const { check, shot, finish } = recorder('p1_10e_privacy')
const OUT = process.env.LOCAH_ACCEPT_OUT || 'acceptance-out'
const owner = load(process.env.LOCAH_ACCEPT_OWNER || `${OUT}/owner2.json`)
const customer = load(process.env.LOCAH_ACCEPT_SESSION || `${OUT}/session.json`)
const as = must(owner.token)

const created = (await as('/v1/platform/businesses', { method: 'POST', body: {
  display_name: 'Annapoorna Dairy', business_type: 'other', category_key: 'fresh_grocery', subcategory_key: 'grocery' } })).data.business
const bid = created.id
const base = `/v1/platform/businesses/${bid}`
for (const m of ['offerings-catalog', 'orders', 'payments', 'fulfilment', 'invoicing', 'customer-relationships'])
  await as(`/v1/b/${bid}/modules/${m}/enable`, { method: 'POST' })
await as(`/v1/b/${bid}/fulfilment/settings`, { method: 'PATCH', body: { pickup_enabled: true } })
await as(`/v1/b/${bid}/marketplace/visibility`, { method: 'POST', body: { visibility: 'unlisted' } })
const slug = (await as(`/v1/b/${bid}`)).data.slug
const ghee = (await as(`${base}/products`, { method: 'POST', body: { status: 'active', offering_type: 'product', title: 'Cow ghee 500 ml', price_amount: 420, visibility: 'public' } })).data
check((await caller(owner.token)(`/v1/b/${bid}/website/publish`, { method: 'POST' })).ok, 'website published')
const placed = await caller(customer.token)(`/v1/public/websites/${slug}/checkout`, { method: 'POST', body: {
  items: [{ offering_id: ghee.id, quantity: 2 }], fulfilment_mode: 'pickup', payment_method: 'cod', guest: { name: 'Lalitha Venkat', phone: '+919840033001' } } })
check(placed.ok, `the customer ordered while signed in (${placed.status})`)
const orderId = placed.data.data.order.id
const contact = sql(`select customer_contact_id from orders_orders where id = '${orderId}'`)
await as(`${base}/customers/${contact}/notes`, { method: 'POST', body: { body: 'Collects on Sundays' } })

// ---------------------------------------------------------------- 1. the customer: download, then ask
{
  const ctx = await open({ who: customer })
  const p = ctx.page
  await p.goto(`${WEB}/${slug}/account`)
  await p.getByRole('heading', { name: 'Your details' }).waitFor()
  const [download] = await Promise.all([p.waitForEvent('download'), p.getByRole('link', { name: 'Download my data' }).click()])
  const file = await download.path()
  const mine = JSON.parse(readFileSync(file, 'utf8'))
  check(download.suggestedFilename() === `my-data-${slug}.json` && mine.records[0].display_name === 'Lalitha Venkat'
    && mine.orders[0].items[0].item === 'Cow ghee 500 ml' && mine.notes[0].body === 'Collects on Sundays',
    `the customer's file has their record, order and the shop's note (${download.suggestedFilename()})`)
  const btn = await p.locator('.ls-account__erase button').evaluate((e) => getComputedStyle(e).borderColor)
  check(!['rgb(37, 99, 235)', 'rgb(194, 70, 26)'].includes(btn), `the account page uses the dairy's colours (${btn})`)
  await p.locator('#erase-note').fill('I am moving away')
  await p.getByRole('button', { name: 'Ask Annapoorna Dairy to delete my details' }).click()
  await p.getByText('Your request was sent to Annapoorna Dairy.').waitFor()
  await p.getByText(/You asked Annapoorna Dairy to delete your details on/).waitFor()
  await shot(p, '01-customer-asked.png')
  check(p.realErrors().length === 0, `customer: no console errors (${p.realErrors().join(' | ').slice(0, 200)})`)
  await ctx.context.close()
}

// ---------------------------------------------------------------- 2. the owner: Home → customer → erase
{
  const ctx = await open({ who: owner })
  const p = ctx.page
  await p.goto(`${WS}/b/${bid}`)
  const row = p.locator('.bos-attention__row', { hasText: 'customers asked you to delete their details' })
  await row.waitFor()
  check((await row.innerText()).includes('Lalitha Venkat'), 'Home names the customer who asked')
  await shot(p, '02-home-request.png')
  await row.click()
  await p.getByRole('heading', { name: 'Their data' }).waitFor()
  let panel = await p.locator('.bos-privacy').innerText()
  check(panel.includes('They asked you to delete their details') && panel.includes('I am moving away'), 'the request and their note show on the customer')
  check(panel.includes('finish these first') && panel.includes('1 order still in progress'), 'erasure waits for the order in progress')
  const [dl] = await Promise.all([p.waitForEvent('download'), p.getByRole('button', { name: 'Download their data' }).click()])
  const theirs = JSON.parse(readFileSync(await dl.path(), 'utf8'))
  check(theirs.records[0].phone === '+919840033001' && theirs.business === 'Annapoorna Dairy', 'the owner downloads the same data')
  await shot(p, '03-blocked-by-order.png')
  await as(`${base}/orders/${orderId}/cancel`, { method: 'POST', body: { reason: 'Customer is moving away' } })
  await p.reload()
  await p.getByText('Erase their details for good.').waitFor()
  panel = await p.locator('.bos-privacy').innerText()
  check(panel.includes('GST') || panel.includes('72 months'), 'what stays is stated before erasing')
  const eraseBtn = p.getByRole('button', { name: 'Erase their details' })
  check(await eraseBtn.isDisabled(), 'the button waits for the name')
  await p.locator('input[name=erase-confirm]').fill('Lalitha Venkat')
  await p.locator('input[name=erase-reason]').fill('Asked by the customer')
  await shot(p, '04-erase-confirm.png')
  await eraseBtn.click()
  await p.getByText(/Their personal details were erased on/).waitFor()
  await p.getByRole('heading', { name: 'Erased customer' }).waitFor()
  const stored = sql(`select display_name, coalesce(phone, '-'), (select count(*) from customer_relationships_notes where contact_id = '${contact}') from customer_relationships_contacts where id = '${contact}'`)
  check(stored === 'Erased customer|-|0', `stored: ${stored}`)
  await shot(p, '05-erased.png')
  await p.goto(`${WS}/b/${bid}`)
  await p.locator('.bos-band--now').waitFor()
  check(await p.locator('.bos-attention__row', { hasText: 'customers asked you to delete their details' }).count() === 0, 'the request is closed on Home')
  check(p.realErrors().length === 0, `owner: no console errors (${p.realErrors().join(' | ').slice(0, 200)})`)
  await ctx.context.close()
}

// ---------------------------------------------------------------- 3. the customer's account after erasure; 390 px
{
  const phone = await open({ who: customer, mobile: true })
  await phone.page.goto(`${WEB}/${slug}/account`)
  await phone.page.getByRole('heading', { name: 'Your account with Annapoorna Dairy' }).waitFor()
  const text = await phone.page.locator('main').innerText()
  check(text.includes('Nothing with Annapoorna Dairy yet') && !text.includes('Cow ghee'), 'the account no longer shows the erased records')
  check(await fits(phone.page), 'the account fits 390 px')
  await shot(phone.page, '06-account-after-390.png')
  await phone.context.close()
  const ownerPhone = await open({ who: owner, mobile: true })
  await ownerPhone.page.goto(`${WS}/b/${bid}/customers/${contact}`)
  await ownerPhone.page.getByRole('heading', { name: 'Their data' }).waitFor()
  check(await fits(ownerPhone.page), 'the erased customer page fits 390 px')
  await shot(ownerPhone.page, '07-customer-390.png')
  await ownerPhone.context.close()
}

await closeAll()
finish()
