import { createServerClient } from '@supabase/ssr'

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
