// P1-10E6 — the Workspace in the owner's language (MD "Dashboard Language —
// UI language preference (English / Tamil / Hindi)"; GP-22 P1 part).
//
//  A grocer picks தமிழ் at the foot of the sidebar. The navigation, Home and
//  Orders speak Tamil: the Home band "needs you now" with the order waiting,
//  the order list's states, and an order's own page with "Accept" — which the
//  owner taps. A customer's Tamil WhatsApp message reads in a real Tamil face
//  in the inbox. The choice is saved on the owner's account (a fresh browser
//  adopts it). Back to English at the end. Desktop and 390 px.
//
//   node tools/acceptance/phase_b/p1_10e_workspace_language.mjs
import { WS, caller, closeAll, fits, load, must, open, recorder, sql } from './pw.mjs'

const { check, shot, finish } = recorder('p1_10e_workspace_language')
const OUT = process.env.LOCAH_ACCEPT_OUT || 'acceptance-out'
const owner = load(process.env.LOCAH_ACCEPT_OWNER || `${OUT}/owner2.json`)
const as = must(owner.token)
const me = caller(owner.token)

const created = (await as('/v1/platform/businesses', { method: 'POST', body: {
  display_name: 'Kavitha Stores', business_type: 'retail', category_key: 'fresh_grocery', subcategory_key: 'grocery' } })).data.business
const bid = created.id
const base = `/v1/platform/businesses/${bid}`
for (const m of ['offerings-catalog', 'orders', 'payments', 'fulfilment', 'customer-relationships', 'messaging'])
  await as(`/v1/b/${bid}/modules/${m}/enable`, { method: 'POST' })
await as(`/v1/b/${bid}/fulfilment/settings`, { method: 'PATCH', body: { pickup_enabled: true } })
const rice = (await as(`${base}/products`, { method: 'POST', body: { status: 'active', offering_type: 'product', title: 'Ponni rice 5 kg', price_amount: 340 } })).data
await as(`${base}/orders/phone`, { method: 'POST', body: { customer: { name: 'Lakshmi', phone: '98400 66666' },
  items: [{ offering_id: rice.id, quantity: 2 }], fulfilment_mode: 'pickup', payment_method: 'cod' } })
await as(`${base}/messaging/channel/sandbox`, { method: 'POST', body: { display_phone: '+919840077777', display_name: 'Kavitha Stores' } })
await as(`${base}/messaging/sandbox/inbound`, { method: 'POST', body: { from_phone: '919840088888', name: 'Rani', text: 'அரிசி இருக்கா? நாளை வரலாமா' } })

const ctx = await open({ who: owner })
const p = ctx.page
try {
  await p.goto(`${WS}/b/${bid}`)
  await p.locator('select[name=workspace-language]').selectOption('ta')
  await p.locator('html[lang=ta-IN]').waitFor()
  await p.getByRole('link', { name: 'முகப்பு' }).first().waitFor()
  const nav = await p.locator('#ws-primary-navigation').innerText()
  check(nav.includes('ஆர்டர்கள்') && nav.includes('வாடிக்கையாளர்கள்') && nav.includes('அமைப்புகள்'), 'the navigation is in Tamil')
  const saved = sql(`select coalesce(preferences->>'workspace_language', '') from consumer_profiles where identity_id = (select identity_id from business_memberships where business_id = '${bid}' limit 1)`)
  check(saved === 'ta', `the choice is saved on the owner's account (${saved})`)
  const home = await p.locator('main').innerText()
  check(home.includes('இப்போது உங்களுக்காக') && home.includes('ஏற்கக் காத்திருக்கும் ஆர்டர்கள்'), `Home says what needs them, in Tamil (${home.replace(/\s+/g, ' ').slice(0, 160)})`)
  check(home.includes('Kavitha Stores'), 'the business name stays as written')
  const faces = await p.evaluate(async () => { await document.fonts.ready; return [...document.fonts].filter((f) => f.status === 'loaded').map((f) => f.family).join(' | ') })
  check(/Noto_Sans_Tamil/.test(faces), `Tamil is drawn in a real Tamil face (${faces.slice(0, 120)})`)
  await shot(p, '01-home-tamil.png')

  await p.getByRole('link', { name: 'ஆர்டர்கள்' }).first().click()
  await p.getByRole('heading', { name: 'ஆர்டர்கள்' }).waitFor()
  const list = await p.locator('main').innerText()
  check(list.includes('புதியது') && list.includes('தொலைபேசி') && list.includes('ரொக்கம் · வசூலிக்க வேண்டும்'), `the order list's state, channel and payment read in Tamil (${list.replace(/\s+/g, ' ').slice(0, 200)})`)
  await shot(p, '02-orders-tamil.png')
  await p.locator('table a').first().click()
  await p.getByRole('button', { name: 'ஏற்கவும்' }).waitFor()
  const detail = await p.locator('main').innerText()
  check(detail.includes('பணம் கேள்') && detail.includes('ஆர்டரை மாற்று') && detail.includes('இன்னும் வசூலிக்கப்படவில்லை'),
    'the order page — its money panel and "change order" — is Tamil throughout')
  await shot(p, '03-order-tamil.png')
  await p.getByRole('button', { name: 'ஏற்கவும்' }).click()
  await p.getByRole('button', { name: 'தயாரிக்கத் தொடங்கு' }).waitFor()
  const status = sql(`select status from orders_orders where business_id = '${bid}'`)
  check(status === 'accepted', `"ஏற்கவும்" accepts the order (${status})`)

  await p.goto(`${WS}/b/${bid}/inbox`)
  await p.locator('.bos-inbox__row').first().click()
  await p.locator('.bos-inbox__messages').waitFor()
  check((await p.locator('.bos-inbox__messages').innerText()).includes('அரிசி இருக்கா'), 'the customer’s Tamil message is in the inbox')
  await shot(p, '04-inbox-tamil-message.png')
  check(p.realErrors().length === 0, `no console errors (${p.realErrors().join(' | ').slice(0, 200)})`)
} finally {
  await ctx.context.close()
}

// A fresh browser (no cookie) adopts the saved language.
{
  const fresh = await open({ who: owner })
  await fresh.page.goto(`${WS}/b/${bid}`)
  await fresh.page.locator('html[lang=ta-IN]').waitFor()
  await fresh.page.getByRole('heading', { name: 'இப்போது உங்களுக்காக' }).waitFor()
  check(true, 'a new browser opens in the saved language')
  await fresh.context.close()
}

// 390 px
{
  const phone = await open({ who: owner, mobile: true })
  const q = phone.page
  await q.goto(`${WS}/b/${bid}`)
  await q.locator('html[lang=ta-IN]').waitFor()
  check(await fits(q), 'Home in Tamil fits 390 px')
  await q.getByRole('button', { name: 'வழிசெலுத்தலைத் திற' }).click()
  await q.locator('#ws-primary-navigation[data-mobile-open]').waitFor()
  await q.waitForTimeout(500) // the drawer slides in
  await shot(q, '05-nav-tamil-390.png')
  check(await fits(q), 'the Tamil navigation drawer fits 390 px')
  await q.goto(`${WS}/b/${bid}/orders`)
  await q.getByRole('heading', { name: 'ஆர்டர்கள்' }).waitFor()
  check(await fits(q), 'Orders in Tamil fits 390 px')
  await shot(q, '06-orders-tamil-390.png')
  await phone.context.close()
}

// Back to English for everything else that uses this owner.
const back = await me('/v1/me/workspace-language', { method: 'PUT', body: { language: 'en' } })
check(back.ok, 'back to English')
await closeAll()
finish()
