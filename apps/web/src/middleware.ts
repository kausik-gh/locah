import { type NextRequest } from 'next/server'
import { updateSession } from '@platform/auth'

const supabaseUrl =
  process.env.NEXT_PUBLIC_SUPABASE_URL || 'http://127.0.0.1:54321'
const supabaseAnonKey =
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ||
  'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.dummy.signature'

export async function middleware(request: NextRequest) {
  return updateSession(request, supabaseUrl, supabaseAnonKey)
}

export const config = {
  matcher: [
    '/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)',
  ],
}
