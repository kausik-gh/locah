import { createSupabaseBrowserClientInstance } from '@platform/auth'

export function createClient() {
  return createSupabaseBrowserClientInstance(
    process.env.NEXT_PUBLIC_SUPABASE_URL || 'http://127.0.0.1:54321',
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.dummy.signature'
  )
}
