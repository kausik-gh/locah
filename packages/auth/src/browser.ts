import { createBrowserClient as createSupabaseBrowserClient } from '@supabase/ssr'
import { resolveSessionCookieOptions } from './cookie-options'

export function createSupabaseBrowserClientInstance(url: string, anonKey: string) {
  return createSupabaseBrowserClient(url, anonKey, {
    cookieOptions: resolveSessionCookieOptions(),
  })
}
