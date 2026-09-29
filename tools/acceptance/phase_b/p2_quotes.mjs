// Quotes — RFQ draft, a priced revision, the customer's acceptance, the lock,
// and the conversion contract (Capability Universe §19.4, §21.10).
//
// A website request becomes a draft. The merchant prices it, sends it, revises
// the price, and sends the new version. The customer opens that version, asks
// for a code, and accepts. The accepted prices are locked. Handing the quote
// to an order publishes the contract and does not create an order.
//
//   node tools/acceptance/phase_b/p2_quotes.mjs
import { API, DB, WEB, WS, caller, closeAll, load, must, open, recorder, sql } from './pw.mjs'

const { check, shot, finish } = recorder('p2_quotes')
const owner = load(process.env.LOCAH_ACCEPT_OWNER || 'acceptance-out/quotes-owner.json')
const as = must(owner.token)
const raw = caller(null)

const created = await as('/v1/platform/businesses', {
  method: 'POST',
  body: { display_name: 'Gate Works', business_type: 'other' },
})
const business = created.data.business
const bid = business.id
for (const module of ['quotes', 'leads', 'customer-relationships', 'offerings-catalog']) {
  await as(`/v1/b/${bid}/modules/${module}/enable`, { method: 'POST' })
}

const enquiry = await raw(`/v1/public/websites/${business.slug}/enquiries`, {
  method: 'POST',
  body: {
    name: 'Ravi',
    phone: '9840012345',
    message: 'Main gate, 12 ft',
    purpose: 'quote_request',
  },
})
check(enquiry.status === 200, `the website request is received (${enquiry.status})`)

const listed = await as(`/v1/platform/businesses/${bid}/quotes`)
const draft = listed.data.quotes[0]
check(draft && draft.source === 'website' && draft.status === 'draft', 'the request is a website draft quote')
const originalId = draft.id
const originalNumber = draft.quote_number

const ctx = await open({ who: owner })
const page = ctx.page
page.setDefaultTimeout(60000)
try {
  await page.goto(`${WS}/b/${bid}/quotes/${originalId}`)
  await page.getByRole('heading', { name: 'Edit this draft' }).waitFor()
  await page.getByLabel('Unit price').first().fill('45000')
  await page.getByRole('button', { name: 'Save draft' }).click()
  await page.getByRole('button', { name: 'Send quote' }).waitFor()
  await page.getByRole('button', { name: 'Send quote' }).click()
  await page.getByRole('heading', { name: 'Customer link' }).waitFor()
  const sentTotal = sql(`select total::text from quotes_quotes where id = '${originalId}'`)
  check(sentTotal === '45000.00', `the sent quote is priced at 45000 (${sentTotal})`)
  await shot(page, '01-quote-sent.png')

  await page.getByRole('button', { name: 'Revise as a new version' }).click()
  await page.getByRole('heading', { name: 'Edit this draft' }).waitFor()
  const revisionId = page.url().split('/quotes/')[1].split(/[?#]/)[0]
  check(revisionId && revisionId !== originalId, 'revision is a new quote')
  await page.getByLabel('Unit price').first().fill('42000')
  await page.getByRole('button', { name: 'Save draft' }).click()
  await page.getByRole('button', { name: 'Send quote' }).click()
  await page.getByRole('heading', { name: 'Customer link' }).waitFor()
  const revisionRow = sql(
    `select revision::text || ':' || status || ':' || total::text from quotes_quotes where id = '${revisionId}'`
  )
  const originalRow = sql(
    `select status || ':' || total::text from quotes_quotes where id = '${originalId}'`
  )
  check(revisionRow === '2:issued:42000.00', `revision 2 is the 42000 offer (${revisionRow})`)
  check(originalRow === `superseded:${sentTotal}`, `the first version is unchanged (${originalRow})`)
  await shot(page, '02-revision-sent.png')

  const token = sql(`select access_token from quotes_quotes where id = '${revisionId}'`)
  const customer = await ctx.context.newPage()
  await customer.goto(`${WEB}/q/${token}`)
  await customer.locator('input[name=name]').fill('Ravi')
  await customer.getByRole('button', { name: 'Send me a code' }).click()
  await customer.getByText('Enter the code we sent you').waitFor()
  const code = sql(
    `select payload->>'code' from platform_outbox_events where event_type = 'quote.acceptance_code_issued' and payload->>'quote_id' = '${revisionId}' order by created_at desc limit 1`
  )
  check(/^\d{6}$/.test(code), 'the acceptance code is issued for messaging, not shown on the page')
  check(!(await customer.content()).includes(code), 'the customer page does not contain the code')
  await customer.locator('input[name=code]').fill(code)
  await customer.getByRole('button', { name: 'Accept', exact: true }).click()
  await customer.getByText('prices on this version are locked').waitFor()
  const opens = sql(`select open_count::text from quotes_quotes where id = '${revisionId}'`)
  check(Number(opens) >= 1, `the customer opening is recorded (${opens})`)
  await shot(customer, '03-customer-accepted.png')
  await customer.close()

  await page.goto(`${WS}/b/${bid}/quotes/${revisionId}`)
  await page.getByText('Locked on the accepted version').waitFor()
  await page.getByRole('button', { name: 'Hand to order' }).click()
  await page.getByText('Handed to order.').waitFor()
  const handed = sql(
    `select status || ':' || conversion_target || ':' || (price_locked_at is not null) || ':' || coalesce(converted_to_id::text, '') || ':' || total::text from quotes_quotes where id = '${revisionId}'`
  )
  const orders = sql(`select count(*) from orders_orders where business_id = '${bid}'`)
  const projects = sql(`select count(*) from projects_projects where business_id = '${bid}'`)
  const invoices = sql(`select count(*) from invoicing_documents where business_id = '${bid}'`)
  const contract = sql(
    `select payload->>'contract' from platform_outbox_events where event_type = 'quote.conversion_requested' and payload->>'quote_id' = '${revisionId}'`
  )
  check(
    handed === 'accepted:order:true::42000.00',
    `the accepted version stays locked and is only marked for an order (${handed})`
  )
  check(contract === 'locah.quote.conversion.v1', `Orders receives the conversion contract (${contract})`)
  check(orders === '0' && projects === '0' && invoices === '0', 'no order, project, or invoice row was created')
  check(
    sql(`select quote_number from quotes_quotes where id = '${revisionId}'`) === originalNumber,
    'the revision keeps the original quote number'
  )
  await shot(page, '04-handed-to-order.png')
  check(page.realErrors().length === 0, `no page errors (${page.realErrors().slice(0, 3).join(' | ')})`)
} finally {
  await ctx.context.close()
  await closeAll()
  finish()
}

console.log(`database ${DB}`)
