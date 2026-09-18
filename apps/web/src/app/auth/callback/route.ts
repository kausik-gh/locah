import { NextResponse } from 'next/server'
import { resolveDestinationIntent, siteUrl } from '@platform/auth'
import { createClient } from '@/lib/supabase/server'
import { authErrorUrl, classifyAuthError } from '../auth-errors'

/**
 * PKCE callback: Supabase's own `/auth/v1/verify` sends the browser here with
 * `?code=` once it has checked the token.
 *
 * Redirect targets are built from the configured site URL rather than the
 * request's own origin, which behind a proxy can be the internal host.
 */
export async function GET(request: Request) {
  const { searchParams } = new URL(request.url)
  const code = searchParams.get('code')
  const next = resolveDestinationIntent(searchParams.get('next'))

  // Supabase reports a refused link on the query string rather than as a
  // failed exchange, so read it before trying to spend the code.
  const errorCode = searchParams.get('error_code') ?? searchParams.get('error')
  const errorDescription = searchParams.get('error_description')
  if (errorCode) {
    return NextResponse.redirect(
      authErrorUrl(classifyAuthError(errorCode, errorDescription))
    )
  }

  if (!code) {
    return NextResponse.redirect(authErrorUrl('missing_code'))
  }

  const supabase = createClient()
  const { error } = await supabase.auth.exchangeCodeForSession(code)
  if (error) {
    return NextResponse.redirect(
      authErrorUrl(classifyAuthError(error.code ?? error.name, error.message))
    )
  }

  return NextResponse.redirect(siteUrl(next))
}
