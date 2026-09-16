import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/platform-api'
import { OnboardingError, OnboardingShell, Steps } from '@/components/onboarding/Shell'
import {
  WebsiteQuestionnaire,
  type QuestionnaireSchema,
} from '@/components/website-questionnaire/WebsiteQuestionnaire'
import {
  completeQuestionnaireUpload,
  requestQuestionnaireUpload,
  submitQuestionnaireAction,
} from './actions'

export const dynamic = 'force-dynamic'

/**
 * Onboarding step 2 — the website questionnaire (Doc 12 §12.7).
 *
 * A thorough, fully skippable, business-type-aware form. Whatever is answered
 * feeds one generation call; the rest is filled deterministically. This is not
 * a chat and there are no per-field AI helpers.
 */
export default async function WebsiteQuestionsPage({
  params,
}: {
  params: { businessId: string }
}) {
  const token = await getAccessToken()
  if (!token) redirect(`/login?destination=/start/${params.businessId}/website/questions`)

  const schemaRes = await apiTry<{ data: QuestionnaireSchema }>(
    `/v1/b/${params.businessId}/website/questionnaire`,
    token
  )

  const resultHref = `/start/${params.businessId}/website`

  if (!schemaRes.ok) {
    return (
      <OnboardingShell>
        <Steps current={2} />
        <OnboardingError
          title="Could not load the questionnaire"
          code={schemaRes.error.code}
          message={schemaRes.error.message}
        >
          <Link href={resultHref}>Skip and see your draft site →</Link>
        </OnboardingError>
      </OnboardingShell>
    )
  }

  const submit = submitQuestionnaireAction.bind(null, params.businessId)
  const uploadStart = requestQuestionnaireUpload.bind(null, params.businessId)
  const uploadFinish = completeQuestionnaireUpload.bind(null, params.businessId)

  return (
    <OnboardingShell>
      <Steps current={2} />
      <h1 style={{ fontSize: '2rem', margin: '0 0 0.5rem' }}>Tell us a little about your business</h1>
      <p
        style={{
          color: '#3c4855',
          lineHeight: 1.65,
          margin: '0 0 2rem',
          maxWidth: '38rem',
          fontFamily: 'system-ui, sans-serif',
          fontSize: '0.95rem',
        }}
      >
        Everything here is optional. Answer what&apos;s easy, skip the rest — we&apos;ll write the
        rest from your business details. It all goes into one pass, so your whole site is built at
        once. You can edit every word afterwards.
      </p>
      <WebsiteQuestionnaire
        schema={schemaRes.data.data}
        action={submit}
        skipHref={resultHref}
        uploadStart={uploadStart}
        uploadFinish={uploadFinish}
      />
    </OnboardingShell>
  )
}
