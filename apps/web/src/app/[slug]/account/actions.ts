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

async function me(slug: string, path: string, body?: unknown): Promise<{ ok: boolean; data?: { pay_path?: string }; message?: string }> {
  const token = await getAccessToken()
  if (!token) redirect(`/login?destination=${encodeURIComponent(`/${slug}/account`)}`)
  const res = await fetch(`${platformUrl('api')}/v1/me/businesses/${encodeURIComponent(slug)}${path}`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(body ?? {}),
    cache: 'no-store',
  })
  const json = await res.json().catch(() => null)
  return res.ok ? { ok: true, data: json?.data } : { ok: false, message: json?.error?.message }
}

/** Renew from My account: the next period after this one, then its payment page. */
export async function renewMembership(formData: FormData) {
  const slug = String(formData.get('slug') || '')
  const r = await me(slug, `/memberships/${String(formData.get('id'))}/renew`)
  redirect(r.ok && r.data?.pay_path ? r.data.pay_path : `/${slug}/account?membership=failed#acc-m`)
}

/** Pay what is due now on a fee plan, dues or an unpaid period. */
export async function payMembership(formData: FormData) {
  const slug = String(formData.get('slug') || '')
  const r = await me(slug, `/memberships/${String(formData.get('id'))}/pay`)
  redirect(r.ok && r.data?.pay_path ? r.data.pay_path : `/${slug}/account?membership=failed#acc-m`)
}

/** Skip tomorrow's delivery, or put it back — until the business's cutoff. */
export async function changeTomorrow(formData: FormData) {
  const slug = String(formData.get('slug') || '')
  const r = await me(slug, `/memberships/${String(formData.get('id'))}/delivery-day`, {
    on_date: String(formData.get('on_date')),
    kind: String(formData.get('kind')),
  })
  redirect(`/${slug}/account?membership=${r.ok ? 'changed' : 'late'}#acc-m`)
}
