// Screenshots of the websites the owner flow built and published — the real
// public route (/<slug>), not the site lab.
//
//   node tools/acceptance/owner_sites.mjs acceptance-out/v4
//
// Reads <dir>/results.json from tools/acceptance/stack/owner_flow_v4.py. Needs
// the local API (api.sh), the web app (web.sh) and the stand-in picture server
// running. Shoots each site at 1440 (two screens) and 390 (two screens), the
// full desktop page, and a contact sheet of all of them.

import { existsSync, readFileSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import { launch } from './cdp.mjs'

const WEB = process.env.LOCAH_WEB || 'http://localhost:3100'
const DIR = path.resolve(process.argv[2] || 'acceptance-out/v4')
const results = JSON.parse(readFileSync(path.join(DIR, 'results.json'), 'utf8'))
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

// Which pixels these are, from the run that made them: gemini_verify_v4.py
// writes report.json (mode + the image models that answered); owner_flow_v4.py
// writes none, and its pictures are labelled stand-in plates.
const report = existsSync(path.join(DIR, 'report.json'))
  ? JSON.parse(readFileSync(path.join(DIR, 'report.json'), 'utf8'))
  : null
const models = (report?.image_models_seen || []).filter((m) => m && !/stand-in|self-test/i.test(m))
const realGemini = report?.mode === 'REAL GEMINI' && models.length > 0
const pictures = realGemini
  ? `Pictures are real Gemini drafts (${models.join(', ')}), shown to visitors as illustrative.`
  : 'Pictures are labelled stand-in plates, not Gemini output.'

// Runs in the page: resolves once the hero's picture has actually loaded and
// decoded — an <img> in the hero, or the CSS background-image on it — or at
// once for a hero drawn without a picture. A ~700 KB hero takes longer than
// any fixed delay is guaranteed to allow.
function heroPainted(timeoutMs) {
  const deadline = Date.now() + timeoutMs
  const settle = (how) => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(() => done(how))))
  return new Promise((resolve) => {
    const later = (why) => (Date.now() > deadline ? resolve(`timeout:${why}`) : setTimeout(tick, 150))
    function tick() {
      const hero = document.querySelector('.ls-hero')
      if (!hero) return later('no-hero')
      if (hero.classList.contains('ls-hero--noimage')) return resolve('no-image')
      const img = hero.querySelector('img')
      if (img) {
        if (!img.complete || !img.naturalWidth) return later('img')
        return img.decode().then(() => settle('img'), () => settle('img')).then(resolve)
      }
      const url = (getComputedStyle(hero).backgroundImage.match(/url\(["']?(.*?)["']?\)/) || [])[1]
      if (!url) return later('background')
      const probe = new Image()
      probe.onload = () => probe.decode().then(() => settle('background'), () => settle('background')).then(resolve)
      probe.onerror = () => resolve('background-error')
      probe.src = url
    }
    tick()
  })
}

// Runs in the page: fonts, and every picture now inside the viewport, loaded.
function viewportPainted(timeoutMs) {
  const deadline = Date.now() + timeoutMs
  return document.fonts.ready.then(() => new Promise((resolve) => {
    function tick() {
      const pending = [...document.images].filter((i) => i.getBoundingClientRect().top < innerHeight && !i.complete)
      if (!pending.length) return requestAnimationFrame(() => requestAnimationFrame(() => resolve('ok')))
      if (Date.now() > deadline) return resolve(`timeout:${pending.length}`)
      setTimeout(tick, 150)
    }
    tick()
  }))
}

async function shoot(page, slug, key, device, screens = 2) {
  const [w, h, mobile] = device === 'mobile' ? [390, 844, true] : [1440, 900, false]
  await page.viewport(w, h, mobile)
  await page.goto(`${WEB}/${slug}`)
  await page.waitFor('[data-locah-site]', { timeout: 90000 })
  const hero = await page.eval(`(${heroPainted})(30000)`)
  await page.viewport(w, h * screens, mobile)
  const rest = await page.eval(`(${viewportPainted})(15000)`)
  const file = path.join(DIR, `${key}-${device}${screens > 2 ? '-full' : ''}.png`)
  await page.shot(file)
  await page.viewport(w, h, mobile)
  if (String(hero).startsWith('timeout') || String(rest).startsWith('timeout')) {
    console.log(`  ${key} ${device}: hero ${hero}, page ${rest} — shot anyway, check it`)
  }
  return { file: path.basename(file), hero }
}

const page = await launch({ width: 1440, height: 900 })
const rows = []
for (const r of results) {
  const desktop = await shoot(page, r.slug, r.key, 'desktop')
  const mobile = await shoot(page, r.slug, r.key, 'mobile')
  const full = await shoot(page, r.slug, r.key, 'desktop', 6)
  rows.push({ ...r, desktop: desktop.file, mobile: mobile.file, full: full.file })
  console.log(`shot ${r.key} /${r.slug} (hero: desktop ${desktop.hero}, mobile ${mobile.hero})`)
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
<p class="sub">Built through the interview API, the real website.generate job and Publish. ${esc(pictures)}</p>
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
