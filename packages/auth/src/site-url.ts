/**
 * Canonical public origin for this deployment.
 *
 * Auth emails must contain an absolute URL, and `window.location.origin` is the
 * wrong source for it: it is whatever host the browser happened to be on, so a
 * signup started on a dev machine mails a `localhost` link to a real inbox.
 * Server-side, `new URL(request.url).origin` is equally unreliable behind a
 * proxy, where it can be the internal host rather than the public one.
 *
 * `resolvePlatformOrigins()` is the one place that names the public origin for
 * both, so it is the source of truth here: an explicit `NEXT_PUBLIC_WEB_URL`
 * where one is set, otherwise the platform domain, otherwise localhost.
 *
 * Note that Supabase has the final say regardless. It validates `emailRedirectTo`
 * against the project's Redirect URLs allowlist and silently substitutes Site URL
 * when there is no match — so a correct value here still needs the matching
 * allowlist entry, or the link in the email will point somewhere else entirely.
 */

import { resolvePlatformOrigins } from '@platform/config'

export function resolveSiteUrl(): string {
  return resolvePlatformOrigins().web
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
