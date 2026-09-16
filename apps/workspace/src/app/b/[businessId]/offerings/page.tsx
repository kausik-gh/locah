import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import { DataTable, EmptyState, GateNotice, PageHeader, Section, StatusPill } from '@/components/ui'
import { archiveOffering, createOffering, restoreOffering } from './actions'

export const dynamic = 'force-dynamic'

type Offering = {
  id: string
  title: string
  offering_type: string
  status: string
  price_amount: number | null
  currency: string
  track_inventory: boolean
}
type Category = { id: string; name: string; status: string }

/** Doc 11 §7 Offerings Catalog — what the business sells. */
export default async function OfferingsPage({ params }: { params: { businessId: string } }) {
  const token = await getAccessToken()
  if (!token) redirect('/login')

  const [res, catRes] = await Promise.all([
    apiTry<{ data: Offering[] }>(`/v1/platform/businesses/${params.businessId}/products`, token),
    apiTry<{ data: Category[] }>(
      `/v1/platform/businesses/${params.businessId}/product-categories`,
      token
    ),
  ])
  if (!res.ok) {
    return (
      <div>
        <PageHeader title="Offerings" />
        <GateNotice error={res.error} businessId={params.businessId} moduleLabel="the Offerings Catalog" />
      </div>
    )
  }
  const offerings = res.data.data || []
  const categories = catRes.ok ? catRes.data.data || [] : []

  return (
    <div>
      <PageHeader
        title="Offerings"
        subtitle="Everything this business sells or provides — products, services, and classes."
      />

      <DataTable
        rows={offerings}
        rowKey={(o) => o.id}
        columns={[
          { key: 'title', header: 'Title', render: (o) => o.title },
          {
            key: 'type',
            header: 'Type',
            render: (o) => (
              <span style={{ textTransform: 'capitalize', color: 'var(--color-muted)' }}>
                {o.offering_type.replace(/_/g, ' ')}
              </span>
            ),
          },
          { key: 'status', header: 'Status', render: (o) => <StatusPill value={o.status} /> },
          {
            key: 'price',
            header: 'Price',
            align: 'num',
            render: (o) => (o.price_amount === null ? '—' : `${o.currency} ${o.price_amount}`),
          },
          {
            key: 'stock',
            header: 'Stock tracked',
            render: (o) => (o.track_inventory ? 'Yes' : 'No'),
          },
          {
            key: 'action',
            header: '',
            render: (o) => (
              <form action={o.status === 'archived' ? restoreOffering : archiveOffering}>
                <input type="hidden" name="businessId" value={params.businessId} />
                <input type="hidden" name="offeringId" value={o.id} />
                <button type="submit" className="btn-quiet">
                  {o.status === 'archived' ? 'Restore' : 'Archive'}
                </button>
              </form>
            ),
          },
        ]}
        empty={
          <EmptyState title="Nothing in the catalog yet">
            Add your first offering below — it stays a draft until you mark it active, so nothing
            goes public before you are ready.
          </EmptyState>
        }
      />

      {categories.length > 0 ? (
        <Section title="Categories">
          <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
            {categories.map((c) => (
              <span
                key={c.id}
                style={{
                  padding: '0.2rem 0.7rem',
                  borderRadius: '999px',
                  border: '1px solid var(--color-border)',
                  background: 'var(--color-surface)',
                  fontSize: '0.85rem',
                }}
              >
                {c.name}
              </span>
            ))}
          </div>
        </Section>
      ) : null}

      <Section title="Add an offering">
        <form action={createOffering} style={{ display: 'grid', gap: '0.6rem', maxWidth: '32rem' }}>
          <input type="hidden" name="businessId" value={params.businessId} />
          <input name="title" placeholder="Title" required />
          <textarea name="description" placeholder="Description" />
          <select name="offering_type" defaultValue="product">
            <option value="product">Product</option>
            <option value="service">Service</option>
            <option value="class_session">Class or session</option>
          </select>
          <input name="price_amount" type="number" step="0.01" placeholder="Price" />
          <select name="status" defaultValue="draft">
            <option value="draft">Save as draft</option>
            <option value="active">Publish as active</option>
          </select>
          <button type="submit" style={{ justifySelf: 'start' }}>
            Add offering
          </button>
        </form>
      </Section>
    </div>
  )
}
