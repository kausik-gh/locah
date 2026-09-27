'use server'

import { revalidatePath } from 'next/cache'
import { getAccessToken } from '@/lib/supabase/access-token'
import { platformUrl } from '@platform/config'

const apiUrl = platformUrl('api')

export type ActionResult = { ok: true } | { ok: false; message: string }

async function send(path: string, method: string, body: unknown): Promise<ActionResult> {
  const token = await getAccessToken()
  if (!token) return { ok: false, message: 'Your session ended. Sign in again.' }
  const res = await fetch(`${apiUrl}${path}`, {
    method,
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    cache: 'no-store',
  })
  if (res.ok) return { ok: true }
  let message = 'That did not save. Try again.'
  try {
    const data = await res.json()
    message = data?.error?.message ?? message
  } catch {
    /* keep the default */
  }
  return { ok: false, message }
}

function refresh(businessId: string) {
  revalidatePath(`/b/${businessId}/settings/business`)
  revalidatePath(`/b/${businessId}/modules`)
  revalidatePath(`/b/${businessId}`, 'layout')
}

export async function saveTraits(businessId: string, traits: Record<string, boolean>): Promise<ActionResult> {
  const r = await send(`/v1/platform/businesses/${businessId}/traits`, 'PATCH', { traits })
  if (r.ok) refresh(businessId)
  return r
}

export async function saveKind(
  businessId: string,
  categoryKey: string,
  subcategoryKey: string | null,
): Promise<ActionResult> {
  const r = await send(`/v1/platform/businesses/${businessId}/classification`, 'PUT', {
    category_key: categoryKey,
    subcategory_key: subcategoryKey,
  })
  if (r.ok) refresh(businessId)
  return r
}

export async function saveOrgShape(businessId: string, orgShape: string): Promise<ActionResult> {
  const r = await send(`/v1/platform/businesses/${businessId}/classification`, 'PUT', { org_shape: orgShape })
  if (r.ok) refresh(businessId)
  return r
}
