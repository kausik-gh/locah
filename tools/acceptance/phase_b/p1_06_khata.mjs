// P1-06 khata / credit book in the browser (Capability Universe §6.2 `ledger`, §14.5, §23 #3).
//  The owner opens a customer's khata carried over from the notebook with a
//  limit; bills them on credit from the Workspace; at the counter a sale goes
//  on khata, and a sale over the limit needs a manager's PIN; the customer
//  pays off khata at the counter in cash (it lands in the drawer); money
//  received in the Workspace settles the oldest bills first; the statement
//  link opens on the business's own website with a UPI link and QR; a supplier
//  account records a purchase on credit. Desktop and 390 px.
//
//   CHROME_PATH=/opt/pw-browsers/chromium CHROME_NO_SANDBOX=1 node tools/acceptance/phase_b/p1_06_khata.mjs
import { mkdirSync, writeFileSync } from 'node:fs'
import { OUT, WS, api, browser, check, newBusiness, realErrors } from './common.mjs'

const results = []
const shots = `${OUT}/phase_b/p1_06`
mkdirSync(shots, { recursive: true })
const wait = (ms) => new Promise((r) => setTimeout(r, ms))
const C = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
function gstin(state, pan) {
  const body = `${state}${pan}1Z`
  let t = 0
  for (let i = 0; i < 14; i++) { const v = C.indexOf(body[i]) * (i % 2 ? 2 : 1); t += Math.floor(v / 36) + (v % 36) }
  return body + C[(36 - (t % 36)) % 36]
}
const tag = Math.random().toString(36).slice(2, 6).toUpperCase()
const phoneNo = `+9198${String(Math.floor(Math.random() * 1e8)).padStart(8, '0')}`
const rupeeNum = (s) => Number(String(s).replace(/[^\d.-]/g, ''))

const biz = await newBusiness({ name: 'Selvam Hardware', category: 'retail', sub: 'hardware', type: 'retail',
  modules: ['offerings-catalog', 'orders', 'payments', 'inventory', 'customer-relationships', 'invoicing', 'pos', 'ledger'] })
const base = `/v1/platform/businesses/${biz.id}`
await api(`${base}/invoicing/profile`, { method: 'PUT', body: { prices_include_tax: true, round_off: true, issue_on: 'manual' } })
const reg = (await api(`${base}/invoicing/registrations`, { method: 'POST', body: { scheme: 'regular', legal_name: 'Selvam Hardware', gstin: gstin('33', `AA${tag}S1234K`.slice(0, 10)) } })).data
const loc = (await api(`${base}/locations`)).data.find((l) => l.is_primary).id
await api(`${base}/invoicing/registers`, { method: 'POST', body: { location_id: loc, registration_id: reg.id, code: 'SH1', name: 'Counter' } })
const item = async (body) => (await api(`${base}/products`, { method: 'POST', body: { status: 'active', offering_type: 'product', ...body } })).data
await item({ title: 'PVC pipe 3 m', price_amount: 250, hsn_sac: '3917', tax_rate: 18 })
await item({ title: 'Cement bag 50 kg', price_amount: 420, hsn_sac: '2523', tax_rate: 28 })
await api(`${base}/pos/settings`, { method: 'PUT', body: { upi_vpa: 'selvam@okbank', return_window_days: 7 } })
await api(`${base}/pos/pin`, { method: 'PUT', body: { pin: '4826' } })

const page = await browser()
const fill = (label, value) => page.eval(`(() => {
  const l = [...document.querySelectorAll('label')].filter(x => x.offsetParent !== null).find(x => x.innerText.trim().startsWith(${JSON.stringify(label)}));
  if (!l) throw new Error('no label ' + ${JSON.stringify(label)});
  const el = l.querySelector('input, select, textarea');
  const proto = el.tagName === 'SELECT' ? HTMLSelectElement.prototype : el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
  Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, ${JSON.stringify(value)});
  el.dispatchEvent(new Event(el.tagName === 'SELECT' ? 'change' : 'input', { bubbles: true }));
  return true })()`)
