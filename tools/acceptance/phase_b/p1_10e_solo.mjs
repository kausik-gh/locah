// P1-10E4 — a business one person runs (OM-21; MD §22 "Solo professionals: org
// shape solo — simplified navigation (no team menus), one calendar").
//
//  A maths tutor's Workspace has no Team menus, a Calendar under Home and an
//  "Invite someone" path under Settings. The calendar lists tomorrow's class,
//  an overdue follow-up and a term fee ending, each opening its record. When a
//  second person joins, the team menus come back and the solo Calendar entry
//  goes. Desktop and 390 px.
//
//   node tools/acceptance/phase_b/p1_10e_solo.mjs
import { execFileSync } from 'node:child_process'
import { DB, WS, caller, closeAll, fits, load, must, open, recorder, sql } from './pw.mjs'

const { check, shot, finish } = recorder('p1_10e_solo')
const OUT = process.env.LOCAH_ACCEPT_OUT || 'acceptance-out'
const owner = load(process.env.LOCAH_ACCEPT_OWNER || `${OUT}/owner2.json`)
const as = must(owner.token)

const created = (await as('/v1/platform/businesses', { method: 'POST', body: { display_name: "Meera's Maths Tuition", business_type: 'other' } })).data.business
const bid = created.id
const base = `/v1/platform/businesses/${bid}`
for (const m of ['offerings-catalog', 'workforce', 'bookings', 'payments', 'leads', 'memberships', 'customer-relationships'])
  await as(`/v1/b/${bid}/modules/${m}/enable`, { method: 'POST' })
await as(`${base}/classification`, { method: 'PUT', body: { org_shape: 'solo' } })
const loc = (await as(`${base}/locations`)).data.find((l) => l.is_primary).id
const cls = (await as(`${base}/products`, { method: 'POST', body: { title: 'Class 10 maths', offering_type: 'service', status: 'active', price_amount: 600 } })).data
const pupil = (await as(`${base}/customers`, { method: 'POST', body: { display_name: 'Arjun R', phone: '+919840055001' } })).data.id
const tomorrow = new Date(Date.now() + 86400000)
const start = new Date(Date.UTC(tomorrow.getUTCFullYear(), tomorrow.getUTCMonth(), tomorrow.getUTCDate(), 11, 30)) // 5 pm IST
await as(`${base}/bookings`, { method: 'POST', body: { location_id: loc, offering_id: cls.id, reservation_mode: 'appointment', customer_contact_id: pupil,
  starts_at: start.toISOString(), ends_at: new Date(start.getTime() + 3600000).toISOString() } })
const lead = (await as(`${base}/leads`, { method: 'POST', body: { display_name: "Kavya's mother", phone: '+919840055002' } })).data
sql(`update leads_leads set next_follow_up_at = now() - interval '1 day' where id = '${lead.id}'`)
const plan = sql(`insert into memberships_plans (business_id, name) values ('${bid}', 'Term fees') returning id`).split('\n')[0]
sql(`insert into memberships_enrolments (business_id, plan_id, customer_contact_id, starts_at, ends_at, status) values ('${bid}', '${plan}', '${pupil}', now() - interval '80 days', now() + interval '3 days', 'active')`)

const ctx = await open({ who: owner })
const p = ctx.page
try {
  await p.goto(`${WS}/b/${bid}`)
  const nav = p.locator('nav, aside').first()
  await p.getByRole('link', { name: 'Calendar', exact: true }).waitFor()
  const navText = (await p.locator('aside').first().innerText()).toLowerCase()
  check(!navText.includes('people') && !navText.includes('roles') && !navText.includes('staff & rota'), 'no team menus for a business one person runs')
  check(navText.includes('invite someone'), 'Settings keeps a way to invite a second person')
  void nav
  await shot(p, '01-solo-nav.png')
  await p.getByRole('link', { name: 'Calendar', exact: true }).click()
  await p.getByRole('heading', { name: 'Calendar' }).waitFor()
  const text = await p.locator('main').innerText()
  check(text.includes('Today') && text.includes('Follow up') && text.includes("Kavya's mother") && text.includes('Overdue'), 'today: the overdue follow-up')
  check(text.includes('Tomorrow') && text.includes('Class 10 maths') && text.includes('Arjun R') && text.includes('5 pm'), 'tomorrow 5 pm: the class')
  check(text.includes('Membership ends') && text.includes('Not set to renew'), 'the term fee ending is on the calendar')
  await shot(p, '02-calendar.png')
  await p.locator('.bos-agenda__row', { hasText: 'Class 10 maths' }).click()
  await p.waitForURL(/\/bookings\/[0-9a-f-]{36}/)
  check(true, 'a calendar row opens its booking')
  check(p.realErrors().length === 0, `no console errors (${p.realErrors().join(' | ').slice(0, 200)})`)
} finally {
  await ctx.context.close()
}

// ---------------------------------------------------------------- a second person joins
const helperFile = `${OUT}/helper_e4.json`
execFileSync('uv', ['run', '--no-env-file', 'python', 'tools/acceptance/stack/owner.py', DB, helperFile], { stdio: 'ignore' })
const helper = load(helperFile)
const inv = (await as(`${base}/team/people`, { method: 'POST', body: { name: 'Ravi', email: helper.email, role: 'manager', location_ids: [loc] } })).data
check((await caller(helper.token)(`${base}/invitations/${inv.invitation_id}/accept`, { method: 'POST', body: {} })).ok, 'a second person joined')
{
  const c2 = await open({ who: owner })
  await c2.page.goto(`${WS}/b/${bid}`)
  await c2.page.getByRole('link', { name: 'People', exact: true }).waitFor()
  const navText = (await c2.page.locator('aside').first().innerText()).toLowerCase()
  check(navText.includes('roles') && !navText.includes('invite someone') && (await c2.page.getByRole('link', { name: 'Calendar', exact: true }).count()) === 0,
    'with two people the team menus are back and the solo entries go')
  await shot(c2.page, '03-team-nav.png')
  await c2.context.close()
}

// ---------------------------------------------------------------- 390 px
{
  const phone = await open({ who: owner, mobile: true })
  await phone.page.goto(`${WS}/b/${bid}/calendar`)
  await phone.page.getByRole('heading', { name: 'Calendar' }).waitFor()
  const spill = await phone.page.evaluate(() => [...document.querySelectorAll('main a, main span')]
    .filter((e) => e.getBoundingClientRect().right > window.innerWidth + 1).length)
  check(await fits(phone.page) && spill === 0, `the calendar fits 390 px (${spill} spill)`)
  await shot(phone.page, '04-calendar-390.png')
  await phone.context.close()
}

await closeAll()
finish()
