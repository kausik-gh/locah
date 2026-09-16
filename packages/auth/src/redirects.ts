/**
 * Destination Intent — validated post-auth redirect targets (Doc 12 §6.6).
 * Only platform-owned relative paths are permitted.
 */

const BLOCKED_PATTERNS = [
  /^https?:\/\//i,
  /^\/\//,
  /^javascript:/i,
  /%2f%2f/i,
  /\.\./,
]

export function isValidDestinationIntent(destination: string | null | undefined): boolean {
  if (!destination || typeof destination !== 'string') {
    return false
  }
  const trimmed = destination.trim()
  if (!trimmed.startsWith('/') || trimmed.length > 2048) {
    return false
  }
  if (BLOCKED_PATTERNS.some((pattern) => pattern.test(trimmed))) {
    return false
  }
  if (trimmed === '/') {
    return true
  }
  const pathPrefixes = [
    '/login',
    '/auth/',
    '/workspace',
    '/admin',
    '/b/',
    '/me',
    // Business onboarding: someone who picks "I run a business" on the
    // homepage is sent to /login?destination=/start and must land back here.
    '/start',
  ]
  return pathPrefixes.some(
    (prefix) => trimmed === prefix || trimmed.startsWith(prefix)
  )
}

export function resolveDestinationIntent(
  destination: string | null | undefined,
  fallback = '/'
): string {
  return isValidDestinationIntent(destination) ? destination!.trim() : fallback
}

export function buildSignInRedirectUrl(
  signInPath: string,
  destination: string | null | undefined
): string {
  if (!isValidDestinationIntent(destination)) {
    return signInPath
  }
  const params = new URLSearchParams({ destination: destination!.trim() })
  return `${signInPath}?${params.toString()}`
}

export function readDestinationFromSearchParams(
  searchParams: URLSearchParams | { get(name: string): string | null }
): string | null {
  return searchParams.get('destination')
}
