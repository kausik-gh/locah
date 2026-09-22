'use server'

import type { BusinessInterviewData, InterviewCommand, InterviewMedia } from '@platform/contracts'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiPost, apiTry } from '@/lib/platform-api'

type Result = { ok: true; data: BusinessInterviewData } | { ok: false; error: string; stale?: boolean }
export async function interviewAction(businessId: string, command: InterviewCommand): Promise<Result> {
  const token = await getAccessToken()
  if (!token) return { ok: false, error: 'Your session expired. Sign in again to continue.' }
  const res = await apiPost<{ data: BusinessInterviewData }>(`/v1/b/${businessId}/interview`, token, command)
  if (!res.ok) return { ok: false, error: res.error.message, stale: res.error.status === 409 }
  return { ok: true, data: res.data.data }
}

export async function reloadInterview(businessId: string): Promise<Result> {
  const token = await getAccessToken()
  if (!token) return { ok: false, error: 'Sign in to resume your interview.' }
  const res = await apiTry<{ data: BusinessInterviewData }>(`/v1/b/${businessId}/interview`, token)
  return res.ok ? { ok: true, data: res.data.data } : { ok: false, error: res.error.message }
}

export async function startInterviewUpload(businessId: string, role: InterviewMedia['role'],
  mimeType: string, sizeBytes: number, filename: string,
): Promise<{ ok: true; assetId: string; uploadUrl: string } | { ok: false; error: string }> {
  const token = await getAccessToken()
  if (!token) return { ok: false, error: 'Sign in again to upload an image.' }
  const res = await apiPost<{ data: { asset: { id: string }; upload: { upload_url: string } } }>(
    `/v1/b/${businessId}/media/upload-url`, token,
    { purpose: role === 'logo' ? 'brand' : 'website', mime_type: mimeType, size_bytes: sizeBytes, original_filename: filename },
  )
  return res.ok ? { ok: true, assetId: res.data.data.asset.id, uploadUrl: res.data.data.upload.upload_url }
    : { ok: false, error: res.error.message }
}

export async function finishInterviewUpload(businessId: string, assetId: string): Promise<{ ok: boolean; error?: string }> {
  const token = await getAccessToken()
  if (!token) return { ok: false, error: 'Sign in again to finish uploading.' }
  const res = await apiPost(`/v1/b/${businessId}/media/${assetId}/complete`, token)
  return res.ok ? { ok: true } : { ok: false, error: res.error.message }
}

/**
 * Mint a short-lived credential for this owner's voice session.
 *
 * The permanent xAI key stays on the API. What reaches the browser expires in
 * about two minutes and is good for one realtime socket and nothing else.
 */
export async function startVoiceSession(
  businessId: string
): Promise<{ ok: true; session: unknown } | { ok: false; error: string }> {
  const token = await getAccessToken()
  if (!token) return { ok: false, error: 'Your session expired. Sign in again to keep talking.' }
  const res = await apiPost<{ data: Record<string, unknown> }>(
    `/v1/b/${businessId}/interview/voice/session`,
    token
  )
  if (!res.ok) return { ok: false, error: res.error.message }
  return { ok: true, session: res.data.data }
}
