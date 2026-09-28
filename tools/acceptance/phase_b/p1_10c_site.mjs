// P1-10C the website and the Marketplace follow what a business's tools can do
// (Founder §14–16; Guide §4).
//  A gym's site has no plans. The owner switches Memberships on — the
//  Workspace says what is still missing — then publishes a plan: without a
//  rebuild the site gains a Plans section, its main button becomes "See plans",
//  "Ask to join" lands as a lead for that plan, and the Marketplace card leads
//  with Plans. Hiding the section takes it (and the button) away again.
//  A quote-led fabricator's site and card lead with "Get a quote", and the
//  request lands as a lead. Desktop and 390 px. Local stack only.
//
//   node tools/acceptance/phase_b/p1_10c_site.mjs
import { mkdirSync, writeFileSync } from 'node:fs'
import { WEB, WS, api, browser, check, newBusiness, realErrors } from './common.mjs'

const results = []
const shots = 'acceptance-out/phase_b/p1_10c'
mkdirSync(shots, { recursive: true })
const wait = (ms) => new Promise((r) => setTimeout(r, ms))
const tag = Math.random().toString(36).slice(2, 7)

async function publish(bid) {
  await api(`/v1/b/${bid}/website/publish`, { method: 'POST' })
  await api(`/v1/b/${bid}/marketplace/opt-in`, { method: 'POST', body: { confirmed: true } })
}

// ---- a gym, published, with no plans yet
const gym = await newBusiness({ name: `Pulse Fitness ${tag}`, modules: ['leads'] })
await api(`/v1/platform/businesses/${gym.id}/profile`, { method: 'PATCH', body: { description: 'Strength training, yoga and group classes', tagline: 'Train with us' } })
await api(`/v1/platform/businesses/${gym.id}/traits`, { method: 'PATCH', body: { traits: { subscription_led: true } } })
await publish(gym.id)

const page = await browser()
const siteSays = () => page.eval(`({
  sections: [...document.querySelectorAll('section')].map(s => s.id).filter(Boolean),
  cta: (document.querySelector('.ls-nav__cta, .ls-nav a.ls-btn') || {}).innerText || '',
  ctaHref: (document.querySelector('.ls-nav__cta, .ls-nav a.ls-btn') || {}).getAttribute?.('href') || '',
  text: document.body.innerText })`)
/** The live site is cached for up to a minute; reload until it shows `cond`. */
async function siteUntil(url, cond, label) {
  for (let i = 0; i < 16; i++) {
    await page.goto(url)
    await wait(800)
    const s = await siteSays()
    if (cond(s)) return s
    await wait(4500)
  }
  check(false, `site never showed: ${label}`, results)
  return siteSays()
}

