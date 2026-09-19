import { createServerClient } from '@supabase/ssr'
import { resolveSessionCookieOptions } from './cookie-options'

export interface CookieStore {
  getAll: () => any[]
  setAll: (cookiesToSet: any[]) => void
}

export function createSupabaseServerClientInstance(
  url: string,
  anonKey: string,
  cookieStore: CookieStore
) {
  return createServerClient(url, anonKey, {
    cookieOptions: resolveSessionCookieOptions(),
    cookies: {
      getAll() {
        return cookieStore.getAll()
      },
      setAll(cookiesToSet: any[]) {
        cookieStore.setAll(cookiesToSet)
      },
    },
  })
}
