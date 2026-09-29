// Demo gate: cross-module journeys through the real Workspace and the LIVE
// worker (no test drains). Local stack only.
//  Gym: a paid member checks in at the door by the code on their card —
//   Memberships decides, Attendance records, the visit shows the member's
//   name; an unpaid member is refused with Memberships' words, nothing kept.
//  Restaurant: the owner writes a recipe on the Recipes page, an order is
//   accepted and cooked, and the worker takes the ingredients off stock once.
//  Field service: an accepted quote handed to Projects becomes its project.
//  Desktop and 390 px.
//
//   LOCAH_API=http://localhost:8030 LOCAH_WORKSPACE=http://localhost:3301 LOCAH_WEB=http://localhost:3300 \
//   LOCAH_ACCEPT_SESSION=acceptance-out/session.json LOCAH_ACCEPT_DB=locah_accept_int \
//   node tools/acceptance/phase_b/demo_gate.mjs
import { execFileSync } from 'node:child_process'
import { mkdirSync, writeFileSync } from 'node:fs'
import { API, OUT, WS, WEB, api, browser, check, newBusiness, realErrors } from './common.mjs'

const results = []
const shots = `${OUT}/phase_b/demo_gate`
mkdirSync(shots, { recursive: true })
const wait = (ms) => new Promise((r) => setTimeout(r, ms))
const tag = Math.random().toString(36).slice(2, 6)
const PSQL = process.env.PSQL || 'psql'
const DB = process.env.LOCAH_ACCEPT_DB || 'locah_accept'
const sql = (q) => execFileSync(PSQL, ['-h', '127.0.0.1', '-p', process.env.PGPORT || '54329', '-U', 'postgres',
  '-d', DB, '-At', '-c', q], { encoding: 'utf8' }).trim()
const text = (page) => page.eval('document.body.innerText')
const fits = (page) => page.eval('document.documentElement.scrollWidth <= window.innerWidth + 1')
const fill = (page, label, value) => page.eval(`(() => {
  const l = [...document.querySelectorAll('label')].filter(x => x.offsetParent !== null).find(x => x.innerText.trim().startsWith(${JSON.stringify(label)}));
  if (!l) throw new Error('no label ' + ${JSON.stringify(label)});
  const el = l.querySelector('input, select, textarea');
  const proto = el.tagName === 'SELECT' ? HTMLSelectElement.prototype : HTMLInputElement.prototype;
  Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, ${JSON.stringify(value)});
  el.dispatchEvent(new Event(el.tagName === 'SELECT' ? 'change' : 'input', { bubbles: true }));
  return true })()`)
async function until(fn, ms = 30000) {
  const end = Date.now() + ms
  for (;;) {
    const v = await fn().catch(() => undefined)
    if (v) return v
    if (Date.now() > end) return v
    await wait(1000)
  }
}

// ---------------------------------------------------------------- gym: the door
const gym = await newBusiness({ name: `Iron Door ${tag}`, type: 'gym',
  modules: ['offerings-catalog', 'memberships', 'payments', 'customer-relationships', 'attendance'] })
const g = `/v1/platform/businesses/${gym.id}`
const plan = (await api(`${g}/membership-plans`, { method: 'POST', body: {
  name: 'Monthly', price_amount: 1500, duration_days: 30, status: 'active', visibility: 'public' } })).data
async function member(name, phone, paid) {
  const c = (await api(`${g}/customers`, { method: 'POST', body: { display_name: name, phone } })).data
  const e = (await api(`${g}/membership-enrolments`, { method: 'POST', body: {
    plan_id: plan.id, customer_contact_id: c.id, payment_method: 'pay_at_business', idempotency_key: crypto.randomUUID() } })).data
  if (paid) await api(`${g}/collect/record`, { method: 'POST', body: { source_type: 'membership', source_id: e.id, amount: 1500, method: 'cash' } })
  return e
}
const divya = await member('Divya Door', '+919840061001', true)
const unpaid = await member('Kiran Unpaid', '+919840061002', false)

for (const mobile of [false, true]) {
  const page = await browser({ mobile })
  const size = mobile ? '390' : 'desktop'
  try {
    const visitor = mobile ? unpaid : divya
    await page.goto(`${WS}/b/${gym.id}/attendance?view=members`)
    await page.waitFor('Check in member', { text: true })
    await fill(page, 'Member code', visitor.checkin_code)
    await page.click('Check in member', { byText: true })
    await wait(2500)
    if (!mobile) {
      await page.goto(`${WS}/b/${gym.id}/attendance?view=today`)
      await page.waitFor("Today", { text: true })
      const body = await text(page)
      check(body.includes('Divya Door'), `${size}: the paid member's visit is recorded under their name`, results)
      check(sql(`select count(*) from attendance_events where business_id='${gym.id}'`) === '1', `${size}: exactly one visit`, results)
    } else {
      const body = await text(page)
      check(/Not paid yet/i.test(body), `${size}: the unpaid member is refused with Memberships' reason`, results)
      check(sql(`select count(*) from attendance_events where business_id='${gym.id}'`) === '1', `${size}: a refused visit is not recorded`, results)
      check(await fits(page), `${size}: the front desk fits 390 px`, results)
    }
    await page.shot(`${shots}/gym-door-${size}.png`)
    check(realErrors(page).length === 0, `${size}: no console errors on the door (${realErrors(page).slice(0, 2).join(' | ')})`, results)
  } finally {
    await page.close()
  }
}

// ---------------------------------------------------------------- restaurant: recipe → cook → stock
const cafe = await newBusiness({ name: `Wrap House ${tag}`, type: 'restaurant',
  modules: ['offerings-catalog', 'orders', 'inventory', 'kitchen', 'procurement', 'recipes'] })
