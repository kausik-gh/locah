// Workspace survey — the priority routes of the demo businesses, desktop and 390 px.
//
//   node tools/acceptance/workspace_survey.mjs <gymId> <restaurantId> <fieldServiceId> [out]
//
// For each route: loads, no error text, no horizontal scroll at 390 px, a
// screenshot. Read-only: it clicks nothing.

import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import { launch } from './cdp.mjs'

const WS = process.env.LOCAH_WORKSPACE || 'http://localhost:3101'
const [gym, restaurant, field] = process.argv.slice(2, 5)
const OUT = path.resolve(process.argv[5] || 'acceptance-out/survey')
mkdirSync(OUT, { recursive: true })
const session = JSON.parse(readFileSync(process.env.LOCAH_ACCEPT_SESSION || 'acceptance-out/session.json', 'utf8'))
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

const ROUTES = [
  [gym, '', 'home'], [gym, '/modules', 'modules'], [gym, '/website', 'website'], [gym, '/customers', 'customers'],
  [gym, '/bookings', 'bookings'], [gym, '/memberships', 'memberships'], [gym, '/payments', 'payments'],
  [gym, '/settings/automations', 'automations'], [gym, '/ai-employees', 'ai-employees'], [gym, '/insights', 'insights'],
  [gym, '/settings', 'settings'], [restaurant, '/orders', 'orders'], [restaurant, '/inventory', 'inventory'],
  [restaurant, '/kitchen', 'kitchen'], [restaurant, '/recipes', 'recipes'], [field, '/quotes', 'quotes'],
  [field, '/projects', 'projects'], [field, '/jobs', 'jobs'], [field, '/leads', 'leads'],
]
const BAD = /Application error|Unhandled Runtime Error|Internal Server Error|Something went wrong|API .* failed: 5\d\d/i

const rows = []
for (const [mobile, w, h] of [[false, 1440, 900], [true, 390, 844]]) {
  const page = await launch({ width: w, height: h, mobile })
  await page.cookie(session.cookie_name, session.cookie, WS)
  for (const [bid, route, key] of ROUTES) {
    await page.goto(`${WS}/b/${bid}${route}`)
    await sleep(2500)
    const text = String(await page.eval('document.body.innerText') || '')
    const overflow = mobile ? await page.eval('document.documentElement.scrollWidth > window.innerWidth + 1') : false
    const file = `${key}-${mobile ? 'm' : 'd'}.png`
    await page.shot(path.join(OUT, file))
    const bad = BAD.exec(text)?.[0] || ''
    rows.push({ key, route, mobile, bad, overflow, h1: (text.split('\n').find((l) => l.trim()) || '').slice(0, 60), file })
    console.log(`${mobile ? '390 ' : '1440'} ${key.padEnd(13)} ${bad ? 'ERROR ' + bad : 'ok'}${overflow ? ' OVERFLOW' : ''}`)
  }
  await page.close()
}
writeFileSync(path.join(OUT, 'survey.json'), JSON.stringify(rows, null, 2))
