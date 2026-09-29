// P1-10D2b — formula-priced items and the rate board (OK-15; MD §21.2 jewellery
// "price = today's metal rate × weight + making charge + GST from a daily rate
// board"; Business OS Guide p.22).
//
//  A jeweller adds today's 22K rate (₹6,450 per g) on Today's rates, then
//  prices a chain from it in the item editor: 10 g + 12% making = ₹72,240 (GST
//  3% from the item's HSN on the bill). The chain shows on the jeweller's site
//  with how the price is made up. A phone order is taken at that price and
//  billed. Next morning Home asks for today's rate; the owner enters ₹6,600 —
//  the chain is ₹73,920 for the next sale, while the order and its bill keep
//  ₹72,240 and "10 g × ₹6,450". A counter sale at the new rate keeps its own
//  working. Desktop and 390 px.
//
//   node tools/acceptance/phase_b/p1_10d2_formula.mjs
import { WEB, WS, caller, closeAll, fits, load, must, open, recorder, sql, wait } from './pw.mjs'

const { check, shot, finish } = recorder('p1_10d2b')
const OUT = process.env.LOCAH_ACCEPT_OUT || 'acceptance-out'
const owner = load(process.env.LOCAH_ACCEPT_OWNER || `${OUT}/owner2.json`)
const customer = load(process.env.LOCAH_ACCEPT_SESSION || `${OUT}/session.json`)
const as = must(owner.token)
const guestApi = caller(null)

// ------------------------------------------------------------------ the jeweller
const created = (await as('/v1/platform/businesses', { method: 'POST', body: {
  display_name: 'Lakshmi Jewellers', business_type: 'other', category_key: 'retail', subcategory_key: 'jewellery' } })).data.business
const bid = created.id
const base = `/v1/platform/businesses/${bid}`
for (const m of ['offerings-catalog', 'inventory', 'orders', 'payments', 'invoicing', 'pos', 'customer-relationships'])
  await as(`/v1/b/${bid}/modules/${m}/enable`, { method: 'POST' })
const slug = (await as(`/v1/b/${bid}`)).data.slug
await as(`/v1/b/${bid}/marketplace/visibility`, { method: 'POST', body: { visibility: 'unlisted' } })
await as(`${base}/invoicing/profile`, { method: 'PUT', body: { prices_include_tax: false, round_off: false, issue_on: 'manual' } })
const reg = (await as(`${base}/invoicing/registrations`, { method: 'POST', body: {
  scheme: 'regular', legal_name: 'Lakshmi Jewellers', gstin: '33AAACL1234K1ZV' } }))
const regId = reg.data?.id ?? (await as(`${base}/invoicing/registrations`)).data[0].id
const loc = (await as(`${base}/locations`)).data.find((l) => l.is_primary).id
await as(`${base}/invoicing/registers`, { method: 'POST', body: { location_id: loc, registration_id: regId, code: 'LKJ1' } })
const site = (await as(`/v1/b/${bid}/website`)).data
const home = (site.draft?.pages || site.pages || []).find((p) => p.slug === 'home') || (site.draft?.pages || site.pages)[0]
await as(`/v1/b/${bid}/website/pages/${home.id}/sections`, { method: 'POST', body: { section_type_id: 'offerings_list', content: { title: 'Gold' } } })

