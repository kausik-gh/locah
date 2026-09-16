import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import { Card, DataTable, EmptyState, FilterTabs, GateNotice, PageHeader, Section, StatusPill } from '@/components/ui'
import { adjustStock, setOpeningStock } from './actions'

export const dynamic = 'force-dynamic'

type InventoryRow = {
  id: string
  product_title: string
  product_sku: string | null
  quantity_on_hand: number
  quantity_reserved: number
  quantity_available: number
  stock_status: string
}
type LocationRow = { id: string; name: string; is_primary: boolean }

/** Doc 11 §7 Inventory — stock per offering per location. */
export default async function InventoryPage({
  params,
  searchParams,
}: {
  params: { businessId: string }
  searchParams?: { stock_status?: string }
}) {
  const token = await getAccessToken()
  if (!token) redirect('/login')

  const base = `/b/${params.businessId}`
  const qs = searchParams?.stock_status
    ? `?stock_status=${encodeURIComponent(searchParams.stock_status)}`
    : ''
  const [res, locRes] = await Promise.all([
    apiTry<{ data: InventoryRow[] }>(
      `/v1/platform/businesses/${params.businessId}/inventory${qs}`,
      token
    ),
    apiTry<{ data: LocationRow[] }>(
      `/v1/platform/businesses/${params.businessId}/locations`,
      token
    ),
  ])
  if (!res.ok) {
    return (
      <div>
        <PageHeader title="Inventory" />
        <GateNotice error={res.error} businessId={params.businessId} moduleLabel="Inventory" />
      </div>
    )
  }
  const records = res.data.data || []
  const locations = locRes.ok ? locRes.data.data || [] : []
  const lowCount = records.filter((r) => r.stock_status !== 'in_stock').length

  return (
    <div>
      <PageHeader
        title="Inventory"
        subtitle="Stock on hand, reserved, and available for each tracked offering."
      />

      {lowCount > 0 ? (
        <Card tone="urgent" style={{ marginBottom: '1.25rem' }}>
          <strong>{lowCount}</strong> {lowCount === 1 ? 'item needs' : 'items need'} restocking.
        </Card>
      ) : null}

      <FilterTabs
        current={searchParams?.stock_status}
        hrefFor={(v) => `${base}/inventory${v ? `?stock_status=${v}` : ''}`}
        options={[
          { value: '', label: 'All' },
          { value: 'in_stock', label: 'In stock' },
          { value: 'low_stock', label: 'Low stock' },
          { value: 'out_of_stock', label: 'Out of stock' },
        ]}
      />

      <DataTable
        rows={records}
        rowKey={(r) => r.id}
        columns={[
          { key: 'offering', header: 'Offering', render: (r) => r.product_title },
          { key: 'sku', header: 'SKU', render: (r) => r.product_sku || '—' },
          { key: 'on_hand', header: 'On hand', align: 'num', render: (r) => r.quantity_on_hand },
          { key: 'reserved', header: 'Reserved', align: 'num', render: (r) => r.quantity_reserved },
          { key: 'available', header: 'Available', align: 'num', render: (r) => r.quantity_available },
          { key: 'status', header: 'Status', render: (r) => <StatusPill value={r.stock_status} /> },
        ]}
        empty={
          <EmptyState title="No tracked stock yet">
            Inventory appears once an offering has stock tracking on and an opening count set.
          </EmptyState>
        }
      />

      <div style={{ display: 'flex', gap: '2rem', flexWrap: 'wrap', marginTop: '1.5rem' }}>
        <Section title="Set opening stock" style={{ marginTop: 0, minWidth: '20rem' }}>
          <form action={setOpeningStock} style={{ display: 'grid', gap: '0.6rem' }}>
            <input type="hidden" name="businessId" value={params.businessId} />
            <input name="offering_id" placeholder="Offering ID" required />
            <select name="location_id" required>
              {locations.map((loc) => (
                <option key={loc.id} value={loc.id}>
                  {loc.name}
                  {loc.is_primary ? ' (primary)' : ''}
                </option>
              ))}
            </select>
            <input name="quantity" type="number" min="0" placeholder="Quantity" required />
            <button type="submit" style={{ justifySelf: 'start' }}>
              Set opening stock
            </button>
          </form>
        </Section>

        <Section title="Adjust stock" style={{ marginTop: 0, minWidth: '20rem' }}>
          <form action={adjustStock} style={{ display: 'grid', gap: '0.6rem' }}>
            <input type="hidden" name="businessId" value={params.businessId} />
            <input name="offering_id" placeholder="Offering ID" required />
            <select name="location_id" required>
              {locations.map((loc) => (
                <option key={loc.id} value={loc.id}>
                  {loc.name}
                  {loc.is_primary ? ' (primary)' : ''}
                </option>
              ))}
            </select>
            <input name="quantity_delta" type="number" placeholder="Change (+ or −)" required />
            <input name="reason" placeholder="Reason" required />
            <button type="submit" style={{ justifySelf: 'start' }}>
              Adjust
            </button>
          </form>
        </Section>
      </div>
    </div>
  )
}
