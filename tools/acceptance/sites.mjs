// Website fixture screenshots + contact sheet — the design system, looked at.
//
//   LOCAH_SITE_LAB_DIR=<fixtures> node tools/acceptance/sites.mjs <out_dir>
//
// Needs the web app running with LOCAH_SITE_LAB_DIR set (the /site-lab route
// reads the same fixtures). Shoots every fixture at desktop (1440, first
// 2 screens) and phone (390, first 2 screens), then renders a contact sheet
// page and shoots that too. Nothing here calls an API or a provider.

import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import { launch } from './cdp.mjs'

const WEB = process.env.LOCAH_WEB || 'http://localhost:3100'
const LAB = process.env.LOCAH_SITE_LAB_DIR
const OUT = path.resolve(process.argv[2] || 'acceptance-out/sites')
const only = process.argv.slice(3)
mkdirSync(OUT, { recursive: true })
const index = JSON.parse(readFileSync(path.join(LAB, 'index.json'), 'utf8'))
const sites = index.sites.filter((s) => !only.length || only.includes(s.key))

async function shoot(page, key, device) {
  const [w, h, mobile] = device === 'mobile' ? [390, 844, true] : [1440, 900, false]
  await page.viewport(w, h, mobile)
  await page.goto(`${WEB}/site-lab/${key}`)
  await page.waitFor('[data-locah-site]', { timeout: 60000 })
  await new Promise((r) => setTimeout(r, 900))
  // Two screens tall: the hero and what follows it — the decisions that matter.
  await page.viewport(w, h * 2, mobile)
  await new Promise((r) => setTimeout(r, 500))
  const file = path.join(OUT, `${key}-${device}.png`)
  await page.shot(file)
  await page.viewport(w, h, mobile)
  return path.basename(file)
}

const page = await launch({ width: 1440, height: 900 })
const rows = []
for (const site of sites) {
  const desktop = await shoot(page, site.key, 'desktop')
  const mobile = await shoot(page, site.key, 'mobile')
  rows.push({ ...site, desktop, mobile })
  console.log(`shot ${site.key}`)
}
const errors = page.consoleErrors.filter(Boolean)

const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c])
const html = `<!doctype html><meta charset="utf-8"><title>Website fixtures</title>
<style>
  body { margin: 0; padding: 28px; background: #ecebe7; font: 13px/1.4 system-ui, sans-serif; color: #1c1c1c; }
  h1 { font: 600 22px system-ui; margin: 0 0 4px; } p.sub { margin: 0 0 22px; color: #555; }
  .grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 18px; }
  figure { margin: 0; background: #fff; border-radius: 10px; overflow: hidden; box-shadow: 0 1px 3px #0002; }
  .shots { display: grid; grid-template-columns: 1fr 64px; gap: 6px; padding: 6px; background: #f6f5f2; }
  .shots img { width: 100%; display: block; border-radius: 4px; }
  .shots .d { height: 250px; object-fit: cover; object-position: top; }
  .shots .m { height: 250px; object-fit: cover; object-position: top; }
  figcaption { padding: 8px 10px 10px; } b { font-size: 14px; } .t { color: #666; }
</style>
<h1>Website fixtures — ${rows.length} businesses</h1>
<p class="sub">First version as built from the interview. No owner photos, no drawn pictures, no model. Distinct: ${index.distinctness.ok}.</p>
<div class="grid">${rows
  .map(
    (r) => `<figure><div class="shots"><img class="d" src="${r.desktop}"><img class="m" src="${r.mobile}"></div>
<figcaption><b>${esc(r.name)}</b> <span class="t">${esc(r.business)}</span><br>
<span class="t">${esc(r.family)} · ${esc(r.variant)} · ${esc(r.palette)}</span></figcaption></figure>`
  )
  .join('')}</div>`
writeFileSync(path.join(OUT, 'contact-sheet.html'), html)
await page.viewport(1600, 900, false)
await page.goto('file:///' + path.join(OUT, 'contact-sheet.html').replace(/\\/g, '/'))
await new Promise((r) => setTimeout(r, 1500))
await page.shot(path.join(OUT, 'contact-sheet.png'), { full: true })
writeFileSync(path.join(OUT, 'shots.json'), JSON.stringify({ rows, consoleErrors: errors }, null, 1))
console.log(`${rows.length} sites, contact sheet at ${path.join(OUT, 'contact-sheet.png')}; console errors: ${errors.length}`)
await page.close()
