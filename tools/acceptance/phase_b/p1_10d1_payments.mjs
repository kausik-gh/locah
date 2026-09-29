// P1-10D1 — collect what is due (Founder refinement — Payments; MD §6.1, §12.4).
//
//  A. Custom cake: a signed-in customer orders a 2 kg custom cake on the
//     bakery's own website (pay at pickup). The owner asks for an ₹800 advance
//     from the order's Money panel; the customer opens the link (no sign-in —
//     the link is the credential) in the bakery's colours, pays by UPI straight
//     to the bakery and says so. It stays "being confirmed" until the owner
//     sees it under Payments → Waiting for you and taps "It arrived": verified
//     once (a second tap and a second "I have paid" change nothing), the order
//     is part paid with ₹1,600 left, and the bill issued from the order says so.
//     The balance link: a claim the owner did not receive fails → the customer
//     retries on the same order (no new order) → withdraws → pays → confirmed →
//     paid in full. Customer account, My Activity and the owner's customer page
//     all show the same money.
//  B. Recorded money: cash + UPI + card on the bakery's terminal + bank
//     transfer against a phone order; nothing over the balance.
//  C. Full payment link at 390 px (owner and customer).
//  D. Provider truth (fixture): a replayed success pays once; a late success
//     on an older try is kept and flagged "paid twice" for a refund.
//  E. Refund on a recorded payment shows under Refunds; the order reads part
//     refunded and no balance reopens.
//  F. Cash on delivery capped for a first website order.
//  G. A store keeper cannot ask for or confirm money; another business sees
//     nothing; a link under another business's address is not found.
//
//   node tools/acceptance/phase_b/p1_10d1_payments.mjs
import { createHmac, randomUUID } from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { API, DB, PGPORT, WEB, WS, caller, closeAll, fits, load, must, open, recorder, sql, wait } from './pw.mjs'

const { check, shot, finish } = recorder('p1_10d1')
const OUT = process.env.LOCAH_ACCEPT_OUT || 'acceptance-out'
const owner = load(process.env.LOCAH_ACCEPT_OWNER || `${OUT}/owner2.json`)
const customer = load(process.env.LOCAH_ACCEPT_SESSION || `${OUT}/session.json`)
const as = must(owner.token)
const try_ = caller(owner.token)
const guestApi = caller(null)
const WEBHOOK_SECRET = process.env.PAYMENT_WEBHOOK_SECRET || 'local-acceptance-webhook-secret'
const rupeeText = (n) => `₹${Number(n).toLocaleString('en-IN')}`
const money = (page) => page.locator('.bos-money').first()
// labels are upper-cased by CSS, so compare in lower case
const sumOf = async (page) => (await money(page).locator('.bos-money__sum').innerText()).replace(/\s+/g, ' ').toLowerCase()

// ------------------------------------------------------------------ the bakery, set up by its owner
const created = (await as('/v1/platform/businesses', { method: 'POST', body: {
  display_name: 'Madhuram Cakes', business_type: 'other', category_key: 'food_service', subcategory_key: 'bakery' } })).data.business
const bid = created.id
const base = `/v1/platform/businesses/${bid}`
for (const m of ['offerings-catalog', 'inventory', 'orders', 'payments', 'fulfilment', 'invoicing', 'pos',
  'customer-relationships', 'messaging', 'memberships']) await as(`/v1/b/${bid}/modules/${m}/enable`, { method: 'POST' })
const slug = (await as(`/v1/b/${bid}`)).data.slug
await as(`/v1/b/${bid}/fulfilment/settings`, { method: 'PATCH', body: { pickup_enabled: true, delivery_enabled: true } })
await as(`/v1/b/${bid}/fulfilment/zones`, { method: 'POST', body: { name: 'Mylapore', match_type: 'postal_prefix', postal_prefix: '6000', charge_amount: 40 } })
await as(`/v1/b/${bid}/marketplace/visibility`, { method: 'POST', body: { visibility: 'unlisted' } })
await as(`${base}/invoicing/profile`, { method: 'PUT', body: { prices_include_tax: true, round_off: false, issue_on: 'manual' } })
const reg = (await as(`${base}/invoicing/registrations`, { method: 'POST', body: { scheme: 'unregistered', legal_name: 'Madhuram Cakes', state_code: '33' } })).data
const loc = (await as(`${base}/locations`)).data.find((l) => l.is_primary).id
await as(`${base}/invoicing/registers`, { method: 'POST', body: { location_id: loc, registration_id: reg.id, code: 'MDR1' } })
await as(`${base}/pos/settings`, { method: 'PUT', body: { upi_vpa: 'madhuram@okhdfc', upi_payee_name: 'Madhuram Cakes' } })
// the bakery's WhatsApp number — the local sandbox records what would be sent, nothing leaves this machine
await as(`${base}/messaging/channel/sandbox`, { method: 'POST', body: { display_phone: '+919840055501', display_name: 'Madhuram Cakes' } })
const product = async (title, price) => (await as(`${base}/products`, { method: 'POST', body: {
  status: 'active', offering_type: 'product', title, price_amount: price, visibility: 'public' } })).data
