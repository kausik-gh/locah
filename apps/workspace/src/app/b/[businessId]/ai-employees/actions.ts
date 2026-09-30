'use server'

import { revalidatePath } from 'next/cache'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiSend } from '@/lib/api'

async function call(businessId: string, path: string, method: string, body?: unknown) {
  const token = await getAccessToken()
  if (!token) throw new Error('Sign in to manage AI employees')
  await apiSend(`/v1/b/${businessId}/ai-employees${path}`, token, method, body)
  revalidatePath(`/b/${businessId}/ai-employees`)
}

/** Switch one AI employee on or off (its own kill switch). */
export async function setEnabled(form: FormData) {
  await call(String(form.get('businessId')), `/${String(form.get('kind'))}`, 'PATCH', {
    enabled: form.get('enabled') === 'true',
  })
}

/** Autonomy, tools and limits — the owner's settings; the service enforces them. */
export async function saveSettings(form: FormData) {
  const limits: Record<string, number> = {}
  for (const [key, value] of form.entries()) {
    if (key.startsWith('limit:') && String(value).trim() !== '') limits[key.slice(6)] = Number(value)
  }
  await call(String(form.get('businessId')), `/${String(form.get('kind'))}`, 'PATCH', {
    autonomy: String(form.get('autonomy')),
    tools: form.getAll('tools').map(String),
    limits,
  })
}

/** Pause or resume every AI employee at once. */
export async function setPaused(form: FormData) {
  await call(String(form.get('businessId')), '/pause', 'POST', { paused: form.get('paused') === 'true' })
}

/** Approve or decline a request waiting for the owner. */
export async function decide(form: FormData) {
  await call(String(form.get('businessId')), `/actions/${String(form.get('actionId'))}/decision`, 'POST', {
    approve: form.get('approve') === 'true',
  })
}

/** Run the collections or procurement assistant now. */
export async function runNow(form: FormData) {
  await call(String(form.get('businessId')), `/${String(form.get('kind'))}/run`, 'POST')
}
