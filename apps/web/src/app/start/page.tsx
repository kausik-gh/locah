import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { OnboardingShell } from '@/components/onboarding/Shell'
import { StartForm } from './StartForm'

export const dynamic = 'force-dynamic'

export default async function StartPage() {
  if (!await getAccessToken()) redirect('/login?destination=/start')
  return <OnboardingShell>
    <p className="ob-help">YOUR BUSINESS, IN YOUR WORDS</p>
    <h1 style={{ fontSize: 'clamp(2rem, 5vw, 3.5rem)', margin: '0 0 1rem' }}>Let’s make it yours.</h1>
    <p style={{ lineHeight: 1.7, marginBottom: '2rem', maxWidth: '36rem' }}>
      Tell Locah what you do. We’ll organise the essentials, suggest useful tools, and help you make a website.
      Nothing is published without you.
    </p>
    <StartForm />
  </OnboardingShell>
}
