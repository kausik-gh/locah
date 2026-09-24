import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { OnboardingShell } from '@/components/onboarding/Shell'
import { StartForm } from './StartForm'

export const dynamic = 'force-dynamic'

export default async function StartPage() {
  if (!await getAccessToken()) redirect('/login?destination=/start')
  return <OnboardingShell>
    <div className="ui-start">
      <div>
        <p className="lc-eyebrow">Your business / The first step</p>
        <h1>Let’s make it <em>yours.</em></h1>
        <p className="ui-start__intro">Tell LOCAH what you do. We’ll organise the essentials, suggest useful tools and help you shape a website. Nothing is published without you.</p>
        <StartForm />
      </div>
      <aside className="ui-start__guide"><p className="lc-eyebrow">What happens next</p><ol><li><span>01</span><strong>Tell your story</strong><small>Describe the business in your own words.</small></li><li><span>02</span><strong>Check the details</strong><small>Correct what LOCAH understood.</small></li><li><span>03</span><strong>Make it work</strong><small>Review your presence and tools.</small></li></ol><p>You decide when your website goes live.</p></aside>
    </div>
  </OnboardingShell>
}