const cake = await product('Custom cake — 2 kg, made to order', 2400)
const plum = await product('Plum cake 500 g', 450)
const teaBox = await product('Tea cake box', 600)
const biscuits = await product('Butter biscuits 400 g', 400)
const site = (await as(`/v1/b/${bid}/website`)).data
const home = (site.draft?.pages || site.pages || []).find((p) => p.slug === 'home') || (site.draft?.pages || site.pages)[0]
await as(`/v1/b/${bid}/website/pages/${home.id}/sections`, { method: 'POST', body: { section_type_id: 'offerings_list', content: { title: 'Cakes' } } })
const pub = await try_(`/v1/b/${bid}/website/publish`, { method: 'POST' })
check(pub.ok, `website published (${pub.status})`)

const dueOf = async (type, id) => (await as(`${base}/collect/due?source_type=${type}&source_id=${id}`)).data
const tokenOf = (url) => url.split('/pay/')[1]
const localPay = (url) => `${WEB}/${slug}/pay/${tokenOf(url)}`

async function askInPanel(page, amount, purpose, note) {
  await money(page).getByRole('button', { name: 'Ask for payment' }).click()
  const form = money(page).locator('form.bos-money__form')
  await form.locator('input[name=amount]').fill(String(amount))
  await form.locator('select[name=purpose]').selectOption(purpose)
  if (note) await form.locator('input[name=note]').fill(note)
  await form.getByRole('button', { name: 'Make payment link' }).click()
  const input = money(page).getByLabel('Payment link')
  await input.waitFor()
  return input.inputValue()
}

