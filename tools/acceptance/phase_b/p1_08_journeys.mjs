// P1-08 WhatsApp journeys in the browser (Capability Universe §12.2–§12.6;
// §26.3 done-when "§12.6 tests pass with zero model calls").
//  The owner sets opening hours, connects the stack's test number and sets a
//  first-order cash-on-delivery limit; the link and QR appear. A customer then
//  orders on WhatsApp by tapping LOCAH's buttons (tapped here from the inbox,
//  which lets you act as the customer on a test number): menu → item →
//  quantity → delivery → address → summary → place. The order lands in Orders
//  marked WhatsApp. The customer books a tasting from the opening hours. The
//  published website and the Marketplace listing say "Order on WhatsApp".
//  Desktop and 390 px. Zero live provider or model calls.
//
//   CHROME_PATH=/opt/pw-browsers/chromium CHROME_NO_SANDBOX=1 node tools/acceptance/phase_b/p1_08_journeys.mjs
import { mkdirSync, writeFileSync } from 'node:fs'
import { OUT, WEB, WS, api, browser, check, newBusiness, realErrors } from './common.mjs'

const results = []
const shots = `${OUT}/phase_b/p1_08`
mkdirSync(shots, { recursive: true })
const wait = (ms) => new Promise((r) => setTimeout(r, ms))
const rand = () => String(Math.floor(Math.random() * 1e8)).padStart(8, '0')
const customerPhone = `+9197${rand()}`
const shopPhone = `+9198${rand()}`

const biz = await newBusiness({ name: 'Crumbs Home Bakery', category: 'home_food', sub: 'home_bakery', type: 'retail',
  modules: ['offerings-catalog', 'orders', 'fulfilment', 'payments', 'customer-relationships', 'messaging', 'bookings', 'leads'] })
const base = `/v1/platform/businesses/${biz.id}`
const loc = (await api(`${base}/locations`)).data.find((l) => l.is_primary).id
const cake = (await api(`${base}/products`, { method: 'POST', body: { status: 'active', offering_type: 'product', title: 'Plum cake 500 g', price_amount: 450, visibility: 'public' } })).data
await api(`${base}/products`, { method: 'POST', body: { status: 'active', offering_type: 'product', title: 'Choco chip cookies, box of 12', price_amount: 240, visibility: 'public' } })
const tasting = (await api(`${base}/products`, { method: 'POST', body: { status: 'active', offering_type: 'service', title: 'Wedding cake tasting', price_amount: 300, visibility: 'public', attributes: { duration_minutes: 30 } } })).data
await api(`/v1/b/${biz.id}/fulfilment/settings`, { method: 'PATCH', body: { pickup_enabled: true, delivery_enabled: true } })
await api(`/v1/b/${biz.id}/fulfilment/zones`, { method: 'POST', body: { name: 'Anna Nagar', match_type: 'postal_prefix', postal_prefix: '6000', charge_amount: 40 } })

const page = await browser()
const fill = (label, value) => page.eval(`(() => {
  const l = [...document.querySelectorAll('label')].filter(x => x.offsetParent !== null).find(x => x.innerText.trim().startsWith(${JSON.stringify(label)}));
  if (!l) throw new Error('no label ' + ${JSON.stringify(label)});
  const el = l.querySelector('input, select, textarea');
  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(el, ${JSON.stringify(value)});
  el.dispatchEvent(new Event('input', { bubbles: true }));
  return true })()`)
