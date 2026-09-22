'use server'

import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiPost } from '@/lib/platform-api'

export type CreateBusinessState = { error: string | null }

export async function createBusinessAction(_prev: CreateBusinessState, formData: FormData): Promise<CreateBusinessState> {
  const token = await getAccessToken()
  if (!token) redirect('/login?destination=/start')
  const name = String(formData.get('display_name') || '').trim()
  if (!name) return { error: 'Give your business a name.' }
  const res = await apiPost<{ data: { business: { id: string } } }>('/v1/platform/businesses', token, {
    display_name: name, business_type: 'not_sure',
  })
  if (!res.ok) return { error: res.error.message }
  redirect(`/start/${res.data.data.business.id}/interview`)
}
