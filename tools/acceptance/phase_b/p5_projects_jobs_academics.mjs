// Representative browser paths for Projects, Job cards and Academics.
// Local mock auth, local API, local Workspace, disposable Postgres only.
import { execFileSync } from 'node:child_process'
import crypto from 'node:crypto'
import { mkdirSync } from 'node:fs'
import { createRequire } from 'node:module'

// Playwright from tools/acceptance/node_modules, or from LOCAH_PW_DIR (a folder with its own install).
const require = createRequire(process.env.LOCAH_PW_DIR ? `${process.env.LOCAH_PW_DIR}/package.json` : import.meta.url)
const { chromium } = require('playwright-core')

const API = process.env.LOCAH_API || 'http://127.0.0.1:8010'
const WS = process.env.LOCAH_WORKSPACE || 'http://127.0.0.1:3101'
const SECRET = 'local-acceptance-secret-with-at-least-32-characters'
const PSQL = process.env.PSQL || 'psql'
// A browser already on the machine; without it, Playwright's own Chromium.
const CHROME = process.env.CHROME_PATH || undefined
const OUT = 'acceptance-out/p5'
const results = []

function check(ok, msg) {
  results.push({ ok: !!ok, msg })
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${msg}`)
  if (!ok) process.exitCode = 1
}

function b64url(value) {
  return Buffer.from(value).toString('base64url')
}

function mintToken(id, email) {
  const exp = Math.floor(Date.now() / 1000) + 12 * 3600
  const head = b64url(JSON.stringify({ alg: 'HS256', typ: 'JWT' }))
  const body = b64url(JSON.stringify({
    sub: id, email, aud: 'authenticated', role: 'authenticated', exp,
  }))
  const sig = crypto.createHmac('sha256', SECRET).update(`${head}.${body}`).digest('base64url')
  return { token: `${head}.${body}.${sig}`, exp }
}

function cookieFor(id, email) {
  const { token, exp } = mintToken(id, email)
  const session = {
    access_token: token, token_type: 'bearer', expires_in: 43200, expires_at: exp,
    refresh_token: 'local-refresh',
    user: {
      id, aud: 'authenticated', role: 'authenticated', email,
      app_metadata: { provider: 'email' }, user_metadata: {},
    },
  }
  const cookie = `base64-${Buffer.from(JSON.stringify(session)).toString('base64url')}`
  return { token, cookie }
}

function createIdentity(email) {
  const id = crypto.randomUUID()
  execFileSync(PSQL, [
    '-h', '127.0.0.1', '-p', process.env.PGPORT || '54330', '-U', 'postgres', '-d', process.env.LOCAH_ACCEPT_DB || 'locah_p5_replay',
    '-v', 'ON_ERROR_STOP=1', '-c',
    `insert into auth.users (id, instance_id, aud, role, email, encrypted_password, email_confirmed_at, created_at, updated_at)
     values ('${id}', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', '${email}', '', now(), now(), now())`,
  ], { stdio: 'pipe' })
  return id
}

async function api(token, path, { method = 'GET', body } = {}) {
  const res = await fetch(`${API}${path}`, {
    method,
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  const text = await res.text()
  let data
  try { data = JSON.parse(text) } catch { data = text }
  if (!res.ok) throw new Error(`${method} ${path} -> ${res.status} ${text.slice(0, 400)}`)
  return data
}

function realErrors(messages) {
  return messages.filter((line) => !/\/json\/version/.test(line)
    && !/Failed to fetch RSC payload/.test(line)
    && !/Failed to load resource: the server responded with a status of 404/.test(line)
    && !/Extra attributes from the server/.test(line))
}

async function shot(page, name) {
  mkdirSync(OUT, { recursive: true })
  await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true })
}

