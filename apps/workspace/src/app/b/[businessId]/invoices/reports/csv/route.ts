import { NextResponse, type NextRequest } from 'next/server'
import { getAccessToken } from '@/lib/supabase/access-token'
import { platformUrl } from '@platform/config'

const KINDS = new Set(['sales_register', 'hsn_summary', 'tax_by_rate', 'gstr1', 'documents'])

/** A CA report as CSV, fetched as the signed-in person (needs invoices.export). */
export async function GET(req: NextRequest, { params }: { params: { businessId: string } }) {
  const token = await getAccessToken()
  if (!token) return NextResponse.redirect(new URL('/login', req.url))
  const q = req.nextUrl.searchParams
  const kind = q.get('kind') ?? ''
  if (!KINDS.has(kind)) return new NextResponse('Unknown report', { status: 404 })
  const range = new URLSearchParams()
  if (q.get('from')) range.set('from', q.get('from') as string)
  if (q.get('to')) range.set('to', q.get('to') as string)
  const res = await fetch(
    `${platformUrl('api')}/v1/platform/businesses/${params.businessId}/invoicing/reports/${kind}.csv?${range}`,
    { headers: { Authorization: `Bearer ${token}` }, cache: 'no-store' },
  )
  if (!res.ok) return new NextResponse('This report could not be exported.', { status: res.status })
  return new NextResponse(res.body, {
    headers: {
      'Content-Type': 'text/csv; charset=utf-8',
      'Content-Disposition': res.headers.get('content-disposition') ?? `attachment; filename="${kind}.csv"`,
      'Cache-Control': 'private, no-store',
    },
  })
}