const bubbles = () => page.eval(`document.querySelectorAll('.bos-bubble').length`)
const lastOut = () => page.eval(`[...document.querySelectorAll('.bos-bubble--out')].pop()?.innerText || ''`)
/** Tap one of the choices LOCAH offered, as the customer, and wait for LOCAH's answer. */
async function tap(title) {
  const before = await bubbles()
  let ok = false
  for (let i = 0; i < 40 && !ok; i++) {
    ok = await page.eval(`(() => { const b = [...document.querySelectorAll('.bos-bubble__options button:not([disabled])')].find(x => x.innerText.trim() === ${JSON.stringify(title)}); if (!b) return false; b.click(); return true })()`)
    if (!ok) await wait(250)
  }
  if (!ok) throw new Error(`no choice "${title}" to tap: ${await page.eval(`[...document.querySelectorAll('.bos-bubble')].slice(-3).map(x => x.outerHTML).join('\n')`)}`)
  for (let i = 0; i < 60 && (await bubbles()) < before + 2; i++) await wait(250)
  await wait(300)
}
async function write(text) {
  const before = await bubbles()
  await page.type('#as-customer', text)
  await page.click('.bos-inbox__as-customer button[type=submit]')
  for (let i = 0; i < 60 && (await bubbles()) < before + 2; i++) await wait(250)
  await wait(300)
}
const text = () => page.eval('document.body.innerText')

