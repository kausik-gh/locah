'use server'

import { redirect } from 'next/navigation'
import type {
  BusinessInterviewData,
  StartConversationResult,
  TaxonomyMatch,
} from '@platform/contracts'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiPost, apiTry } from '@/lib/platform-api'

export type StartState = { error: string | null }

/**
 * Create Business by talking: a Business to talk about, then straight into
 * the conversation.
 *
 * Nothing is required. A first message is sent as the first turn of the one
 * interview (so LOCAH answers it on the next screen); a category, if picked,
 * seeds the opening; "Talk" opens the same conversation with the microphone.
 */
export async function startConversation(input: {
  text?: string
  categoryKey?: string
  subcategoryKey?: string
  talk?: boolean
}): Promise<StartState> {
  const token = await getAccessToken()
  if (!token) redirect('/login?destination=/start')
  const text = (input.text || '').trim()
  const res = await apiPost<{ data: StartConversationResult }>('/v1/platform/businesses/start', token, {
    ...(input.categoryKey ? { category_key: input.categoryKey } : {}),
    ...(input.subcategoryKey ? { subcategory_key: input.subcategoryKey } : {}),
  })
  if (!res.ok) return { error: res.error.message }
  const id = res.data.data.business.id
  if (text) {
    const current = await apiTry<{ data: BusinessInterviewData }>(`/v1/b/${id}/interview`, token)
    if (!current.ok) return { error: current.error.message }
    const turn = await apiPost(`/v1/b/${id}/interview`, token, {
      action: 'turn',
      text,
      revision: current.data.data.blueprint.revision,
      request_id: crypto.randomUUID(),
    })
    // The business exists either way: a failed first turn is retried there.
    if (!turn.ok) redirect(`/start/${id}/interview?retry=${encodeURIComponent(text.slice(0, 600))}`)
  }
  redirect(`/start/${id}/interview${input.talk ? '?talk=1' : ''}`)
}

/** "meat shop", "gym", "dentist"… — deterministic search over LOCAH's taxonomy. */
export async function searchKinds(query: string): Promise<TaxonomyMatch[]> {
  const q = query.trim().slice(0, 80)
  if (q.length < 2) return []
  const token = (await getAccessToken()) || ''
  const res = await apiTry<{ data: TaxonomyMatch[] }>(
    `/v1/public/taxonomy/search?q=${encodeURIComponent(q)}`,
    token
  )
  return res.ok ? res.data.data : []
}
