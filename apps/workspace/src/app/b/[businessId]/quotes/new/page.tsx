import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import { GateNotice, PageHeader } from '@/components/ui'
import { QuoteEditor } from '../QuoteEditor'
import { createQuote } from '../actions'

export const dynamic = 'force-dynamic'

type Customer = { id: string; display_name: string; email?: string | null; phone?: string | null }
type Offering = {
  id: string
  title: string
  price_amount?: number | null
  tax_rate?: number | null
  unit_of_measure?: string | null
  status?: string | null
}

/**
 * Writing a new quote.
 *
 * The customer list and the catalogue come from their own modules. Either can be
 * switched off for this business, and neither is required to write a quote — a
 * one-off line and a name added later is a perfectly ordinary way to start. So
 * both are fetched permissively and an unavailable one simply means fewer
 * shortcuts, not a blocked page.
 */
export default async function NewQuotePage({ params }: { params: { businessId: string } }) {
  const token = await getAccessToken()
  if (!token) {
    redirect(`/login?destination=${encodeURIComponent(`/b/${params.businessId}/quotes/new`)}`)
  }

  const base = `/b/${params.businessId}/quotes`

  // The quotes list is read first and on its own: if quotes are gated, that is
  // the answer the page owes the reader, not a half-drawn editor.
  const gate = await apiTry<{ data: { quotes: unknown[] } }>(
    `/v1/platform/businesses/${params.businessId}/quotes?limit=1`,
    token
  )
  if (!gate.ok) {
    return (
      <div>
        <PageHeader title="New quote" />
        <GateNotice error={gate.error} businessId={params.businessId} moduleLabel="Quotations" />
      </div>
    )
  }

  const [customersRes, offeringsRes] = await Promise.all([
    apiTry<{ data: Customer[] }>(
      `/v1/platform/businesses/${params.businessId}/customers`,
      token
    ),
    apiTry<{ data: Offering[] }>(
      `/v1/platform/businesses/${params.businessId}/products?status=active`,
      token
    ),
  ])

  return (
    <div>
      <PageHeader
        title="New quote"
        subtitle="It stays a draft until you send it. Nothing reaches the customer before that."
        breadcrumb={<Link href={base}>← Quotes</Link>}
      />
      <QuoteEditor
        businessId={params.businessId}
        customers={customersRes.ok ? customersRes.data.data || [] : []}
        offerings={offeringsRes.ok ? offeringsRes.data.data || [] : []}
        action={createQuote}
        submitLabel="Create draft"
        cancelHref={base}
      />
    </div>
  )
}