const ownerCtx = await open({ who: owner })
const op = ownerCtx.page
let chain = null
let orderId = ''
let billId = ''
try {
  // ---------------------------------------------------------------- 1. today's rate
  await op.goto(`${WS}/b/${bid}/offerings/rates`)
  await op.getByRole('heading', { name: "Today's rates" }).waitFor()
  check((await op.locator('main').innerText()).includes('No rates yet'), 'an empty board says what to do')
  await op.locator('input[name=new-rate-label]').fill('22K gold')
  await op.locator('select[name=new-rate-unit]').selectOption('g')
  await op.locator('input[name=new-rate-value]').fill('6450')
  await op.getByRole('button', { name: 'Add rate' }).click()
  await op.getByRole('heading', { name: '22K gold' }).waitFor()
  let text = await op.locator('main').innerText()
  check(text.includes('₹6,450') && text.includes('per gram') && text.includes('Entered today'), 'the rate is on the board, entered today')
  await shot(op, '01-rate-board.png')

  // ---------------------------------------------------------------- 2. a chain priced from it
  await op.goto(`${WS}/b/${bid}/offerings/new?kind=product`)
  await op.getByLabel('Name').fill('Gold chain 22K')
  await op.getByRole('radio', { name: 'From a rate' }).check()
  await op.locator('select[name=formula-rate]').selectOption('22k_gold')
  await op.locator('input[name=formula-quantity]').fill('10')
  await op.locator('select[name=formula-making]').selectOption('percent')
  await op.locator('input[name=formula-making-value]').fill('12')
  await op.getByLabel('HSN code').fill('7113')
  await op.getByLabel('GST rate (%)').fill('3')
  await op.getByText('At today’s rate: ₹72,240').waitFor()
  await op.getByText('Draft — only you can see it').click()
  await op.getByText('Live — shown to customers').waitFor()
  await shot(op, '02-price-from-rate.png')
  await op.getByRole('button', { name: 'Add', exact: true }).click()
  await op.waitForURL(/offerings\/[0-9a-f-]{36}/)
  chain = (await as(`${base}/products`)).data.find((o) => o.title === 'Gold chain 22K')
  check(chain && chain.price_amount === 72240 && chain.price_formula?.quantity === '10.000'
    && chain.price_formula?.making?.type === 'percent', `the chain is ₹72,240 from 10 g × ₹6,450 + 12% (${chain?.price_amount})`)
  await op.getByText('Now: 10 g × ₹6,450 (22K gold) + making ₹7,740 (12%)').waitFor()
  check(await op.getByRole('radio', { name: 'From a rate' }).isChecked(), 'the saved item opens priced from the rate')
  await op.goto(`${WS}/b/${bid}/offerings`)
  const row = op.locator('.bos-catalogue li', { hasText: 'Gold chain 22K' })
  check((await row.innerText()).includes("₹72,240 at today's rate"), 'the catalogue says it is at today’s rate')
  check(await op.getByRole('link', { name: "Today's rates" }).count() === 1, 'Products & services links to Today’s rates')
  await shot(op, '03-catalogue.png')

  // ---------------------------------------------------------------- 3. on the jeweller's site
  check((await caller(owner.token)(`/v1/b/${bid}/website/publish`, { method: 'POST' })).ok, 'website published')
  const cust = await open({ who: customer })
  const cp = cust.page
  await cp.goto(`${WEB}/${slug}`)
  const card = cp.locator('.ls-offer', { hasText: 'Gold chain 22K' })
  await card.waitFor()
  const cardText = await card.innerText()
  check(cardText.includes('₹72,240') && cardText.includes("Today's price: 10 g × ₹6,450 (22K gold) + making ₹7,740 (12%)"),
    `the site shows the price and how it is made up (${cardText.replace(/\s+/g, ' ').slice(0, 160)})`)
  const basisColour = await card.locator('.ls-offer__basis').evaluate((e) => getComputedStyle(e).color)
  check(!['rgb(37, 99, 235)', 'rgb(194, 70, 26)'].includes(basisColour), `the working uses the jeweller's theme (${basisColour})`)
  await shot(cp, '04-site-card.png')
  check(cp.realErrors().length === 0, `site: no console errors (${cp.realErrors().join(' | ').slice(0, 300)})`)
  await cust.context.close()

  // ---------------------------------------------------------------- 4. a phone order, and its bill
  const placed = await as(`${base}/orders`, { method: 'POST', body: {
    location_id: loc, payment_method: 'pay_at_business', channel: 'phone',
    items: [{ offering_id: chain.id, quantity: 1 }] } })
  orderId = placed.data.id
  await op.goto(`${WS}/b/${bid}/orders/${orderId}`)
  await op.getByText('10 g × ₹6,450 (22K gold) + making ₹7,740 (12%)').waitFor()
  text = await op.locator('main').innerText()
  check(text.includes('₹72,240'), 'the order line is ₹72,240 with its working')
  const bill = await as(`${base}/invoices/from-order/${orderId}`, { method: 'POST', body: {} })
  billId = bill.data.id
  await op.goto(`${WS}/b/${bid}/invoices/${billId}`)
  await op.locator('.bos-bill__basis').first().waitFor()
  text = await op.locator('main').innerText()
  check(text.includes('10 g × ₹6,450') && text.includes('72,240'), 'the bill line keeps weight × rate + making')
  await shot(op, '05-bill-with-working.png')

  // ---------------------------------------------------------------- 5. next morning: Home asks for today's rate
  sql(`update pricing_rate_values set effective_from = now() - interval '1 day' where business_id = '${bid}'`)
  await op.goto(`${WS}/b/${bid}`)
  const ask = op.locator('.bos-attention__row', { hasText: 'rates to enter for today' })
  await ask.waitFor()
  check((await ask.innerText()).includes('22K gold'), 'Home: "rates to enter for today — 22K gold"')
  await shot(op, '06-home-asks-for-rate.png')
  await ask.click()
  await op.getByRole('heading', { name: '22K gold' }).waitFor()
  check((await op.locator('.bos-rate .bos-state').innerText()).includes('Not entered today'), 'the board marks it not entered today')
  await op.locator('input[name=rate-22k_gold]').fill('6600')
  await op.getByLabel('Note — optional').first().fill('Morning rate')
  await op.getByRole('button', { name: 'Save rate' }).click()
  await op.getByText('Saved. 1 item now priced at ₹6,600 per gram.').waitFor()
  await op.locator('.bos-rate__basis', { hasText: '₹6,600' }).waitFor()
  check((await op.locator('.bos-rate .bos-state').innerText()).includes('Entered today'), 'the board marks it entered today')
  text = await op.locator('main').innerText()
  check(text.includes('₹73,920') && text.includes('10 g × ₹6,600'), 'the chain is ₹73,920 at the new rate')
  await op.locator('.bos-rate__history summary').click()
  await op.locator('.bos-rate__history li', { hasText: 'Morning rate' }).waitFor()
  text = await op.locator('.bos-rate__history').innerText()
  check(text.includes('₹6,600') && text.includes('₹6,450') && text.includes('Morning rate'), 'both rates stay in the history')
  await shot(op, '07-new-rate.png')

  // the order and bill already made keep the rate they were sold at
  await op.goto(`${WS}/b/${bid}/orders/${orderId}`)
  await op.getByText('10 g × ₹6,450 (22K gold) + making ₹7,740 (12%)').waitFor()
  check((await op.locator('main').innerText()).includes('₹72,240'), 'the earlier order still says ₹72,240 at ₹6,450')
  await op.goto(`${WS}/b/${bid}/invoices/${billId}`)
  await op.locator('.bos-bill__basis').first().waitFor()
  text = await op.locator('main').innerText()
  check(text.includes('10 g × ₹6,450') && !text.includes('6,600'), 'the issued bill is unchanged by the new rate')
  const lineRow = sql(`select unit_price, price_basis->>'rate' from invoicing_document_lines where document_id = '${billId}'`).split('|')
  check(lineRow[0] === '72240.00' && lineRow[1] === '6450.0000', `stored bill line keeps ₹72,240 at ₹6,450 (${lineRow.join(' · ')})`)
  check((await as(`/v1/b/${bid}`)).ok !== false, 'still signed in')
  await wait(200)
  check(op.realErrors().length === 0, `owner pages: no console errors (${op.realErrors().join(' | ').slice(0, 300)})`)
} finally {
  await ownerCtx.context.close()
}

