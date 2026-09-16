import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/platform-api'
import { OnboardingShell, Steps } from '@/components/onboarding/Shell'
import { StartForm, type BusinessType } from './StartForm'

export const dynamic = 'force-dynamic'

/** Onboarding step 1 — business basics. */
export default async function StartPage() {
  const token = await getAccessToken()
  if (!token) redirect('/login?destination=/start')

  const res = await apiTry<{ data: BusinessType[] }>('/v1/platform/business-types', token)

  if (!res.ok) {
    return (
      <OnboardingShell>
        <Steps current={1} />
        <h1 style={{ fontSize: '2rem', margin: '0 0 0.6rem' }}>Set up your business</h1>
        <p
          role="alert"
          style={{
            padding: '1rem 1.2rem',
            borderRadius: '10px',
            border: '1px solid #c9776f',
            background: '#f8e9e7',
            color: '#8d2f24',
            fontFamily: 'system-ui, sans-serif',
            lineHeight: 1.6,
          }}
        >
          Could not load the business types ({res.error.code}): {res.error.message}
          {res.error.status === 401 ? (
            <>
              {' '}
              <Link href="/login?destination=/start">Sign in again</Link>.
            </>
          ) : null}
        </p>
      </OnboardingShell>
    )
  }

  return (
    <OnboardingShell>
      <Steps current={1} />
      <h1 style={{ fontSize: '2rem', margin: '0 0 0.6rem' }}>Set up your business</h1>
      <p style={{ color: '#3c4855', lineHeight: 1.65, margin: '0 0 2rem', maxWidth: '34rem' }}>
        A few details to start. As soon as you submit, we create your business and build your
        website — you&apos;ll see it on the next screen.
      </p>
      <StartForm types={res.data.data || []} />
    </OnboardingShell>
  )
}
