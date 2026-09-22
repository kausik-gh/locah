'use server'

import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/platform-api'

/**
 * Where the background personalization has got to.
 *
 * Read-only and DB-only — no model call — so polling it costs the platform a
 * row lookup rather than tokens. Returns null when the status cannot be read,
 * which the caller treats as "stop asking" rather than as failure: the site in
 * the frame is already real either way.
 */
export async function personalizationStatus(businessId: string): Promise<string | null> {
  const token = await getAccessToken()
  if (!token) return null
  const res = await apiTry<{ data: { status: string } | null }>(
    `/v1/b/${businessId}/website/generation`,
    token
  )
  return res.ok ? (res.data.data?.status ?? null) : null
}
