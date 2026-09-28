// P1-10B one customer identity across businesses (Founder §12–13; Guide §1; Doc 12 l.848).
//  A customer who once ordered as a guest with their email signs in to LOCAH:
//  the business's own website shows "My account" with that earlier order
//  (linked through the verified email); they order again signed in; the owner
//  completes an order and "Order again" refills the cart at today's price;
//  LOCAH's My Activity shows both orders with Track and "Everything with …".
//  Desktop and 390 px. Local stack only; the owner is a second local identity.
//
//   node tools/acceptance/phase_b/p1_10b_identity.mjs
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { API, OUT, WEB, api, browser, check, realErrors, session } from './common.mjs'

const results = []
const shots = `${OUT}/phase_b/p1_10b`
mkdirSync(shots, { recursive: true })
const owner = JSON.parse(readFileSync(process.env.LOCAH_ACCEPT_OWNER || `${OUT}/owner2.json`, 'utf8'))
const as = (path, opts = {}) => api(path, { ...opts, token: owner.token })
const wait = (ms) => new Promise((r) => setTimeout(r, ms))

// ---- the business, set up by its owner (not the customer)
const created = (await as('/v1/platform/businesses', { method: 'POST', body: { display_name: 'Kaveri Filter Coffee', business_type: 'other', category_key: 'fresh_grocery', sub: undefined } })).data.business
const bid = created.id
for (const m of ['offerings-catalog', 'orders', 'payments', 'fulfilment']) await as(`/v1/b/${bid}/modules/${m}/enable`, { method: 'POST' })
await as(`/v1/b/${bid}/fulfilment/settings`, { method: 'PATCH', body: { pickup_enabled: true } })
await as(`/v1/b/${bid}/marketplace/visibility`, { method: 'POST', body: { visibility: 'unlisted' } })
const slug = (await as(`/v1/b/${bid}`)).data.slug
const coffee = (await as(`/v1/platform/businesses/${bid}/products`, { method: 'POST', body: { status: 'active', offering_type: 'product', title: 'Peaberry filter coffee 500 g', price_amount: 320 } })).data
const site = (await as(`/v1/b/${bid}/website`)).data
const home = (site.draft?.pages || site.pages || []).find((p) => p.slug === 'home') || (site.draft?.pages || site.pages)[0]
await as(`/v1/b/${bid}/website/pages/${home.id}/sections`, { method: 'POST', body: { section_type_id: 'offerings_list', content: { title: 'Our coffee' } } })
const pub = await as(`/v1/b/${bid}/website/publish`, { method: 'POST' }).catch((e) => ({ error: String(e) }))
check(!pub.error, `website published (${pub.error ?? 'ok'})`, results)

// ---- weeks ago, as a guest, with the same email the customer now signs in with
const guestRes = await fetch(`${API}/v1/public/websites/${slug}/checkout`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ items: [{ offering_id: coffee.id, quantity: 1 }], fulfilment_mode: 'pickup', payment_method: 'cod', guest: { name: 'Priya', email: session.email } }) })
const guestOrder = (await guestRes.json()).data
check(guestRes.ok, 'guest order placed with the customer email', results)

