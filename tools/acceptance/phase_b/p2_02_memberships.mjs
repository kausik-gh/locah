// P2-02 one recurring-relationship engine, specialised per trade
// (Founder refinement — Memberships & Subscriptions §6–§23, §28).
//  Gym: the owner builds a monthly plan in the Workspace, enrols a member,
//  records the payment (Active), freezes 10 days (the end moves by exactly
//  10), renews early (the next period starts after the current one), and the
//  front desk scans the code: green.
//  Milk: a daily subscription shows tomorrow's quantity; the owner skips one
//  day; the customer, signed in on the business's own site, sees "My
//  Subscription" and skips / restores tomorrow themselves.
//  Coaching: a fee plan with a guardian payer shows paid / outstanding / next
//  instalment. Desktop and 390 px. Local stack only.
//
//   LOCAH_API=http://localhost:8020 LOCAH_WORKSPACE=http://localhost:3201 LOCAH_WEB=http://localhost:3200 \
//   LOCAH_ACCEPT_SESSION=acceptance-out/mem-owner.json node tools/acceptance/phase_b/p2_02_memberships.mjs
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { launch } from '../cdp.mjs'
import { API, OUT, WEB, WS, api, browser, check, clickUntil, newBusiness, realErrors } from './common.mjs'

const results = []
const shots = `${OUT}/phase_b/p2_02`
mkdirSync(shots, { recursive: true })
const wait = (ms) => new Promise((r) => setTimeout(r, ms))
const tag = Math.random().toString(36).slice(2, 6)
const iso = (d) => d.toISOString().slice(0, 10)
const istDate = (offsetDays = 0) => iso(new Date(Date.now() + 5.5 * 3600e3 + offsetDays * 86400e3))

const fill = (page, label, value) => page.eval(`(() => {
  const l = [...document.querySelectorAll('label')].filter(x => x.offsetParent !== null).find(x => x.innerText.trim().startsWith(${JSON.stringify(label)}));
  if (!l) throw new Error('no label ' + ${JSON.stringify(label)});
  const el = l.querySelector('input, select, textarea');
  const proto = el.tagName === 'SELECT' ? HTMLSelectElement.prototype : el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
  Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, ${JSON.stringify(value)});
  el.dispatchEvent(new Event(el.tagName === 'SELECT' ? 'change' : 'input', { bubbles: true }));
  return true })()`)
const text = (page) => page.eval('document.body.innerText')
const fits = (page) => page.eval('document.documentElement.scrollWidth <= window.innerWidth + 1')

// ---------------------------------------------------------------- a gym
const gym = await newBusiness({ name: `Iron Temple ${tag}`, modules: ['offerings-catalog', 'memberships', 'payments', 'customer-relationships'] })
const b = gym.id
const member = (await api(`/v1/platform/businesses/${b}/customers`, { method: 'POST', body: { display_name: 'Divya Raman', phone: '+919840055501' } })).data