const ownerCtx = await open({ who: owner })
const op = ownerCtx.page
let cakeOrderId = ''
let cakeOrderNumber = ''
let advanceUrl = ''
let balanceUrl = ''
try {
  // ---------------------------------------------------------------- A1. the customer orders the cake on the website
  const cust = await open({ who: customer })
  const cp = cust.page
  await cp.goto(`${WEB}/${slug}`)
  await cp.getByText('Cakes', { exact: true }).first().waitFor()
  await cp.evaluate(([s, id]) => localStorage.setItem(`platform.cart.${s}`, JSON.stringify([
    { offering_id: id, title: 'Custom cake — 2 kg, made to order', quantity: 1, unit_price: 2400, currency: 'INR' }])), [slug, cake.id])
  await cp.goto(`${WEB}/${slug}/checkout`)
  await cp.getByText('Ordering as').waitFor()
  await cp.getByLabel('Name').fill('Kavya')
  await cp.getByLabel('Phone').fill('+91 98400 12345')
  await cp.getByRole('radio', { name: 'Pickup', exact: true }).click()
  await cp.getByText('₹2,400').first().waitFor()
  await cp.getByRole('button', { name: 'Place order' }).click()
  await cp.getByRole('heading', { name: 'Order confirmed' }).waitFor()
  await shot(cp, '01-customer-orders-cake.png')
  const mine = (await as(`${base}/orders`)).data
  cakeOrderId = mine[0].id
  cakeOrderNumber = mine[0].order_number
  check(mine.length === 1 && mine[0].channel === 'web', `one website order for the cake (${cakeOrderNumber})`)

  // ---------------------------------------------------------------- A2. owner asks for an ₹800 advance
  await op.goto(`${WS}/b/${bid}/orders/${cakeOrderId}`)
  await money(op).waitFor()
  let sum = await sumOf(op)
  check(sum.includes('total ₹2,400') && sum.includes('paid ₹0') && sum.includes('balance ₹2,400') && sum.includes('not paid yet'),
    `order Money panel: total, nothing paid, balance (${sum})`)
  const header = await op.locator('main').first().innerText()
  check(header.includes('Cash · to collect') && !/pending_offline|pay_at_business|\bcod\b/.test(header),
    'order header says "Cash · to collect", never a stored state')
  const intent = await money(op).locator('.bos-mini-list').last().innerText()
  check(intent.includes('₹2,400 · Pay at pickup') && intent.includes('Not collected yet'), `checkout choice reads "Pay at pickup · Not collected yet" (${intent.replace(/\s+/g, ' ').slice(0, 80)})`)
  advanceUrl = await askInPanel(op, 800, 'advance', 'Advance for the 2 kg cake on Saturday')
  check(/\/pay\/[A-Za-z0-9_-]{20,}$/.test(advanceUrl), `advance link made (${advanceUrl.slice(0, 60)}…)`)
  const wa = await money(op).getByRole('link', { name: 'Send from my phone' }).getAttribute('href')
  check(wa && wa.startsWith('https://wa.me/919840012345'), `"Send from my phone" goes to the customer's number (${wa?.slice(0, 40)})`)
  await money(op).getByRole('button', { name: 'Send from your WhatsApp number' }).click()
  await money(op).getByText('Sent from your WhatsApp number.').waitFor()
  const sentBodies = sql(`select count(*) from messaging_messages where business_id = '${bid}' and direction = 'out' and body like '%/pay/${tokenOf(advanceUrl)}%'`)
  check(sentBodies === '1', `the link went out once from the bakery's WhatsApp number (sandbox) (${sentBodies})`)
  await shot(op, '02-owner-asks-advance.png')

  // ---------------------------------------------------------------- A3. customer pays the advance by UPI (a guest browser: the link is the credential)
  const guest = await open()
  const gp = guest.page
  await gp.goto(localPay(advanceUrl))
  await gp.getByText('Payment to Madhuram Cakes').waitFor()
  let body = await gp.locator('main').innerText()
  check(body.includes(`Order ${cakeOrderNumber}`) && body.includes('Advance for the 2 kg cake on Saturday'), 'pay page names the order and the note')
  check(body.includes('Amount due') && body.includes('₹2,400') && body.includes('Advance — paying now') && body.includes('₹800')
    && body.includes('Balance after this') && body.includes('₹1,600'), 'pay page: amount due ₹2,400, paying now ₹800, balance after ₹1,600')
  const upiHref = await gp.getByRole('link', { name: /Pay ₹800 by UPI/ }).getAttribute('href')
  check(upiHref.startsWith('upi://pay?pa=madhuram@okhdfc') && upiHref.includes('am=800.00'), `UPI intent is for the exact amount to the bakery (${upiHref.slice(0, 50)})`)
  const btnBg = await gp.locator('.ls-pay__upi').evaluate((e) => getComputedStyle(e).backgroundColor)
  check(!['rgb(37, 99, 235)', 'rgb(194, 70, 26)'].includes(btnBg), `pay button uses the bakery's theme, not LOCAH's (${btnBg})`)
  await shot(gp, '03-customer-pay-page.png')
  await gp.getByLabel('UPI reference (optional)').fill('412345678901')
  await gp.getByRole('button', { name: /I have paid ₹800/ }).click()
  await gp.getByText('Payment still being confirmed').waitFor()
  await gp.getByRole('button', { name: 'Check again' }).click()
  await wait(500)
  check(await gp.getByText('Payment still being confirmed').isVisible(), '"Check again" still says being confirmed — no second payment offered')
  check((await gp.getByRole('link', { name: /by UPI/ }).count()) === 0, 'no UPI button while the first try is being confirmed (no double charge)')
  await shot(gp, '04-customer-being-confirmed.png')
  // a second "I have paid" (a double tap, a replayed request) adds nothing
  await guestApi(`/v1/public/websites/${slug}/pay/${tokenOf(advanceUrl)}/paid`, { method: 'POST', body: {} })
  let due = await dueOf('order', cakeOrderId)
  const claims = due.attempts.filter((a) => a.method === 'upi_direct')
  check(claims.length === 1 && due.paid === 0 && due.being_confirmed === 800 && due.state === 'pending',
    `one claim waiting, nothing paid yet (${claims.length} claim, paid ${due.paid}, ${due.state})`)

  // ---------------------------------------------------------------- A4. owner confirms from Payments → Waiting for you
  await op.goto(`${WS}/b/${bid}/payments`)
  const waiting = op.locator('section[aria-labelledby=pay-confirm] li').filter({ hasText: `Order ${cakeOrderNumber}` })
  await waiting.waitFor()
  const wtext = await waiting.innerText()
  check(wtext.includes('₹800 by UPI') && wtext.includes('reference 412345678901'), `waiting list: ₹800 by UPI with the reference (${wtext.replace(/\s+/g, ' ').slice(0, 120)})`)
  await shot(op, '05-owner-waiting-to-confirm.png')
  await waiting.getByRole('button', { name: 'It arrived' }).click()
  await waiting.waitFor({ state: 'detached' })  // confirmed: it leaves the waiting list
  const attemptId = claims[0].id
  const again = await try_(`${base}/collect/payments/${attemptId}/confirm`, { method: 'POST', body: { arrived: true } })
  check(again.status === 409, `confirming twice is refused (${again.status})`)
  due = await dueOf('order', cakeOrderId)
  check(due.paid === 800 && due.balance === 1600 && due.state === 'partially_paid', `verified once: paid ₹800, balance ₹1,600 (${due.paid}/${due.balance}/${due.state})`)
  const completedEvents = sql(`select count(*) from platform_outbox_events where event_type = 'payment.completed' and payload->>'payment_id' = '${attemptId}'`)
  check(completedEvents === '1', `exactly one payment.completed event (${completedEvents})`)

  // ---------------------------------------------------------------- A5. the order is part paid; the bill from the order agrees
  await op.goto(`${WS}/b/${bid}/orders/${cakeOrderId}`)
  await money(op).waitFor()
  sum = await sumOf(op)
  check(sum.includes('paid ₹800') && sum.includes('balance ₹1,600') && sum.includes('state part paid'), `order reads part paid (${sum})`)
  check((await op.locator('main').first().innerText()).includes('Part paid'), 'order header: "Part paid"')
  const attemptsText = await money(op).locator('.bos-mini-list').last().innerText()
  check(attemptsText.includes('₹800 · UPI to your UPI ID') && attemptsText.includes('Received · 412345678901'), 'payment row: ₹800 UPI received with the reference')
  await op.getByRole('button', { name: 'Issue bill' }).click()
  await op.waitForURL(/\/invoices\//, { timeout: 5000 }).catch(() => undefined)
  if (!op.url().includes('/invoices/')) {
    await op.getByRole('link', { name: /Bill|MDR1/ }).first().click()
  }
  await op.getByText('already paid on the order').waitFor()
  const hint = await op.locator('.bos-inv-side').innerText()
  check(hint.includes('₹800.00 already paid on the order') && hint.includes('₹1,600.00 still due'), `bill from the order: ₹800 paid on the order, ₹1,600 still due (${hint.replace(/\s+/g, ' ').slice(0, 160)})`)
  check(!hint.includes('Record money received'), 'a bill from an order takes money only through the order')
  await shot(op, '06-bill-part-paid.png')
  await op.goto(`${WS}/b/${bid}/orders`)
  const row = await op.locator('tr', { hasText: cakeOrderNumber }).innerText()
  check(row.includes('Part paid') && row.includes('Website'), `orders list: Website · Part paid (${row.replace(/\s+/g, ' ')})`)
  await shot(op, '07-orders-list-part-paid.png')

  // the customer's link now says received, with the balance
  await gp.goto(localPay(advanceUrl))
  await gp.getByText('Payment received').waitFor()
  body = await gp.locator('main').innerText()
  check(body.includes('Balance remaining') && body.includes('₹1,600') && body.includes('Already paid'), 'customer link: payment received, balance ₹1,600 remaining')
  await shot(gp, '08-customer-advance-received.png')

  // ---------------------------------------------------------------- A6. balance: not received → retry → withdraw → paid
  await op.goto(`${WS}/b/${bid}/orders/${cakeOrderId}`)
  await money(op).waitFor()
  await money(op).getByRole('button', { name: 'Ask for payment' }).click()
  const form = money(op).locator('form.bos-money__form')
  check(await form.locator('select[name=purpose]').inputValue() === 'balance' && await form.locator('input[name=amount]').inputValue() === '1600',
    'second link defaults to the ₹1,600 balance')
  await form.getByRole('button', { name: 'Make payment link' }).click()
  balanceUrl = await money(op).getByLabel('Payment link').inputValue()
  await gp.goto(localPay(balanceUrl))
  await gp.getByText('Balance — paying now').waitFor()
  body = await gp.locator('main').innerText()
  check(body.includes('Already paid') && body.includes('₹800') && body.includes('₹1,600'), 'balance link: already paid ₹800, paying now ₹1,600')
  await gp.getByRole('button', { name: /I have paid ₹1,600/ }).click()
  await gp.getByText('Payment still being confirmed').waitFor()
  // owner checks the UPI app: it did not arrive
  await op.reload()
  await op.getByRole('group', { name: 'Payment to confirm' }).getByRole('button', { name: 'Not received' }).click()
  await op.getByText('The customer can try again.').waitFor()
  due = await dueOf('order', cakeOrderId)
  check(due.paid === 800 && due.state === 'partially_paid', `a failed try leaves the advance paid (${due.paid}, ${due.state})`)
  const orderAfterFail = (await as(`${base}/orders/${cakeOrderId}`)).data
  check(orderAfterFail.payment_status === 'partially_paid', `order stays part paid after the failed try (${orderAfterFail.payment_status})`)
  await gp.reload()
  await gp.getByText('Payment failed — try again').waitFor()
  check(await gp.getByRole('link', { name: 'Try again — pay by UPI' }).isVisible(), 'customer sees "Try again — pay by UPI"')
  await shot(gp, '09-customer-failed-retry.png')
  await gp.getByRole('button', { name: /I have paid ₹1,600/ }).click()
  await gp.getByText('Payment still being confirmed').waitFor()
  await gp.getByRole('button', { name: 'I haven’t paid yet' }).or(gp.getByRole('button', { name: "I haven't paid yet" })).click()
  await gp.getByRole('link', { name: /by UPI/ }).first().waitFor()
  check((await gp.locator('main').innerText()).includes('paying now'), 'withdrawing the claim reopens the link safely')
  await gp.getByRole('button', { name: /I have paid ₹1,600/ }).click()
  await gp.getByText('Payment still being confirmed').waitFor()
  await op.reload()
  await op.getByRole('group', { name: 'Payment to confirm' }).getByRole('button', { name: 'It arrived' }).click()
  await op.getByText('Marked as received.').waitFor()
  await op.reload()
  await money(op).waitFor()
  sum = await sumOf(op)
  check(sum.includes('paid ₹2,400') && sum.includes('balance ₹0') && sum.includes('payment received'), `paid in full (${sum})`)
  due = await dueOf('order', cakeOrderId)
  const tries = due.attempts.filter((a) => a.method === 'upi_direct').map((a) => a.status)
  check(JSON.stringify(tries.sort()) === JSON.stringify(['cancelled', 'failed', 'succeeded', 'succeeded']),
    `every try kept on the same order: ${tries.join(', ')}`)
  check((await as(`${base}/orders`)).data.length === 1, 'retrying never created another order')
  await shot(op, '10-owner-paid-in-full.png')
  await gp.reload()
  await gp.getByText('Payment received').waitFor()
  check((await gp.locator('main').innerText()).includes('₹2,400'), 'customer balance link: payment received')

  // the customer's own account and LOCAH My Activity show the same money
  await wait(2500) // the worker writes My Activity from the payment events
  await cp.goto(`${WEB}/${slug}/account`)
  await cp.getByText('Your account with Madhuram Cakes').waitFor()
  body = await cp.locator('main').innerText()
  check(body.includes(`Order ${cakeOrderNumber}`), `customer account lists the cake order (${cakeOrderNumber})`)
  await shot(cp, '11-customer-account.png')
  await cp.goto(`${WEB}/activity`)
  await cp.getByText('My activity').first().waitFor()
  body = await cp.locator('body').innerText()
  check(body.includes('Madhuram Cakes'), 'My Activity shows the bakery')
  await shot(cp, '12-my-activity.png')
  // owner's customer page: the order and both payments in words
  const contactId = (await as(`${base}/orders/${cakeOrderId}`)).data.customer_contact_id
  await op.goto(`${WS}/b/${bid}/customers/${contactId}`)
  await op.getByText('Activity').first().waitFor()
  const tl = await op.locator('.bos-timeline').innerText()
  check(tl.includes(`Placed order ${cakeOrderNumber}`) && tl.includes('Paid ₹800 (advance)') && tl.includes('Paid ₹1,600 (balance)'),
    `customer page timeline: order, ₹800 advance, ₹1,600 balance (${tl.replace(/\s+/g, ' ').slice(0, 200)})`)
  await shot(op, '13-owner-customer-timeline.png')
  check(op.realErrors().length === 0, `owner pages: no console errors (${op.realErrors().join(' | ').slice(0, 300)})`)
  check(gp.realErrors().length === 0, `pay page: no console errors (${gp.realErrors().join(' | ').slice(0, 300)})`)
  check(cp.realErrors().length === 0, `customer pages: no console errors (${cp.realErrors().join(' | ').slice(0, 300)})`)
  await cust.context.close()
  await guest.context.close()

  // ---------------------------------------------------------------- B. recorded money against a phone order
  const kavya = contactId
  const phoneOrder = (await as(`${base}/orders`, { method: 'POST', body: {
    location_id: loc, customer_contact_id: kavya, payment_method: 'pay_at_business', channel: 'phone',
    items: [{ offering_id: teaBox.id, quantity: 1 }, { offering_id: plum.id, quantity: 1 }] } })).data
  check(Number(phoneOrder.total_amount) === 1050, `phone order for ₹1,050 (${phoneOrder.total_amount})`)
  await op.goto(`${WS}/b/${bid}/orders/${phoneOrder.id}`)
  await money(op).waitFor()
  const record = async (amount, method, reference) => {
    await money(op).getByRole('button', { name: 'Record money received' }).click()
    const f = money(op).locator('form.bos-money__form')
    await f.locator('input[name=amount]').fill(String(amount))
    await f.locator('select[name=method]').selectOption(method)
    if (reference) await f.locator('input[name=reference]').fill(reference)
    await f.getByRole('button', { name: 'Record' }).click()
    await money(op).getByText('Recorded.').waitFor()
    await op.reload()
    await money(op).waitFor()
  }
  await record(400, 'cash')
  await record(300, 'upi', 'UTR 99887766')
  await record(250, 'card', 'slip 0042')
  await record(100, 'bank_transfer', 'NEFT N12345')
  sum = await sumOf(op)
  check(sum.includes('paid ₹1,050') && sum.includes('balance ₹0') && sum.includes('payment received'), `cash + UPI + card + bank settle the order (${sum})`)
  const rows = await money(op).locator('.bos-mini-list').last().innerText()
  check(['₹400 · Cash', '₹300 · UPI', '₹250 · Card (own terminal)', '₹100 · Bank transfer', 'slip 0042', 'NEFT N12345'].every((x) => rows.includes(x)),
    'each method recorded with its reference')
  check((await money(op).getByRole('button', { name: 'Record money received' }).count()) === 0, 'nothing left to record once paid')
  const over = await try_(`${base}/collect/record`, { method: 'POST', body: { source_type: 'order', source_id: phoneOrder.id, amount: 50, method: 'cash' } })
  check(over.status === 422, `recording more than is due is refused (${over.status})`)
  await shot(op, '14-recorded-methods.png')

  // ---------------------------------------------------------------- E. refund on the cash payment
  const cash = (await dueOf('order', phoneOrder.id)).attempts.find((a) => a.method === 'cash')
  await op.goto(`${WS}/b/${bid}/payments/${cash.id}`)
  await op.locator('input[name=amount]').fill('100')
  await op.locator('input[name=reason]').fill('Two tea cakes were broken')
  await op.getByRole('button', { name: 'Issue refund' }).click()
  await op.getByText('Refund history').waitFor({ timeout: 10000 }).catch(() => undefined)
  due = await dueOf('order', phoneOrder.id)
  check(due.refunded === 100 && due.state === 'partially_refunded' && due.balance === 0,
    `order: ₹100 refunded, part refunded, no balance reopened (${due.refunded}/${due.state}/${due.balance})`)
  await op.goto(`${WS}/b/${bid}/payments`)
  const refunds = await op.locator('section[aria-labelledby=pay-refunds]').innerText().catch(() => '')
  check(refunds.includes('₹100') && refunds.includes('Two tea cakes were broken'), `Payments → Refunds lists it (${refunds.replace(/\s+/g, ' ').slice(0, 120)})`)
  await shot(op, '15-refund-visible.png')

  // ---------------------------------------------------------------- D. provider truth (fixture: the not-yet-activated online adapter's attempts)
  const lateOrder = (await as(`${base}/orders`, { method: 'POST', body: {
    location_id: loc, customer_contact_id: kavya, payment_method: 'pay_at_business', channel: 'phone',
    items: [{ offering_id: teaBox.id, quantity: 1 }] } })).data
  const fullLink = (await as(`${base}/collect/requests`, { method: 'POST', body: { source_type: 'order', source_id: lateOrder.id, amount: 600, purpose: 'full' } })).data
  const insert = (id) => execFileSync('psql', ['-h', 'localhost', '-p', PGPORT, '-U', 'postgres', '-d', DB, '-qc',
    `INSERT INTO payments_payment_attempts (id, business_id, source_type, source_id, amount, payment_method, status, provider, request_id, purpose, customer_contact_id)
     VALUES ('${id}', '${bid}', 'order', '${lateOrder.id}', 600, 'online', 'processing', 'stub', '${fullLink.id}', 'full', '${kavya}')`])
  const older = randomUUID()
  const first = randomUUID()
  insert(older)
  insert(first)
  const webhook = async (paymentId, status) => {
    const raw = JSON.stringify({ event_id: randomUUID(), payment_id: paymentId, status, provider_reference: 'stub-ref' })
    const sig = createHmac('sha256', WEBHOOK_SECRET).update(raw).digest('hex')
    const r = await fetch(`${API}/v1/webhooks/payments/stub`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'x-payment-signature': sig }, body: raw })
    return r.status
  }
  check(await webhook(older, 'failed') === 200, 'provider: first try failed')
  check(await webhook(first, 'succeeded') === 200, 'provider: retry succeeded')
  check(await webhook(first, 'succeeded') === 200, 'provider: the success replayed under a new event id')
  due = await dueOf('order', lateOrder.id)
  check(due.paid === 600 && due.state === 'paid', `a replayed success pays once (${due.paid}, ${due.state})`)
  check(await webhook(older, 'succeeded') === 200, 'provider: the failed try settles late')
  due = await dueOf('order', lateOrder.id)
  check(due.paid === 1200 && due.attempts.some((a) => a.id === older && a.attention === 'paid_twice'),
    `late success kept (money moved) and flagged paid twice (${due.paid})`)
  await op.goto(`${WS}/b/${bid}/payments`)
  const attention = await op.locator('section[aria-labelledby=pay-attention]').innerText()
  check(attention.includes('Paid twice on the same link — refund the extra payment.') && attention.includes(`Order ${lateOrder.order_number}`),
    `Payments → Needs attention: paid twice on Order ${lateOrder.order_number}`)
  const paidToday = await op.locator('.bos-money__sum').first().innerText()
  await shot(op, '16-paid-twice-attention.png')
  check(paidToday.replace(/\s+/g, ' ').toLowerCase().includes('paid today ₹'), `overview shows paid today (${paidToday.replace(/\s+/g, ' ').slice(0, 120)})`)
} finally {
  await ownerCtx.context.close()
}