const ownerEmail = `p5-owner-${Date.now()}@locah.test`
const guardianEmail = `p5-guardian-${Date.now()}@locah.test`
const ownerId = createIdentity(ownerEmail)
const guardianId = createIdentity(guardianEmail)
const owner = cookieFor(ownerId, ownerEmail)
const guardian = cookieFor(guardianId, guardianEmail)

const business = await api(owner.token, '/v1/platform/businesses', {
  method: 'POST',
  body: {
    display_name: 'P5 Field and Class',
    business_type: 'professional_service',
    category_key: 'home_services',
    subcategory_key: 'appliance_repair',
  },
})
const bid = business.data.business.id
for (const moduleId of [
  'projects', 'jobs', 'academics', 'inventory', 'offerings-catalog',
  'customer-relationships', 'workforce',
]) {
  await api(owner.token, `/v1/b/${bid}/modules/${moduleId}/enable`, { method: 'POST' })
}
const locations = await api(owner.token, `/v1/platform/businesses/${bid}/locations`)
const loc = locations.data[0].id
const customer = await api(owner.token, `/v1/platform/businesses/${bid}/customers`, {
  method: 'POST',
  body: { display_name: 'Ravi site', phone: '9790001111' },
})
const asha = await api(owner.token, `/v1/platform/businesses/${bid}/customers`, {
  method: 'POST',
  body: { display_name: 'Asha', phone: '9790002222' },
})
const parent = await api(owner.token, `/v1/platform/businesses/${bid}/customers`, {
  method: 'POST',
  body: { display_name: "Asha's parent", phone: '9790003333', identity_id: guardianId },
})
const bharat = await api(owner.token, `/v1/platform/businesses/${bid}/customers`, {
  method: 'POST',
  body: { display_name: 'Bharat', phone: '9790004444' },
})
const member = await api(owner.token, `/v1/platform/businesses/${bid}/workforce/members`, {
  method: 'POST',
  body: { display_name: 'Arun', location_ids: [loc], primary_location_id: loc },
})
const product = await api(owner.token, `/v1/platform/businesses/${bid}/products`, {
  method: 'POST',
  body: {
    title: 'Shutter bolt', status: 'active', offering_type: 'product',
    track_inventory: true, price_amount: 120,
  },
})
const opening = await api(owner.token, `/v1/platform/businesses/${bid}/inventory/opening-stock`, {
  method: 'POST',
  body: { offering_id: product.data.id, location_id: loc, quantity: 20 },
})
const recordId = opening.data.id

const browser = await chromium.launch({
  executablePath: CHROME, headless: true,
  args: ['--disable-dev-shm-usage'],
})
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } })
const consoleErrors = []
const page = await context.newPage()
page.setDefaultTimeout(120000)
page.setDefaultNavigationTimeout(120000)
page.on('console', (msg) => {
  if (msg.type() === 'error') consoleErrors.push(msg.text())
})
page.on('pageerror', (err) => consoleErrors.push(String(err)))
await context.addCookies([{
  name: 'sb-127-auth-token', value: owner.cookie, url: WS, httpOnly: false, sameSite: 'Lax',
}])

