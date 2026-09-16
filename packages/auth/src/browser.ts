import { createBrowserClient as createSupabaseBrowserClient } from '@supabase/ssr'

export function createSupabaseBrowserClientInstance(url: string, anonKey: string) {
  return createSupabaseBrowserClient(url, anonKey)
}