const page = await browser()
try {
  await page.goto(`${WS}/b/${b}/memberships`)
  await page.waitFor('New plan', { text: true })
  check((await text(page)).includes('Members'), 'the gym sees a Members home, not a generic table', results)
  await fill(page, 'Name', 'Monthly unlimited')
  await fill(page, 'Price per period', '1500')
  await fill(page, 'Length (days)', '30')
  await fill(page, 'Grace after it ends', '3')
  await fill(page, 'Most freeze days per member', '15')
  await page.click('Save plan', { byText: true })
  await page.waitFor('Membership · ₹1,500', { text: true })
  await wait(500)
  await page.goto(`${WS}/b/${b}/memberships`)
  await page.waitFor('Add a membership', { text: true })
  await page.shot(`${shots}/01-gym-home-empty.png`, { full: true })
  await page.click('Add', { byText: true })
  await page.waitFor('Payment pending', { text: true })
  const eid = (await page.eval('location.pathname')).split('/').pop()
  check(/^[0-9a-f-]{36}$/.test(eid), `enrolled — the member's page opened (${eid})`, results)
  await page.shot(`${shots}/02-member-pending.png`, { full: true })

  // record the payment at the desk (the shared money panel)
  await clickUntil(page, 'Record money received', 'form.bos-money__form input[name=amount]')
  await page.click('Record', { byText: true })
  await page.waitFor('Recorded.', { text: true })
  await page.goto(`${WS}/b/${b}/memberships/${eid}`)
  await page.waitFor('Front desk code', { text: true })
  let t = await text(page)
  check(t.includes('Active') && t.includes('Front desk code'), 'paid at the desk → Active, with the front-desk code', results)
  const validBefore = await page.eval(`[...document.querySelectorAll('.bos-money__sum div')].find(d => d.innerText.startsWith('VALID UNTIL') || d.innerText.startsWith('Valid until'))?.querySelector('dd')?.innerText`)
  await page.shot(`${shots}/03-member-active.png`, { full: true })

  // freeze 10 days → the end moves by exactly 10
  const before = (await api(`/v1/platform/businesses/${b}/membership-enrolments/${eid}`)).data.detail
  await clickUntil(page, 'Freeze', 'form.bos-money__form input[name=days]')
  await fill(page, 'From', istDate(7))
  await fill(page, 'Days', '10')
  await fill(page, 'Reason (optional)', 'Travelling')
  await page.eval(`[...document.querySelectorAll('form button[type=submit]')].find(b => b.innerText.trim() === 'Freeze').click()`)
  await page.waitFor('extended 10 days by freezes', { text: true })
  const after = (await api(`/v1/platform/businesses/${b}/membership-enrolments/${eid}`)).data.detail
  const moved = (new Date(after.valid_until) - new Date(before.valid_until)) / 86400e3
  check(moved === 10, `10-day freeze moves the end by exactly ${moved} days (was ${validBefore})`, results)
  check(after.freezes.length === 1 && after.freezes[0].reason === 'Travelling', 'the freeze is kept as history with its reason', results)
  await page.shot(`${shots}/04-member-frozen.png`, { full: true })

  // renew early → the next period starts when this one ends
  await page.click('Renew membership', { byText: true })
  await page.waitFor('Waiting for payment', { text: true })
  const renewed = (await api(`/v1/platform/businesses/${b}/membership-enrolments/${eid}`)).data.detail
  check(renewed.periods[1].starts_at === after.valid_until && renewed.periods[1].source === 'early_renewal',
    'early renewal queues after the current period — no day lost', results)
  await clickUntil(page, 'Record money received', 'form.bos-money__form input[name=amount]')
  await page.click('Record', { byText: true })
  await page.waitFor('Recorded.', { text: true })
  await page.goto(`${WS}/b/${b}/memberships/${eid}`)
  await page.waitFor('renewed early', { text: true })
  const done = (await api(`/v1/platform/businesses/${b}/membership-enrolments/${eid}`)).data.detail
  check(done.periods.every((p) => p.payment_state === 'paid') && done.periods.length === 2, 'two paid periods, both kept', results)
  await page.shot(`${shots}/05-member-renewed.png`, { full: true })

  // the front desk
  await page.goto(`${WS}/b/${b}/memberships/checkin`)
  await page.waitFor('Member code', { text: true })
  await fill(page, 'Member code', done.checkin_code)
  await page.click('Check', { byText: true })
  await page.waitFor('Come in', { text: true })
  const colour = await page.eval(`document.querySelector('.bos-checkin')?.className`)
  check(colour.includes('bos-checkin--green'), `front desk: green for an active member (${colour})`, results)
  await page.shot(`${shots}/06-checkin-green.png`)
  await fill(page, 'Member code', 'NOTACODE')
  await page.click('Check', { byText: true })
  await page.waitFor('No membership with that code', { text: true })
  check(true, 'an unknown code is refused plainly', results)

  await page.goto(`${WS}/b/${b}/memberships`)
  await page.waitFor('Active', { text: true })
  t = await text(page)
  check(t.includes('Divya Raman') && /renewed today\s*1/i.test(t), 'the Members home lists the member and today’s renewal', results)
  await page.shot(`${shots}/07-gym-home.png`, { full: true })
  check(realErrors(page).length === 0, `no console errors (${realErrors(page).join(' | ').slice(0, 300)})`, results)
} finally {
  await page.close()
}

