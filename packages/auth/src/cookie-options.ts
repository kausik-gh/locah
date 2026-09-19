import { resolvePlatformOrigins } from '@platform/config'

/**
 * Cookie settings that decide how far a LOCAH session reaches.
 *
 * `@supabase/ssr` writes a host-only cookie by default, which is correct for a
 * single-origin app and wrong for this one: LOCAH is a public platform, a
 * Workspace and an Admin surface, and a person signs in once for all three.
 * Naming the registrable platform domain here is what turns three sign-ins into
 * one.
 *
 * Returning `undefined` — rather than a domain the browser will quietly discard
 * — is the deliberate behaviour when no shared domain is configured. Host-only
 * cookies at least keep each surface individually usable, which is how local
 * development works: `localhost:3000` and `localhost:3001` already share
 * cookies because the port is not part of a cookie's scope.
 */
export interface SessionCookieOptions {
  domain?: string
  path: string
  sameSite: 'lax'
  secure?: boolean
}

export function resolveSessionCookieOptions(): SessionCookieOptions {
  const { sessionCookieDomain, web } = resolvePlatformOrigins()
  if (!sessionCookieDomain) {
    return { path: '/', sameSite: 'lax' }
  }
  return {
    domain: sessionCookieDomain,
    path: '/',
    // `lax` still covers the case that matters — following a link from the
    // public site into Workspace is a top-level GET — without opting the
    // session into cross-site POSTs.
    sameSite: 'lax',
    // Follows the scheme the platform is actually served over. In production
    // that is https and the flag is set; over plain http a `Secure` cookie
    // would be dropped by the browser, which is precisely the silent failure
    // this module exists to avoid — and it would make the shared-domain path
    // impossible to exercise outside production.
    secure: web.startsWith('https://'),
  }
}
