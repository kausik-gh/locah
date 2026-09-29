// P1-10E6 — English, Tamil and Hindi on a business's own website and on
// WhatsApp (PR-10, GP-22 P1 part; MD §2 rule 10, §12 "in the customer's
// language").
//
//  A sweet shop's owner ticks Tamil and Hindi under "Languages on your
//  website". A visitor sees a slim language row above the header, picks
//  தமிழ், and the site's own words — buttons, basket, section headings LOCAH
//  supplies, footer — are Tamil in a real Tamil face; what the owner wrote
//  (the shop's name, its products) stays as written. They order in Tamil:
//  checkout, confirmation and tracking are Tamil. हिंदी from the footer turns
//  the same site Hindi. On WhatsApp, a customer who writes "வணக்கம்" is
//  answered in Tamil and their tracking link opens the Tamil page. Desktop and
//  390 px.
//
//   node tools/acceptance/phase_b/p1_10e_language.mjs
import { WEB, WS, caller, closeAll, fits, load, must, open, recorder, sql } from './pw.mjs'

const { check, shot, finish } = recorder('p1_10e_language')
const OUT = process.env.LOCAH_ACCEPT_OUT || 'acceptance-out'
const owner = load(process.env.LOCAH_ACCEPT_OWNER || `${OUT}/owner2.json`)
const as = must(owner.token)

const created = (await as('/v1/platform/businesses', { method: 'POST', body: {
  display_name: 'Meenakshi Sweets', business_type: 'retail', category_key: 'fresh_grocery', subcategory_key: 'grocery' } })).data.business
const bid = created.id
const base = `/v1/platform/businesses/${bid}`
for (const m of ['offerings-catalog', 'orders', 'payments', 'fulfilment', 'customer-relationships', 'messaging'])
  await as(`/v1/b/${bid}/modules/${m}/enable`, { method: 'POST' })
const slug = (await as(`/v1/b/${bid}`)).data.slug
await as(`/v1/b/${bid}/fulfilment/settings`, { method: 'PATCH', body: { pickup_enabled: true } })
await as(`/v1/b/${bid}/marketplace/visibility`, { method: 'POST', body: { visibility: 'unlisted' } })
await as(`${base}/products`, { method: 'POST', body: { status: 'active', offering_type: 'product', title: 'Mysore pak 250 g', price_amount: 180, visibility: 'public' } })
await as(`${base}/products`, { method: 'POST', body: { status: 'active', offering_type: 'product', title: 'Jangiri 250 g', price_amount: 160, visibility: 'public' } })
await as(`${base}/messaging/channel/sandbox`, { method: 'POST', body: { display_phone: '+919840033333', display_name: 'Meenakshi Sweets' } })
check((await caller(owner.token)(`/v1/b/${bid}/website/publish`, { method: 'POST' })).ok, 'website published')

const glyphs = (page) => page.evaluate(async () => {
  await document.fonts.ready
  return [...document.fonts].filter((f) => f.status === 'loaded').map((f) => f.family).join(' | ')
})
const spills = (page) => page.evaluate(() => [...document.querySelectorAll('main a, main button, main input, main select, header a, header button, footer a, footer button, .ls-langs button')]
  .filter((e) => e.getBoundingClientRect().right > Math.min(window.innerWidth, screen.width) + 1).map((e) => e.textContent?.trim() || e.getAttribute('name')))

// ---------------------------------------------------------------- 1. the owner picks the languages
const ownerCtx = await open({ who: owner })
const op = ownerCtx.page
try {
  await op.goto(`${WS}/b/${bid}/website`)
  await op.getByRole('heading', { name: 'Languages on your website' }).waitFor()
  await op.locator('input[name=site-lang-ta]').check()
  await op.locator('input[name=site-lang-hi]').check()
  await op.locator('select[name=site-lang-first]').waitFor()
  await shot(op, '01-owner-languages.png')
  await op.getByRole('button', { name: 'Save languages' }).click()
  await op.getByText('Saved. Your live site uses these now.').waitFor()
  const stored = sql(`select array_to_string(languages, ',') from websites where business_id = '${bid}'`)
  check(stored === 'en,ta,hi', `the site speaks English first, then Tamil and Hindi (${stored})`)
  check(op.realErrors().length === 0, `no console errors in the Workspace (${op.realErrors().join(' | ').slice(0, 200)})`)
} finally {
  await ownerCtx.context.close()
}

