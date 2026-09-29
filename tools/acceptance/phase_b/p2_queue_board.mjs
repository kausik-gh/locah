// Queue board: issue a walk-in, see them in Waiting, call next, see them in Called.
// Local stack only. node tools/acceptance/phase_b/p2_queue_board.mjs
import { WS, OUT, caller, closeAll, fits, load, must, open, recorder, sql } from './pw.mjs'

const { check, shot, finish } = recorder('p2_queue_board')
const owner = load(process.env.LOCAH_ACCEPT_OWNER || `${OUT}/owner2.json`)
const as = must(owner.token)

const shop = (await as('/v1/platform/businesses', { method: 'POST', body: {
  display_name: 'North Clinic Queue', business_type: 'clinic' } })).data.business
const bid = shop.id
for (const moduleId of ['workforce', 'bookings', 'queue-operations']) {
  await as(`/v1/b/${bid}/modules/${moduleId}/enable`, { method: 'POST' })
}
const locations = (await as(`/v1/platform/businesses/${bid}/locations`)).data
const locationId = locations.find((row) => row.is_primary).id

const ctx = await open({ who: owner })
const page = ctx.page
try {
  await page.goto(`${WS}/b/${bid}/queue`)
  await page.getByRole('heading', { name: 'Walk-in queue' }).waitFor()
  await page.getByLabel('Name').fill('Morning OPD')
  await page.getByRole('button', { name: 'Add queue' }).click()
  await page.getByRole('link', { name: /Morning OPD/ }).waitFor()
  check(sql(`select count(*) from queue_lanes where business_id = '${bid}'`) === '1', 'the lane is saved')
  await page.getByLabel('Walk-in name').fill('Lakshmi')
  await page.getByRole('button', { name: 'Issue token' }).click()
  await page.getByText('#1').waitFor()
  await page.getByText('Lakshmi').waitFor()
  check((await page.getByRole('region', { name: 'Waiting' }).innerText()).includes('Lakshmi'), 'Lakshmi is waiting')
  await shot(page, '01-waiting.png')
  await page.getByRole('button', { name: 'Call next' }).click()
  await page.getByRole('region', { name: 'Called' }).getByText('Lakshmi').waitFor()
  const status = sql(`select status from queue_entries where business_id = '${bid}'`)
  check(status === 'called', `the token is called (${status})`)
  await shot(page, '02-called.png')
  check(await fits(page), 'the board fits the desktop width')
  check(page.realErrors().length === 0, `no console errors (${page.realErrors().slice(0, 2).join(' | ')})`)
} finally {
  await ctx.context.close()
  await closeAll()
  finish()
}

void caller
