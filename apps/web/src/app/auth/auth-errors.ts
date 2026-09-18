import { siteUrl } from '@platform/auth'

/**
 * What went wrong with a confirmation link, in terms the recipient can act on.
 *
 * "Could not authenticate" was the only outcome before, which left someone
 * holding a two-day-old link with nothing to do about it. The distinction that
 * matters is whether a fresh link would help: `expired` and `already_used` are
 * recoverable by resending, the rest are not.
 */
export type AuthErrorReason =
  | 'expired'
  | 'already_used'
  | 'invalid_link'
  | 'missing_code'
  | 'missing_token'
  | 'access_denied'
  | 'unknown'

export const RECOVERABLE_BY_RESEND: ReadonlySet<AuthErrorReason> = new Set([
  'expired',
  'already_used',
])

/**
 * Which flow the dead link belonged to, so the recovery offer matches it.
 *
 * Without this the page can only offer one kind of resend. Offering a signup
 * confirmation to someone whose password-reset link expired sends the wrong
 * mail and fails outright, because their account is already confirmed.
 */
export type AuthFlow = 'signup' | 'recovery' | 'magiclink' | 'invite' | 'unknown'

export function toAuthFlow(type: string | null | undefined): AuthFlow {
  switch (type) {
    case 'signup':
    case 'email':
      return 'signup'
    case 'recovery':
      return 'recovery'
    case 'magiclink':
      return 'magiclink'
    case 'invite':
      return 'invite'
    default:
      return 'unknown'
  }
}

/** Supabase reports these inconsistently — as an error code, or only in prose. */
export function classifyAuthError(
  code: string | null | undefined,
  description?: string | null
): AuthErrorReason {
  const haystack = `${code ?? ''} ${description ?? ''}`.toLowerCase()

  if (haystack.includes('expired')) {
    return 'expired'
  }
  // A link opened twice — commonly a mail client prefetching it, so the person
  // clicking has done nothing wrong and should just be offered a new one.
  if (
    haystack.includes('already') ||
    haystack.includes('used') ||
    haystack.includes('consumed')
  ) {
    return 'already_used'
  }
  if (haystack.includes('access_denied')) {
    return 'access_denied'
  }
  if (
    haystack.includes('invalid') ||
    haystack.includes('not found') ||
    haystack.includes('otp')
  ) {
    return 'invalid_link'
  }
  return 'unknown'
}

export function authErrorUrl(reason: AuthErrorReason, flow: AuthFlow = 'unknown'): string {
  const params = new URLSearchParams({ reason, flow })
  return siteUrl(`/auth/error?${params.toString()}`)
}

export const AUTH_ERROR_COPY: Record<
  AuthErrorReason,
  { title: string; body: string }
> = {
  expired: {
    title: 'This link has expired',
    body: 'Confirmation links are only valid for a short time. Enter your email and we will send a new one.',
  },
  already_used: {
    title: 'This link has already been used',
    body: 'It may have been opened automatically by your email app. Send yourself a fresh link to continue.',
  },
  invalid_link: {
    title: 'This link is not valid',
    body: 'It may have been copied incompletely, or it was meant for a different account. Request a new one below.',
  },
  missing_code: {
    title: 'Something is missing from this link',
    body: 'The confirmation details did not arrive with the link. Request a new one and open it directly from your email.',
  },
  missing_token: {
    title: 'Something is missing from this link',
    body: 'The confirmation details did not arrive with the link. Request a new one and open it directly from your email.',
  },
  access_denied: {
    title: 'We could not confirm this account',
    body: 'Access was refused for this link. Request a new one, or sign in if you have already confirmed.',
  },
  unknown: {
    title: 'We could not complete sign in',
    body: 'Something went wrong confirming your account. Request a new link and try again.',
  },
}
