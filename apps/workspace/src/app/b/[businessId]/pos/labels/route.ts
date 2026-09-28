import { NextResponse, type NextRequest } from 'next/server'
import { getAccessToken } from '@/lib/supabase/access-token'
import { platformUrl } from '@platform/config'

/** Barcode labels for items (A4 sheet or 50 × 25 mm), fetched as the signed-in person. */
export async function GET(req: NextRequest, { params }: { params: { businessId: string } }) {
  const token = await getAccessToken()
  if (!token) return NextResponse.redirect(new URL('/login', req.url))
  const q = new URLSearchParams()
  for (const k of ['ids', 'copies', 'layout']) if (req.nextUrl.searchParams.get(k)) q.set(k, req.nextUrl.searchParams.get(k) as string)
  const res = await fetch(`${platformUrl('api')}/v1/platform/businesses/${params.businessId}/pos/labels?${q}`, {
    headers: { Authorization: `Bearer ${token}` }, cache: 'no-store',
  })
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    return new NextResponse(body?.error?.message ?? 'Labels could not be made.', { status: res.status })
  }
  return new NextResponse(res.body, { headers: { 'Content-Type': 'application/pdf', 'Content-Disposition': 'inline; filename="labels.pdf"', 'Cache-Control': 'private, no-store' } })
}
