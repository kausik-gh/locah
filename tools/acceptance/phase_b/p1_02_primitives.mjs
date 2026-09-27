// P1-02 browser check: the shared primitives an owner can see.
//  1. A shop's stock falls below its reorder point → the low-stock automation
//     runs once (worker lane), the owner sees it in Settings › Automations with
//     every step in words, and can switch it off (persisted).
//  2. Settings › Usage shows this month's meters; the owner sets a limit.
//  3. A customer's consent: record a WhatsApp offers opt-in, then withdraw it —
//     the history keeps both.
// Desktop and 390 px.
//
//   CHROME_PATH=/opt/pw-browsers/chromium CHROME_NO_SANDBOX=1 node tools/acceptance/phase_b/p1_02_primitives.mjs
import { execFileSync } from 'node:child_process'
import { mkdirSync, writeFileSync } from 'node:fs'
import { OUT, WS, api, browser, check, newBusiness } from './common.mjs'

const results = []
const shots = `${OUT}/phase_b/p1_02`
mkdirSync(shots, { recursive: true })
const biz = await newBusiness({
  name: 'Selvi Provisions', category: 'fresh_grocery', sub: 'grocery', type: 'retail',
  modules: ['offerings-catalog', 'inventory', 'leads'],
})
const base = `/v1/platform/businesses/${biz.id}`
const locs = (await api(`${base}/locations`)).data
const loc = locs.find((l) => l.is_primary).id
const product = (await api(`${base}/products`, {
  method: 'POST',
  body: { title: 'Toor dal 1 kg', sku: `TD-${Date.now()}`, track_inventory: true, low_stock_threshold: 5, status: 'active', price_amount: 165 },
})).data.id
await api(`${base}/inventory/opening-stock`, { method: 'POST', body: { offering_id: product, location_id: loc, quantity: 8 } })
await api(`${base}/inventory/adjust`, { method: 'POST', body: { offering_id: product, location_id: loc, quantity_delta: -4, reason: 'Sold at counter' } })
const worker = () => execFileSync('.venv/bin/python', ['tools/acceptance/stack/worker_once.py', biz.id], {
  env: { ...process.env, PYTHONPATH: 'python/testing:apps/worker/src' }, encoding: 'utf8',
}).trim()
const ran = worker()
check(/steps=1$/.test(ran), `worker lane ran the low-stock step once (${ran})`, results)
check(/steps=0$/.test(worker()), 'running the lane again does nothing', results)
const customer = (await api(`${base}/customers`, { method: 'POST', body: { display_name: 'Meena R', phone: '+919840000123' } })).data.id