try {
  // 1. before: nothing about plans
  await page.goto(`${WEB}/${gym.slug}`)
  await page.waitFor(`Pulse Fitness ${tag}`, { text: true })
  let s = await siteSays()
  check(!s.sections.includes('plans') && !/See plans/.test(s.cta), `before: no plans section, main button "${s.cta || 'none'}"`, results)
  await page.shot(`${shots}/01-site-before.png`)

  // 2. Memberships switched on: the Workspace says what is still missing
  await api(`/v1/b/${gym.id}/modules/memberships/enable`, { method: 'POST' })
  await page.goto(`${WS}/b/${gym.id}/website`)
  await page.waitFor('What customers can do on your site', { text: true })
  let body = await page.eval('document.body.innerText')
  check(/Customers can see and join plans\s*Not yet:/.test(body), 'Workspace: plans are "Not yet" with the missing step', results)
  await page.shot(`${shots}/02-workspace-not-yet.png`, { full: true })

  // 3. a public plan (and a private one that must not show)
  await api(`/v1/platform/businesses/${gym.id}/membership-plans`, { method: 'POST', body: { name: 'Monthly unlimited', description: 'All classes, open gym 6am–10pm', price_amount: 1800, duration_days: 30, status: 'active', visibility: 'public' } })
  await api(`/v1/platform/businesses/${gym.id}/membership-plans`, { method: 'POST', body: { name: 'Quarterly', price_amount: 4800, duration_days: 90, status: 'active', visibility: 'public' } })
  await api(`/v1/platform/businesses/${gym.id}/membership-plans`, { method: 'POST', body: { name: 'Staff comp', price_amount: 0, duration_days: 30, status: 'active', visibility: 'private' } })
  await page.goto(`${WS}/b/${gym.id}/website`)
  await page.waitFor('Sections your tools add', { text: true })
  body = await page.eval('document.body.innerText')
  check(body.includes('Main button: See plans'), 'Workspace: main button is now "See plans"', results)
  check(await page.eval(`[...document.querySelectorAll('[aria-label="Live on your site"] li')].some(li => li.innerText.includes('join plans'))`), 'Workspace: joining plans is live', results)
  check(body.includes('Your plans, so people can join') && body.includes('Showing on your home page'), 'Workspace: the Plans section is listed as showing', results)
  await page.shot(`${shots}/03-workspace-live.png`, { full: true })

  // 4. the live site gains Plans without a rebuild
  s = await siteUntil(`${WEB}/${gym.slug}`, (x) => x.sections.includes('plans') && x.text.includes('Monthly unlimited'), 'the Plans section')
  check(s.sections.includes('plans') && s.text.includes('Monthly unlimited') && s.text.includes('Quarterly'), 'site: Plans section with both public plans', results)
  check(!s.text.includes('Staff comp'), 'site: the private plan is not shown', results)
  check(/See plans/i.test(s.cta) && s.ctaHref.endsWith('#plans'), `site: main button "${s.cta}" → ${s.ctaHref}`, results)
  await page.eval(`document.getElementById('plans')?.scrollIntoView()`)
  await wait(400)
  await page.shot(`${shots}/04-site-plans.png`)

  // 5. "Ask to join" lands as a lead for that plan
  await page.click('Ask to join', { byText: true })
  await page.waitFor('Plan: ', { text: true })
  body = await page.eval('document.body.innerText')
  check(body.includes('Ask to join') && /Monthly unlimited|Quarterly/.test(body), 'join page names the plan in the business colours', results)
  await page.type('input[name=name]', 'Divya')
  await page.type('input[name=phone]', '9840011122')
  await page.shot(`${shots}/05-ask-to-join.png`)
  await page.click('Send', { byText: true })
  await page.waitFor('Sent', { text: true })
  const leads = (await api(`/v1/platform/businesses/${gym.id}/leads`)).data
  const joinLead = leads.find((l) => l.origin_context?.purpose === 'membership')
  check(joinLead && joinLead.display_name === 'Divya' && joinLead.origin_context.plan_title, `lead "${joinLead?.origin_context?.purpose_label}" for plan ${joinLead?.origin_context?.plan_title}`, results)

  // 6. the Marketplace card leads with the plans too (the worker reindexes)
  let card = null
  for (let i = 0; i < 40 && !card; i++) {
    await wait(2500)
    const found = (await api(`/v1/public/search?q=${encodeURIComponent(`Pulse Fitness ${tag}`)}`)).data.businesses
    const b = found.find((x) => x.business_id === gym.id)
    if (b && b.actions.some((a) => a.action === 'join')) card = b
  }
  check(card && card.actions[0].action === 'join' && card.actions[0].href === `/${gym.slug}#plans`, `listing leads with plans (${card?.actions.map((a) => a.action).join(', ')})`, results)
  await page.goto(`${WEB}/marketplace/search?q=${encodeURIComponent(`Pulse Fitness ${tag}`)}`)
  await page.waitFor(`Pulse Fitness ${tag}`, { text: true })
  const cardActs = await page.eval(`[...document.querySelectorAll('.mx-act')].map(a => a.innerText + '→' + a.getAttribute('href'))`)
  check(cardActs.length > 0 && cardActs[0].includes(`#plans`), `Marketplace card's first button goes to the plans (${cardActs.join(' | ')})`, results)
  await page.shot(`${shots}/06-marketplace-card.png`)

  // 7. the owner hides the section: it leaves the site, and so does the button
  await page.goto(`${WS}/b/${gym.id}/website`)
  await page.waitFor('Sections your tools add', { text: true })
  await page.click('input[aria-label="Show your plans, so people can join on your website"]')
  await page.waitFor('Hidden from your site.', { text: true })
  await page.shot(`${shots}/07-workspace-hidden.png`, { full: true })
  s = await siteUntil(`${WEB}/${gym.slug}`, (x) => !x.sections.includes('plans'), 'the Plans section gone')
  check(!s.sections.includes('plans') && !/See plans/i.test(s.cta), `site: plans hidden, main button now "${s.cta || 'none'}"`, results)
  await api(`/v1/b/${gym.id}/website/auto-sections`, { method: 'PATCH', body: { module: 'memberships', hidden: false } })
  check(realErrors(page).length === 0, `no console errors (${realErrors(page).join(' | ').slice(0, 300)})`, results)
} finally {
  await page.close()
}

