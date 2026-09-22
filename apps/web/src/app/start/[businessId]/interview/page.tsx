import Link from 'next/link'
import { redirect } from 'next/navigation'
import type { BusinessInterviewData } from '@platform/contracts'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/platform-api'
import { OnboardingError, OnboardingShell } from '@/components/onboarding/Shell'
import { BusinessInterview } from './BusinessInterview'
import './interview.css'

export const dynamic = 'force-dynamic'
export default async function InterviewPage({ params }: { params: { businessId: string } }) {
  const token = await getAccessToken()
  if (!token) redirect(`/login?destination=/start/${params.businessId}/interview`)
  const res = await apiTry<{ data: BusinessInterviewData }>(`/v1/b/${params.businessId}/interview`, token)
  return <OnboardingShell>{res.ok ? <BusinessInterview initial={res.data.data} /> :
    <OnboardingError title="Could not open your interview" message={res.error.message}>
      <Link href={`/start/${params.businessId}/interview`}>Try again</Link>
    </OnboardingError>}
  </OnboardingShell>
}