// The next day the location is open, two days out so every slot is in the future.
const day = new Date(Date.now() + 2 * 86400000)
const dayKey = ['sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat'][new Date(day.toLocaleString('en-US', { timeZone: 'Asia/Kolkata' })).getDay()]
const dayLabel = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'][['sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat'].indexOf(dayKey)]
let orderNumber = ''
try {
  // ---- 1. opening hours, in Locations
  await page.goto(`${WS}/b/${biz.id}/locations/${loc}`)
  await page.waitFor('Opening hours', { text: true })
  await page.eval(`(() => { const d = document.querySelector('[data-day="mon"] input[type=checkbox]'); if (!d.checked) d.click(); return true })()`)
  await page.waitFor('[data-day="mon"] input[type=time]')
  await page.click('Copy Monday to Tuesday–Saturday', { byText: true })
  await wait(200)
  if (dayKey === 'sun') await page.eval(`document.querySelector('[data-day="sun"] input[type=checkbox]').click()`)
  await wait(200)
  await page.click('Save opening hours', { byText: true })
  await page.waitFor('Opening hours saved', { text: true })
  const saved = (await api(`${base}/locations/${loc}`)).data.hours
  check(saved[dayKey]?.[0]?.join('-') === '09:00-18:00' && saved.mon && saved.sat, `weekly hours saved as structured times (${JSON.stringify(saved).slice(0, 80)})`, results)
  await page.shot(`${shots}/01-opening-hours.png`, { full: true })

  // ---- 2. connect the test number; the link, the QR, the payment rules
  await page.goto(`${WS}/b/${biz.id}/whatsapp`)
  await page.waitFor('Your WhatsApp number', { text: true })
  await fill('Test number', shopPhone)
  await page.click('Connect test number', { byText: true })
  await page.waitFor('Customers order and book here', { text: true })
  const body = await text()
  const digits = shopPhone.slice(1)
  check(body.includes(`https://wa.me/${digits}?text=menu`), 'the link opens the business number with "menu" typed', results)
  check(await page.eval(`!!document.querySelector('.bos-wa-qr svg')`), 'a QR for the counter and packaging', results)
  check(body.includes('Order — pick items') && body.includes('Book — a service') && body.includes('Ask a question'), 'what customers can do, from the modules that are on', results)
  await fill('First order: pay on delivery up to', '2000')
  await page.click('Save payment rules', { byText: true })
  await page.waitFor('Saved', { text: true })
  check((await api(`${base}/messaging/setup`)).data.settings.first_order_cod_cap === 2000, 'first-order cash-on-delivery limit saved', results)
  await page.shot(`${shots}/02-whatsapp-entry.png`, { full: true })

  // ---- 3. the customer says hi; LOCAH answers with the menu
  await fill('From', customerPhone)
  await fill('Name', 'Divya')
  await fill('Message', 'Hi')
  await page.click('Send as the customer', { byText: true })
  await page.waitFor('Delivered to the inbox', { text: true })
  const chat = (await api(`${base}/messaging/conversations?view=open`)).data.conversations[0]
  await page.goto(`${WS}/b/${biz.id}/inbox?view=open&c=${chat.id}`)
  await page.waitFor('.bos-bubble__options button')
  const menu = await page.eval(`[...document.querySelectorAll('.bos-bubble__options button')].map(b => b.innerText.trim())`)
  // P1-10E6a added the language choice to the menu.
  check(menu.join('|') === 'Order|Book|Ask a question|Talk to a person|Language · மொழி · भाषा', `the menu offers what works now (${menu.join(', ')})`, results)
  check(!chat.needs_person, 'LOCAH is handling the chat — nobody is waiting', results)
  await page.shot(`${shots}/03-menu.png`, { full: true })

  // ---- 4. order: item → quantity → checkout → delivery → address → summary → place
  await tap('Order')
  check((await lastOut()).includes('Choose an item'), 'items listed with today\'s prices', results)
  await tap('Plum cake 500 g')
  await tap('2')
  check((await lastOut()).includes('₹900.00'), `cart priced from the catalogue (${(await lastOut()).split('\n')[0]})`, results)
  await tap('Checkout')
  await tap('Delivery')
  check((await lastOut()).includes('location pin'), 'asks for a pin or the address', results)
  await write('7, 3rd Avenue, Anna Nagar, Chennai 600040')
  const summary = await lastOut()
  check(summary.includes('2 × Plum cake 500 g — ₹900.00') && summary.includes('Delivery — ₹40.00') && summary.includes('Total ₹940.00') && summary.includes('Pay on delivery'),
    `the customer sees the whole order before placing it (${summary.replace(/\s+/g, ' ').slice(0, 120)})`, results)
  const beforeOrders = (await api(`${base}/orders`)).data.length
  check(beforeOrders === 0, 'nothing is placed without the button', results)
  await page.shot(`${shots}/04-summary.png`, { full: true })
  await tap('Place order')
  const placed = await lastOut()
  const orders = (await api(`${base}/orders`)).data
  orderNumber = orders[0]?.order_number
  check(orders.length === 1 && orders[0].channel === 'whatsapp' && Number(orders[0].total_amount) === 940, `one order, from WhatsApp, ₹940 (${orders.length})`, results)
  check(placed.includes(`Order ${orderNumber} placed for ₹940.00`) && placed.includes('/track/'), 'confirmation with the tracking link', results)
  await page.shot(`${shots}/05-placed.png`, { full: true })

  // ---- 5. Orders: marked WhatsApp
  await page.goto(`${WS}/b/${biz.id}/orders`)
  await page.waitFor(orderNumber, { text: true })
  const row = await page.eval(`[...document.querySelectorAll('tr')].find(r => r.innerText.includes(${JSON.stringify(orderNumber)}))?.innerText || ''`)
  check(row.includes('WhatsApp'), `the orders list says where it came from (${row.replace(/\s+/g, ' ')})`, results)
  await page.shot(`${shots}/06-orders.png`, { full: true })

  // ---- 6. book a tasting from the opening hours
  await page.goto(`${WS}/b/${biz.id}/inbox?view=open&c=${chat.id}`)
  await page.waitFor('#as-customer')
  await write('book')
  await tap('Wedding cake tasting')
  const ist = new Date(day.toLocaleString('en-US', { timeZone: 'Asia/Kolkata' }))
  const dayRow = `${['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'][ist.getDay()]} ${String(ist.getDate()).padStart(2, '0')} ${['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][ist.getMonth()]}`
  await tap(dayRow)
  const slots = await page.eval(`[...[...document.querySelectorAll('.bos-bubble--out')].pop().querySelectorAll('.bos-bubble__options button')].map(b => b.innerText.trim())`)
  check(slots[0] === '9:00 AM' && slots.length === 10, `free times from the ${dayLabel} hours (${slots.slice(0, 3).join(', ')} …)`, results)
  await tap('10:30 AM')
  check((await lastOut()).includes('Confirm?'), 'the customer confirms the booking with a button', results)
  await tap('Confirm')
  const booked = await lastOut()
  const bookings = (await api(`${base}/bookings`)).data
  const bk = (bookings.items || bookings)[0]
  check(bk && bk.channel === 'whatsapp' && booked.startsWith(`Booking ${bk.booking_number}: Wedding cake tasting`) && booked.includes('10:30 AM'),
    `booking made from WhatsApp (${booked.slice(0, 80)})`, results)
  await page.shot(`${shots}/07-booked.png`, { full: true })
  check(realErrors(page).length === 0, `no console errors (${realErrors(page).join(' | ').slice(0, 300)})`, results)
} finally {
  await page.close()
}

