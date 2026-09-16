/**
 * Next.js middleware/Proxy session refresh (Document 12 §3.4 / §13.7).
 * Refreshes the cookie-backed Supabase session. Never performs Business authorization.
 */

import { createServerClient } from '@supabase/ssr'
import { NextResponse, type NextRequest } from 'next/server'

type AuthWithOptionalClaims = {
  getClaims?: () => Promise<unknown>
  getUser: () => Promise<unknown>
}

/**
 * Validate/refresh the Supabase session from request cookies and propagate
 * any refreshed cookies onto the response.
 */
export async function updateSession(
  request: NextRequest,
  supabaseUrl: string,
  supabaseAnonKey: string
): Promise<NextResponse> {
  let supabaseResponse = NextResponse.next({
    request: {
      headers: request.headers,
    },
  })

  const supabase = createServerClient(supabaseUrl, supabaseAnonKey, {
    cookies: {
      getAll() {
        return request.cookies.getAll()
      },
      setAll(cookiesToSet: { name: string; value: string; options?: Record<string, unknown> }[]) {
        cookiesToSet.forEach(({ name, value }) => {
          request.cookies.set(name, value)
        })
        supabaseResponse = NextResponse.next({
          request: {
            headers: request.headers,
          },
        })
        cookiesToSet.forEach(({ name, value, options }) => {
          supabaseResponse.cookies.set(name, value, options)
        })
      },
    },
  })

  // Prefer getClaims() when available (Doc 12); fall back to getUser() which
  // still triggers refresh and validates the JWT with the Auth server.
  const auth = supabase.auth as unknown as AuthWithOptionalClaims
  if (typeof auth.getClaims === 'function') {
    await auth.getClaims()
  } else {
    await auth.getUser()
  }

  return supabaseResponse
}
