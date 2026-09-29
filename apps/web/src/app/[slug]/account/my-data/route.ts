import { platformUrl } from '@platform/config'
import { getAccessToken } from '@/lib/supabase/access-token'

/**
 * "Download my data" (DPDP right of access, MD §25.1): everything this business
 * keeps about the signed-in customer, as a file they can save.
 */
export async function GET(_request: Request, { params }: { params: { slug: string } }) {
  const token = await getAccessToken()
  if (!token) return new Response('Sign in first', { status: 401 })
  const res = await fetch(`${platformUrl('api')}/v1/me/businesses/${encodeURIComponent(params.slug)}/my-data`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: 'no-store',
  })
  if (!res.ok) return new Response('We could not prepare your data just now. Try again in a moment.', { status: res.status })
  const body = (await res.json()) as { data: unknown }
  return new Response(JSON.stringify(body.data, null, 2), {
    headers: {
      'Content-Type': 'application/json; charset=utf-8',
      'Content-Disposition': `attachment; filename="my-data-${params.slug}.json"`,
      'Cache-Control': 'no-store',
    },
  })
}