// ---------------------------------------------------------------- C. full payment link, owner and customer at 390 px
{
  const phoneOwner = await open({ who: owner, mobile: true })
  const pp = phoneOwner.page
  const small = (await as(`${base}/orders`, { method: 'POST', body: {
    location_id: loc, customer_contact_id: (await as(`${base}/orders/${cakeOrderId}`)).data.customer_contact_id,
    payment_method: 'pay_at_business', channel: 'phone', items: [{ offering_id: plum.id, quantity: 1 }] } })).data
  await pp.goto(`${WS}/b/${bid}/orders/${small.id}`)
  await money(pp).waitFor()
  check(await fits(pp), 'order page with Money fits 390 px')
  const url = await askInPanel(pp, 450, 'full')
  await shot(pp, '17-owner-390-link.png')
  const phoneGuest = await open({ mobile: true })
  const gq = phoneGuest.page
  await gq.goto(localPay(url))
  await gq.getByText('Full payment — paying now').waitFor()
  check(await fits(gq), 'pay page fits 390 px')
  await shot(gq, '18-customer-390-pay.png')
  await gq.getByRole('button', { name: /I have paid ₹450/ }).click()
  await gq.getByText('Payment still being confirmed').waitFor()
  await shot(gq, '19-customer-390-confirming.png')
  await pp.goto(`${WS}/b/${bid}/payments`)
  const w = pp.locator('section[aria-labelledby=pay-confirm] li').filter({ hasText: `Order ${small.order_number}` })
  await w.getByRole('button', { name: 'It arrived' }).click()
  await w.waitFor({ state: 'detached' })
  check(await fits(pp), 'Payments overview fits 390 px')
  await shot(pp, '20-owner-390-payments.png')
  const d = await dueOf('order', small.id)
  check(d.paid === 450 && d.state === 'paid', `full payment by link (${d.paid}, ${d.state})`)
  await gq.reload()
  await gq.getByText('Payment received').waitFor()
  await shot(gq, '21-customer-390-received.png')
  check(pp.realErrors().length === 0 && gq.realErrors().length === 0, `390 px: no console errors (${[...pp.realErrors(), ...gq.realErrors()].join(' | ').slice(0, 200)})`)
  await phoneOwner.context.close()
  await phoneGuest.context.close()
}

