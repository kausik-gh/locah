'use server'

import { revalidatePath } from 'next/cache'
import { redirect } from 'next/navigation'
import { platformUrl } from '@platform/config'
import { getAccessToken } from '@/lib/supabase/access-token'

const apiUrl = platformUrl('api')

/**
 * Apply a template to the draft.
 *
 * The API owns what this means — including refusing a template whose modules
 * are off, and replacing the draft rather than merging into it. Nothing is
 * decided here; the failure the owner sees is the API's own sentence.
 */
export async function applyTemplate(formData: FormData): Promise<void> {
  const businessId = String(formData.get('businessId'))
  const templateId = String(formData.get('templateId'))
  const token = await getAccessToken()
  if (!token) redirect('/login')

  const res = await fetch(`${apiUrl}/v1/b/${businessId}/website/templates/apply`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ template_id: templateId }),
    cache: 'no-store',
  })
  if (!res.ok) {
    const text = await res.text()
    let message = `Could not apply that template (${res.status})`
    try {
      message = JSON.parse(text)?.error?.message || message
    } catch {
      // Non-JSON body — the status-derived message is the best available.
    }
    throw new Error(message)
  }

  revalidatePath(`/b/${businessId}/website`)
  revalidatePath(`/b/${businessId}/website/templates`)
  revalidatePath(`/b/${businessId}/website/preview`)
  // Straight to the editor: the point of choosing a template is to start
  // working on it, not to admire the confirmation.
  redirect(`/b/${businessId}/website/preview`)
}
