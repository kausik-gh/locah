// Shared setup for Phase B browser flows against the LOCAL stack only.
import { readFileSync } from 'node:fs'
import { launch } from '../cdp.mjs'

export const API = process.env.LOCAH_API || 'http://localhost:8010'
export const WS = process.env.LOCAH_WORKSPACE || 'http://localhost:3101'
export const WEB = process.env.LOCAH_WEB || 'http://localhost:3100'
export const OUT = process.env.LOCAH_ACCEPT_OUT || 'acceptance-out'
export const session = JSON.parse(readFileSync(process.env.LOCAH_ACCEPT_SESSION || `${OUT}/session.json`, 'utf8'))

export async function api(path, { method = 'GET', body, token = session.token } = {}) {
  const res = await fetch(`${API}${path}`, {
    method,
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  const text = await res.text()
  let data
  try { data = JSON.parse(text) } catch { data = text }
  if (!res.ok) throw new Error(`${method} ${path} → ${res.status} ${text.slice(0, 300)}`)
  return data
}

export async function newBusiness({ name, category, sub, type = 'other', modules = [] }) {
  const r = await api('/v1/platform/businesses', {
    method: 'POST',
    body: { display_name: name, business_type: type, category_key: category, subcategory_key: sub },
  })
  const id = r.data.business.id
  for (const m of modules) await api(`/v1/b/${id}/modules/${m}/enable`, { method: 'POST' })
  return { id, slug: r.data.business.slug }
}

export async function browser({ mobile = false } = {}) {
  const page = mobile ? await launch({ width: 390, height: 844, mobile: true }) : await launch({ width: 1440, height: 900 })
  for (const origin of [WS, WEB]) await page.cookie(session.cookie_name, session.cookie, origin)
  return page
}

export function check(cond, msg, results) {
  results.push({ ok: !!cond, msg: String(msg).slice(0, 400) })
  console.log(`${cond ? 'PASS' : 'FAIL'}  ${msg}`)
  if (!cond) process.exitCode = 1
}
