import { NextResponse } from 'next/server'
import { platformUrl } from '@platform/config'
import { getAccessToken } from '@/lib/supabase/access-token'

export const dynamic = 'force-dynamic'

export async function GET(_request: Request, { params }: { params: { photoId: string } }) {
  const token = await getAccessToken()
  if (!token) return new NextResponse(null, { status: 401 })
  const res = await fetch(`${platformUrl('api')}/v1/admin/reviews/photos/${encodeURIComponent(params.photoId)}`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: 'no-store',
  })
  if (!res.ok) return new NextResponse(null, { status: res.status })
  return new NextResponse(await res.arrayBuffer(), {
    headers: { 'Content-Type': res.headers.get('content-type') || 'application/octet-stream', 'Cache-Control': 'no-store, private', 'X-Robots-Tag': 'noindex, nofollow' },
  })
}
