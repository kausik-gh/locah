import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import { DataTable, EmptyState, FilterTabs, GateNotice, PageHeader, Section, StatusPill } from '@/components/ui'
import { updateBookingsPolicy } from './actions'
import { LocalTime } from '@/components/LocalTime'

export const dynamic = 'force-dynamic'

/** Doc 11 §4.2 Bookings — list/calendar + policies. */
export default async function BookingsPage({
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
  const [listRes, policyRes] = await Promise.all([
    apiTry<{ data: Array<Record<string, unknown>> }>(
      `/v1/platform/businesses/${params.businessId}/bookings${qs}`,
      token
    ),
    apiTry<{
      data: { require_deposit: boolean; deposit_amount: number | null; cancel_window_hours: number }
    }>(`/v1/platform/businesses/${params.businessId}/bookings-policy`, token),
  ])
  if (!listRes.ok) {
    return (
      <div>
        <PageHeader title="Bookings" />
        <GateNotice error={listRes.error} businessId={params.businessId} moduleLabel="Bookings" />
      </div>
    )
  }
  const bookings = listRes.data.data || []
  const policy = policyRes.ok
    ? policyRes.data.data
    : { require_deposit: false, deposit_amount: null, cancel_window_hours: 24 }

  async function savePolicy(formData: FormData) {
    'use server'
    await updateBookingsPolicy(params.businessId, {
      require_deposit: formData.get('require_deposit') === 'on',
      deposit_amount: formData.get('deposit_amount') ? Number(formData.get('deposit_amount')) : null,
      cancel_window_hours: Number(formData.get('cancel_window_hours') || 24),
    })
  }

  return (
    <div>
      <PageHeader title="Bookings" subtitle="Confirm or cancel reservations, and set the deposit and cancellation policy." />
      <FilterTabs
        current={searchParams?.status}
        hrefFor={(v) => `${base}/bookings${v ? `?status=${v}` : ''}`}
        options={[
          { value: '', label: 'All' },
          { value: 'pending', label: 'Pending' },
          { value: 'confirmed', label: 'Confirmed' },
          { value: 'completed', label: 'Completed' },
          { value: 'cancelled', label: 'Cancelled' },
        ]}
      />
      <DataTable
        rows={bookings}
        rowKey={(b) => String(b.id)}
        columns={[
          {
            key: 'booking',
            header: 'Booking',
            render: (b) => (
              <div>
                <Link href={`${base}/bookings/${b.id}`}>{String(b.booking_number)}</Link>
                <div style={{ color: 'var(--color-muted)', fontSize: '0.82rem' }}>{String(b.title)}</div>
              </div>
            ),
          },
          {
            key: 'when',
            header: 'When',
            align: 'num',
            render: (b) => <LocalTime value={b.starts_at as string | null} />,
          },
          {
            key: 'mode',
            header: 'Mode',
            render: (b) => <span style={{ textTransform: 'capitalize' }}>{String(b.reservation_mode)}</span>,
          },
          { key: 'status', header: 'Status', render: (b) => <StatusPill value={String(b.status)} /> },
          {
            key: 'payment',
            header: 'Payment',
            render: (b) => <span style={{ color: 'var(--color-muted)' }}>{String(b.payment_status)}</span>,
          },
        ]}
        empty={
          <EmptyState title="No bookings here">
            {searchParams?.status
              ? `Nothing with status "${searchParams.status}".`
              : 'Reservations made on your website appear here for you to confirm.'}
          </EmptyState>
        }
      />

      <Section title="Booking policy">
        <form action={savePolicy} style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <label style={{ display: 'flex', gap: '0.4rem', alignItems: 'center', color: 'var(--color-foreground)' }}>
            <input type="checkbox" name="require_deposit" defaultChecked={policy.require_deposit} style={{ minHeight: 'auto' }} />
            Require a deposit
          </label>
          <label style={{ display: 'grid', gap: '0.2rem' }}>
            Deposit amount
            <input name="deposit_amount" type="number" step="0.01" defaultValue={policy.deposit_amount ?? ''} />
          </label>
          <label style={{ display: 'grid', gap: '0.2rem' }}>
            Cancellation window (hours)
            <input name="cancel_window_hours" type="number" defaultValue={policy.cancel_window_hours} />
          </label>
          <button type="submit">Save policy</button>
        </form>
      </Section>
    </div>
  )
}
