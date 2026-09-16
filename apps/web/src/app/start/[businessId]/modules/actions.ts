'use server'

import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiPost } from '@/lib/platform-api'

export type ClaimState = { error: string | null }

/**
 * Onboarding step 4 — activate the modules the owner picked.
 *
 * Each selection is a real `POST /v1/b/{id}/modules/{module_id}/enable`. One
 * failure does not abandon the rest: everything that can be enabled is, and
 * the owner is told exactly which ones did not take.
 */
export async function claimModulesAction(
  _prev: ClaimState,
  formData: FormData
): Promise<ClaimState> {
  const businessId = String(formData.get('business_id') || '')
  if (!businessId) return { error: 'Missing business.' }

  const token = await getAccessToken()
  if (!token) redirect(`/login?destination=/start/${businessId}/modules`)

  const selected = formData
    .getAll('modules')
    .map((v) => String(v))
    .filter(Boolean)

  const failures: string[] = []
  for (const moduleId of selected) {
    const res = await apiPost(`/v1/b/${businessId}/modules/${moduleId}/enable`, token)
    if (!res.ok) failures.push(`${moduleId} (${res.error.code})`)
  }

  if (failures.length > 0) {
    return {
      error: `Could not turn on: ${failures.join(', ')}. Everything else was activated — you can retry these from the Workspace.`,
    }
  }

  // Land on an in-app arrival screen, not straight at the Workspace origin:
  // `redirect()` from a server action to a cross-origin URL is not followed by
  // the client router, which left the button stuck on "Turning them on…".
  redirect(`/start/${businessId}/done`)
}
