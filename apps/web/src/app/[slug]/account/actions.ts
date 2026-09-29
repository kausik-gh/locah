'use server'

import { redirect } from 'next/navigation'
import { platformUrl } from '@platform/config'
import { getAccessToken } from '@/lib/supabase/access-token'

/** Ask the business to delete my details (DPDP right of erasure). */
export async function askToErase(formData: FormData) {
  const slug = String(formData.get('slug') || '')
  const token = await getAccessToken()
  if (!token) redirect(`/login?destination=${encodeURIComponent(`/${slug}/account`)}`)
  const note = String(formData.get('note') || '').trim().slice(0, 500)
  const res = await fetch(`${platformUrl('api')}/v1/me/businesses/${encodeURIComponent(slug)}/erasure-request`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(note ? { note } : {}),
    cache: 'no-store',
  })
  redirect(`/${slug}/account?privacy=${res.ok ? 'asked' : 'failed'}#acc-data`)
}