// ---------------------------------------------------------------- H. a membership fee: part at the desk, the rest by link
{
  const kavyaId = (await as(`${base}/orders/${cakeOrderId}`)).data.customer_contact_id
  const plan = (await as(`${base}/membership-plans`, { method: 'POST', body: { name: 'Cake club — monthly box', price_amount: 1500, duration_days: 30, status: 'active' } })).data
  const enrolment = (await as(`${base}/membership-enrolments`, { method: 'POST', body: { plan_id: plan.id, customer_contact_id: kavyaId, payment_method: 'pay_at_business' } })).data
  const ctx = await open({ who: owner })
  const p = ctx.page
  await p.goto(`${WS}/b/${bid}/memberships`)
  await p.getByRole('link', { name: 'Cake club — monthly box' }).click()
  await money(p).waitFor()
  let sum = await sumOf(p)
  check(sum.includes('total ₹1,500') && sum.includes('balance ₹1,500'), `membership Money panel: fee ₹1,500 due (${sum})`)
  await money(p).getByRole('button', { name: 'Record money received' }).click()
  const f = money(p).locator('form.bos-money__form')
  await f.locator('input[name=amount]').fill('500')
  await f.locator('select[name=method]').selectOption('cash')
  await f.getByRole('button', { name: 'Record' }).click()
  await money(p).getByText('Recorded.').waitFor()
  await p.reload()
  await money(p).waitFor()
  sum = await sumOf(p)
  check(sum.includes('paid ₹500') && sum.includes('balance ₹1,000') && sum.includes('part paid'), `membership part paid at the desk (${sum})`)
  const url = await askInPanel(p, 1000, 'balance')
  await shot(p, '24-membership-part-paid.png')
  const g = await open()
  await g.page.goto(localPay(url))
  await g.page.getByText('Membership · Cake club — monthly box').waitFor()
  const body = await g.page.locator('main').innerText()
  check(body.includes('Already paid') && body.includes('₹500') && body.includes('Balance — paying now') && body.includes('₹1,000'), 'membership link: already paid ₹500, paying now ₹1,000')
  await g.context.close()
  await p.goto(`${WS}/b/${bid}/memberships`)
  const row = await p.locator('tr', { hasText: 'Cake club — monthly box' }).last().innerText()
  check(row.includes('Part paid'), `memberships list says "Part paid" (${row.replace(/\s+/g, ' ')})`)
  check(p.realErrors().length === 0, `membership pages: no console errors (${p.realErrors().join(' | ').slice(0, 200)})`)
  await ctx.context.close()
  void enrolment
}

