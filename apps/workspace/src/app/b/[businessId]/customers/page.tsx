import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import { DataTable, EmptyState, FilterTabs, GateNotice, PageHeader, Section, StatusPill } from '@/components/ui'
import { createCustomer } from './actions'

export const dynamic = 'force-dynamic'

type CustomerRow = {
  id: string
  display_name: string
  email: string | null
  phone: string | null
  status: string
}

/**
 * Doc 11 §9 Customer Relationships. Business-owned customer records (Doc 05
 * CUS-001) — distinct from platform identities.
 */
export default async function CustomersPage({
  params,
  searchParams,
}: {
  params: { businessId: string }
  searchParams?: { status?: string }
}) {
  const token = await getAccessToken()
  if (!token) redirect('/login')
  const base = `/b/${params.businessId}`
  const qs = searchParams?.status ? `?status=${encodeURIComponent(searchParams.status)}` : ''
  const res = await apiTry<{ data: CustomerRow[] }>(
    `/v1/platform/businesses/${params.businessId}/customers${qs}`,
    token
  )
  if (!res.ok) {
    return (
      <div>
        <PageHeader title="Customers" />
        <GateNotice error={res.error} businessId={params.businessId} moduleLabel="Customers" />
      </div>
    )
  }
  const customers = res.data.data || []

  return (
    <div>
      <PageHeader
        title="Customers"
        subtitle="This business's own customer records — separate from platform accounts."
      />
      <FilterTabs
        current={searchParams?.status}
        hrefFor={(v) => `${base}/customers${v ? `?status=${v}` : ''}`}
        options={[
          { value: '', label: 'All' },
          { value: 'active', label: 'Active' },
          { value: 'blocked', label: 'Blocked' },
          { value: 'archived', label: 'Archived' },
        ]}
      />
      <DataTable
        rows={customers}
        rowKey={(c) => c.id}
        columns={[
          {
            key: 'name',
            header: 'Name',
            render: (c) => <Link href={`${base}/customers/${c.id}`}>{c.display_name}</Link>,
          },
          { key: 'email', header: 'Email', render: (c) => c.email || '—' },
          { key: 'phone', header: 'Phone', render: (c) => c.phone || '—' },
          { key: 'status', header: 'Status', render: (c) => <StatusPill value={c.status} /> },
        ]}
        empty={
          <EmptyState title="No customer records yet">
            A record is created the first time someone orders or books. You can also add one below.
          </EmptyState>
        }
      />

      <Section title="Add a customer">
        <form action={createCustomer} style={{ display: 'grid', gap: '0.6rem', maxWidth: '32rem' }}>
          <input type="hidden" name="businessId" value={params.businessId} />
          <input name="display_name" placeholder="Name" required />
          <input name="email" type="email" placeholder="Email" />
          <input name="phone" placeholder="Phone" />
          <button type="submit" style={{ justifySelf: 'start' }}>
            Add customer
          </button>
        </form>
      </Section>
    </div>
  )
}
