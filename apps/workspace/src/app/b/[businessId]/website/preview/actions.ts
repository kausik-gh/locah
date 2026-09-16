'use server'

import { revalidatePath } from 'next/cache'
import { getAccessToken } from '@/lib/supabase/access-token'

/**
 * Inline click-to-edit (Doc 09 §9.1.1) — additive UI over the EXISTING
 * section content-update endpoint. No new backend: this is exactly the same
 * `PATCH /v1/b/{id}/website/sections/{id}` the structured editor uses, so the
 * same schema validation and content-safety checks apply on the server.
 *
 * The whole (merged) content object is sent, because that endpoint validates
 * the complete section content against its SectionType schema.
 */
export async function saveSectionContent(
  businessId: string,
  sectionId: string,
  content: Record<string, unknown>
): Promise<{ ok: boolean; error?: string }> {
  const token = await getAccessToken()
  if (!token) return { ok: false, error: 'Your session expired — sign in again.' }

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000'
  const res = await fetch(`${apiUrl}/v1/b/${businessId}/website/sections/${sectionId}`, {
    method: 'PATCH',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ content }),
    cache: 'no-store',
  })
  if (!res.ok) {
    let message = `Save failed (${res.status})`
    try {
      const body = (await res.json()) as { error?: { message?: string } }
      if (body?.error?.message) message = body.error.message
    } catch {
      /* keep status message */
    }
    return { ok: false, error: message }
  }
  revalidatePath(`/b/${businessId}/website/preview`)
  return { ok: true }
}

/**
 * Step 1 of the two-step upload (Doc 12 §15.3): ask the API for a signed
 * upload URL. The browser then PUTs the bytes straight to Supabase Storage —
 * neither this server action nor the API ever sees the file body.
 */
export async function requestImageUpload(
  businessId: string,
  mimeType: string,
  sizeBytes: number,
  originalFilename: string
): Promise<
  | { ok: true; assetId: string; uploadUrl: string }
  | { ok: false; error: string }
> {
  const token = await getAccessToken()
  if (!token) return { ok: false, error: 'Your session expired — sign in again.' }

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000'
  const res = await fetch(`${apiUrl}/v1/b/${businessId}/media/upload-url`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({
      purpose: 'website',
      mime_type: mimeType,
      size_bytes: sizeBytes,
      original_filename: originalFilename,
    }),
    cache: 'no-store',
  })
  if (!res.ok) {
    let message = `Could not start the upload (${res.status})`
    try {
      const body = (await res.json()) as { error?: { message?: string } }
      if (body?.error?.message) message = body.error.message
    } catch {
      /* keep status message */
    }
    return { ok: false, error: message }
  }
  const body = (await res.json()) as {
    data: { asset: { id: string }; upload: { upload_url: string } }
  }
  return { ok: true, assetId: body.data.asset.id, uploadUrl: body.data.upload.upload_url }
}

/** Step 2: confirm the object landed, flipping the asset to `ready`. */
export async function completeImageUpload(
  businessId: string,
  assetId: string
): Promise<{ ok: true; url: string | null } | { ok: false; error: string }> {
  const token = await getAccessToken()
  if (!token) return { ok: false, error: 'Your session expired — sign in again.' }

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000'
  const res = await fetch(
    `${apiUrl}/v1/b/${businessId}/media/${assetId}/complete`,
    {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
      cache: 'no-store',
    }
  )
  if (!res.ok) {
    let message = `Upload could not be confirmed (${res.status})`
    try {
      const body = (await res.json()) as { error?: { message?: string } }
      if (body?.error?.message) message = body.error.message
    } catch {
      /* keep status message */
    }
    return { ok: false, error: message }
  }
  const body = (await res.json()) as { data: { url: string | null } }
  revalidatePath(`/b/${businessId}/website/preview`)
  return { ok: true, url: body.data.url }
}