// ---------------------------------------------------------------- I. the counter: ₹1,000 as ₹400 cash + ₹600 UPI (Payments §8)
{
  const ctx = await open({ who: owner })
  const p = ctx.page
  await p.goto(`${WS}/pos/${bid}`)
  await p.getByText('Open the counter').waitFor()
  await p.locator('.pos-form input[inputmode=decimal]').first().fill('500')
  await p.getByRole('button', { name: 'Open shift' }).click()
  await p.locator('.pos-tile').first().waitFor()
  await p.locator('.pos-tile', { hasText: 'Tea cake box' }).click()
  await p.locator('.pos-tile', { hasText: 'Butter biscuits 400 g' }).click()
  await p.locator('.pos-pay').click()
  await p.getByRole('heading', { name: 'Pay ₹1,000.00' }).or(p.getByRole('heading', { name: 'Pay ₹1,000' })).waitFor()
  await p.getByRole('textbox', { name: 'Cash received' }).fill('400')
  await p.getByRole('button', { name: 'Take cash' }).click()
  await p.getByRole('tab', { name: 'UPI' }).click()
  await p.getByPlaceholder('UPI reference').fill('UTR 5566')
  await p.getByRole('button', { name: /^Paid ₹600/ }).click()
  const tenders = await p.locator('.pos-tenders').innerText()
  check(tenders.includes('Cash') && tenders.includes('₹400') && tenders.includes('UPI') && tenders.includes('₹600'), `split: ₹400 cash + ₹600 UPI (${tenders.replace(/\s+/g, ' ')})`)
  await shot(p, '25-counter-split.png')
  await p.getByRole('button', { name: 'Complete sale' }).click()
  await p.locator('.pos-receipt-head').waitFor()
  await p.getByText('Saved to LOCAH.').waitFor({ timeout: 20000 })
  const counterBill = (await as(`${base}/invoices?kind=invoices`)).data.find((b) => b.source === 'pos')
  const detail = (await as(`${base}/invoices/${counterBill.id}`)).data
  const methods = (detail.payments || []).map((x) => `${x.method}:${x.amount}`).sort().join(',')
  check(detail.amount_due === 1000 && detail.payment_status === 'paid' && methods === 'cash:400,upi:600',
    `one bill sees the combined settlement (${detail.amount_due}, ${detail.payment_status}, ${methods})`)
  await p.goto(`${WS}/b/${bid}/invoices/${counterBill.id}`)
  const received = await p.locator('.bos-inv-pay').first().innerText()
  check(received.includes('Cash') && received.includes('UPI') && received.includes('UTR 5566'), 'the bill lists both tenders with the UPI reference')
  await shot(p, '26-counter-bill-two-tenders.png')
  await ctx.context.close()
}

