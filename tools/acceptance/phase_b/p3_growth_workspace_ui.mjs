// Desktop Chrome walk of the loyalty desk and the marketing campaign builder.
// Local stack only. No Meta, WhatsApp, or other external calls.
import { readFileSync, mkdirSync } from 'node:fs'
import { createRequire } from 'node:module'
import path from 'node:path'

const require = createRequire(path.join(process.env.PW_ROOT, 'package.json'))
const { chromium } = require('playwright')

const WS = process.env.LOCAH_WORKSPACE || 'http://127.0.0.1:3101'
const session = JSON.parse(readFileSync(process.env.LOCAH_ACCEPT_SESSION, 'utf8'))
const businessId = process.env.GROWTH_BUSINESS_ID
const out = path.resolve('acceptance-out/phase_b/growth-ui')
mkdirSync(out, { recursive: true })

const checks = []
function check(cond, msg) {
  checks.push({ ok: !!cond, msg })
  console.log(`${cond ? 'PASS' : 'FAIL'}  ${msg}`)
}

const browser = await chromium.launch({
  // CHROME_PATH uses a browser already on the machine, as pw.mjs does.
  ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : { channel: 'chrome' }),
  headless: true,
  args: ['--no-sandbox'],
})
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } })
await context.addCookies([
  { name: session.cookie_name, value: session.cookie, url: WS },
])
const page = await context.newPage()
page.setDefaultTimeout(45000)
const errors = []
page.on('pageerror', (e) => errors.push(String(e)))

async function shot(name) {
  await page.screenshot({ path: path.join(out, name), fullPage: true })
}

try {
  await page.goto(`${WS}/b/${businessId}/loyalty`, { waitUntil: 'networkidle' })
  await shot('01-loyalty.png')
  check(page.url().includes('/loyalty'), `loyalty page loaded (${page.url()})`)
  check(await page.getByRole('heading', { name: 'Points programme' }).count(), 'programme editor is on the page')

  await page.getByRole('textbox', { name: 'Name', exact: true }).fill('Desk points')
  await page.getByRole('button', { name: 'Save programme' }).click()
  await page.waitForLoadState('networkidle')
  const savedName = await page.getByRole('textbox', { name: 'Name', exact: true }).inputValue()
  check(savedName === 'Desk points', `programme name saved as ${savedName}`)

  const earn = page.locator('form', { has: page.locator('button', { hasText: 'Earn' }) }).first()
  await earn.locator('input[name="amount_rupees"]').fill('200')
  await earn.getByRole('button', { name: 'Earn' }).click()
  await page.getByRole('cell', { name: '200', exact: true }).waitFor()
  check(true, 'earned 200 points shows on the customer balance')

  const redeem = page.locator('form', { has: page.locator('button', { hasText: 'Redeem' }) }).first()
  await redeem.locator('input[name="points"]').fill('10')
  await redeem.getByRole('button', { name: 'Redeem' }).click()
  await page.getByRole('cell', { name: '190', exact: true }).waitFor()
  check(true, 'redeemed 10 points, usable balance is 190')

  await page.getByPlaceholder('Card name, for example Coffee card').fill('Coffee card')
  await page.locator('input[name="reward_item"]').fill('Free coffee')
  await page.getByRole('button', { name: 'Add stamp card' }).click()
  await page.getByRole('cell', { name: 'Coffee card' }).waitFor()
  check(true, 'stamp card created')

  await page.locator('input[name="amount_rupees"]').last().fill('500')
  await page.getByRole('button', { name: 'Issue voucher' }).click()
  await page.getByRole('heading', { name: 'Issue a gift voucher' }).waitFor()
  check(errors.length === 0, `voucher form submitted without a page error (${errors.join('; ')})`)
  await shot('02-loyalty-done.png')

  await page.goto(`${WS}/b/${businessId}/marketing/offers`, { waitUntil: 'networkidle' })
  await page.locator('input[name="code"]').fill('DIWALI10')
  await page.getByPlaceholder('Name').fill('Diwali ten')
  await page.locator('input[name="discount_value"]').fill('10')
  await page.getByRole('button', { name: 'Create offer' }).click()
  await page.getByRole('cell', { name: 'DIWALI10' }).waitFor()
  check(true, 'offer DIWALI10 created')
  await shot('03-offer.png')

  await page.goto(`${WS}/b/${businessId}/marketing/new`, { waitUntil: 'networkidle' })
  await page.getByRole('textbox', { name: 'Name', exact: true }).fill('Tuesday regulars')
  await page.locator('input[name="goal"]').fill('Bring regulars back')
  await page.locator('input[name="budget_rupees"]').fill('1000')
  await page.getByRole('button', { name: 'Create draft' }).click()
  await page.waitForURL(/\/marketing\/[0-9a-f-]{36}$/)
  check(true, `campaign builder opened (${page.url()})`)

  const audience = page.locator('select[name="audience_segment_id"]')
  const audienceValue = await audience.locator('option', { hasText: 'Regulars' }).getAttribute('value')
  await audience.selectOption(audienceValue)
  const offer = page.locator('select[name="offer_id"]')
  const offerValue = await offer.locator('option', { hasText: 'DIWALI10' }).getAttribute('value')
  await offer.selectOption(offerValue)
  await page.locator('textarea[name="creative"]').fill('Tuesday is quieter. Your usual order is on us to start.')
  await page.getByRole('button', { name: 'Save draft' }).click()
  await page.waitForLoadState('networkidle')
  const selectedAudience = await page.locator('select[name="audience_segment_id"]').inputValue()
  check(selectedAudience === audienceValue, 'audience and offer saved on the draft')

  await page.getByRole('button', { name: 'Count audience and submit for approval' }).click()
  const consentLine = page.getByText('1 with marketing consent')
  await consentLine.waitFor()
  check(true, await consentLine.innerText())

  await page.getByRole('button', { name: 'Approve' }).click()
  await page.getByText('APPROVED').waitFor()
  check(true, 'owner approval recorded')

  await page.getByRole('button', { name: 'Record fixture send' }).click()
  await page.getByText(/Sent 1/).waitFor()
  const results = await page.getByRole('heading', { name: 'Results' }).locator('xpath=..').innerText()
  check(/Sent 1/.test(results), 'fixture dispatch sent 1')
  check(/Approximate/.test(results), `attribution label present: ${results.split('\n').slice(-1)[0]}`)
  await shot('04-campaign-results.png')
} catch (err) {
  check(false, String(err).slice(0, 500))
  try {
    await shot('failed.png')
  } catch {
    // page may already be closed
  }
} finally {
  console.log('PAGE', page.url())
  console.log('ERRORS', errors.join(' | ') || 'none')
  await browser.close()
}

const failed = checks.filter((row) => !row.ok)
if (failed.length) process.exitCode = 1