// ---------------------------------------------------------------- milk: tomorrow, skip (owner and customer)
const dairy = await newBusiness({ name: `Nandini Milk ${tag}`, modules: ['offerings-catalog', 'memberships', 'payments', 'customer-relationships', 'orders', 'fulfilment', 'inventory'] })
const d = dairy.id
await api(`/v1/b/${d}/fulfilment/settings`, { method: 'PATCH', body: { pickup_enabled: true, delivery_enabled: true } })
const milk = (await api(`/v1/platform/businesses/${d}/products`, { method: 'POST', body: { title: 'Milk 500 ml', offering_type: 'product', status: 'active', price_amount: 30 } })).data
const plan = (await api(`/v1/platform/businesses/${d}/membership-plans`, { method: 'POST', body: {
  name: 'Morning milk', plan_kind: 'recurring_delivery', price_amount: 900, duration_days: 30, status: 'active', visibility: 'public',
  delivery: { offering_id: milk.id, quantity: 1, slot: 'Morning', window: '06:00-08:00', cutoff: '23:30', mode: 'pickup' } } })).data
// the customer who will sign in on the business's site (a second local identity)
const cust = JSON.parse(readFileSync(process.env.LOCAH_ACCEPT_CUSTOMER || `${OUT}/mem-customer.json`, 'utf8'))
const lakshmi = (await api(`/v1/platform/businesses/${d}/customers`, { method: 'POST', body: { display_name: 'Lakshmi', phone: '+919840055502', email: cust.email } })).data
const sub = (await api(`/v1/platform/businesses/${d}/membership-enrolments`, { method: 'POST', body: {
  plan_id: plan.id, customer_contact_id: lakshmi.id, payment_method: 'pay_at_business', idempotency_key: crypto.randomUUID(),
  starts_at: new Date(`${istDate(0)}T00:00:00+05:30`).toISOString() } })).data
await api(`/v1/platform/businesses/${d}/collect/record`, { method: 'POST', body: { source_type: 'membership', source_id: sub.id, amount: 900, method: 'cash' } })
await api(`/v1/b/${d}/website/publish`, { method: 'POST' })
await api(`/v1/b/${d}/marketplace/visibility`, { method: 'POST', body: { visibility: 'unlisted' } }).catch(() => null)

const p2 = await browser()
try {
  await p2.goto(`${WS}/b/${d}/memberships?kind=recurring_delivery`)
  await p2.waitFor('Tomorrow', { text: true })
  let t = await text(p2)
  check(t.includes('Morning: 1 to deliver') && t.includes('Subscriptions'), 'the milkman sees tomorrow’s quantity first', results)
  await p2.shot(`${shots}/08-milk-home.png`, { full: true })
  await p2.goto(`${WS}/b/${d}/memberships/${sub.id}`)
  await p2.waitFor('Save for that day', { text: true })
  await p2.click('Save for that day', { byText: true })
  await p2.waitFor('Skipped for that day', { text: true })
  const day = (await api(`/v1/platform/businesses/${d}/subscriptions/day?on_date=${istDate(1)}`)).data
  check(day.slots.Morning.skipped === 1 && day.slots.Morning.deliver === 0, 'owner skips tomorrow → nothing to deliver tomorrow', results)
  await p2.shot(`${shots}/09-milk-skipped-owner.png`, { full: true })
} finally {
  await p2.close()
}

// the customer, on the business's own site
const custPage = await launch({ width: 390, height: 844, mobile: true })
try {
  for (const origin of [WEB]) await custPage.cookie(cust.cookie_name, cust.cookie, origin)
  await custPage.goto(`${WEB}/${dairy.slug}/account`)
  await custPage.waitFor('My Subscription', { text: true })
  let t = await text(custPage)
  check(t.includes('Tomorrow: skipped') && t.includes('Back to the usual tomorrow'), 'customer sees “My Subscription” with tomorrow skipped', results)
  await custPage.shot(`${shots}/10-customer-subscription-390.png`, { full: true })
  await custPage.click('Back to the usual tomorrow', { byText: true })
  await custPage.waitFor('Skip tomorrow', { text: true })
  t = await text(custPage)
  check(t.includes('Tomorrow: 1'), 'customer restores tomorrow themselves (before the cutoff)', results)
  await custPage.click('Skip tomorrow', { byText: true })
  await custPage.waitFor('Tomorrow: skipped', { text: true })
  const day = (await api(`/v1/platform/businesses/${d}/subscriptions/day?on_date=${istDate(1)}`)).data
  check(day.slots.Morning.skipped === 1, 'the customer’s skip reaches the owner’s tomorrow count', results)
  check(await fits(custPage), 'customer account fits 390 px', results)
  await custPage.shot(`${shots}/11-customer-skipped-390.png`, { full: true })
} finally {
  await custPage.close()
}

