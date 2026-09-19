import { Suspense } from 'react'
import { redirect } from 'next/navigation'
import { resolveDestinationIntent } from '@platform/auth'
import { createClient } from '@/lib/supabase/server'
import { LoginForm } from './LoginForm'

export const dynamic = 'force-dynamic'

/**
 * Show the sign-in form only to someone who is not already signed in.
 *
 * Without this check an authenticated visitor gets the form again, which is
 * how the Workspace hand-off became a loop: Workspace finds no session, sends
 * the user here, and here they are met by a login form despite already having
 * one. Anyone who *is* signed in should simply continue to where they were
 * going.
 */
export default async function LoginPage({
  searchParams,
}: {
  searchParams: { destination?: string | string[] }
}) {
  const supabase = createClient()
  // getUser, not getSession: it verifies the token with Supabase rather than
  // trusting whatever is in the cookie.
  const {
    data: { user },
  } = await supabase.auth.getUser()

  if (user) {
    const raw = Array.isArray(searchParams.destination)
      ? searchParams.destination[0]
      : searchParams.destination
    redirect(resolveDestinationIntent(raw))
  }

  return (
    <Suspense fallback={<div style={{ minHeight: '100vh' }} />}>
      <LoginForm />
    </Suspense>
  )
}
