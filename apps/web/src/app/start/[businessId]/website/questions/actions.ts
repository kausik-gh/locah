'use server'

import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiPatch, apiPost } from '@/lib/platform-api'

/**
 * Onboarding step 2a — submit the website questionnaire.
 *
 * The answered fields become ONE `POST /v1/b/{id}/website/generate` with an
 * `intake` body (Doc 12 §12.7). Skipped fields are absent; the backend fills
 * them deterministically. A failure here is non-fatal: business creation
 * already produced a draft, so we still move the owner forward to see it.
 */
export async function submitQuestionnaireAction(
  businessId: string,
  intakeJson: string
): Promise<void> {
  const token = await getAccessToken()
  if (!token) redirect(`/login?destination=/start/${businessId}/website/questions`)

  let intake: unknown = {}
  try {
    intake = JSON.parse(intakeJson || '{}')
  } catch {
    intake = {}
  }

  // A logo belongs to Business branding, not to a website section — send it
  // to the branding surface that already owns `logo_asset_id`. Non-fatal.
  const logoAssetId =
    intake && typeof intake === 'object'
      ? (intake as Record<string, unknown>).logo_asset_id
      : undefined
  if (typeof logoAssetId === 'string' && logoAssetId) {
    await apiPatch(`/v1/platform/businesses/${businessId}/branding`, token, {
      logo_asset_id: logoAssetId,
    })
  }

  await apiPost(`/v1/b/${businessId}/website/generate`, token, { intake })
  redirect(`/start/${businessId}/website`)
}

/**
 * Two-step image upload for the questionnaire (Doc 12 §15.3). Same flow the
 * Workspace preview uses: signed URL from the API, bytes straight from the
 * browser to Supabase Storage, then confirm.
 */
export async function requestQuestionnaireUpload(
  businessId: string,
  mimeType: string,
  sizeBytes: number,
  originalFilename: string
): Promise<{ ok: true; assetId: string; uploadUrl: string } | { ok: false; error: string }> {
  const token = await getAccessToken()
  if (!token) return { ok: false, error: 'Your session expired — sign in again.' }

  const res = await apiPost<{
    data: { asset: { id: string }; upload: { upload_url: string } }
  }>(`/v1/b/${businessId}/media/upload-url`, token, {
    purpose: 'website',
    mime_type: mimeType,
    size_bytes: sizeBytes,
    original_filename: originalFilename,
  })
  if (!res.ok) return { ok: false, error: `${res.error.message} (${res.error.code})` }
  return {
    ok: true,
    assetId: res.data.data.asset.id,
    uploadUrl: res.data.data.upload.upload_url,
  }
}

export async function completeQuestionnaireUpload(
  businessId: string,
  assetId: string
): Promise<{ ok: boolean; error?: string }> {
  const token = await getAccessToken()
  if (!token) return { ok: false, error: 'Your session expired — sign in again.' }

  const res = await apiPost(
    `/v1/b/${businessId}/media/${assetId}/complete`,
    token
  )
  if (!res.ok) return { ok: false, error: `${res.error.message} (${res.error.code})` }
  return { ok: true }
}
