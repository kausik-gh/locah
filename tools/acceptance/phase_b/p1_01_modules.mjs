// P1-01 browser check: a meat shop sees tools recommended from its kind and
// traits, switches one on, changes how it works, and the recommendations and
// setup status follow — persisted across reloads, on desktop and phone.
//
//   CHROME_PATH=/opt/pw-browsers/chromium CHROME_NO_SANDBOX=1 node tools/acceptance/phase_b/p1_01_modules.mjs
import { writeFileSync } from 'node:fs'
import { OUT, WS, browser, check, newBusiness } from './common.mjs'

const results = []
const shots = `${OUT}/phase_b/p1_01`
const biz = await newBusiness({ name: 'Anna Meat Stall', category: 'fresh_grocery', sub: 'meat_shop', type: 'retail' })
const page = await browser()
try {
  await page.goto(`${WS}/b/${biz.id}/modules`)
  await page.waitFor('Recommended for you', { text: true })
  const body = await page.eval('document.body.innerText')
  check(body.includes('meat, chicken, fish shops'), 'recommendations name the §21 family', results)
  check(body.includes('Orders') && body.includes('Stock') && body.includes('Pickup & delivery'), 'core tools shown', results)
  check(!body.includes('Counter billing') && !body.includes('Live delivery'), 'unbuilt tools (POS, dispatch) are not shown', results)
  const lower = body.toLowerCase()
  check(lower.includes('customers can') && lower.includes('your team can') && lower.includes('why'), 'each card says why, customers, team', results)
  await page.shot(`${shots}/01-recommended-desktop.png`, { full: true })

  // Turn on Orders.
  await page.eval(`(() => { const card = [...document.querySelectorAll('article.bos-tool')].find(a => a.querySelector('h3').innerText === 'Orders'); card.querySelector('button').click(); return true })()`)
  await page.waitFor('Running', { text: true })
  await page.goto(`${WS}/b/${biz.id}/modules`)
  const running = await page.eval(`[...document.querySelectorAll('#running-h ~ .bos-grid article h3')].map(h => h.innerText)`)
  check(running.includes('Orders'), 'Orders moved to Running and survived reload', results)
  const status = await page.eval(`(() => { const card = [...document.querySelectorAll('article.bos-tool')].find(a => a.querySelector('h3').innerText === 'Orders'); return card.querySelector('.bos-state').innerText })()`)
  check(/^Setup: 1 of 2 done$/.test(status), `Orders is on but not ready (${status}) — no priced product yet`, results)
  await page.shot(`${shots}/02-orders-running.png`, { full: true })

  // Change how the business works: no local delivery.
  await page.goto(`${WS}/b/${biz.id}/settings/business`)
  await page.waitFor('How your business works', { text: true })
  const kind = await page.text('.bos-kind')
  check(kind.includes('Meat shop'), `kind shown in words (${kind.trim()})`, results)
  await page.eval(`(() => { const l = [...document.querySelectorAll('label.bos-toggle')].find(x => x.innerText.includes('I deliver locally')); l.querySelector('input').click(); return true })()`)
  await page.waitFor('Saved. Your recommended tools have been updated.', { text: true })
  await page.shot(`${shots}/03-traits.png`, { full: true })
  await page.goto(`${WS}/b/${biz.id}/settings/business`)
  const deliverOn = await page.eval(`[...document.querySelectorAll('label.bos-toggle')].find(x => x.innerText.includes('I deliver locally')).querySelector('input').checked`)
  check(deliverOn === false, 'trait change persisted across reload', results)
  const tag = await page.eval(`[...document.querySelectorAll('label.bos-toggle')].find(x => x.innerText.includes('I deliver locally')).innerText`)
  check(tag.includes('your choice'), 'owner choice is labelled', results)

  // Phone.
  await page.viewport(390, 844, true)
  await page.goto(`${WS}/b/${biz.id}/modules`)
  await page.waitFor('Recommended for you', { text: true })
  const overflow = await page.eval('document.documentElement.scrollWidth > window.innerWidth + 1')
  check(!overflow, 'no sideways scroll at 390 px', results)
  await page.shot(`${shots}/04-modules-phone.png`, { full: true })
  await page.goto(`${WS}/b/${biz.id}/settings/business`)
  await page.shot(`${shots}/05-traits-phone.png`, { full: true })
  check(page.consoleErrors.length === 0, `no console errors (${page.consoleErrors.slice(0, 2).join(' | ')})`, results)
} finally {
  await page.close()
  writeFileSync(`${shots}/results.json`, JSON.stringify({ business: biz, results }, null, 1))
}
