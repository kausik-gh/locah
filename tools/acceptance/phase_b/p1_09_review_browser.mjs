// Local-only P1-09 browser smoke: a real invitation from the scratch database
// opens in Chromium, posts through the browser form, and persists a review.
// It never touches a deployed service or a payment/AI provider.
//
// LOCAH_TEST_DATABASE_URL=postgresql://postgres@localhost:54329/locah_p109_scratch
// LOCAH_REVIEW_SIGNING_SECRET=<local test secret>
// node tools/acceptance/phase_b/p1_09_review_browser.mjs
import { execFileSync } from 'node:child_process'
import { createHmac } from 'node:crypto'
import { join } from 'node:path'
import { tmpdir } from 'node:os'
import { launch } from '../cdp.mjs'

const db = process.env.LOCAH_TEST_DATABASE_URL || ''
const secret = process.env.LOCAH_REVIEW_SIGNING_SECRET || ''
const web = process.env.LOCAH_WEB || 'http://localhost:3000'
const api = process.env.LOCAH_API || 'http://localhost:8000'
if (!/localhost:54329\/locah_[a-z0-9_]*scratch$/.test(db) || !secret ||
    !/^http:\/\/localhost:\d+$/.test(web) || !/^http:\/\/localhost:\d+$/.test(api)) {
  throw new Error('This smoke test requires a local scratch DB, local Web/API, and local signing secret')
}

const rows = execFileSync('psql', [db, '-Atc', `
  SELECT b.slug, i.business_id, i.id, b.visibility
  FROM reviews_invitations i JOIN businesses b ON b.id=i.business_id
  LEFT JOIN reviews_reviews r ON r.invitation_id=i.id
  WHERE i.expires_at > now() AND i.declined_at IS NULL AND r.id IS NULL
    AND (
      (i.source_type='order' AND EXISTS (
        SELECT 1 FROM orders_orders o WHERE o.id=i.source_id AND o.business_id=i.business_id
          AND o.customer_contact_id=i.customer_contact_id AND o.status='completed' AND o.deleted_at IS NULL
      )) OR
      (i.source_type='booking' AND EXISTS (
        SELECT 1 FROM bookings_bookings bk WHERE bk.id=i.source_id AND bk.business_id=i.business_id
          AND bk.customer_contact_id=i.customer_contact_id AND bk.status='completed' AND bk.deleted_at IS NULL
      ))
    )
  ORDER BY i.created_at DESC LIMIT 60
`], { encoding: 'utf8' }).trim().split(/\r?\n/)

let selected
for (const row of rows) {
  const [slug, businessId, invitationId, visibility] = row.split('|')
  if (!slug || !businessId || !invitationId) continue
  const token = createHmac('sha256', secret).update(`review:${businessId}:${invitationId}`)
    .digest('base64url').slice(0, 32)
  const res = await fetch(`${api}/v1/public/websites/${slug}/review/${token}`)
  if (!res.ok) continue
  const view = (await res.json()).data
  if (view.state === 'open') { selected = { slug, businessId, token, visibility }; break }
}
if (!selected) throw new Error('No open invitation signed with this test secret exists in the scratch database')

const { slug, businessId, token, visibility } = selected
const url = `${web}/${slug}/review/${token}`
const out = join(tmpdir(), 'locah-p109-review-desktop.png')
const mobileOut = join(tmpdir(), 'locah-p109-review-mobile.png')
const page = await launch({ width: 1440, height: 900 })
let unlistedForCheck = false
try {
  await page.goto(url)
  await page.waitFor('.ls-review-form')
  const visible = await page.eval('document.querySelector(".ls-reviews-header h1")?.innerText.startsWith("Review ")')
  const overlay = await page.eval('!!document.querySelector("[data-nextjs-dialog]")')
  if (!visible || overlay) throw new Error('The customer review form did not render cleanly')
  await page.shot(out)
  await page.click('.ls-review-stars label:nth-of-type(5)')
  await page.type('#review-body', 'Thoughtful service and a smooth visit. Local acceptance test.')
  await page.click('.ls-review-form button[type=submit]')
  try {
    await page.waitFor('Your review has been saved', { text: true, timeout: 15000 })
  } catch (error) {
    const state = await page.eval(`({rating: document.querySelector('input[name=rating]:checked')?.value,
      body: document.querySelector('#review-body')?.value, message: document.querySelector('.ls-review-error')?.innerText,
      overlay: !!document.querySelector('[data-nextjs-dialog]')})`)
    console.error(JSON.stringify({ failed: 'browser submission', state, errors: page.consoleErrors.map((e) => e.slice(0, 180)) }))
    throw error
  }
  const saved = await (await fetch(`${api}/v1/public/websites/${slug}/review/${token}`)).json()
  if (saved.data.review?.rating !== 5 || !saved.data.review?.body?.includes('Local acceptance test')) {
    throw new Error('The browser submission was not persisted with the expected review facts')
  }
  await page.viewport(390, 844, true)
  await page.shot(mobileOut)
  const overflow = await page.eval('document.documentElement.scrollWidth > window.innerWidth')
  // The seeded customer businesses are private. Temporarily make only this
  // synthetic scratch business unlisted to exercise the public read path.
  if (visibility === 'private') {
    if (!/^[0-9a-f-]{36}$/.test(businessId)) throw new Error('Invalid scratch business ID')
    const changed = execFileSync('psql', [db, '-Atc', `UPDATE businesses SET visibility='unlisted'
      WHERE id='${businessId}' AND visibility='private' RETURNING id`], { encoding: 'utf8' }).trim()
    if (!changed.startsWith(businessId)) throw new Error('Could not make the scratch fixture unlisted')
    unlistedForCheck = true
  }
  const publicListResponse = await fetch(`${api}/v1/public/websites/${slug}/reviews`)
  if (!publicListResponse.ok) throw new Error(`Public review list returned ${publicListResponse.status}`)
  const publicList = await publicListResponse.json()
  const publicReview = publicList.data?.reviews?.some((review) => review.body?.includes('Local acceptance test'))
  const hasPublishedSite = (await fetch(`${api}/v1/public/websites/${slug}`)).ok
  let publicPage = 'no published site in scratch fixture'
  let publicOverflow = false
  if (hasPublishedSite) {
    await page.goto(`${web}/${slug}/reviews`)
    await page.waitFor('.ls-reviews-page')
    if (!await page.eval('document.querySelector(".ls-reviews-list")?.innerText.includes("Local acceptance test")')) {
      throw new Error('The saved review is missing from the public website page')
    }
    publicOverflow = await page.eval('document.documentElement.scrollWidth > window.innerWidth')
    publicPage = 'verified in Chromium'
  }
  const errors = page.consoleErrors.map((error) => error.slice(0, 240))
  console.log(JSON.stringify({ rendered: visible, savedRating: saved.data.review.rating, mobileOverflow: overflow,
    publicReview, publicPage, publicOverflow, overlay, errors, screenshots: [out, mobileOut] }))
  if (overflow || publicOverflow || !publicReview || errors.length) process.exitCode = 1
} finally {
  if (unlistedForCheck) execFileSync('psql', [db, '-Atc', `UPDATE businesses SET visibility='private'
    WHERE id='${businessId}' AND visibility='unlisted'`])
  await page.close()
}