// ---------------------------------------------------------------- F. cash on delivery, capped for a first order
{
  const ctx = await open({ who: owner })
  await ctx.page.goto(`${WS}/b/${bid}/fulfilment/zones`)
  const rules = ctx.page.locator('form[aria-labelledby=cod-h]')
  await rules.waitFor()
  check((await rules.innerText()).includes('The same rule for orders from your website and WhatsApp'), 'Zones & charges: one paying-on-delivery rule for website and WhatsApp')
  await rules.getByLabel(/First order: pay on delivery up to/).fill('500')
  await rules.getByRole('button', { name: 'Save payment rules' }).click()
  await ctx.page.waitForTimeout(1500)
  const saved = (await as(`/v1/b/${bid}/fulfilment/settings`)).data
  check(saved.first_order_cod_cap === 500 && saved.cod_allowed === true && saved.pickup_enabled && saved.delivery_enabled,
    `first-order cap saved without touching pickup/delivery (${JSON.stringify(saved).slice(0, 160)})`)
  await ctx.page.reload()
  check(await ctx.page.locator('form[aria-labelledby=cod-h] input[name=first_order_cod_cap]').inputValue() === '500', 'the page shows the saved cap')
  await shot(ctx.page, '22-owner-cod-cap.png')
  await ctx.context.close()
  const g = await open()
  const p = g.page
  await p.goto(`${WEB}/${slug}`)
  await p.evaluate(([s, id]) => localStorage.setItem(`platform.cart.${s}`, JSON.stringify([
    { offering_id: id, title: 'Tea cake box', quantity: 2, unit_price: 600, currency: 'INR' }])), [slug, teaBox.id])
  await p.goto(`${WEB}/${slug}/checkout`)
  await p.getByRole('heading', { name: 'How you get it' }).waitFor()
  await p.getByRole('radio', { name: 'Delivery', exact: true }).click()
  await p.getByLabel('Address').fill('12 Kutchery Road')
  await p.getByLabel('City').fill('Chennai')
  await p.getByLabel('PIN code').fill('600004')
  await p.getByText(/Delivery charge/).waitFor()
  check(await p.getByText('For a first order, cash on delivery is up to ₹500.').isVisible(), 'checkout states the first-order COD cap')
  await p.getByLabel('Name').fill('Ramesh')
  await p.getByLabel('Email').fill(`ramesh-${randomUUID().slice(0, 6)}@example.com`)
  const before = (await as(`${base}/orders`)).data.length
  await p.getByRole('button', { name: 'Place order' }).click()
  await p.getByText(/For a first order, cash on delivery is up to ₹500\. Choose pickup/).waitFor()
  check((await as(`${base}/orders`)).data.length === before, 'no order placed over the cap')
  await shot(p, '23-cod-cap-refused.png')
  await p.getByRole('radio', { name: 'Pickup', exact: true }).click()
  await wait(800)
  await p.getByRole('button', { name: 'Place order' }).click()
  await p.getByRole('heading', { name: 'Order confirmed' }).waitFor()
  check((await as(`${base}/orders`)).data.length === before + 1, 'pay at pickup is not cash on delivery — the same cart is accepted')
  await g.context.close()
}

