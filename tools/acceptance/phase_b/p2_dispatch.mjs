// Dispatch — owner board and crew stops (Capability Universe §13).
//
// An owner opens Dispatch, sees an unassigned delivery, and assigns Anbu.
// Anbu opens My jobs: next stop, pickup, drop-off, the customer's number,
// and marks it picked up. Bala's job is not on Anbu's list.
//
//   node tools/acceptance/phase_b/p2_dispatch.mjs
import { execFileSync } from 'node:child_process'
import { WS, OUT, closeAll, fits, load, must, open, recorder, sql } from './pw.mjs'

const python = process.env.LOCAH_PYTHON || '.venv/Scripts/python.exe'
execFileSync(python, ['tools/acceptance/stack/owner.py', process.env.LOCAH_ACCEPT_DB || 'locah_dispatch', `${OUT}/dispatch-owner.json`], { stdio: 'inherit' })
execFileSync(python, ['tools/acceptance/stack/owner.py', process.env.LOCAH_ACCEPT_DB || 'locah_dispatch', `${OUT}/dispatch-crew.json`], { stdio: 'inherit' })

const { check, shot, finish } = recorder('p2_dispatch')
const owner = load(`${OUT}/dispatch-owner.json`)
const crew = load(`${OUT}/dispatch-crew.json`)
const as = must(owner.token)

const shop = (await as('/v1/platform/businesses', {
  method: 'POST',
  body: { display_name: 'Temple Street Stores', business_type: 'retail' },
})).data.business
const bid = shop.id
const base = `/v1/platform/businesses/${bid}`
for (const m of ['offerings-catalog', 'orders', 'inventory', 'payments', 'fulfilment', 'dispatch', 'workforce', 'customer-relationships']) {
  await as(`/v1/b/${bid}/modules/${m}/enable`, { method: 'POST' })
}
const locations = (await as(`${base}/locations`)).data
const loc = locations.find((row) => row.is_primary).id

async function parcel(name, phone) {
  const product = (await as(`${base}/products`, {
    method: 'POST',
    body: {
      title: `Parcel ${name}`,
      sku: `P-${phone.slice(-6)}`,
      track_inventory: true,
      status: 'active',
      price_amount: 50,
      tax_rate: 0,
    },
  })).data
  await as(`${base}/inventory/opening-stock`, {
    method: 'POST',
    body: { offering_id: product.id, location_id: loc, quantity: 5, reason: 'Test stock' },
  })
  const customer = (await as(`${base}/customers`, {
    method: 'POST',
    body: { display_name: name, phone },
  })).data
  const order = (await as(`${base}/orders`, {
    method: 'POST',
    body: {
      location_id: loc,
      customer_contact_id: customer.id,
      payment_method: 'cod',
      items: [{ offering_id: product.id, quantity: 1 }],
    },
  })).data
  return order.id
}

async function hire(person, name, role) {
  const invited = (await as(`/v1/b/${bid}/team/invitations`, {
    method: 'POST',
    body: { identity_id: person.user_id, role: 'member' },
  })).data
  await as(`/v1/b/${bid}/team/members/${invited.id}/activate`, { method: 'POST' })
  await as(`${base}/members/${invited.id}/role`, { method: 'PUT', body: { role } })
  const member = (await as(`${base}/workforce/members`, {
    method: 'POST',
    body: { display_name: name, identity_id: person.user_id, location_ids: [loc], primary_location_id: loc },
  })).data
  return member.id
}

const anbuId = await hire(crew, 'Anbu', 'delivery_partner')
const balaPerson = { user_id: null }
// Bala is staff on the books, with no login in this flow. A second identity
// keeps the workforce row real without opening a third browser.
execFileSync(python, ['tools/acceptance/stack/owner.py', process.env.LOCAH_ACCEPT_DB || 'locah_dispatch', `${OUT}/dispatch-bala.json`], { stdio: 'inherit' })
const bala = load(`${OUT}/dispatch-bala.json`)
balaPerson.user_id = bala.user_id
const balaId = await hire(balaPerson, 'Bala', 'delivery_partner')

const lakshmiOrder = await parcel('Lakshmi', '9840012121')
const meenaOrder = await parcel('Meena', '9840034343')
const lakshmi = (await as(`/v1/b/${bid}/dispatch/jobs`, {
  method: 'POST',
  body: { order_id: lakshmiOrder, kind: 'delivery', dropoff: { line: '12 Temple Street', city: 'Coimbatore' } },
})).data
const meena = (await as(`/v1/b/${bid}/dispatch/jobs`, {
  method: 'POST',
  body: { order_id: meenaOrder, kind: 'delivery', dropoff: { line: '4 Market Road', city: 'Erode' } },
})).data

const ownerCtx = await open({ who: owner })
const p = ownerCtx.page
p.setDefaultTimeout(60000)
try {
  await p.goto(`${WS}/b/${bid}/dispatch`)
  await p.getByRole('heading', { name: 'Dispatch', exact: true }).waitFor()
  await p.getByRole('heading', { name: 'Unassigned' }).waitFor()
  check(await p.getByRole('link', { name: lakshmi.order_number }).isVisible(), `unassigned job ${lakshmi.order_number} is on the board`)
  check(await p.getByText('Live location appears only when a device is sharing it.').isVisible(), 'the board does not pretend a live location exists')
  await shot(p, '01-owner-unassigned.png')

  await p.getByRole('link', { name: lakshmi.order_number }).click()
  await p.getByRole('heading', { name: lakshmi.order_number }).waitFor()
  await p.getByLabel('Assign crew').selectOption({ label: 'Anbu' })
  await p.getByRole('button', { name: 'Assign' }).click()
  await p.getByText('Anbu').waitFor()
  const assigned = sql(`select status || ':' || assigned_member_id from dispatch_jobs where id = '${lakshmi.id}'`)
  check(assigned === `assigned:${anbuId}`, `assign writes Anbu onto the job (${assigned})`)
  await shot(p, '02-owner-assigned.png')
} finally {
  await ownerCtx.context.close()
}

await as(`/v1/b/${bid}/dispatch/jobs/${meena.id}/assign`, { method: 'POST', body: { member_id: balaId } })

const crewCtx = await open({ who: crew })
const c = crewCtx.page
c.setDefaultTimeout(60000)
try {
  await c.goto(`${WS}/b/${bid}/crew`)
  await c.getByRole('heading', { name: 'My jobs', exact: true }).waitFor()
  await c.getByRole('heading', { name: `Next stop · ${lakshmi.order_number}` }).waitFor()
  const body = await c.locator('body').innerText()
  check(body.includes('12 Temple Street'), 'the drop-off address is on the stop')
  check(body.includes('Pickup:'), 'the pickup is on the stop')
  check(await c.getByRole('link', { name: '9840012121' }).isVisible(), 'the customer number is there while the job is active')
  check(!body.includes(meena.order_number), 'Bala’s job is not on Anbu’s list')
  await shot(c, '03-crew-next-stop.png')

  await c.getByRole('button', { name: 'Picked up' }).click()
  await c.getByRole('button', { name: 'Out for delivery' }).waitFor()
  const picked = sql(`select status from dispatch_jobs where id = '${lakshmi.id}'`)
  check(picked === 'picked_up', `picked up is the stored status (${picked})`)
  await shot(c, '04-crew-picked-up.png')

  await c.setViewportSize({ width: 390, height: 844 })
  await c.waitForTimeout(300)
  check(await fits(c), 'the crew list fits a 390 px screen')
  await shot(c, '05-crew-mobile.png')
} finally {
  await crewCtx.context.close()
}

finish()
await closeAll()
