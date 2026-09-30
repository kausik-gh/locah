// Workspace editor → picture buttons, clicked in a real browser.
//
//   ACCEPT_STANDIN_IMAGES=1 tools/acceptance/stack/api.sh   (stand-in plates, NOT Gemini)
//   node tools/acceptance/editor_pictures.mjs <business_id> [out_dir]
//
// Hero → "Generate a picture" → "Generate a new picture" → "Keep this picture"
// → "Remove picture"; then one card picture. After each click the database
// row is checked (source_type / approval_state / generated_for) through psql.
// "Upload my photo" needs a Storage signed-upload URL, which the local stack
// does not have; it is covered by the API tests and gemini_verify_v4.py.

import { execFileSync } from 'node:child_process'
import { readFileSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import { launch } from './cdp.mjs'

const WORKSPACE = process.env.LOCAH_WORKSPACE || 'http://localhost:3101'
const businessId = process.argv[2]
const OUT = path.resolve(process.argv[3] || 'acceptance-out/editor')
const session = JSON.parse(readFileSync(process.env.LOCAH_ACCEPT_SESSION || 'acceptance-out/session.json', 'utf8'))
const DB = process.env.ACCEPT_DB || 'locah_accept'
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const psql = (q) =>
  execFileSync('psql', ['-h', 'localhost', '-p', '54329', '-U', 'postgres', '-d', DB, '-Atc', q], { encoding: 'utf8' }).trim()
const heroAsset = () =>
  psql(`select coalesce(s.content->>'image_asset_id','') from website_sections s join website_pages p on p.id=s.page_id
        join website_versions v on v.id=p.website_version_id where s.business_id='${businessId}' and v.version_type='draft'
        and v.superseded_at is null and s.section_type_id='hero' limit 1`)
const row = (id) => (id ? psql(`select source_type||'|'||approval_state||'|'||coalesce(generated_for,'') from media_assets where id='${id}'`) : '')

const checks = []
const check = (name, ok, detail = '') => {
  checks.push({ name, ok: Boolean(ok), detail })
  console.log(`${ok ? 'PASS' : 'FAIL'} ${name}${detail ? ` — ${detail}` : ''}`)
}
async function waitUntil(fn, ms = 60000) {
  const end = Date.now() + ms
  while (Date.now() < end) {
    const v = fn()
    if (v) return v
    await sleep(500)
  }
  return fn()
}

const page = await launch({ width: 1440, height: 1000 })
await page.cookie(session.cookie_name, session.cookie, WORKSPACE)
await page.goto(`${WORKSPACE}/b/${businessId}/website/preview`)
await page.waitFor('Top of the page', { text: true, timeout: 120000 })
// Open "Top of the page" — retried until React has hydrated and it reports open.
async function openSection(label) {
  for (let i = 0; i < 40; i++) {
    const open = await page.eval(`(() => {
      const b = [...document.querySelectorAll('.ed-sec__head')].find(x => x.innerText.includes(${JSON.stringify(label)}))
      if (!b) return false
      if (b.getAttribute('aria-expanded') === 'true') return true
      b.click(); return false })()`)
    if (open) return true
    await sleep(750)
  }
  return false
}
check('editor opens "Top of the page"', await openSection('Top of the page'))

const before = heroAsset()
await page.click('Generate a picture', { byText: true }).catch(async () => page.click('Generate a new picture', { byText: true }))
const first = await waitUntil(() => (heroAsset() !== before ? heroAsset() : ''))
check('Generate a picture: hero now has a new picture', first, row(first))
check('  it is a LOCAH draft for the hero slot', row(first) === 'gemini_generated|draft|editor:hero', row(first))
await page.waitFor('Draft picture by LOCAH', { text: true, timeout: 20000 }).catch(() => {})
check('  the editor says "Draft picture by LOCAH"', await page.eval(`document.body.innerText.includes('Draft picture by LOCAH')`))
await page.shot(path.join(OUT, '1-generated.png'))

await page.click('Generate a new picture', { byText: true })
const second = await waitUntil(() => (heroAsset() !== first ? heroAsset() : ''))
check('Generate a new picture: a different picture replaces it', second && second !== first, row(second))

await page.click('Keep this picture', { byText: true })
const kept = await waitUntil(() => row(second).includes('|approved|'), 20000)
check('Keep this picture: approved', kept, row(second))
await page.shot(path.join(OUT, '2-kept.png'))

await page.click('Remove picture', { byText: true })
const removed = await waitUntil(() => heroAsset() === '', 20000)
check('Remove picture: the hero has no picture', removed)
await page.shot(path.join(OUT, '3-removed.png'))

// A card: the first section offering card pictures.
const opened = await page.eval(`(() => {
  const s = [...document.querySelectorAll('.ed-sec__head')].find(b => /shop|menu|categor|what you/i.test(b.innerText) && !b.innerText.includes('Top of the page'));
  return s ? s.innerText.split('\\n')[0] : '' })()`)
if (opened) await openSection(opened)
await sleep(600)
const summary = await page.eval(`(() => { const d = [...document.querySelectorAll('details.ed-field')][0]; if (!d) return ''; d.open = true; return d.innerText.split('\\n')[0] })()`)
check('card pictures are offered', summary, `${opened} → ${summary}`)
if (summary) {
  const cards = () => psql(`select count(*) from media_assets where business_id='${businessId}' and generated_for like 'editor:%:%'`)
  const n = cards()
  await page.eval(`(() => { const b = [...document.querySelectorAll('details.ed-field button')].find(x => /Generate/.test(x.innerText)); b && b.click() })()`)
  const drew = await waitUntil(() => (cards() !== n ? cards() : ''), 60000)
  check('Generate a card picture', drew, psql(`select generated_for from media_assets where business_id='${businessId}' and generated_for like 'editor:%:%' order by created_at desc limit 1`))
  await page.shot(path.join(OUT, '4-card.png'))
}

writeFileSync(path.join(OUT, 'editor-results.json'), JSON.stringify({ businessId, checks }, null, 2))
console.log(`${checks.filter((c) => c.ok).length}/${checks.length} editor checks passed`)
await page.close()
process.exit(checks.every((c) => c.ok) ? 0 : 1)
