import { Suspense } from 'react'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { LoginForm } from '../login/LoginForm'

export const dynamic = 'force-dynamic'

export default async function SignupPage() {
  if (await getAccessToken()) redirect('/start')
  return <Suspense fallback={<div style={{ minHeight: '100vh' }} />}><LoginForm initialMode="signup" /></Suspense>
}
