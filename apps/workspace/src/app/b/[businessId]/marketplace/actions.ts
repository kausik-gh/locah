'use server'

import { revalidatePath } from 'next/cache'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { platformUrl } from '@platform/config'

/**
 * Fail loudly.
 *
 * These two calls used to ignore the response. A refusal — not eligible to be
 * listed, say — came back as the same page with the same values and no reason,
 * which reads as a button that does nothing. Throwing hands it to the route's
 * error boundary, which is how every other action in Workspace reports a failed
 * write.
 */
async function assertOk(res: Response, what: string): Promise<void> {
  if (res.ok) return
  throw new Error(`${what} failed: ${res.status} ${await res.text()}`)
}

export async function optInDiscoverable(formData: FormData) {
  const token = await getAccessToken()
  if (!token) redirect('/login')
  const businessId = String(formData.get('businessId') || '')
  const apiUrl = platformUrl('api')
  const res = await fetch(`${apiUrl}/v1/b/${businessId}/marketplace/opt-in`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ confirmed: formData.get('confirmed') === 'true' }),
  })
  await assertOk(res, 'Becoming discoverable')
  revalidatePath(`/b/${businessId}/marketplace`)
}

export async function setVisibility(formData: FormData) {
  const token = await getAccessToken()
  if (!token) redirect('/login')
  const businessId = String(formData.get('businessId') || '')
  const visibility = String(formData.get('visibility') || 'private')
  const apiUrl = platformUrl('api')
  const res = await fetch(`${apiUrl}/v1/b/${businessId}/marketplace/visibility`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ visibility }),
  })
  await assertOk(res, 'Changing visibility')
  revalidatePath(`/b/${businessId}/marketplace`)
}