const r = `/v1/platform/businesses/${cafe.id}`
const loc = (await api(`${r}/locations`)).data.find((l) => l.is_primary).id
const wrap = (await api(`${r}/products`, { method: 'POST', body: {
  title: 'Paneer wrap', offering_type: 'menu_item', status: 'active', price_amount: 180, track_inventory: false } })).data
const paneer = (await api(`${r}/products`, { method: 'POST', body: {
  title: 'Paneer', offering_type: 'product', status: 'active', price_amount: 0, track_inventory: true, stock_unit: 'g' } })).data
await api(`${r}/inventory/opening-stock`, { method: 'POST', body: { offering_id: paneer.id, location_id: loc, quantity: 1000, reason: 'Opening' } })
const onHand = async () => (await api(`${r}/inventory?offering_id=${paneer.id}`)).data[0].quantity_on_hand

const page = await browser()
try {
  await page.goto(`${WS}/b/${cafe.id}/recipes`)
  await page.waitFor('Add or replace a recipe', { text: true })
  await fill(page, 'Dish', wrap.id)
  await fill(page, 'Ingredient 1', paneer.id)
  await page.eval(`(() => { const i = document.querySelector('input[name=quantity_0]');
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(i, '150');
    i.dispatchEvent(new Event('input', { bubbles: true })); return true })()`)
  await page.click('Save recipe', { byText: true })
  await until(async () => (await text(page)).includes('Paneer 150 g'), 15000)
  check((await text(page)).includes('Paneer 150 g'), 'restaurant: the recipe is saved from the Workspace page', results)
  await page.shot(`${shots}/recipes.png`)

  const order = (await api(`${r}/orders`, { method: 'POST', body: {
    location_id: loc, channel: 'workspace', internal_reference: 'Table 3', items: [{ offering_id: wrap.id, quantity: 2 }] } })).data
  await api(`${r}/orders/${order.id}/status`, { method: 'POST', body: { status: 'accepted' } })
  const ticket = await until(async () => {
    const rows = sql(`select id || '|' || version from kitchen_tickets where business_id='${cafe.id}'`)
    return rows ? rows.split('\n') : undefined
  })
  check(ticket && ticket.length === 1, 'restaurant: the accepted order is exactly one KOT (live worker)', results)
  let [ticketId, version] = ticket[0].split('|')
  for (const step of ['start', 'ready', 'serve']) {
    version = (await api(`${r}/kitchen/tickets/${ticketId}/${step}`, { method: 'POST', body: { version: Number(version) } })).data.version
  }
  check(await onHand() === 1000 || await onHand() === 700, 'restaurant: serving does not edit stock itself', results)
  const after = await until(async () => (await onHand()) === 700 ? 700 : undefined, 45000)
  check(after === 700, `restaurant: the worker used 2 × 150 g of paneer once (1000 → ${await onHand()})`, results)
  await wait(4000)
  check(await onHand() === 700, 'restaurant: still 700 after the worker kept running (no second consumption)', results)
  await page.goto(`${WS}/b/${cafe.id}/inventory`)
  await page.waitFor('Paneer', { text: true })
  check((await text(page)).includes('0.7 kg'), 'restaurant: the stock page shows 0.7 kg (700 g)', results)
  await page.shot(`${shots}/stock-after.png`)
  check(realErrors(page).length === 0, `restaurant: no console errors (${realErrors(page).slice(0, 2).join(' | ')})`, results)
} finally {
  await page.close()
}

// ---------------------------------------------------------------- field service: quote → project
const fix = await newBusiness({ name: `Cool Fix ${tag}`, type: 'professional_service',
  modules: ['offerings-catalog', 'quotes', 'customer-relationships', 'projects'] })
const f = `/v1/platform/businesses/${fix.id}`
const client = (await api(`${f}/customers`, { method: 'POST', body: { display_name: 'Ravi Kumar', phone: '+919840061003' } })).data
const quote = (await api(`${f}/quotes`, { method: 'POST', body: { title: 'AC servicing — 3 units', customer_contact_id: client.id,
  items: [{ title: 'Split AC deep service', quantity: 3, unit_price: 1200, tax_rate: 18 }] } })).data
const issued = (await api(`${f}/quotes/${quote.id}/issue`, { method: 'POST', body: { valid_days: 10 } })).data
const share = `${API}/v1/public/quotes/${issued.share_token}`
const form = (body) => fetch(share, { method: 'POST', body: new URLSearchParams(body) })
await form({ decision: 'request_code', name: 'Ravi Kumar' })
const code = sql(`select payload->>'code' from platform_outbox_events where event_type='quote.acceptance_code_issued' and payload->>'quote_id'='${quote.id}' order by created_at desc limit 1`)
const accepted = await form({ decision: 'accepted', name: 'Ravi Kumar', code })
check(accepted.ok, 'field service: the customer accepts the quote with the code', results)
await api(`${f}/quotes/${quote.id}/conversion`, { method: 'POST', body: { target: 'project' } })
const project = await until(async () => sql(`select id from projects_projects where business_id='${fix.id}' and source_quote_id='${quote.id}'`) || undefined)
check(!!project, 'field service: the live worker made the project from the accepted quote', results)
const p3 = await browser()
try {
  await p3.goto(`${WS}/b/${fix.id}/projects`)
  await p3.waitFor('AC servicing', { text: true })
  check((await text(p3)).includes('AC servicing'), 'field service: the project shows in the Workspace', results)
  await p3.shot(`${shots}/project.png`)
} finally {
  await p3.close()
}

writeFileSync(`${shots}/results.json`, JSON.stringify(results, null, 1))
const passed = results.filter((x) => x.ok).length
console.log(`\n${passed}/${results.length} checks passed (API ${API}, web ${WEB})`)