try {
  await page.goto(`${WS}/b/${bid}/projects/new`, { waitUntil: 'domcontentloaded' })
  await page.getByRole('heading', { name: 'New project' }).waitFor()
  await page.getByLabel('What is this project for').fill('Shop refit')
  await page.locator('select[name="customer_contact_id"]').selectOption({ label: 'Ravi site' })
  await page.getByRole('button', { name: 'Create project' }).click()
  await page.waitForURL(/\/projects\/[0-9a-f-]{36}$/)
  check(page.url().includes('/projects/'), 'project page opened after create')

  await page.getByPlaceholder('Add a stage').fill('Payment milestone')
  await page.getByRole('checkbox', { name: 'Milestone' }).check()
  await page.getByRole('button', { name: 'Add stage' }).click()
  await page.getByText('Payment milestone').first().waitFor()
  check(await page.getByText('Milestone').first().isVisible(), 'milestone is visible on the project')

  await page.getByLabel('Work for this project').fill('Fit the shutter')
  await page.getByLabel('What needs doing').fill('Shutter will not lock')
  await page.getByRole('button', { name: 'Start a job card' }).click()
  await page.waitForURL(/\/jobs\/[0-9a-f-]{36}$/)
  check(await page.getByText('Fit the shutter').first().isVisible(), 'job card opened from the project')

  await page.getByLabel('Assign a person').selectOption({ label: 'Arun' })
  await page.getByRole('button', { name: 'Assign job' }).click()
  await page.getByText('Arun').first().waitFor()
  await page.getByLabel('Move to').selectOption('in_progress')
  await page.getByLabel('Work performed').fill('Removed the old lock')
  await page.getByRole('button', { name: 'Update job' }).click()
  await page.getByText('Work under way').first().waitFor()

  const stockSelect = page.locator('select[name="inventory_record_id"]')
  const stockValue = await stockSelect.locator('option', { hasText: 'Shutter bolt' }).getAttribute('value')
  await stockSelect.selectOption(stockValue)
  await page.getByLabel('Quantity in stock units').fill('3')
  await page.getByRole('button', { name: 'Record part used' }).click()
  await page.getByText(/Shutter bolt/).first().waitFor()
  const stock = await api(owner.token, `/v1/platform/businesses/${bid}/stock`)
  const line = stock.data.items.find((item) => item.id === recordId)
  check(Number(line.quantity_available) === 17, `stock moved 20 to 17 after one consumption (now ${line.quantity_available})`)

  await page.getByLabel('Move to').selectOption('quality_check')
  await page.getByLabel('Work performed').fill('Removed the old lock and fitted the bolt')
  await page.getByRole('button', { name: 'Update job' }).click()
  await page.getByText('Quality check').first().waitFor()
  await page.getByLabel('Move to').selectOption('completed')
  await page.getByLabel('Work performed').fill('Removed the old lock and fitted the bolt')
  await page.getByLabel('Completion note').fill('Shutter locks')
  await page.getByRole('button', { name: 'Update job' }).click()
  await page.getByText('This job is closed').waitFor()
  const after = await api(owner.token, `/v1/platform/businesses/${bid}/stock`)
  const afterLine = after.data.items.find((item) => item.id === recordId)
  check(Number(afterLine.quantity_available) === 17, `completing the job did not consume stock again (still ${afterLine.quantity_available})`)

  const projectId = (await api(owner.token, `/v1/b/${bid}/jobs`)).data.find((row) => row.title === 'Fit the shutter').project_id
  await page.goto(`${WS}/b/${bid}/projects/${projectId}`, { waitUntil: 'domcontentloaded' })
  check(await page.getByText('Fit the shutter').first().isVisible(), 'project lists the related job card')
  const job = (await api(owner.token, `/v1/b/${bid}/jobs`)).data.find((row) => row.title === 'Fit the shutter')
  await page.goto(`${WS}/b/${bid}/jobs/${job.id}`, { waitUntil: 'domcontentloaded' })
  check(await page.getByRole('link', { name: 'Open project' }).isVisible(), 'job card links back to the project')

  await page.goto(`${WS}/b/${bid}/academics`, { waitUntil: 'domcontentloaded' })
  await page.getByRole('heading', { name: 'Courses & batches' }).waitFor()
  await page.getByRole('textbox', { name: 'Name', exact: true }).fill('Foundation Mathematics')
  await page.getByRole('button', { name: 'Add course' }).click()
  await page.getByRole('option', { name: 'Foundation Mathematics' }).waitFor({ state: 'attached' })
  await page.getByLabel('Course').selectOption({ label: 'Foundation Mathematics' })
  await page.getByLabel('Batch name').fill('Morning 2026')
  await page.getByLabel('Teacher').selectOption({ label: 'Arun' })
  await page.getByRole('button', { name: 'Create batch' }).click()
  await page.getByRole('heading', { name: 'Morning 2026' }).waitFor()
  await page.locator('select[name="student_contact_id"]').selectOption({ label: 'Asha' })
  await page.locator('select[name="guardian_contact_id"]').selectOption({ label: "Asha's parent" })
  await page.getByRole('checkbox', { name: /under 18/ }).check()
  await page.getByRole('button', { name: 'Enrol in batch' }).click()
  await page.getByText('Asha').first().waitFor()
  await page.getByRole('checkbox', { name: /under 18/ }).uncheck()
  await page.locator('select[name="student_contact_id"]').selectOption({ label: 'Bharat' })
  await page.getByRole('button', { name: 'Enrol in batch' }).click()
  await page.getByText('Bharat').first().waitFor()

  const start = '2026-10-02T10:00'
  const end = '2026-10-02T11:00'
  await page.getByLabel('Starts (IST)').fill(start)
  await page.getByLabel('Ends (IST)').fill(end)
  await page.getByLabel('Topic').fill('Quadratic equations')
  await page.getByRole('button', { name: 'Schedule class' }).click()
  await page.getByText('Quadratic equations').first().waitFor()
  await page.getByLabel('Assessment').fill('September check')
  await page.getByLabel('Maximum marks').fill('20')
  await page.getByRole('button', { name: 'Add assessment' }).click()
  await page.getByText('September check').first().waitFor()
  const testSelect = page.locator('select[name="assessmentId"]')
  const testValue = await testSelect.locator('option', { hasText: 'September check' }).getAttribute('value')
  await testSelect.selectOption(testValue)
  await page.locator('form').filter({ hasText: 'Save result' }).getByLabel('Student').selectOption({ label: 'Asha' })
  await page.getByRole('spinbutton', { name: 'Marks', exact: true }).fill('16')
  await page.getByLabel('Teacher note').fill('Steady')
  await page.getByRole('button', { name: 'Save result' }).click()
  await page.getByText('September check').first().waitFor()
  check(true, 'course, batch, both students, class and result form submitted')
  await shot(page, 'batch')

  const guardianContext = await browser.newContext({ viewport: { width: 390, height: 844 } })
  const guardianPage = await guardianContext.newPage()
  guardianPage.setDefaultTimeout(120000)
  guardianPage.setDefaultNavigationTimeout(120000)
  const guardianErrors = []
  guardianPage.on('console', (msg) => {
    if (msg.type() === 'error') guardianErrors.push(msg.text())
  })
  await guardianContext.addCookies([{
    name: 'sb-127-auth-token', value: guardian.cookie, url: WS, httpOnly: false, sameSite: 'Lax',
  }])
  await guardianPage.goto(`${WS}/my/academics/${bid}`, { waitUntil: 'domcontentloaded' })
  await guardianPage.getByRole('heading', { name: 'Asha' }).waitFor()
  const portal = await guardianPage.locator('main').innerText()
  check(portal.includes('Asha') && portal.includes('Foundation Mathematics'), 'guardian sees their own student and course')
  check(portal.includes('16') && portal.includes('September check'), 'guardian sees the published result')
  check(!portal.includes('Bharat'), 'guardian does not see the other student')
  await shot(guardianPage, 'guardian-390')
  await guardianContext.close()

  const errors = realErrors([...consoleErrors, ...guardianErrors])
  check(errors.length === 0, errors.length ? `console errors: ${errors.slice(0, 3).join(' | ')}` : 'no app console errors')
  await shot(page, 'job-closed')
} catch (err) {
  check(false, err instanceof Error ? err.message : String(err))
  await shot(page, 'failure').catch(() => undefined)
} finally {
  await browser.close()
}

console.log(JSON.stringify({ business_id: bid, passed: results.filter((r) => r.ok).length, failed: results.filter((r) => !r.ok).length, results }, null, 2))
if (process.exitCode) process.exit(process.exitCode)
