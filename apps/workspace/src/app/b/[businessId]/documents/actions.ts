'use server'

import { revalidatePath } from 'next/cache'
import { platformUrl } from '@platform/config'
import { getAccessToken } from '@/lib/supabase/access-token'

type Result = { ok: true; data: Record<string, unknown> } | { ok: false; error: string }

async function send(businessId: string, path: string, body: unknown): Promise<Result> {
  const token = await getAccessToken()
  if (!token) return { ok: false, error: 'Please sign in again.' }
  try {
    const response = await fetch(`${platformUrl('api')}/v1/b/${businessId}/documents${path}`, {
      method: 'POST', headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify(body), cache: 'no-store',
    })
    const payload = await response.json()
    if (!response.ok) return { ok: false, error: payload?.error?.message || payload?.detail?.message || `Request failed (${response.status})` }
    revalidatePath(`/b/${businessId}/documents`)
    revalidatePath(`/b/${businessId}/forms`)
    return { ok: true, data: payload.data as Record<string, unknown> }
  } catch {
    return { ok: false, error: 'Could not reach Documents. Please try again.' }
  }
}

export async function createTemplate(businessId: string, form: FormData): Promise<Result> {
  const title = String(form.get('title') || '').trim()
  const body = String(form.get('body') || '').trim()
  return send(businessId, '/templates', {
    title, kind: String(form.get('kind') || 'generic'), description: String(form.get('description') || ''),
    traits: {}, content: { sections: [{ heading: title, body }] },
  })
}

export async function saveForm(businessId: string, body: Record<string, unknown>, formId?: string): Promise<Result> {
  return send(businessId, formId ? `/forms/${formId}/versions` : '/forms', body)
}

export async function createRequest(businessId: string, body: Record<string, unknown>): Promise<Result> {
  return send(businessId, '/requests', body)
}

export async function createFileAccess(businessId: string, fileId: string): Promise<Result> {
  return send(businessId, `/files/${fileId}/access`, {})
}
