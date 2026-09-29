// One kitchen pass in the browser. Local stack only. Does not start the servers.
//
//   node tools/acceptance/phase_b/p2_kitchen_kds.mjs
import { execFileSync } from 'node:child_process'
import { mkdirSync } from 'node:fs'
import { OUT, WS, api, browser, check, clickUntil, newBusiness } from './common.mjs'

const results = []
const shots = `${OUT}/phase_b/p2_kitchen`
mkdirSync(shots, { recursive: true })

const biz = await newBusiness({
  name: 'Shawarma Counter',
  type: 'restaurant',
  modules: ['offerings-catalog', 'orders', 'kitchen'],
})
const base = `/v1/platform/businesses/${biz.id}`
const loc = (await api(`${base}/locations`)).data.find((row) => row.is_primary).id
const wrap = (await api(`${base}/products`, {
  method: 'POST',
  body: {
    title: 'Chicken shawarma',
    offering_type: 'menu_item',
    status: 'active',
    price_amount: 180,
    option_groups: [{
      name: 'Sauce',
      required: true,
      max: 1,
      choices: [{ label: 'Garlic', price_delta: 0 }],
    }],
  },
})).data
const grill = (await api(`${base}/kitchen/stations`, {
  method: 'POST',
  body: { key: 'grill', name: 'Grill' },
})).data
await api(`${base}/kitchen/routes`, {
  method: 'PUT',
  body: { offering_id: wrap.id, station_ids: [grill.id] },
})
const order = (await api(`${base}/orders`, {
  method: 'POST',
  body: {
    location_id: loc,
    channel: 'workspace',
    internal_reference: 'Table 4',
    items: [{ offering_id: wrap.id, quantity: 1, options: { choices: { Sauce: ['Garlic'] } } }],
  },
})).data
await api(`${base}/orders/${order.id}/notes`, {
  method: 'POST',
  body: { body: 'Call 9876543210 if late' },
})
await api(`${base}/orders/${order.id}/status`, { method: 'POST', body: { status: 'accepted' } })

const python = process.platform === 'win32' ? '.venv/Scripts/python.exe' : '.venv/bin/python'
const pythonPath = ['apps/worker/src', 'python/testing', 'apps/api/src', process.env.PYTHONPATH]
  .filter(Boolean)
  .join(process.platform === 'win32' ? ';' : ':')
execFileSync(python, ['tools/acceptance/stack/worker_once.py', biz.id], {
  stdio: 'inherit',
  env: { ...process.env, PYTHONPATH: pythonPath },
})

const page = await browser()
try {
  await page.goto(`${WS}/kds/${biz.id}`)
  await page.waitFor('[data-testid=kds-column-new]')
  await page.waitFor('KOT-', { text: true })
  const card = await page.eval(`document.querySelector('[data-testid=kds-ticket]')?.innerText || ''`)
  check(card.includes('KOT-'), 'new column has the ticket', results)
  check(card.includes('Table 4'), 'table is on the card', results)
  check(card.includes('Chicken shawarma'), 'item is on the card', results)
  check(card.includes('Garlic'), 'modifier is on the card', results)
  check(!card.includes('180') && !card.includes('₹') && !card.includes('9876543210'), 'no price and no phone', results)
  await page.shot(`${shots}/01-new.png`)

  await clickUntil(page, 'Start', '[data-testid=kds-column-preparing] [data-testid=kds-ticket]')
  const preparing = await page.eval(`document.querySelector('[data-testid=kds-column-preparing] [data-testid=kds-ticket]')?.innerText || ''`)
  check(preparing.includes('KOT-'), 'start moves the ticket to preparing', results)
  check((await page.eval(`document.querySelector('[data-testid=kds-elapsed]')?.innerText || ''`)).length > 0, 'elapsed time is showing', results)
  await page.shot(`${shots}/02-preparing.png`)

  await clickUntil(page, 'Ready', '[data-testid=kds-column-ready] [data-testid=kds-ticket]')
  const ready = await page.eval(`document.querySelector('[data-testid=kds-column-ready] [data-testid=kds-ticket]')?.innerText || ''`)
  check(ready.includes('KOT-'), 'ready moves the ticket to the pass', results)
  await page.shot(`${shots}/03-ready.png`)

  await page.goto(`${WS}/b/${biz.id}`)
  await page.waitFor('Kitchen display', { text: true })
  const href = await page.eval(`[...document.querySelectorAll('a')].find(a => a.innerText.trim() === 'Kitchen display')?.getAttribute('href')`)
  check(href === `/kds/${biz.id}`, `nav opens the pass (${href})`, results)
} finally {
  await page.close().catch(() => undefined)
  console.log(JSON.stringify(results, null, 2))
}
