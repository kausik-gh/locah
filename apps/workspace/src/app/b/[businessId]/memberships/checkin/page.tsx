import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { PageHeader } from '@/components/ModuleState'
import { CheckinDesk } from './CheckinDesk'

export const dynamic = 'force-dynamic'

/**
 * Front desk (Founder refinement — Memberships §6): scan or type the member's
 * code and see at once whether they may come in — green, amber (in grace, if
 * the owner allows) or red — without searching invoices.
 */
export default async function CheckinPage({ params }: { params: { businessId: string } }) {
  const token = await getAccessToken()
  if (!token) redirect('/login')
  return (
    <div className="bos-page">
      <PageHeader
        title="Front desk check-in"
        subtitle="Scan the member's QR or type their code."
        breadcrumb={<Link href={`/b/${params.businessId}/memberships`}>← Members</Link>}
      />
      <CheckinDesk businessId={params.businessId} />
    </div>
  )
}
