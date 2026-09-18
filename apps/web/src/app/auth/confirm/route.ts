import { NextResponse } from 'next/server'
import { type EmailOtpType, resolveDestinationIntent, siteUrl } from '@platform/auth'
import { createClient } from '@/lib/supabase/server'
import { authErrorUrl, classifyAuthError, toAuthFlow } from '../auth-errors'

/**
 * Token-hash confirmation: the link in a LOCAH-branded email points straight
 * here, so the address the recipient sees is LOCAH's own domain rather than
 * `*.supabase.co`, and the redirect never depends on Supabase's Site URL.
 *
 * Kept alongside `/auth/callback` on purpose — which one is used depends on
 * whether the Supabase email template emits `{{ .TokenHash }}` or
 * `{{ .ConfirmationURL }}`, and both should work.
 */
const ALLOWED_TYPES: ReadonlySet<string> = new Set([
  'signup',
  'email',
  'email_change',
  'recovery',
  'invite',
  'magiclink',
])

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url)
  const tokenHash = searchParams.get('token_hash')
  const type = searchParams.get('type')
  const next = resolveDestinationIntent(searchParams.get('next'))

  if (!tokenHash || !type) {
    return NextResponse.redirect(authErrorUrl('missing_token'))
  }
  if (!ALLOWED_TYPES.has(type)) {
    return NextResponse.redirect(authErrorUrl('invalid_link', toAuthFlow(type)))
  }

  const supabase = createClient()
  const { error } = await supabase.auth.verifyOtp({
    type: type as EmailOtpType,
    token_hash: tokenHash,
  })
  if (error) {
    return NextResponse.redirect(
      authErrorUrl(classifyAuthError(error.code ?? error.name, error.message), toAuthFlow(type))
    )
  }

  // A recovery link has to land on the password form, not the home page —
  // the session it just established is the only thing authorising the change.
  const destination = type === 'recovery' ? '/auth/update-password' : next
  return NextResponse.redirect(siteUrl(destination))
}
