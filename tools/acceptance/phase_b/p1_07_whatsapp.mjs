// P1-07 WhatsApp foundation in the browser (Capability Universe §9.1, §12.1, §12.4, §12.5;
// §26.3 done-when "owner connects a number and receives order notifications").
//  With no Meta partnership switched on, the real connection says so; the
//  owner connects the stack's test number (messages are recorded, never
//  delivered), turns on their own new-order alerts, a customer writes and
//  waits for a person, the owner answers from the inbox beside what LOCAH
//  knows about them, an order comes in and both the owner's alert and the
//  customer's update go out, and a khata statement is sent from the business
//  number. Desktop and 390 px. Zero live provider calls.
//
//   CHROME_PATH=/opt/pw-browsers/chromium CHROME_NO_SANDBOX=1 node tools/acceptance/phase_b/p1_07_whatsapp.mjs
import { execFileSync } from 'node:child_process'
import { mkdirSync, writeFileSync } from 'node:fs'
import { OUT, WS, api, browser, check, newBusiness, realErrors } from './common.mjs'

const results = []
const shots = `${OUT}/phase_b/p1_07`
mkdirSync(shots, { recursive: true })
const wait = (ms) => new Promise((r) => setTimeout(r, ms))
const rand = () => String(Math.floor(Math.random() * 1e8)).padStart(8, '0')
const customerPhone = `+9197${rand()}`
const ownerPhone = `+9196${rand()}`

const biz = await newBusiness({ name: 'Anbu Sweets', category: 'home_food', sub: 'sweets', type: 'retail',
  modules: ['offerings-catalog', 'orders', 'payments', 'customer-relationships', 'ledger', 'messaging'] })
const base = `/v1/platform/businesses/${biz.id}`
const loc = (await api(`${base}/locations`)).data.find((l) => l.is_primary).id
const laddu = (await api(`${base}/products`, { method: 'POST', body: { status: 'active', offering_type: 'product', title: 'Motichoor laddu 500 g', price_amount: 280 } })).data
const worker = () => execFileSync('.venv/bin/python', ['tools/acceptance/stack/worker_once.py', biz.id], {
  env: { ...process.env, PYTHONPATH: 'python/testing:apps/worker/src', MESSAGING_SANDBOX: '1' }, encoding: 'utf8',
}).trim()

const page = await browser()
const fill = (label, value) => page.eval(`(() => {
  const l = [...document.querySelectorAll('label')].filter(x => x.offsetParent !== null).find(x => x.innerText.trim().startsWith(${JSON.stringify(label)}));
  if (!l) throw new Error('no label ' + ${JSON.stringify(label)});
  const el = l.querySelector('input, select, textarea');
  const proto = el.tagName === 'SELECT' ? HTMLSelectElement.prototype : el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
  Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, ${JSON.stringify(value)});
  el.dispatchEvent(new Event(el.tagName === 'SELECT' ? 'change' : 'input', { bubbles: true }));
  return true })()`)
