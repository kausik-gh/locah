'use server'

import { revalidatePath } from 'next/cache'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiPost } from '@/lib/api'

/**
 * Re-index one Business, as the signed-in Super Admin.
 *
 * The token comes from the session, never from the page. This surface used to
 * take a bearer token typed into a form field, which both bypassed the session
 * every other Admin page relies on and taught an operator to carry raw JWTs
 * around by hand.
 */
export async function reindexBusiness(formData: FormData) {
  const businessId = String(formData.get('businessId') || '')
  const token = await getAccessToken()
  if (!token) {
    throw new Error('Not signed in')
  }
  await apiPost(`/v1/admin/marketplace/indexing/${businessId}/reindex`, undefined, token)
  revalidatePath('/marketplace/indexing')
}
