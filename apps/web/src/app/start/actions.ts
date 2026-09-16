'use server'

import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiPatch, apiPost } from '@/lib/platform-api'

export type CreateBusinessState = { error: string | null }

type CreateBusinessResponse = {
  data: { business: { id: string; slug: string; display_name: string } }
}

/**
 * Onboarding step 1 -> POST /v1/platform/businesses.
 *
 * The same endpoint `tools/create_business.py` calls. Business creation also
 * provisions the Website shell and enqueues draft generation server-side, so
 * step 2 has something to show the moment we land there.
 */
export async function createBusinessAction(
  _prev: CreateBusinessState,
  formData: FormData
): Promise<CreateBusinessState> {
  const token = await getAccessToken()
  if (!token) redirect('/login?destination=/start')

  const displayName = String(formData.get('display_name') || '').trim()
  const businessType = String(formData.get('business_type') || '').trim()
  const tagline = String(formData.get('tagline') || '').trim()
  const description = String(formData.get('description') || '').trim()

  if (!displayName) return { error: 'Give your business a name.' }
  if (!businessType) return { error: 'Choose the option that best describes your business.' }

  const res = await apiPost<CreateBusinessResponse>('/v1/platform/businesses', token, {
    display_name: displayName,
    business_type: businessType,
  })

  if (!res.ok) {
    return {
      error:
        res.error.status === 401
          ? 'Your session expired. Sign in again to continue.'
          : `${res.error.message} (${res.error.code})`,
    }
  }

  const businessId = res.data.data.business.id

  // The Marketplace will not list a Business whose profile has neither a
  // tagline nor a description (`profile_public_facts_missing`), and business
  // creation does not accept either field. Set it here so onboarding produces
  // a Business that can actually become discoverable. The description matters
  // twice over: website generation writes the site from it. Non-fatal: a
  // failure here should not strand someone whose Business already exists.
  if (tagline || description) {
    await apiPatch(`/v1/platform/businesses/${businessId}/profile`, token, {
      ...(tagline ? { tagline } : {}),
      ...(description ? { description } : {}),
    })
  }

  redirect(`/start/${businessId}/website/questions`)
}
