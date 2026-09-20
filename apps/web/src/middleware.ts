import { NextResponse, type NextRequest } from 'next/server'
import { updateSession } from '@platform/auth'
import { businessSlugFromHost, platformUrl } from '@platform/config'

const supabaseUrl =
  process.env.NEXT_PUBLIC_SUPABASE_URL || 'http://127.0.0.1:54321'
const supabaseAnonKey =
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ||
  'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.dummy.signature'

/**
 * Paths that belong to LOCAH itself rather than to any one Business.
 *
 * Reaching `/marketplace` on a Business's own subdomain is a navigation that
 * escaped its site, so it is sent back to the platform origin rather than
 * rendered as if the Business owned it. `/auth` is the exception that stays put:
 * the session routes must work on whatever host is serving them.
 */
const PLATFORM_PATHS = ['/marketplace', '/search', '/activity', '/start', '/login', '/for-businesses', '/capabilities']

function isPlatformPath(pathname: string): boolean {
  return PLATFORM_PATHS.some((p) => pathname === p || pathname.startsWith(`${p}/`))
}

/**
 * Serve a Business website from its own subdomain without a second route tree.
 *
 * Document 10 §12.1 gives every Business `{slug}.<platform-domain>`, while the
 * app's routes are written as `/{slug}/...`. Rewriting one onto the other keeps
 * a single implementation of every page: the subdomain and the path form are
 * the same rendering reached two ways, so they cannot drift apart.
 *
 * The rewrite is invisible to the visitor — the address bar keeps the subdomain
 * — and it only ever applies when a platform domain is configured. On localhost
 * and on `*.vercel.app` there is no subdomain to read, so `businessSlugFromHost`
 * returns null and this is a plain session refresh.
 */
export async function middleware(request: NextRequest) {
  const sessionResponse = await updateSession(request, supabaseUrl, supabaseAnonKey)

  const slug = businessSlugFromHost(request.headers.get('host'))
  if (!slug) {
    return sessionResponse
  }

  const { pathname, search } = request.nextUrl

  if (pathname.startsWith('/_next') || pathname.startsWith('/auth')) {
    return sessionResponse
  }

  if (isPlatformPath(pathname)) {
    return NextResponse.redirect(platformUrl('web', `${pathname}${search}`))
  }

  // Already inside the Business's own subtree: rewriting again would nest it
  // as `/{slug}/{slug}`.
  if (pathname === `/${slug}` || pathname.startsWith(`/${slug}/`)) {
    return sessionResponse
  }

  const url = request.nextUrl.clone()
  url.pathname = pathname === '/' ? `/${slug}` : `/${slug}${pathname}`

  const rewritten = NextResponse.rewrite(url, { request: { headers: request.headers } })
  // Carry over anything the session refresh just issued; dropping these would
  // silently sign the visitor out one request later.
  sessionResponse.cookies.getAll().forEach((cookie) => {
    rewritten.cookies.set(cookie)
  })
  return rewritten
}

export const config = {
  matcher: [
    '/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)',
  ],
}
