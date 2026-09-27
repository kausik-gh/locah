import { NextResponse, type NextRequest } from 'next/server'
import { getAccessToken } from '@/lib/supabase/access-token'
import { platformUrl } from '@platform/config'

/** The bill's PDF (A4 or 80 / 58 mm), fetched as the signed-in person. */
export async function GET(req: NextRequest, { params }: { params: { businessId: string; docId: string } }) {
  const token = await getAccessToken()
  if (!token) return NextResponse.redirect(new URL('/login', req.url))
  const layout = req.nextUrl.searchParams.get('layout') ?? 'a4'
  const res = await fetch(
    `${platformUrl('api')}/v1/platform/businesses/${params.businessId}/invoices/${params.docId}/pdf?layout=${encodeURIComponent(layout)}`,
    { headers: { Authorization: `Bearer ${token}` }, cache: 'no-store' },
  )
  if (!res.ok) return new NextResponse('This bill could not be opened.', { status: res.status })
  return new NextResponse(res.body, {
    headers: {
      'Content-Type': 'application/pdf',
      'Content-Disposition': res.headers.get('content-disposition') ?? 'inline',
      'Cache-Control': 'private, no-store',
    },
  })
}