// ---------------------------------------------------------------- coaching: fees with a guardian payer
const tuition = await newBusiness({ name: `Vidya Coaching ${tag}`, modules: ['offerings-catalog', 'memberships', 'payments', 'customer-relationships'] })
const c = tuition.id
const feePlan = (await api(`/v1/platform/businesses/${c}/membership-plans`, { method: 'POST', body: {
  name: 'NEET 2027 batch', plan_kind: 'fee_plan', price_amount: 0, duration_days: 120, status: 'active', visibility: 'private',
  instalment_template: [{ label: 'Admission', amount: 10000, due_after_days: 0 }, { label: 'Second term', amount: 10000, due_after_days: 30 }, { label: 'Third term', amount: 10000, due_after_days: 60 }] } })).data
const asha = (await api(`/v1/platform/businesses/${c}/customers`, { method: 'POST', body: { display_name: 'Asha', phone: '+919840055503' } })).data
const meera = (await api(`/v1/platform/businesses/${c}/customers`, { method: 'POST', body: { display_name: 'Meera (mother)', phone: '+919840055504' } })).data
const fee = (await api(`/v1/platform/businesses/${c}/membership-enrolments`, { method: 'POST', body: {
  plan_id: feePlan.id, customer_contact_id: asha.id, payer_contact_id: meera.id, payment_method: 'pay_at_business', idempotency_key: crypto.randomUUID() } })).data
await api(`/v1/platform/businesses/${c}/collect/record`, { method: 'POST', body: { source_type: 'membership', source_id: fee.id, amount: 10000, method: 'upi' } })

const p3 = await browser({ mobile: true })
try {
  await p3.goto(`${WS}/b/${c}/memberships/${fee.id}`)
  await p3.waitFor('Instalments', { text: true })
  const t = await text(p3)
  check(/paid\s*₹10,000/i.test(t) && /outstanding\s*₹20,000/i.test(t) && t.includes('Second term'), 'fees: paid ₹10,000, outstanding ₹20,000, next instalment shown', results)
  check(!t.includes('Not collected yet'), 'the admission paid by UPI leaves nothing “not collected”', results)
  check(await fits(p3), 'fee page fits 390 px', results)
  await p3.shot(`${shots}/12-fees-390.png`, { full: true })
  await p3.goto(`${WS}/b/${c}/memberships`)
  await p3.waitFor('Fees', { text: true })
  check((await text(p3)).includes('Students'), 'a coaching centre sees Students and Fees, not Members', results)
  check(await fits(p3), 'fees home fits 390 px', results)
  await p3.shot(`${shots}/13-fees-home-390.png`, { full: true })
} finally {
  await p3.close()
}

// 390 px gym pages
const phone = await browser({ mobile: true })
try {
  for (const [path, want, name] of [[`/b/${b}/memberships`, 'Members', '14-gym-home-390'], [`/b/${b}/memberships/checkin`, 'Member code', '15-checkin-390']]) {
    await phone.goto(`${WS}${path}`)
    await phone.waitFor(want, { text: true })
    check(await fits(phone), `${name} fits 390 px`, results)
    await phone.shot(`${shots}/${name}.png`, { full: true })
  }
} finally {
  await phone.close()
}

writeFileSync(`${shots}/results.json`, JSON.stringify(results, null, 2))
const failed = results.filter((r) => !r.ok)
console.log(`\n${results.length - failed.length}/${results.length} checks passed (API ${API})`)