const page = await browser()
try {
  // 1. the business's own site offers "My account"
  await page.goto(`${WEB}/${slug}`)
  await page.waitFor('Our coffee', { text: true })
  const accountLink = await page.eval(`document.querySelector('.ls-nav__account')?.getAttribute('href')`)
  check(accountLink === `/${slug}/account`, `site header links to My account (${accountLink})`, results)

  // 2. signed in, the earlier guest order is theirs (verified email)
  await page.goto(`${WEB}/${slug}/account`)
  await page.waitFor('Your account with Kaveri Filter Coffee', { text: true })
  let body = await page.eval('document.body.innerText')
  const guestNumber = guestOrder.order_number ?? guestOrder.order?.order_number
  check(body.includes(`Order ${guestNumber}`), `earlier guest order ${guestNumber} is in their account`, results)
  const btn = await page.eval(`getComputedStyle(document.querySelector('.ls-account .ls-btn, .ls-account .ls-btn--outline') || document.body).borderColor`)
  check(!['rgb(37, 99, 235)', 'rgb(194, 70, 26)'].includes(btn), `account page uses the business's colours, not LOCAH's (${btn})`, results)
  await page.shot(`${shots}/01-account-linked.png`, { full: true })

  // 3. a new order, signed in: no email to type, it joins their account
  // the basket the site's "Add" buttons fill (platform.cart.<slug>)
  await page.eval(`localStorage.setItem('platform.cart.${slug}', JSON.stringify([{ offering_id: '${coffee.id}', title: 'Peaberry filter coffee 500 g', quantity: 2, unit_price: 320, currency: 'INR' }]))`)
  await page.goto(`${WEB}/${slug}/checkout`)
  await page.waitFor('Ordering as', { text: true })
  check(!(await page.eval(`!!document.querySelector('input[type=email]')`)), 'signed-in checkout does not ask for an email', results)
  check(await page.eval(`document.body.innerText.includes('Peaberry filter coffee 500 g')`), 'the basket reached checkout', results)
  await page.shot(`${shots}/02-checkout-signed-in.png`, { full: true })
  await page.click('Place order', { byText: true })
  await page.waitFor('Order confirmed', { text: true })
  await page.shot(`${shots}/02b-order-confirmed.png`)
  await wait(1500)
  await page.goto(`${WEB}/${slug}/account`)
  await page.waitFor('Orders', { text: true })
  const orders = await page.eval(`[...document.querySelectorAll('.ls-account__card .ls-account__row strong')].map(s => s.innerText).filter(t => t.startsWith('Order'))`)
  check(orders.length === 2, `account now shows both orders (${orders.join(', ')})`, results)

  // 4. the owner completes the guest-time order and raises the price; "Order again" uses today's price
  const oid = guestOrder.order_id ?? guestOrder.order?.id
  for (const status of ['accepted', 'preparing', 'ready']) await as(`/v1/platform/businesses/${bid}/orders/${oid}/status`, { method: 'POST', body: { status } })
  await as(`/v1/platform/businesses/${bid}/orders/${oid}/complete`, { method: 'POST', body: {} })
  await as(`/v1/platform/businesses/${bid}/products/${coffee.id}`, { method: 'PATCH', body: { price_amount: 340 } })
  await page.goto(`${WEB}/${slug}/account`)
  await page.waitFor('Order again', { text: true })
  await page.click('Order again', { byText: true })
  await page.waitFor('at today', { text: true })
  body = await page.eval('document.body.innerText')
  check(body.includes('340') && body.includes('Peaberry filter coffee 500 g'), 'Order again refills the cart at today’s price (₹340)', results)
  await page.shot(`${shots}/03-order-again.png`, { full: true })

  // 5. LOCAH My Activity: both orders, with links back
  await wait(2500) // the worker writes activity from the order events
  await page.goto(`${WEB}/activity`)
  await page.waitFor('My activity', { text: true })
  body = await page.eval('document.body.innerText')
  const cards = await page.eval(`[...document.querySelectorAll('.lc-card')].filter(c => c.innerText.includes('Kaveri Filter Coffee') && c.innerText.includes('Order')).length`)
  check(cards >= 2, `My Activity lists both Kaveri orders (${cards})`, results)
  check(body.includes('Everything with Kaveri Filter Coffee'), 'each links to the business account page', results)
  await page.shot(`${shots}/04-my-activity.png`, { full: true })
  check(realErrors(page).length === 0, `no console errors (${realErrors(page).join(' | ').slice(0, 300)})`, results)
} finally {
  await page.close()
}

const phone = await browser({ mobile: true })
try {
  for (const [path, want, name] of [[`${WEB}/${slug}/account`, 'Your account with', '05-account-390'], [`${WEB}/activity`, 'My activity', '06-activity-390']]) {
    await phone.goto(path)
    await phone.waitFor(want, { text: true })
    check(await phone.eval('document.documentElement.scrollWidth <= window.innerWidth + 1'), `${name} fits 390 px`, results)
    await phone.shot(`${shots}/${name}.png`, { full: true })
  }
} finally {
  await phone.close()
}

writeFileSync(`${shots}/results.json`, JSON.stringify(results, null, 2))
const failed = results.filter((r) => !r.ok)
console.log(`\n${results.length - failed.length}/${results.length} checks passed`)
