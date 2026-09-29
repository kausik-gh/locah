import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import { GateNotice, PageHeader } from '@/components/ui'
import { RateBoard, type Rate } from './RateBoard'

export const dynamic = 'force-dynamic'

/**
 * Today's rates (OK-15; MD §21.2 "a daily rate board"): the rates the owner
 * enters each morning — 22K gold, silver — and every item priced from them.
 * Entering a rate re-prices those items for the next sale; sales already made
 * keep the rate they were sold at.
 */
export default async function RatesPage({ params }: { params: { businessId: string } }) {
  const token = await getAccessToken()
  if (!token) redirect('/login')
  const res = await apiTry<{ data: Rate[] }>(`/v1/platform/businesses/${params.businessId}/pricing/rates`, token)
  const back = <Link href={`/b/${params.businessId}/offerings`}>Products & services</Link>
  const header = (
    <PageHeader
      title="Today's rates"
      subtitle="Enter the day's rate each morning. Items priced from it change for the next sale; sales already made keep their rate."
      breadcrumb={back}
    />
  )
  if (!res.ok) {
    return (
      <div className="bos-page">
        {header}
        <GateNotice error={res.error} businessId={params.businessId} moduleLabel="Products & services" />
      </div>
    )
  }
  return (
    <div className="bos-page">
      {header}
      <RateBoard businessId={params.businessId} rates={res.data.data} />
    </div>
  )
}