const toggle = (text) => page.eval(`(() => { const l = [...document.querySelectorAll('label')].find(x => x.innerText.includes(${JSON.stringify(text)})); l.querySelector('input').click(); return true })()`)
const tile = (title) => page.eval(`[...document.querySelectorAll('.pos-tile')].find(t => t.innerText.includes(${JSON.stringify(title)})).click()`)
const account = async () => (await api(`${base}/ledger/accounts?party=customer`)).data.accounts[0]
let acctId = ''
let statementUrl = ''
try {
  // ---- 1. Money → Khata, and opening a khata carried over from the notebook
  await page.goto(`${WS}/b/${biz.id}`)
  await page.waitFor('Khata (credit book)', { text: true })
  const href = await page.eval(`[...document.querySelectorAll('a')].find(a => a.innerText.trim() === 'Khata (credit book)')?.getAttribute('href')`)
  check(href === `/b/${biz.id}/khata`, `Money area has the khata (${href})`, results)
  await page.goto(`${WS}/b/${biz.id}/khata`)
  await page.waitFor('.bos-inv-summary')
  await page.shot(`${shots}/01-khata-empty.png`, { full: true })
  await page.click('Open an account', { byText: true })
  await page.waitFor('Already owes you', { text: true })
  await fill('Name', 'Selvi Constructions')
  await fill('Phone', phoneNo)
  await fill('Already owes you', '500')
  await fill('Credit limit', '3000')
  await fill('Days to pay', '15')
  await page.shot(`${shots}/02-open-account.png`)
  await page.click('Open account', { byText: true })
  await page.waitFor('How old is what they owe', { text: true })
  acctId = (await account()).id
  check((await page.eval('document.body.innerText')).includes('Owes you ₹500.00'), 'opened with ₹500 carried over from the notebook', results)

  // ---- 2. a Workspace bill on their khata
  await page.goto(`${WS}/b/${biz.id}/invoices/new`)
  await page.waitFor('From your customers', { text: true })
  const contact = (await account()).customer_contact_id
  await fill('From your customers', contact)
  await page.waitFor('Put this bill on their khata', { text: true })
  await toggle('Put this bill on their khata')
  await page.waitFor('limit ₹3,000.00', { text: true })
  await fill('Item', (await api(`${base}/products`)).data.find((p) => p.title === 'PVC pipe 3 m').id)
  await fill('Qty', '4')
  await page.shot(`${shots}/03-bill-on-khata.png`, { full: true })
  await page.click('Issue bill', { byText: true })
  await page.waitFor('On Khata', { text: true })
  const afterBill = await account()
  check(afterBill.balance === 1500, `bill of ₹1,000 on khata: balance ₹500 → ₹${afterBill.balance}`, results)
  await page.shot(`${shots}/04-bill-page.png`)

  // ---- 3. the counter: khata tender, then over the limit with a manager's PIN
  await page.goto(`${WS}/pos/${biz.id}`)
  await page.waitFor('Open the counter', { text: true })
  await page.type('.pos-form input[inputmode=decimal]', '1000')
  await page.click('Open shift', { byText: true })
  await page.waitFor('.pos-tile')
  await tile('Cement bag 50 kg')
  await tile('Cement bag 50 kg')
  await page.click('.pos-pay')
  await page.waitFor('Take cash', { text: true })
  await page.eval(`[...document.querySelectorAll('.pos-tabs button')].find(b => b.innerText === 'Khata').click()`)
  await page.waitFor('Check their khata', { text: true })
  await fill('Customer’s phone', phoneNo)
  await page.click('Check their khata', { byText: true })
  await page.waitFor('Selvi Constructions owes', { text: true })
  await page.shot(`${shots}/05-pos-khata.png`)
  await page.click('Put ₹840.00 on khata', { byText: true })
  await page.click('Complete sale', { byText: true })
  await page.waitFor('.pos-receipt-head')
  check((await page.text('.pos-receipt-head')).startsWith('On khata'), 'counter sale on khata: the receipt says so', results)
  await page.waitFor('Saved to LOCAH.', { text: true, timeout: 20000 })
  check((await account()).balance === 2340, `khata now ₹${(await account()).balance} (1500 + 840)`, results)
  await page.click('New sale', { byText: true })

  for (let i = 0; i < 2; i++) await tile('Cement bag 50 kg')
  await tile('PVC pipe 3 m')
  await page.click('.pos-pay')
  await page.waitFor('Take cash', { text: true })
  await page.eval(`[...document.querySelectorAll('.pos-tabs button')].find(b => b.innerText === 'Khata').click()`)
  await fill('Customer’s phone', phoneNo)
  await page.click('Check their khata', { byText: true })
  await page.waitFor('over their limit', { text: true })
  await page.shot(`${shots}/06-pos-over-limit.png`)
  await page.click('Over the limit — manager’s PIN', { byText: true })
  await page.waitFor('A manager approves credit above their khata limit', { text: true })
  await page.type('.pos-dialog input[type=password]', '4826')
  await page.click('Approve', { byText: true })
  await page.waitFor('Complete sale', { text: true })
  await page.click('Complete sale', { byText: true })
  await page.waitFor('Saved to LOCAH.', { text: true, timeout: 20000 })
  const over = await account()
  check(over.balance === 3430 && over.over_limit, `allowed over the limit with a PIN: ₹${over.balance}, over limit ${over.over_limit}`, results)
  await page.click('New sale', { byText: true })

  // ---- 4. khata paid off at the counter, into the drawer
  await page.click('Khata', { byText: true })
  await page.waitFor('Find their khata', { text: true })
  await fill('Customer’s phone', phoneNo)
  await page.click('Find their khata', { byText: true })
  await page.waitFor('Amount paid', { text: true })
  await fill('Amount paid', '1000')
  await page.shot(`${shots}/07-pos-khata-payment.png`)
  await page.click('Record payment', { byText: true })
  await page.waitFor('Khata payment ₹1,000.00', { text: true })
  for (let i = 0; i < 30 && (await page.eval(`!!document.querySelector('.pos-pill.is-wait')`)); i++) await wait(500)
  check((await account()).balance === 2430, `₹1,000 paid at the counter: khata ₹${(await account()).balance}`, results)
  await page.click('Close shift', { byText: true })
  await page.waitFor('Expected in the drawer', { text: true })
  const expected = await page.eval(`[...document.querySelectorAll('.pos-dialog dt')].find(d => d.innerText.startsWith('Expected'))?.nextElementSibling.innerText`)
  const khataLine = await page.eval(`[...document.querySelectorAll('.pos-dialog dt')].find(d => d.innerText === 'Khata')?.nextElementSibling.innerText || ''`)
  check(rupeeNum(expected) === 2000 && khataLine.includes('given'), `drawer expects opening + khata cash = ${expected}; khata line "${khataLine}"`, results)
  await page.shot(`${shots}/08-close-with-khata.png`, { full: true })
  await page.click('Back', { byText: true })

  // ---- 5. the account in the Workspace: ageing, entries, money received settles the oldest bill
  await page.goto(`${WS}/b/${biz.id}/khata/${acctId}`)
  await page.waitFor('Entries', { text: true })
  const kinds = await page.eval(`[...document.querySelectorAll('.bos-khata-table tbody td:nth-child(2) strong')].map(s => s.innerText)`)
  check(kinds.join('|') === 'Money received|Sold on credit|Sold on credit|Sold on credit|Opening balance', `entries newest first (${kinds.join(', ')})`, results)
  check(await page.eval(`!!document.querySelector('.bos-khata-age')`) && (await page.eval('document.body.innerText')).includes('Allowed over the limit'), 'ageing card and the over-limit approval are shown', results)
  await page.click('Record money received', { byText: true })
  await fill('Amount', '930')
  await fill('How', 'upi')
  await fill('Reference', 'UTR 55120')
  await page.click('Record', { byText: true })
  await page.waitFor('Recorded — the oldest bills are settled first', { text: true })
  // The counter's ₹1,000 already settled the Workspace bill; ₹930 settles the next oldest (₹840), then ₹90 of the last.
  const bills = (await api(`${base}/invoices?kind=invoices`)).data.filter((b) => b.source === 'pos').sort((a, b) => a.number.localeCompare(b.number))
  const states = bills.map((b) => `${b.number} ${b.payment_status} ${b.outstanding}`)
  check(bills[0].payment_status === 'paid' && bills[1].payment_status === 'part_paid' && bills[1].outstanding === 1000,
    `money received settles the oldest khata bills first (${states.join('; ')})`, results)
  await page.shot(`${shots}/09-account.png`, { full: true })

  // ---- 6. the statement link on the business's own website
  await page.click('Copy customer link', { byText: true })
  await page.waitFor('.bos-inv-link')
  statementUrl = await page.eval(`document.querySelector('.bos-inv-link').value`)
  check(statementUrl.includes(`/${biz.slug}/khata/`), `statement link is on the business's site (${statementUrl})`, results)
  const pdf = await page.eval(`fetch(${JSON.stringify(`/b/${biz.id}/khata/${acctId}/statement`)}).then(r => r.headers.get('content-type') + '|' + r.status)`)
  check(pdf === 'application/pdf|200', `statement PDF opens (${pdf})`, results)
  await page.goto(statementUrl)
  await page.waitFor('Your account with', { text: true })
  const body = await page.eval('document.body.innerText')
  check(body.includes('₹1,500.00 due') && body.includes('Pay ₹1,500.00 by UPI'), `customer sees what is due and a UPI link (${body.slice(0, 120).replace(/\s+/g, ' ')})`, results)
  const upi = await page.eval(`document.querySelector('a[href^="upi://"]')?.getAttribute('href') || ''`)
  check(upi.startsWith('upi://pay?pa=selvam@okbank') && upi.includes('am=1500.00'), `UPI link pays the business's own UPI ID the amount due (${upi.slice(0, 60)})`, results)
  const qrOk = await page.eval(`new Promise(r => { const i = document.querySelector('.ls-khata__qr'); if (!i) return r(false); if (i.complete) return r(i.naturalWidth > 0); i.onload = () => r(true); i.onerror = () => r(false) })`)
  check(qrOk, 'UPI QR image loads for a computer', results)
  const brand = await page.eval(`getComputedStyle(document.querySelector('.ls-btn')).backgroundColor`)
  check(!['rgb(37, 99, 235)', 'rgb(79, 70, 229)'].includes(brand), `statement uses the business's theme, not LOCAH's colour (${brand})`, results)
  await page.shot(`${shots}/10-statement-site.png`, { full: true })

  // ---- 7. customer profile shows the khata; a supplier account records a purchase on credit
  await page.goto(`${WS}/b/${biz.id}/customers/${contact}`)
  await page.waitFor('Open khata', { text: true })
  check((await page.eval('document.body.innerText')).includes('Owes you ₹1,500.00'), 'customer profile shows their khata', results)
  await page.goto(`${WS}/b/${biz.id}/khata?tab=suppliers`)
  await page.waitFor('Open an account', { text: true })
  await page.click('Open an account', { byText: true })
  await page.waitFor('You already owe them', { text: true })
  await fill('Name', 'Ramco Cement Depot')
  await fill('Days to pay', '30')
  await page.click('Open account', { byText: true })
  await page.waitFor('Record a purchase on credit', { text: true })
  await page.click('Record a purchase on credit', { byText: true })
  await fill('Bill amount', '18000')
  await fill('Their bill number', 'RD/2291')
  await page.click('Record purchase', { byText: true })
  await page.waitFor('Purchase recorded', { text: true })
  const owed = await page.waitFor('You owe ₹18,000.00', { text: true, timeout: 10000 }).catch(() => false)
  check(owed, 'supplier purchase on credit: you owe ₹18,000', results)
  await page.goto(`${WS}/b/${biz.id}/khata`)
  await page.waitFor('.bos-inv-summary')
  const summary = await page.eval(`[...document.querySelectorAll('.bos-inv-summary strong')].map(s => s.innerText)`)
  check(summary[0] === '₹1,500.00' && summary[2] === '₹18,000.00', `khata totals: customers owe ${summary[0]}, you owe ${summary[2]}`, results)
  await page.shot(`${shots}/11-khata-list.png`, { full: true })
  check(realErrors(page).length === 0, `no console errors (${realErrors(page).join(' | ').slice(0, 300)})`, results)
} finally {
  await page.close()
}

// ---- 8. 390 px: list, account and the customer's statement
const phone = await browser({ mobile: true })
try {
  for (const [path, want, name] of [[`${WS}/b/${biz.id}/khata`, 'Who owes you and whom you owe', '12-list-390'],
    [`${WS}/b/${biz.id}/khata/${acctId}`, 'Entries', '13-account-390'], [statementUrl, 'Your account with', '14-statement-390']]) {
    await phone.goto(path)
    await phone.waitFor(want, { text: true })
    check(await phone.eval('document.documentElement.scrollWidth <= window.innerWidth + 1'), `${name} fits 390 px`, results)
    await phone.shot(`${shots}/${name}.png`, { full: true })
  }
  check(realErrors(phone).length === 0, `no console errors at 390 px (${realErrors(phone).join(' | ').slice(0, 200)})`, results)
} finally {
  await phone.close()
}

writeFileSync(`${shots}/results.json`, JSON.stringify(results, null, 2))
const failed = results.filter((r) => !r.ok)
console.log(`\n${results.length - failed.length}/${results.length} checks passed`)