const page = await browser()
try {
  // ---- automations
  await page.goto(`${WS}/b/${biz.id}/settings/automations`)
  await page.waitFor('What automations did', { text: true })
  let body = await page.eval('document.body.innerText')
  check(body.includes('Low-stock alerts') && body.includes('Lead follow-ups'), 'both wired automations listed', results)
  check(!body.includes('Renewal reminders') && !body.includes('Booking reminders'), 'automations without code behind them are not offered', results)
  check(body.includes('Alert everyone who looks after stock'), 'each step says what it does', results)
  check(body.includes('Stops when stock is restored'), 'each automation says when it stops', results)
  check(body.includes('Told you Toor dal 1 kg is low (4 left)') && body.includes('Done'), 'activity log shows what the step did', results)
  await page.shot(`${shots}/01-automations-desktop.png`, { full: true })
  await page.eval(`(() => { const card = [...document.querySelectorAll('section.bos-auto')].find(s => s.querySelector('h2').innerText === 'Low-stock alerts'); card.querySelector('.bos-card__head input').click(); return true })()`)
  await page.waitFor('Switched off. Anything scheduled was stopped.', { text: true })
  await page.goto(`${WS}/b/${biz.id}/settings/automations`)
  await page.waitFor('What automations did', { text: true })
  const offAfterReload = await page.eval(`[...document.querySelectorAll('section.bos-auto')].find(s => s.querySelector('h2').innerText === 'Low-stock alerts').classList.contains('is-off')`)
  check(offAfterReload, 'switching an automation off persists across reload', results)
  const rule = (await api(`${base}/automations`)).data.automations.find((a) => a.key === 'stock.low')
  check(rule.enabled === false, 'API agrees the automation is off', results)
  await page.shot(`${shots}/02-automation-off.png`, { full: true })

  // ---- the notification the step produced is in the owner's feed
  const feed = (await api(`${base}/notifications`)).data
  check(feed.some((n) => n.title === 'Toor dal 1 kg is running low'), 'the alert reached the owner’s notifications', results)
  await page.goto(`${WS}/b/${biz.id}/notifications`)
  await page.waitFor('Toor dal 1 kg is running low', { text: true })
  check(true, 'the alert is visible on the Notifications page', results)

  // ---- usage
  await page.goto(`${WS}/b/${biz.id}/settings/usage`)
  await page.waitFor('Counted once connected', { text: true })
  body = await page.eval('document.body.innerText')
  check(body.includes('AI usage (tokens)') && body.includes('WhatsApp messages'), 'meters listed in words', results)
  await page.eval(`(() => { const card = [...document.querySelectorAll('section.bos-meter')].find(s => s.querySelector('h3').innerText === 'WhatsApp messages'); card.querySelector('button').click(); return true })()`)
  await page.waitFor('.bos-meter__form input')
  await page.eval(`(() => { const i = document.querySelector('.bos-meter__form input'); const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; set.call(i, '500'); i.dispatchEvent(new Event('input', { bubbles: true })); return true })()`)
  await page.eval(`document.querySelector('.bos-meter__form button[type=submit]').click()`)
  await page.waitFor('of 500 this month', { text: true })
  await page.goto(`${WS}/b/${biz.id}/settings/usage`)
  await page.waitFor('of 500 this month', { text: true })
  check(true, 'limit saved and shown after reload', results)
  await page.shot(`${shots}/03-usage.png`, { full: true })

  // ---- consent
  await page.goto(`${WS}/b/${biz.id}/customers/${customer}`)
  await page.waitFor('What they agreed to', { text: true })
  const row = `[...document.querySelectorAll('.bos-consents li')].find(l => l.querySelector('strong').innerText === 'Offers on WhatsApp')`
  await page.eval(`${row}.querySelector('button').click()`)
  await page.waitFor('How did they agree?', { text: true })
  await page.eval(`(() => { const s = document.querySelector('.bos-consents__ask select'); s.value = 'On a phone call'; s.dispatchEvent(new Event('change', { bubbles: true })); return true })()`)
  await page.eval(`[...document.querySelectorAll('.bos-consents__ask button')].find(b => b.innerText === 'Record agreement').click()`)
  await page.waitFor('Agreement recorded.', { text: true })
  await page.goto(`${WS}/b/${biz.id}/customers/${customer}`)
  await page.waitFor('What they agreed to', { text: true })
  const yes = await page.eval(`${row}.querySelector('.bos-state').innerText`)
  check(yes === 'Yes', 'opt-in recorded and shown after reload', results)
  const activity = await page.eval(`document.querySelector('.bos-timeline').innerText`)
  check(activity.includes('Became a customer') && !activity.includes('[object Object]'), 'customer activity reads as words', results)
  await page.shot(`${shots}/04-consent-yes.png`, { full: true })
  await page.eval(`[...${row}.querySelectorAll('button')].find(b => b.innerText === 'Withdraw').click()`)
  await page.waitFor('Withdrawn. Nothing more will be sent for this.', { text: true })
  const hist = (await api(`${base}/customers/${customer}/consents`)).data.history
  check(hist.length === 1 && hist[0].withdrawn_at && hist[0].source === 'staff_recorded', 'history keeps the grant with its withdrawal', results)
  await page.goto(`${WS}/b/${biz.id}/customers/${customer}`)
  await page.waitFor('What they agreed to', { text: true })
  const after = await page.eval(`${row}.innerText`)
  check(after.includes('Withdrawn'), 'withdrawal shown after reload', results)

  // ---- phone
  await page.viewport(390, 844, true)
  for (const [path, name] of [['settings/automations', '05-automations-phone'], ['settings/usage', '06-usage-phone'], [`customers/${customer}`, '07-consent-phone']]) {
    await page.goto(`${WS}/b/${biz.id}/${path}`)
    await page.waitFor('main')
    const overflow = await page.eval('document.documentElement.scrollWidth > window.innerWidth + 1')
    check(!overflow, `no sideways scroll at 390 px (${path})`, results)
    await page.shot(`${shots}/${name}.png`, { full: true })
  }
  check(page.consoleErrors.length === 0, `no console errors (${page.consoleErrors.slice(0, 2).join(' | ')})`, results)
} finally {
  await page.close()
  writeFileSync(`${shots}/results.json`, JSON.stringify({ business: biz, results }, null, 1))
}
