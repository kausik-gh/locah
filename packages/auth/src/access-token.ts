/**
 * Access-token retrieval for forwarding to FastAPI (Document 12 §3.4 / §13.7).
 * Returns the Supabase JWT string only — never Business authorization.
 */

import { createSupabaseServerClientInstance, type CookieStore } from './server'

type AuthWithOptionalClaims = {
  getClaims?: () => Promise<unknown>
  getUser: () => Promise<unknown>
  getSession: () => Promise<{
    data: { session: { access_token: string } | null }
  }>
}

/**
 * Read the current access token from the cookie-backed session for
 * `Authorization: Bearer <token>` calls to FastAPI.
 */
export async function getAccessToken(
  supabaseUrl: string,
  supabaseAnonKey: string,
  cookieStore: CookieStore
): Promise<string | null> {
  const supabase = createSupabaseServerClientInstance(
    supabaseUrl,
    supabaseAnonKey,
    cookieStore
  )

  const auth = supabase.auth as unknown as AuthWithOptionalClaims
  // Validate/refresh before reading the token when possible.
  if (typeof auth.getClaims === 'function') {
    await auth.getClaims()
  } else {
    await auth.getUser()
  }

  const { data } = await auth.getSession()
  return data.session?.access_token ?? null
}

/**
 * Build the Authorization header value for FastAPI, or null if unauthenticated.
 */
export async function getAuthorizationHeader(
  supabaseUrl: string,
  supabaseAnonKey: string,
  cookieStore: CookieStore
): Promise<string | null> {
  const token = await getAccessToken(supabaseUrl, supabaseAnonKey, cookieStore)
  return token ? `Bearer ${token}` : null
}
