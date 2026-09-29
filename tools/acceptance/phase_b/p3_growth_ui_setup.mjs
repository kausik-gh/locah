// Local-only setup for the growth Workspace browser flow.
// Creates a business on the growth plan, turns loyalty and marketing on,
// and leaves one consented customer plus a segment. No external APIs.
import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'

const API = process.env.LOCAH_API || 'http://127.0.0.1:8010'
const session = JSON.parse(readFileSync(process.env.LOCAH_ACCEPT_SESSION, 'utf8'))

async function call(path, method, body) {
  const res = await fetch(`${API}${path}`, {
    method,
    headers: {
      Authorization: `Bearer ${session.token}`,
      'Content-Type': 'application/json',
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  const text = await res.text()
  let data = null
  try {
    data = text ? JSON.parse(text) : null
  } catch {
    data = { raw: text }
  }
  if (!res.ok) {
    throw new Error(`${method} ${path} ${res.status} ${text}`)
  }
  return data
}

const biz = await call('/v1/platform/businesses', 'POST', {
  display_name: `Growth desk ${Date.now().toString().slice(-5)}`,
  business_type: 'other',
})
const businessId = biz.data.business.id

execFileSync(
  'psql',
  [
    '-h', 'localhost',
    '-p', process.env.PGPORT || '54329',
    '-U', 'postgres',
    '-d', process.env.LOCAH_ACCEPT_DB || 'locah_growth_scratch',
    '-v', 'ON_ERROR_STOP=1',
    '-c',
    `update businesses set metadata = jsonb_set(
        jsonb_set(coalesce(metadata, '{}'::jsonb), '{commercial}', coalesce(metadata->'commercial', '{}'::jsonb), true),
        '{commercial,plan_id}', '"growth"'::jsonb, true)
      where id = '${businessId}'`,
  ],
  { stdio: 'inherit' },
)

for (const moduleId of ['customer-relationships', 'loyalty', 'marketing']) {
  await call(`/v1/b/${businessId}/modules/${moduleId}/enable`, 'POST', {})
}

const customer = await call(`/v1/platform/businesses/${businessId}/customers`, 'POST', {
  display_name: 'Asha Rao',
  phone: '+919810000021',
  tags: ['regular'],
})
const contactId = customer.data.id

await call(`/v1/platform/businesses/${businessId}/customers/${contactId}/consents`, 'POST', {
  purpose: 'marketing',
  channel: 'whatsapp',
  granted: true,
  source: 'staff_recorded',
})

const segment = await call(`/v1/platform/businesses/${businessId}/customers/segments`, 'POST', {
  name: 'Regulars',
  rules: [{ kind: 'tag', tag: 'regular' }],
})

process.stdout.write(JSON.stringify({
  businessId,
  contactId,
  segmentId: segment.data.id,
  customerName: 'Asha Rao',
}) + '\n')