// ---- a quote-led fabricator
const fab = await newBusiness({ name: `Sri Balaji Fabrication ${tag}`, modules: ['leads', 'quotes'] })
await api(`/v1/platform/businesses/${fab.id}/profile`, { method: 'PATCH', body: { description: 'Gates, grills, sheds and steel work to order', tagline: 'Steel work to order' } })
await api(`/v1/platform/businesses/${fab.id}/traits`, { method: 'PATCH', body: { traits: { quote_led: true } } })
await publish(fab.id)

const phone = await browser({ mobile: true })
try {
  await phone.goto(`${WEB}/${fab.slug}`)
  await phone.waitFor('Get a quote', { text: true })
  const fabCta = await phone.eval(`(document.querySelector('.ls-nav__cta, .ls-nav a.ls-btn') || {}).innerText || ''`)
  const form = await phone.eval(`!!document.querySelector('#enquire form, section#enquire')`)
  check(form, 'fabricator site has a "Get a quote" form', results)
  check(await phone.eval('document.documentElement.scrollWidth <= window.innerWidth + 1'), `fabricator site fits 390 px (main button "${fabCta || 'in menu'}")`, results)
  await phone.shot(`${shots}/08-fabricator-390.png`, { full: true })
  await phone.eval(`document.getElementById('enquire')?.scrollIntoView()`)
  await phone.type('#enquire input[name=name]', 'Karthik')
  await phone.type('#enquire input[name=phone]', '9840099887')
  await phone.type('#enquire textarea[name=message]', 'Main gate 12 ft x 6 ft, MS, primer + paint')
  await phone.click('#enquire button[type=submit]')
  await phone.waitFor('Sent', { text: true })
  await phone.shot(`${shots}/09-quote-sent-390.png`)
  const lead = (await api(`/v1/platform/businesses/${fab.id}/leads`)).data.find((l) => l.origin_context?.purpose === 'quote_request')
  check(lead && lead.display_name === 'Karthik', `quote request is a lead ("${lead?.origin_context?.purpose_label}")`, results)

  // Workspace panel at 390 px
  await phone.goto(`${WS}/b/${gym.id}/website`)
  await phone.waitFor('What customers can do on your site', { text: true })
  check(await phone.eval('document.documentElement.scrollWidth <= window.innerWidth + 1'), 'Workspace website panel fits 390 px', results)
  await phone.shot(`${shots}/10-workspace-390.png`, { full: true })
  // shown again after the owner's "show" (the live page is cached for up to a minute)
  for (let i = 0; i < 16; i++) {
    await phone.goto(`${WEB}/${gym.slug}`)
    await wait(800)
    if (await phone.eval(`document.body.innerText.includes('Monthly unlimited')`)) break
    await wait(4500)
  }
  check(await phone.eval(`!!document.getElementById('plans')`), 'gym site shows Plans again after the owner shows it', results)
  check(await phone.eval('document.documentElement.scrollWidth <= window.innerWidth + 1'), 'gym site with Plans fits 390 px', results)
  await phone.eval(`document.getElementById('plans')?.scrollIntoView()`)
  await wait(400)
  await phone.shot(`${shots}/11-gym-plans-390.png`)
} finally {
  await phone.close()
}

const cardFab = (await api(`/v1/public/search?q=${encodeURIComponent(`Sri Balaji Fabrication ${tag}`)}`)).data.businesses.find((b) => b.business_id === fab.id)
check(cardFab && cardFab.actions[0].action === 'request_quote', `fabricator listing leads with Get a quote (${cardFab?.actions.map((a) => a.action).join(', ')})`, results)

writeFileSync(`${shots}/results.json`, JSON.stringify(results, null, 2))
const failed = results.filter((r) => !r.ok)
console.log(`\n${results.length - failed.length}/${results.length} checks passed`)
