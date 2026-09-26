import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { OnboardingShell } from '@/components/onboarding/Shell'
import { StartScreen } from './StartScreen'
import './start.css'

export const dynamic = 'force-dynamic'

export default async function StartPage() {
  if (!(await getAccessToken())) redirect('/login?destination=/start')
  return (
    <OnboardingShell>
      <StartScreen />
    </OnboardingShell>
  )
}
