import { cookies } from 'next/headers'
import { getAccessToken as getAccessTokenFromAuth } from '@platform/auth'

/**
 * Forwardable Supabase access token for FastAPI Authorization headers.
 * Display/session only — FastAPI remains the authorization authority.
 */
export async function getAccessToken(): Promise<string | null> {
  const cookieStore = cookies()
  return getAccessTokenFromAuth(
    process.env.NEXT_PUBLIC_SUPABASE_URL || 'http://127.0.0.1:54321',
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ||
      'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.dummy.signature',
    {
      getAll() {
        return cookieStore.getAll()
      },
      setAll(cookiesToSet: any[]) {
        try {
          cookiesToSet.forEach(({ name, value, options }: any) =>
            cookieStore.set(name, value, options)
          )
        } catch {
          // Called from a Server Component without mutable cookies — middleware refreshes sessions.
        }
      },
    }
  )
}
