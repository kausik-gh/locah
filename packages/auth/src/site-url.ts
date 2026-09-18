/**
 * Canonical public origin for this deployment.
 *
 * Auth emails must contain an absolute URL, and `window.location.origin` is the
 * wrong source for it: it is whatever host the browser happened to be on, so a
 * signup started on a dev machine mails a `localhost` link to a real inbox.
 * Server-side, `new URL(request.url).origin` is equally unreliable behind a
 * proxy, where it can be the internal host rather than the public one.
 *
 * `NEXT_PUBLIC_WEB_URL` is the one value that names the public origin in both
 * places, so it is the source of truth here.
 *
 * Note that Supabase has the final say regardless. It validates `emailRedirectTo`
 * against the project's Redirect URLs allowlist and silently substitutes Site URL
 * when there is no match — so a correct value here still needs the matching
 * allowlist entry, or the link in the email will point somewhere else entirely.
 */

const DEV_FALLBACK = 'http://localhost:3000'

function normalize(raw: string): string {
  const trimmed = raw.trim().replace(/\/+$/, '')
  return trimmed
}

export function resolveSiteUrl(): string {
  const configured = process.env.NEXT_PUBLIC_WEB_URL
  if (configured && configured.trim()) {
    return normalize(configured)
  }
  return DEV_FALLBACK
}

/** Absolute URL for a platform-owned path, e.g. `/auth/callback`. */
export function siteUrl(path: string): string {
  const base = resolveSiteUrl()
  if (!path) {
    return base
  }
  return `${base}${path.startsWith('/') ? path : `/${path}`}`
}

/**
 * The confirmation link types Supabase can send to `/auth/confirm`.
 *
 * Re-exported here so the apps can type a `verifyOtp` call without taking a
 * direct dependency on `@supabase/supabase-js`, which belongs to this package.
 */
export type { EmailOtpType } from '@supabase/supabase-js'
