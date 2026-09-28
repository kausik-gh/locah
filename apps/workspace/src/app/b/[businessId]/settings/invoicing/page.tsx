import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import { GateNotice, PageHeader } from '@/components/ui'
import { InvoicingSetup } from './InvoicingSetup'
import type { Setup } from '../../invoices/types'

export const dynamic = 'force-dynamic'

/**
 * Tax & invoicing (Capability Universe §14.4): how this business bills. Every
 * answer here is the owner's or their CA's — LOCAH computes, it does not
 * advise — and anything touching tax treatment says so.
 */
export default async function InvoicingSettingsPage({ params }: { params: { businessId: string } }) {
  const token = await getAccessToken()
  if (!token) redirect('/login')
  const b = params.businessId
  const res = await apiTry<{ data: Setup }>(`/v1/platform/businesses/${b}/invoicing/setup`, token)
  const header = (
    <PageHeader
      title="Tax & invoicing"
      breadcrumb={<Link href={`/b/${b}/settings`}>← Settings</Link>}
      subtitle="How you bill: your GST registration, your billing counters and how prices are taxed. LOCAH works out the numbers; the choices are yours and your CA's."
    />
  )
  if (!res.ok) {
    return <div className="bos-page">{header}<GateNotice error={res.error} businessId={b} moduleLabel="Invoices & GST" /></div>
  }
  return (
    <div className="bos-page">
      {header}
      <InvoicingSetup businessId={b} setup={res.data.data} />
    </div>
  )
}
