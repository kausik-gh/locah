import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import { Card, GateNotice, PageHeader } from '@/components/ui'
import { BillForm, type CatalogueItem, type CustomerLite } from './BillForm'
import type { Bill, Setup } from '../types'

export const dynamic = 'force-dynamic'

/** Raise a bill directly — a business customer, a service, a walk-in without an order. */
export default async function NewBillPage({
  params,
  searchParams,
}: {
  params: { businessId: string }
  searchParams: { draft?: string }
}) {
  const token = await getAccessToken()
  if (!token) redirect('/login')
  const b = params.businessId
  const base = `/b/${b}/invoices`
  const [setup, items, customers, draft] = await Promise.all([
    apiTry<{ data: Setup }>(`/v1/platform/businesses/${b}/invoicing/setup`, token),
    apiTry<{ data: CatalogueItem[] }>(`/v1/platform/businesses/${b}/products`, token),
    apiTry<{ data: CustomerLite[] }>(`/v1/platform/businesses/${b}/customers?limit=200`, token),
    searchParams.draft
      ? apiTry<{ data: Bill }>(`/v1/platform/businesses/${b}/invoices/${searchParams.draft}`, token)
      : Promise.resolve(null),
  ])
  const header = (
    <PageHeader
      title={searchParams.draft ? 'Edit draft bill' : 'New bill'}
      breadcrumb={<Link href={base}>← Bills & invoices</Link>}
      subtitle="LOCAH works out the tax from your rates and numbers the bill when you issue it."
    />
  )
  if (!setup.ok) {
    return <div className="bos-page">{header}<GateNotice error={setup.error} businessId={b} moduleLabel="Invoices & GST" /></div>
  }
  const s = setup.data.data
  if (!s.profile || !s.registrations.length || !s.registers.some((r) => r.status === 'active')) {
    return (
      <div className="bos-page">
        {header}
        <Card tone="urgent" style={{ maxWidth: '44rem' }}>
          <h2 style={{ marginBottom: '.35rem' }}>Set up billing first</h2>
          <p className="bos-hint">Tell LOCAH how you bill and your GST registration (or that you are not registered), and add a billing register.</p>
          <Link className="btn" href={`/b/${b}/settings/invoicing`}>Open Tax & invoicing</Link>
        </Card>
      </div>
    )
  }
  return (
    <div className="bos-page">
      {header}
      <BillForm
        businessId={b}
        setup={s}
        items={items.ok ? items.data.data.filter((o) => o.status !== 'archived' && o.title !== 'Delivery fee') : []}
        customers={customers.ok ? customers.data.data : []}
        draft={draft && draft.ok && draft.data.data.status === 'draft' ? draft.data.data : null}
      />
    </div>
  )
}