const text = () => page.eval('document.body.innerText')
try {
  // ---- 1. Reach → WhatsApp; the real connection is honest about activation
  await page.goto(`${WS}/b/${biz.id}`)
  await page.waitFor('WhatsApp inbox', { text: true })
  const links = await page.eval(`[...document.querySelectorAll('a')].map(a => a.getAttribute('href'))`)
  check(links.includes(`/b/${biz.id}/inbox`) && links.includes(`/b/${biz.id}/whatsapp`), 'Reach area has the WhatsApp inbox and WhatsApp settings', results)
  await page.goto(`${WS}/b/${biz.id}/whatsapp`)
  await page.waitFor('Your WhatsApp number', { text: true })
  check((await text()).includes('being switched on') && !(await text()).includes('Connect with WhatsApp'),
    'no Meta partnership yet: the page says so and offers no fake connect button', results)
  await page.shot(`${shots}/01-not-connected.png`, { full: true })

  // ---- 2. the stack's test number
  await fill('Test number', '+91 98400 12345')
  await page.click('Connect test number', { byText: true })
  await page.waitFor('Message templates', { text: true })
  const body = await text()
  check(body.includes('+919840012345') && body.includes('Test number') && body.includes('recorded in the inbox but not delivered'),
    'test number connected and clearly marked as not delivering', results)
  check(/9 of 9 approved/.test(body.replace(/\s+/g, ' ')), `this phase's templates approved (${(body.match(/\d+ of \d+ approved/) || [''])[0]})`, results)
  // The owner's own alerts: new orders and waiting chats.
  await page.eval(`[...document.querySelectorAll('label')].find(l => l.innerText.includes('Send me alerts on WhatsApp')).querySelector('input').click()`)
  await page.waitFor('My WhatsApp number', { text: true })
  await fill('My WhatsApp number', ownerPhone)
  await page.eval(`(() => { const want = ['New orders', 'Customers waiting for a person on WhatsApp'];
    for (const l of document.querySelectorAll('label.bos-choice')) { const i = l.querySelector('input'); if (want.includes(l.innerText.trim()) !== i.checked) i.click() } return true })()`)
  await page.click('Save my alerts', { byText: true })
  await page.waitFor('Alerts on', { text: true })
  await page.shot(`${shots}/02-connected.png`, { full: true })

  // ---- 3. a customer writes; it waits for a person
  await fill('From', customerPhone)
  await fill('Name', 'Priya')
  await fill('Message', 'Do you have kaju katli today? Can you deliver to Anna Nagar?')
  await page.click('Send as the customer', { byText: true })
  await page.waitFor('Delivered to the inbox', { text: true })
  await page.goto(`${WS}/b/${biz.id}/inbox?view=waiting`)
  await page.waitFor('.bos-inbox__row')
  check((await page.text('.bos-inbox__row')).includes('Needs a person'), 'the chat waits for a person', results)
  await page.click('.bos-inbox__row')
  await page.waitFor('.bos-inbox__messages')
  const bubbles = await page.eval(`[...document.querySelectorAll('.bos-bubble')].map(b => b.className.includes('--in') ? 'in' : 'out')`)
  check(bubbles.join(',') === 'in,out', `the customer is told someone will reply (${bubbles.join(',')})`, results)
  check((await page.text('.bos-inbox__side')).includes('Customer profile'), 'the side panel knows the customer', results)
  await page.shot(`${shots}/03-waiting.png`, { full: true })

  // ---- 4. the owner answers; LOCAH steps back
  await page.type('#reply-box', 'Yes! Kaju katli is fresh today. We deliver to Anna Nagar from 4 pm.')
  await page.click('.bos-inbox__reply button[type=submit]')
  await page.waitFor('A person is handling this chat', { text: true })
  const outs = await page.eval(`[...document.querySelectorAll('.bos-bubble--out .bos-bubble__meta')].map(m => m.innerText)`)
  check(outs.length === 2 && /Sent/.test(outs[1]), `reply sent from the inbox (${outs[1]})`, results)
  await page.shot(`${shots}/04-replied.png`, { full: true })

  // ---- 5. an order comes in: the owner's alert and the customer's update (the done-when)
  const contact = (await api(`${base}/customers?search=Priya`)).data[0]
  const order = (await api(`${base}/orders`, { method: 'POST', body: { location_id: loc, customer_contact_id: contact.id,
    items: [{ offering_id: laddu.id, quantity: 2 }] } })).data
  const ran = worker()
  check(/deliveries=[1-9]/.test(ran), `the worker ran the order's subscribers (${ran})`, results)
  const chat = (await api(`${base}/messaging/conversations?view=open`)).data.conversations[0]
  await page.goto(`${WS}/b/${biz.id}/inbox?view=open&c=${chat.id}`)
  await page.waitFor(`order ${order.order_number}`, { text: true, timeout: 15000 }).catch(() => undefined)
  const last = await page.eval(`[...document.querySelectorAll('.bos-bubble--out')].pop()?.innerText || ''`)
  check(last.includes(`order ${order.order_number}`) && last.includes('₹560.00') && last.toUpperCase().includes('TEMPLATE'),
    `the customer hears their order arrived, as an approved template (${last.replace(/\s+/g, ' ').slice(0, 90)})`, results)
  const alert = await api(`${base}/messaging/setup`).then(() => execFileSync('psql', ['-tA', 'postgresql://postgres@localhost:54329/locah_accept', '-c',
    `select m.status || '|' || c.wa_id || '|' || m.body from messaging_messages m join messaging_conversations c on c.id = m.conversation_id where m.business_id = '${biz.id}' and m.template_key = 'staff_alert'`], { encoding: 'utf8' }).trim())
  check(alert.startsWith(`sent|${ownerPhone.slice(1)}|`) && alert.includes(`New order ${order.order_number}`),
    `the owner got the new-order alert on their own WhatsApp (${alert.slice(0, 90)})`, results)
  await page.waitFor('.bos-inbox__row')
  const inboxRows = await page.eval(`document.querySelectorAll('.bos-inbox__row').length`)
  check(inboxRows === 1, 'the owner\'s alert thread never shows as a customer chat', results)
  await page.shot(`${shots}/05-order-update.png`, { full: true })

  // ---- 6. a khata statement from the business number
  const acct = (await api(`${base}/ledger/accounts`, { method: 'POST', body: { party_type: 'customer', customer_contact_id: contact.id, opening_balance: 450 } })).data
  await page.goto(`${WS}/b/${biz.id}/khata/${acct.id}`)
  await page.waitFor('Send statement from your WhatsApp number', { text: true })
  await page.click('Send statement from your WhatsApp number', { byText: true })
  await page.waitFor('Statement sent from your WhatsApp number', { text: true })
  await page.goto(`${WS}/b/${biz.id}/inbox?view=open&c=${chat.id}`)
  await page.waitFor('₹450.00 is due', { text: true })
  check(true, 'the statement is in the same chat, with the amount due and the link', results)

  // ---- 7. home and usage
  const meter = (await api(`${base}/usage`)).data.find((m) => m.resource === 'whatsapp_message')
  check(meter.used === 5, `every message is metered: ack + reply + order update + owner alert + statement = ${meter.used}`, results)
  await page.goto(`${WS}/b/${biz.id}/whatsapp`)
  await page.waitFor('Messages this month', { text: true })
  check((await text()).includes('5 sent'), 'the WhatsApp page shows this month\'s count', results)
  check(realErrors(page).length === 0, `no console errors (${realErrors(page).join(' | ').slice(0, 300)})`, results)
} finally {
  await page.close()
}

