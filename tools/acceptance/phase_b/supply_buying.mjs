// One owner buying flow on the local stack. Desktop only.
// Launches the machine's Chrome through playwright-core so Claude's pw.mjs
// launcher, which expects a preinstalled Playwright browser, stays untouched.
import { createRequire } from 'node:module'
import { existsSync, readFileSync } from 'node:fs'
import { recorder, API } from './pw.mjs'

const chromeCandidates = [
  process.env.LOCAH_CHROME,
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
].filter(Boolean)
const executablePath = chromeCandidates.find((file) => existsSync(file))
if (!executablePath) throw new Error('No local Chrome or Edge found for the buying flow')
const corePackage = process.env.LOCAH_PLAYWRIGHT_CORE
if (!corePackage) throw new Error('Set LOCAH_PLAYWRIGHT_CORE to a playwright-core package.json')
const { chromium } = createRequire(corePackage)('playwright-core')

async function openOwner(who) {
  const browser = await chromium.launch({
    headless: true,
    executablePath,
    args: ['--no-sandbox'],
  })
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } })
  await context.addCookies([{ name: who.cookie_name, value: who.cookie, url: 'http://localhost:3101' }])
  const page = await context.newPage()
  page.setDefaultTimeout(60000)
  const errors = []
  page.on('pageerror', (e) => errors.push(String(e)))
  page.on('response', (res) => {
    if (res.status() >= 400) errors.push(`${res.status()} ${res.url()}`)
  })
  page.realErrors = () => errors.filter((e) => !/\/json\/version|favicon\.ico|webpack-hmr|_next\/static\/webpack/.test(e))
  return { browser, page }
}

const session = JSON.parse(readFileSync(process.env.LOCAH_ACCEPT_SESSION, 'utf8'))
const token = session.token

async function api(path, body) {
  const res = await fetch(`${API}${path}`, {
    method: body ? 'POST' : 'GET',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })
  const text = await res.text()
  if (!res.ok) throw new Error(`${path} ${res.status} ${text.slice(0, 400)}`)
  return text ? JSON.parse(text) : {}
}

const rec = recorder('supply-buying')
const { browser, page } = await openOwner(session)
try {
  const business = await api('/v1/platform/businesses', {
    display_name: `Supply ${Date.now().toString().slice(-6)}`,
    business_type: 'other',
  })
  const id = business.data.business.id
  const locationId = business.data.business.primary_location.id
  for (const module of ['offerings-catalog', 'inventory', 'procurement', 'expenses', 'donations']) {
    await api(`/v1/b/${id}/modules/${module}/enable`, {})
  }
  const product = await api(`/v1/platform/businesses/${id}/products`, {
    title: 'Rice', status: 'active', offering_type: 'product', track_inventory: true, price_amount: 5000,
  })
  await api(`/v1/platform/businesses/${id}/inventory/opening-stock`, {
    offering_id: product.data.id, location_id: locationId, quantity: 70,
  })

  await page.goto(`http://localhost:3101/b/${id}/buying`, { waitUntil: 'networkidle' })
  rec.check(page.url().includes('/buying'), 'buying route opened')
  await rec.shot(page, '01-buying.png')

  await page.getByLabel('Name').fill('Upstream mill')
  await page.getByRole('button', { name: 'Save supplier' }).click()
  await page.locator('select[name="supplier_id"] option', { hasText: 'Upstream mill' }).waitFor({ state: 'attached' })
  await rec.shot(page, '02-supplier.png')

  await page.getByLabel('Required demand').fill('100')
  await page.getByRole('button', { name: 'Calculate requirement' }).click()
  await page.getByText('so buy 30').waitFor()
  const why = await page.getByText('Required 100').innerText()
  rec.check(why.includes('Usable 70') && why.includes('Net 30'), `explanation shows the arithmetic: ${why}`)
  await rec.shot(page, '03-requirement.png')

  await page.getByRole('button', { name: 'Approve and send' }).click()
  await page.getByRole('button', { name: 'Record receipt' }).waitFor()
  await rec.shot(page, '04-approved.png')

  await page.getByLabel('Good quantity').fill('10')
  await page.getByLabel('Damaged').fill('2')
  await page.getByRole('button', { name: 'Record receipt' }).click()
  await page.getByText('received so far 10').waitFor()
  rec.check(true, 'partial receipt is visible and a purchase order alone did not skip the receipt step')
  await rec.shot(page, '05-received.png')

  await page.goto(`http://localhost:3101/b/${id}/expenses`, { waitUntil: 'networkidle' })
  rec.check(await page.getByRole('heading', { name: 'Expenses' }).count(), 'expenses route rendered')
  await rec.shot(page, '06-expenses.png')

  await page.goto(`http://localhost:3101/b/${id}/donations`, { waitUntil: 'networkidle' })
  rec.check(await page.getByRole('heading', { name: 'Donations' }).count(), 'donations route rendered')
  await rec.shot(page, '07-donations.png')

  const errors = page.realErrors()
  rec.check(errors.length === 0, errors.length ? `page errors: ${errors.join(' | ')}` : 'no page errors')
} catch (error) {
  await rec.shot(page, 'failure.png').catch(() => {})
  rec.check(false, error instanceof Error ? error.message : String(error))
} finally {
  rec.finish()
  await browser.close()
}
