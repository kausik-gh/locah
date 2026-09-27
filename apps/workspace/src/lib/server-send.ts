import { getAccessToken } from '@/lib/supabase/access-token'
import { platformUrl } from '@platform/config'

const apiUrl = platformUrl('api')

export type ActionResult<T = unknown> = { ok: true; data?: T } | { ok: false; message: string }

/**
 * One JSON call to the platform API as the signed-in person, for server
 * actions. The API decides what they may do; this only carries their token
 * and turns a refusal into a sentence the page can show.
 */
export async function sendJson<T = unknown>(path: string, method: string, body?: unknown): Promise<ActionResult<T>> {
  const token = await getAccessToken()
  if (!token) return { ok: false, message: 'Your session ended. Sign in again.' }
  const res = await fetch(`${apiUrl}${path}`, {
    method,
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: 'no-store',
  })
  let payload: { data?: T; error?: { message?: string } } | null = null
  try {
    payload = await res.json()
  } catch {
    /* empty or non-JSON body */
  }
  if (res.ok) return { ok: true, data: payload?.data }
  return { ok: false, message: payload?.error?.message ?? 'That did not save. Try again.' }
}