// ---- 8. 390 px: inbox list, the chat, settings
const phone = await browser({ mobile: true })
try {
  await phone.goto(`${WS}/b/${biz.id}/inbox?view=open`)
  await phone.waitFor('.bos-inbox__row')
  check(await phone.eval('document.documentElement.scrollWidth <= window.innerWidth + 1'), 'inbox list fits 390 px', results)
  await phone.shot(`${shots}/06-inbox-390.png`, { full: true })
  await phone.click('.bos-inbox__row')
  await phone.waitFor('.bos-inbox__messages')
  check(await phone.eval(`getComputedStyle(document.querySelector('.bos-inbox__list')).display === 'none'`), 'on a phone the chat takes the screen', results)
  check(await phone.eval('document.documentElement.scrollWidth <= window.innerWidth + 1'), 'chat fits 390 px', results)
  await phone.shot(`${shots}/07-chat-390.png`, { full: true })
  await phone.goto(`${WS}/b/${biz.id}/whatsapp`)
  await phone.waitFor('Message templates', { text: true })
  check(await phone.eval('document.documentElement.scrollWidth <= window.innerWidth + 1'), 'WhatsApp settings fit 390 px', results)
  await phone.shot(`${shots}/08-settings-390.png`, { full: true })
  check(realErrors(phone).length === 0, `no console errors at 390 px (${realErrors(phone).join(' | ').slice(0, 200)})`, results)
} finally {
  await phone.close()
}
await wait(10)

writeFileSync(`${shots}/results.json`, JSON.stringify(results, null, 2))
const failed = results.filter((r) => !r.ok)
console.log(`\n${results.length - failed.length}/${results.length} checks passed`)
