'use server'

import { getAccessToken } from '@/lib/supabase/access-token'

/** A fresh API token for the counter, read from the signed-in session. */
export async function posToken(): Promise<string | null> {
  return getAccessToken()
}
