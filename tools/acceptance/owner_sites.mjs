// Screenshots of the websites the owner flow built and published — the real
// public route (/<slug>), not the site lab.
//
//   node tools/acceptance/owner_sites.mjs acceptance-out/v4
//
// Reads <dir>/results.json from tools/acceptance/stack/owner_flow_v4.py. Needs
// the local API (api.sh), the web app (web.sh) and the stand-in picture server
// running. Shoots each site at 1440 (two screens) and 390 (two screens), the
// full desktop page, and a contact sheet of all of them.

import { readFileSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import { launch } from './cdp.mjs'

const WEB = process.env.LOCAH_WEB || 'http://localhost:3100'
const DIR = path.resolve(process.argv[2] || 'acceptance-out/v4')
const results = JSON.parse(readFileSync(path.join(DIR, 'results.json'), 'utf8'))
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

async function shoot(page, slug, key, device, screens = 2) {
  const [w, h, mobile] = device === 'mobile' ? [390, 844, true] : [1440, 900, false]
  await page.viewport(w, h, mobile)
  await page.goto(`${WEB}/${slug}`)
  await page.waitFor('[data-locah-site]', { timeout: 90000 })
  await sleep(1500)
  await page.viewport(w, h * screens, mobile)
  await sleep(700)
  const file = path.join(DIR, `${key}-${device}${screens > 2 ? '-full' : ''}.png`)
  await page.shot(file)
  await page.viewport(w, h, mobile)
  return path.basename(file)
}

const page = await launch({ width: 1440, height: 900 })
const rows = []
for (const r of results) {
  const desktop = await shoot(page, r.slug, r.key, 'desktop')
  const mobile = await shoot(page, r.slug, r.key, 'mobile')
  const full = await shoot(page, r.slug, r.key, 'desktop', 6)
  rows.push({ ...r, desktop, mobile, full })
  console.log(`shot ${r.key} /${r.slug}`)
}

const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c])
const html = `<!doctype html><meta charset="utf-8"><title>Owner flow — five websites</title>
<style>
  body { margin: 0; padding: 28px; background: #ecebe7; font: 13px/1.4 system-ui, sans-serif; color: #1c1c1c; }
  h1 { font: 600 22px system-ui; margin: 0 0 4px; } p.sub { margin: 0 0 22px; color: #555; }
  .grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 16px; }
  figure { margin: 0; background: #fff; border-radius: 10px; overflow: hidden; box-shadow: 0 1px 3px #0002; }
  .shots { display: grid; grid-template-columns: 1fr 70px; gap: 6px; padding: 6px; background: #f6f5f2; }
  .shots img { width: 100%; display: block; border-radius: 4px; height: 300px; object-fit: cover; object-position: top; }
  figcaption { padding: 8px 10px 10px; } b { font-size: 14px; } .t { color: #666; }
</style>
<h1>Owner flow — five websites</h1>
<p class="sub">Built through the interview API, the real website.generate job and Publish. Pictures are labelled stand-in plates, not Gemini output.</p>
<div class="grid">${rows.map((r) => `<figure><div class="shots"><img src="${r.desktop}"><img src="${r.mobile}"></div>
<figcaption><b>${esc(r.name)}</b><br><span class="t">${esc(r.hero_style)} · ${esc(r.palette)}</span></figcaption></figure>`).join('')}</div>`
writeFileSync(path.join(DIR, 'contact-sheet.html'), html)
await page.viewport(1800, 560, false)
await page.goto(`file://${path.join(DIR, 'contact-sheet.html')}`)
await sleep(1200)
await page.shot(path.join(DIR, 'contact-sheet.png'))
const errors = page.consoleErrors.filter(Boolean)
if (errors.length) console.log('console errors:', errors.slice(0, 5))
await page.close()
