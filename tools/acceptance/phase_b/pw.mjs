// Playwright (real Chromium) for Phase B browser flows against the LOCAL stack
// only. Uses the project's `playwright` if installed, otherwise the global one
// (the cloud image ships playwright + /opt/pw-browsers). Never downloads.
import { execFileSync } from 'node:child_process'
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import path from 'node:path'

export const API = process.env.LOCAH_API || 'http://localhost:8010'
export const WS = process.env.LOCAH_WORKSPACE || 'http://localhost:3101'
export const WEB = process.env.LOCAH_WEB || 'http://localhost:3100'
export const OUT = process.env.LOCAH_ACCEPT_OUT || 'acceptance-out'
export const DB = process.env.LOCAH_ACCEPT_DB || 'locah_accept'
export const PGPORT = process.env.PGPORT || '54329'

export const load = (file) => JSON.parse(readFileSync(file, 'utf8'))
export const wait = (ms) => new Promise((r) => setTimeout(r, ms))

async function chromium() {
  try {
    return (await import('playwright')).chromium
  } catch {
    const globalRoot = path.join(path.dirname(process.execPath), '..', 'lib', 'node_modules', 'playwright', 'package.json')
    return createRequire(globalRoot)('playwright').chromium
  }
}

let shared
export async function launch() {
  if (!shared) shared = await (await chromium()).launch({ headless: true, args: ['--no-sandbox'] })
  return shared
}
export async function closeAll() {
  if (shared) await shared.close()
  shared = undefined
}

/** A fresh browser context: signed in as `who` (a session json from owner.py) or a guest. */
export async function open({ who = null, mobile = false } = {}) {
  const browser = await launch()
  const context = await browser.newContext(
    mobile
      ? { viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true }
      : { viewport: { width: 1440, height: 900 } }
  )
  if (who) {
    await context.addCookies([WS, WEB].map((url) => ({ name: who.cookie_name, value: who.cookie, url })))
  }
  const page = await context.newPage()
  page.setDefaultTimeout(20000)
  const errors = []
  page.on('pageerror', (e) => errors.push(String(e)))
  page.on('console', (m) => {
    if (m.type() === 'error') errors.push(m.text())
  })
  page.realErrors = () =>
    errors.filter(
      (e) =>
        !/Failed to fetch RSC payload/.test(e) &&
        // the dev server's HMR socket and aborted prefetches are harness noise
        !/webpack-hmr|_next\/static\/webpack|net::ERR_ABORTED/.test(e)
    )
  return { context, page }
}

export function recorder(name) {
  const results = []
  const shots = `${OUT}/phase_b/${name}`
  mkdirSync(shots, { recursive: true })
  const check = (cond, msg) => {
    results.push({ ok: !!cond, msg: String(msg).slice(0, 400) })
    console.log(`${cond ? 'PASS' : 'FAIL'}  ${msg}`)
    if (!cond) process.exitCode = 1
  }
  const shot = async (page, file, full = true) => page.screenshot({ path: `${shots}/${file}`, fullPage: full })
  const finish = () => {
    writeFileSync(`${shots}/results.json`, JSON.stringify(results, null, 2))
    const failed = results.filter((r) => !r.ok)
    console.log(`\n${results.length - failed.length}/${results.length} checks passed`)
    for (const f of failed) console.log(`  FAILED: ${f.msg}`)
  }
  return { results, check, shot, shots, finish }
}

/** An API caller bound to one identity's token. Returns { status, data } and never throws on HTTP errors. */
export function caller(token) {
  return async (p, { method = 'GET', body } = {}) => {
    const res = await fetch(`${API}${p}`, {
      method,
      headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}), 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : typeof body === 'string' ? body : JSON.stringify(body),
    })
    const text = await res.text()
    let data
    try {
      data = JSON.parse(text)
    } catch {
      data = text
    }
    return { status: res.status, ok: res.ok, data }
  }
}

/** Like caller, but throws on anything other than 2xx — for setup steps. */
export function must(token) {
  const c = caller(token)
  return async (p, opts) => {
    const r = await c(p, opts)
    if (!r.ok) throw new Error(`${opts?.method || 'GET'} ${p} → ${r.status} ${JSON.stringify(r.data).slice(0, 300)}`)
    return r.data
  }
}

/** Read-only SQL against the LOCAL acceptance database (verification only). */
export function sql(query) {
  return execFileSync('psql', ['-h', 'localhost', '-p', PGPORT, '-U', 'postgres', '-d', DB, '-tAc', query], {
    encoding: 'utf8',
  }).trim()
}

/** True when nothing on the page is wider than the viewport (no sideways scroll). */
export const fits = (page) => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)