// ---------------------------------------------------------------- 2. a visitor reads it in Tamil and orders
const visitor = await open()
const p = visitor.page
let trackUrl = ''
try {
  await p.goto(`${WEB}/${slug}`)
  const row = p.locator('.ls-langs--nav')
  await row.waitFor()
  check((await row.innerText()).includes('தமிழ்') && (await row.innerText()).includes('हिंदी'), 'the language row offers English, Tamil and Hindi')
  await p.getByRole('button', { name: 'Add to cart' }).first().waitFor()
  check(true, 'English first')
  await row.getByRole('button', { name: 'தமிழ்' }).click()
  await p.locator('[data-locah-site][lang=ta-IN]').waitFor()
  await p.getByRole('button', { name: 'கூடையில் சேர்' }).first().waitFor()
  const tamil = await p.locator('[data-locah-site]').innerText()
  check(tamil.includes('கூடை') && tamil.includes('LOCAH மூலம் இயங்குகிறது'), 'the basket and the footer are in Tamil')
  check(tamil.includes('Meenakshi Sweets') && tamil.includes('Mysore pak 250 g'), 'what the owner wrote stays as written')
  const faces = await glyphs(p)
  check(/Noto_Sans_Tamil|Noto Sans Tamil/.test(faces), `Tamil is drawn in a real Tamil face (${faces.slice(0, 160)})`)
  await shot(p, '02-site-tamil.png')

  await p.getByRole('button', { name: 'கூடையில் சேர்' }).first().click()
  await p.getByRole('link', { name: 'கூடையைப் பார்' }).first().click()
  await p.getByRole('heading', { name: 'உங்கள் ஆர்டர்' }).waitFor()
  await p.locator('dl.ls-bill__totals dd.is-total').filter({ hasText: '₹' }).waitFor()
  const checkout = await p.locator('main').innerText()
  check(checkout.includes('கூடை') && checkout.includes('மொத்தம்') && checkout.includes('உங்கள் விவரங்கள்'), 'checkout is in Tamil')
  await p.locator('input[name=name]').fill('Selvi')
  await p.locator('input[name=email]').fill(`selvi.${Date.now()}@example.com`)
  await p.locator('input[name=phone]').fill('98400 44444')
  await shot(p, '03-checkout-tamil.png')
  await p.getByRole('button', { name: 'ஆர்டர் செய்', exact: true }).click()
  await p.getByRole('heading', { name: 'ஆர்டர் உறுதி செய்யப்பட்டது' }).waitFor()
  check((await p.locator('main').innerText()).includes('வாங்கும்போது'), 'the confirmation says how to pay, in Tamil')
  await p.getByRole('link', { name: 'உங்கள் ஆர்டர் எங்கே' }).click()
  await p.waitForURL(/\/track\//)
  trackUrl = p.url()
  await p.locator('h1', { hasText: 'ஆர்டர்' }).waitFor()
  const tracking = await p.locator('main').innerText()
  check(tracking.includes('கடை ஏற்கக் காத்திருக்கிறது') && tracking.includes('நேரில் வாங்க'), `tracking reads in plain Tamil words (${tracking.replace(/\s+/g, ' ').slice(0, 140)})`)
  check(!/pending|received/.test(tracking), 'no stored states on the tracking page')
  await shot(p, '04-tracking-tamil.png')

  // Hindi from the footer
  await p.goto(`${WEB}/${slug}`)
  await p.locator('.ls-langs--foot').getByRole('button', { name: 'हिंदी' }).click()
  await p.locator('[data-locah-site][lang=hi-IN]').waitFor()
  await p.getByRole('button', { name: 'टोकरी में डालें' }).first().waitFor()
  const hindi = await p.locator('[data-locah-site]').innerText()
  check(hindi.includes('टोकरी') && hindi.includes('LOCAH द्वारा संचालित'), 'the same site in Hindi')
  const hfaces = await glyphs(p)
  check(/Noto_Sans_Devanagari|Noto Sans Devanagari/.test(hfaces), `Hindi is drawn in a real Devanagari face (${hfaces.slice(0, 160)})`)
  await p.evaluate(() => window.scrollTo(0, 0))
  await shot(p, '05-site-hindi.png')
  check(p.realErrors().length === 0, `no console errors on the site (${p.realErrors().join(' | ').slice(0, 200)})`)
} finally {
  await visitor.context.close()
}

// ---------------------------------------------------------------- 3. WhatsApp in Tamil, and its link
{
  await as(`${base}/messaging/sandbox/inbound`, { method: 'POST', body: { from_phone: '919840055555', name: 'Kala', text: 'வணக்கம்' } })
  const said = sql(`select m.body from messaging_messages m join messaging_conversations c on c.id = m.conversation_id where c.business_id = '${bid}' and c.wa_id = '919840055555' and m.direction = 'out' order by m.created_at desc limit 1`)
  check(said.startsWith('வணக்கம் Kala!'), `a customer who writes in Tamil is answered in Tamil (${said.slice(0, 60)})`)
  const lang = sql(`select c.language || '|' || c.language_source from customer_relationships_contacts c join messaging_conversations m on m.contact_id = c.id where m.business_id = '${bid}' and m.wa_id = '919840055555'`)
  check(lang === 'ta|detected', `their language is kept (${lang})`)
  // A tracking link sent to a Tamil customer carries ?lang=ta and opens in Tamil even for an English-first site.
  const guest = await open()
  await guest.page.goto(`${trackUrl.split('?')[0]}?${new URL(trackUrl).searchParams.toString().replace(/&?lang=[a-z]+/, '')}&lang=ta`)
  await guest.page.locator('[data-locah-site][lang=ta-IN]').waitFor()
  check((await guest.page.locator('main').innerText()).includes('கடை ஏற்கக் காத்திருக்கிறது'), 'a WhatsApp tracking link with ?lang=ta opens in Tamil')
  await guest.context.close()
}

// ---------------------------------------------------------------- 390 px
{
  const phone = await open({ mobile: true })
  const q = phone.page
  await q.context().addCookies([{ name: 'ls_lang', value: 'ta', url: WEB }])
  await q.goto(`${WEB}/${slug}`)
  await q.locator('[data-locah-site][lang=ta-IN]').waitFor()
  await q.getByRole('button', { name: 'கூடையில் சேர்' }).first().waitFor()
  check(await fits(q), 'the Tamil site fits 390 px')
  const s1 = await spills(q)
  check(s1.length === 0, `nothing spills at 390 px (${s1.join(', ') || 'none'})`)
  check(await q.locator('.ls-langs--nav').isVisible(), 'the language row is there on a phone')
  await shot(q, '06-site-tamil-390.png')
  await q.getByRole('button', { name: 'கூடையில் சேர்' }).first().click()
  await q.goto(`${WEB}/${slug}/checkout`)
  await q.getByRole('heading', { name: 'உங்கள் ஆர்டர்' }).waitFor()
  check(await fits(q), 'Tamil checkout fits 390 px')
  await shot(q, '07-checkout-tamil-390.png')
  await phone.context.close()
  const ws = await open({ who: owner, mobile: true })
  await ws.page.goto(`${WS}/b/${bid}/website`)
  await ws.page.getByRole('heading', { name: 'Languages on your website' }).scrollIntoViewIfNeeded()
  check(await fits(ws.page), 'the Workspace website page fits 390 px')
  await shot(ws.page, '08-owner-languages-390.png')
  await ws.context.close()
}

await closeAll()
finish()
