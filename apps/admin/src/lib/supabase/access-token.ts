import { cookies } from 'next/headers'
import { getAccessToken as getAccessTokenFromAuth } from '@platform/auth'

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
      setAll(cookiesToSet: { name: string; value: string; options?: object }[]) {
        try {
          cookiesToSet.forEach(({ name, value, options }) =>
            cookieStore.set(name, value, options)
          )
        } catch {
          // Server Component — middleware refreshes sessions.
        }
      },
    }
  )
}
