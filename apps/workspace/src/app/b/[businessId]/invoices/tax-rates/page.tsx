import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import { GateNotice, PageHeader } from '@/components/ui'
import { RatesEditor, type RateData } from './RatesEditor'

export const dynamic = 'force-dynamic'

/**
 * Tax rates (Capability Universe §14.4: "Rates are data: stored per offering
 * or HSN with effective dates, because the GST Council revises them. Never
 * hard-coded."). LOCAH ships no rates; the owner or their CA enters them.
 */
export default async function TaxRatesPage({ params }: { params: { businessId: string } }) {
  const token = await getAccessToken()
  if (!token) redirect('/login')
  const b = params.businessId
  const res = await apiTry<{ data: RateData }>(`/v1/platform/businesses/${b}/invoicing/tax-rates`, token)
  const header = (
    <PageHeader
      title="Tax rates"
      breadcrumb={<Link href={`/b/${b}/invoices`}>← Bills & invoices</Link>}
      subtitle="The GST rates your bills charge, from the dates they apply. You or your CA set them — LOCAH never guesses a rate."
    />
  )
  if (!res.ok) {
    return <div className="bos-page">{header}<GateNotice error={res.error} businessId={b} moduleLabel="Invoices & GST" /></div>
  }
  return (
    <div className="bos-page">
      {header}
      <RatesEditor businessId={b} data={res.data.data} />
    </div>
  )
}
