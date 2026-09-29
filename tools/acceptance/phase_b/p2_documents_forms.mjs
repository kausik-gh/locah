// P2 Documents / Forms browser smoke — local stack only.
// LOCAH_ACCEPT_SESSION=acceptance-out/session.json node tools/acceptance/phase_b/p2_documents_forms.mjs
import { writeFileSync } from 'node:fs'
import { WEB, WS, api, browser, check, newBusiness, realErrors } from './common.mjs'

const results = []
const shots = `${process.env.LOCAH_ACCEPT_OUT || 'acceptance-out'}/phase_b/p2_documents`

const biz = await newBusiness({ name: 'Studio Consent Forms', category: 'personal_services', sub: 'makeup_artist', type: 'service', modules: ['documents'] })

const form = (await api(`/v1/b/${biz.id}/documents/forms`, {
  method: 'POST',
  body: {
    title: 'Intake and waiver',
    kind: 'consent',
    consent_text: 'I agree to the studio terms.',
    guardian_required: false,
    fields: [
      { key: 'full_name', type: 'text', label: 'Full name', required: true },
      { key: 'consent', type: 'consent', label: 'I agree', required: true },
      { key: 'signature', type: 'signature', label: 'Signature', required: true },
    ],
  },
})).data

const formRequest = (await api(`/v1/b/${biz.id}/documents/requests`, {
  method: 'POST',
  body: {
    request_type: 'form',
    title: 'Please complete your intake',
    form_id: form.id,
    related_type: 'general',
    days_valid: 7,
  },
})).data

const uploadRequest = (await api(`/v1/b/${biz.id}/documents/requests`, {
  method: 'POST',
  body: {
    request_type: 'upload',
    title: 'Upload your ID',
    related_type: 'general',
    days_valid: 7,
  },
})).data

const page = await browser()
try {
  await page.goto(`${WS}/b/${biz.id}/documents`)
  await page.waitFor('Documents & requests', { text: true })
  check((await page.eval('document.body.innerText')).includes('Awaiting customer'), 'workspace documents summary renders', results)

  const formUrl = `${WEB}${formRequest.public_path}`
  await page.goto(formUrl)
  await page.waitFor('Secure request', { text: true })
  await page.type('#signer-name', 'Meera Nair')
  await page.eval(`(() => { const i = document.querySelector('#field-full_name'); i.value = 'Meera Nair'; i.dispatchEvent(new Event('input', { bubbles: true })); return true })()`)
  await page.eval(`document.querySelector('#field-consent').click()`)
  await page.click('Submit')
  await page.waitFor('Thank you', { text: true, timeout: 15000 })
  check(!(await page.eval('document.body.innerText')).includes('undefined'), 'form success message is honest', results)

  await page.goto(`${WS}/b/${biz.id}/documents?view=received`)
  await page.waitFor('Received', { text: true })
  check((await page.eval('document.body.innerText')).includes('Please complete your intake'), 'merchant sees fulfilled form request', results)

  const uploadUrl = `${WEB}${uploadRequest.public_path}`
  await page.goto(uploadUrl)
  await page.waitFor('Upload PDF', { text: true })
  check(realErrors(page).length === 0, `no console errors on public form (${realErrors(page).slice(0, 2).join(' | ')})`, results)

  await page.viewport(390, 844, true)
  await page.goto(formUrl)
  check(await page.eval('document.documentElement.scrollWidth <= window.innerWidth + 1'), 'customer form fits 390 px', results)
  await page.shot(`${shots}/form-mobile.png`, { full: true })
} finally {
  await page.close()
  writeFileSync(`${shots}/results.json`, JSON.stringify({ business: biz, formRequest, uploadRequest, results }, null, 1))
}

console.log(JSON.stringify({ pass: results.every((r) => r.ok), results }, null, 1))
