import { getAccessToken } from '@/lib/supabase/access-token'
import { listMyBusinesses, type BusinessSummary } from '@/lib/platform-api'
import { platformUrl } from '@platform/config'

/** Who is looking, for the nav's account menu. Best-effort: a failure is a
 *  signed-out nav, never a broken page. */
export async function getNavAccount(): Promise<{
  token: string | null
  signedIn: boolean
  businesses: BusinessSummary[]
}> {
  const token = await getAccessToken().catch(() => null)
  if (!token) return { token: null, signedIn: false, businesses: [] }
  const businesses = await listMyBusinesses(token)
    .then((bs) => bs.filter((b) => b.state !== 'closed'))
    .catch(() => [] as BusinessSummary[])
  return { token, signedIn: true, businesses }
}

/** Businesses this person has booked with, for "Book again". Bookings are the
 *  only activity LOCAH records against a customer account today. */
export async function getBookedBusinessIds(token: string | null): Promise<string[]> {
  if (!token) return []
  try {
    const res = await fetch(`${platformUrl('api')}/v1/me/activity?resource_type=booking&limit=50`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: 'no-store',
    })
    if (!res.ok) return []
    const json = (await res.json()) as { data?: Array<{ business_id?: string }> }
    const ids = (json.data || []).map((a) => a.business_id).filter((id): id is string => Boolean(id))
    return Array.from(new Set(ids)).slice(0, 20)
  } catch {
    return []
  }
}
