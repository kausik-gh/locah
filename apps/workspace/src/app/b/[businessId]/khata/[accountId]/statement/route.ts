import { NextResponse, type NextRequest } from 'next/server'
import { getAccessToken } from '@/lib/supabase/access-token'
import { platformUrl } from '@platform/config'

/** The account's statement PDF for a period, fetched as the signed-in person. */
export async function GET(req: NextRequest, { params }: { params: { businessId: string; accountId: string } }) {
  const token = await getAccessToken()
  if (!token) return NextResponse.redirect(new URL('/login', req.url))
  const q = new URLSearchParams()
  for (const k of ['from', 'to']) {
    const v = req.nextUrl.searchParams.get(k)
    if (v && /^\d{4}-\d{2}-\d{2}$/.test(v)) q.set(k, v)
  }
  const res = await fetch(
    `${platformUrl('api')}/v1/platform/businesses/${params.businessId}/ledger/accounts/${params.accountId}/statement.pdf?${q}`,
    { headers: { Authorization: `Bearer ${token}` }, cache: 'no-store' },
  )
  if (!res.ok) return new NextResponse('This statement could not be opened.', { status: res.status })
  return new NextResponse(res.body, {
    headers: {
      'Content-Type': 'application/pdf',
      'Content-Disposition': res.headers.get('content-disposition') ?? 'inline',
      'Cache-Control': 'private, no-store',
    },
  })
}