// ---- 7. the website says "Order on WhatsApp"
const site = (await api(`/v1/b/${biz.id}/website`)).data
check(Boolean(site), 'the business has a website to publish', results)
await api(`/v1/b/${biz.id}/marketplace/visibility`, { method: 'POST', body: { visibility: 'unlisted' } }).catch(() => null)
const pub = await api(`/v1/b/${biz.id}/website/publish`, { method: 'POST' }).catch((e) => ({ error: String(e) }))
check(!pub.error, `website published (${pub.error ?? 'ok'})`, results)
const visitor = await browser()
try {
  await visitor.goto(`${WEB}/${biz.slug}`)
  await visitor.waitFor('.ls-wa-float')
  const float = await visitor.eval(`document.querySelector('.ls-wa-float').getAttribute('href')`)
  check(float === `https://wa.me/${shopPhone.slice(1)}?text=menu`, `the WhatsApp button opens the menu on the business number (${float})`, results)
  check((await visitor.eval('document.body.innerText')).includes('Order on WhatsApp'), 'the footer says "Order on WhatsApp"', results)
  await visitor.eval(`window.scrollTo(0, document.body.scrollHeight)`)
  await visitor.shot(`${shots}/08-website.png`)
  check(realErrors(visitor).length === 0, `no console errors on the website (${realErrors(visitor).join(' | ').slice(0, 200)})`, results)
} finally {
  await visitor.close()
}

// ---- 8. 390 px: the chat with choices, WhatsApp settings, opening hours, the website bar
const phone = await browser({ mobile: true })
try {
  const chat = (await api(`${base}/messaging/conversations?view=open`)).data.conversations[0]
  await phone.goto(`${WS}/b/${biz.id}/inbox?view=open&c=${chat.id}`)
  await phone.waitFor('.bos-bubble__options')
  check(await phone.eval('document.documentElement.scrollWidth <= window.innerWidth + 1'), 'chat with choices fits 390 px', results)
  await phone.shot(`${shots}/09-chat-390.png`, { full: true })
  await phone.goto(`${WS}/b/${biz.id}/whatsapp`)
  await phone.waitFor('.bos-wa-qr svg')
  check(await phone.eval('document.documentElement.scrollWidth <= window.innerWidth + 1'), 'WhatsApp settings with the QR fit 390 px', results)
  await phone.shot(`${shots}/10-whatsapp-390.png`, { full: true })
  await phone.goto(`${WS}/b/${biz.id}/locations/${loc}`)
  await phone.waitFor('[data-day="mon"] input[type=time]')
  check(await phone.eval('document.documentElement.scrollWidth <= window.innerWidth + 1'), 'opening hours fit 390 px', results)
  await phone.shot(`${shots}/11-hours-390.png`, { full: true })
  await phone.goto(`${WEB}/${biz.slug}`)
  await phone.waitFor('.ls-mobile-bar')
  const bar = await phone.eval(`[...document.querySelectorAll('.ls-mobile-bar a')].map(a => a.innerText.trim())`)
  check(bar.includes('Order on WhatsApp'), `the phone bar says "Order on WhatsApp" (${bar.join(', ')})`, results)
  check(await phone.eval('document.documentElement.scrollWidth <= window.innerWidth + 1'), 'website fits 390 px', results)
  await phone.shot(`${shots}/12-website-390.png`)
  check(realErrors(phone).length === 0, `no console errors at 390 px (${realErrors(phone).join(' | ').slice(0, 200)})`, results)
} finally {
  await phone.close()
}

writeFileSync(`${shots}/results.json`, JSON.stringify(results, null, 2))
const failed = results.filter((r) => !r.ok)
console.log(`\n${results.length - failed.length}/${results.length} checks passed`)