// ---------------------------------------------------------------- G. permissions and isolation
{
  // a store keeper (no payments.collect) joins this bakery
  const keeperFile = `${OUT}/keeper_d1.json`
  execFileSync('uv', ['run', '--no-env-file', 'python', 'tools/acceptance/stack/owner.py', DB, keeperFile], { stdio: 'ignore' })
  const keeper = load(keeperFile)
  const inv = (await as(`${base}/team/people`, { method: 'POST', body: { name: 'Selvam', email: keeper.email, role: 'store_keeper', location_ids: [loc] } })).data
  const accepted = await caller(keeper.token)(`${base}/invitations/${inv.invitation_id}/accept`, { method: 'POST', body: {} })
  check(accepted.ok, `store keeper joined (${accepted.status})`)
  const k = caller(keeper.token)
  const kAsk = await k(`${base}/collect/requests`, { method: 'POST', body: { source_type: 'order', source_id: cakeOrderId, amount: 10, purpose: 'full' } })
  const kRecord = await k(`${base}/collect/record`, { method: 'POST', body: { source_type: 'order', source_id: cakeOrderId, amount: 10, method: 'cash' } })
  const kView = await k(`${base}/collect/overview`)
  check([kAsk.status, kRecord.status, kView.status].every((s) => s === 403), `store keeper cannot ask, record or see payments (${kAsk.status}/${kRecord.status}/${kView.status})`)
  // another business's owner
  const otherFile = `${OUT}/other_d1.json`
  execFileSync('uv', ['run', '--no-env-file', 'python', 'tools/acceptance/stack/owner.py', DB, otherFile], { stdio: 'ignore' })
  const other = load(otherFile)
  const o = must(other.token)
  const theirs = (await o('/v1/platform/businesses', { method: 'POST', body: { display_name: 'Other Bakes', business_type: 'other', category_key: 'food_service', subcategory_key: 'bakery' } })).data.business
  for (const m of ['offerings-catalog', 'orders', 'payments']) await o(`/v1/b/${theirs.id}/modules/${m}/enable`, { method: 'POST' })
  const oc = caller(other.token)
  const cross = [
    await oc(`${base}/collect/overview`),
    await oc(`${base}/collect/due?source_type=order&source_id=${cakeOrderId}`),
    await oc(`/v1/platform/businesses/${theirs.id}/collect/due?source_type=order&source_id=${cakeOrderId}`),
    await oc(`/v1/platform/businesses/${theirs.id}/collect/requests`, { method: 'POST', body: { source_type: 'order', source_id: cakeOrderId, amount: 10, purpose: 'full' } }),
  ].map((r) => r.status)
  check(cross[0] === 403 || cross[0] === 404, `another owner cannot open this bakery's payments (${cross[0]})`)
  check(cross[1] === 403 || cross[1] === 404, `…nor what is due on its order (${cross[1]})`)
  check(cross[2] === 404 && cross[3] === 404, `…nor reach the order through their own business (${cross[2]}/${cross[3]})`)
  const theirSlug = (await o(`/v1/b/${theirs.id}`)).data.slug
  const wrongSite = await guestApi(`/v1/public/websites/${theirSlug}/pay/${tokenOf(advanceUrl)}`)
  check(wrongSite.status === 404, `a bakery link under another business's address is not found (${wrongSite.status})`)
  const junk = await guestApi(`/v1/public/websites/${slug}/pay/${'x'.repeat(24)}`)
  check(junk.status === 404, `an invented token is not found (${junk.status})`)
}

await closeAll()
finish()