// ---------------------------------------------------------------- 6. a counter sale at today's rate
{
  const ctx = await open({ who: owner })
  const p = ctx.page
  await p.goto(`${WS}/pos/${bid}`)
  await p.getByText('Open the counter').waitFor()
  await p.locator('.pos-form input[inputmode=decimal]').first().fill('0')
  await p.getByRole('button', { name: 'Open shift' }).click()
  await p.locator('.pos-tile', { hasText: 'Gold chain 22K' }).click()
  await p.locator('.pos-pay').click()
  await p.getByRole('heading', { name: /^Pay ₹76,137/ }).waitFor()
  await p.getByRole('tab', { name: 'Card' }).click()
  await p.getByLabel('Approval code or last 4 digits').fill('4411')
  await p.getByRole('button', { name: 'Record card' }).click()
  await p.locator('.pos-tenders', { hasText: 'Card' }).waitFor()
  await shot(p, '08-counter-sale.png')
  await p.getByRole('button', { name: 'Complete sale' }).click()
  await p.locator('.pos-receipt-head').waitFor()
  await p.getByText('Saved to LOCAH.').waitFor({ timeout: 20000 })
  const counterBill = (await as(`${base}/invoices?kind=invoices`)).data.find((b) => b.source === 'pos')
  const detail = (await as(`${base}/invoices/${counterBill.id}`)).data
  check(detail.lines[0].unit_price === 73920 && (detail.lines[0].basis_words || '').includes('₹6,600'),
    `the counter bill keeps today's working (${detail.lines[0].unit_price}, ${detail.lines[0].basis_words})`)
  check(p.realErrors().length === 0, `counter: no console errors (${p.realErrors().join(' | ').slice(0, 300)})`)
  await ctx.context.close()
}

// ---------------------------------------------------------------- 390 px
{
  const phoneOwner = await open({ who: owner, mobile: true })
  const p = phoneOwner.page
  await p.goto(`${WS}/b/${bid}/offerings/rates`)
  await p.getByRole('heading', { name: '22K gold' }).waitFor()
  check(await fits(p), 'the rate board fits 390 px')
  await shot(p, '09-rates-390.png')
  await p.goto(`${WS}/b/${bid}/offerings/${chain.id}`)
  await p.locator('select[name=formula-rate]').waitFor()
  check(await fits(p), 'the item editor priced from a rate fits 390 px')
  await shot(p, '10-editor-390.png')
  const phone = await open({ who: customer, mobile: true })
  await phone.page.goto(`${WEB}/${slug}`)
  await phone.page.locator('.ls-offer__basis').first().waitFor()
  check(await fits(phone.page), 'the jeweller’s site with the working fits 390 px')
  await shot(phone.page, '11-site-390.png')
  check(p.realErrors().length === 0 && phone.page.realErrors().length === 0, '390 px: no console errors')
  await phone.context.close()
  await phoneOwner.context.close()
}

await closeAll()
finish()
