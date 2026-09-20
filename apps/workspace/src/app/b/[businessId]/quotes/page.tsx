import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import {
  DataTable,
  EmptyState,
  FilterTabs,
  GateNotice,
  PageHeader,
  StatusPill,
} from '@/components/ui'
import { daysUntil, money, quoteRef, validityDate, statusLabel, STATUS_TONE, type QuoteRow } from './shared'

export const dynamic = 'force-dynamic'

type CustomerRow = { id: string; display_name: string }

/** The states worth filtering by, in the order a quote moves through them. */
const FILTERS = [
  { value: '', label: 'All' },
  { value: 'draft', label: 'Draft' },
  { value: 'issued', label: 'Sent' },
  { value: 'accepted', label: 'Accepted' },
  { value: 'rejected', label: 'Declined' },
  { value: 'cancelled', label: 'Cancelled' },
]

/**
 * Quotations — the list.
 *
 * A quote is a priced offer the business is held to, so the two things that
 * matter at a glance are what it is worth and whether the customer can still
 * accept it. Both lead the row.
 */
export default async function QuotesPage({
  params,
  searchParams,
}: {
  params: { businessId: string }
  searchParams?: { status?: string; q?: string }
}) {
  const token = await getAccessToken()
  if (!token) redirect(`/login?destination=${encodeURIComponent(`/b/${params.businessId}/quotes`)}`)

  const base = `/b/${params.businessId}/quotes`
  const status = (searchParams?.status || '').trim()
  const search = (searchParams?.q || '').trim().toLowerCase()

  // `status` filters on the stored value; an issued quote past its validity is
  // reported as expired but is still stored as issued, so "Sent" legitimately
  // includes it and the row says which it is.
  const qs = status ? `?status=${encodeURIComponent(status)}&limit=200` : '?limit=200'
  const [res, customersRes] = await Promise.all([
    apiTry<{ data: { quotes: QuoteRow[] } }>(
      `/v1/platform/businesses/${params.businessId}/quotes${qs}`,
      token
    ),
    apiTry<{ data: CustomerRow[] }>(
      `/v1/platform/businesses/${params.businessId}/customers`,
      token
    ),
  ])

  if (!res.ok) {
    return (
      <div>
        <PageHeader title="Quotes" />
        <GateNotice error={res.error} businessId={params.businessId} moduleLabel="Quotations" />
      </div>
    )
  }

  const all = res.data.data.quotes || []
  // Customer names are a separate module's data; when it is not readable the
  // list still works, it just shows no name rather than an error.
  const names = new Map(
    (customersRes.ok ? customersRes.data.data || [] : []).map((c) => [c.id, c.display_name])
  )

  const quotes = search
    ? all.filter((q) => {
        const customer = q.customer_contact_id ? names.get(q.customer_contact_id) || '' : ''
        return (
          q.quote_number.toLowerCase().includes(search) ||
          (q.title || '').toLowerCase().includes(search) ||
          customer.toLowerCase().includes(search)
        )
      })
    : all

  const openValue = all
    .filter((q) => q.status === 'issued')
    .reduce((sum, q) => sum + Number(q.total || 0), 0)
  const currency = all[0]?.currency || 'INR'

  return (
    <div>
      <PageHeader
        title="Quotes"
        subtitle={
          all.length > 0
            ? `${all.length} in total · ${money(openValue, currency)} awaiting a decision`
            : 'Priced offers your customers can accept.'
        }
        actions={
          <Link href={`${base}/new`} className="btn">
            New quote
          </Link>
        }
      />

      <FilterTabs
        current={status}
        hrefFor={(v) => (v ? `${base}?status=${v}` : base)}
        options={FILTERS.map((f) => ({
          ...f,
          count: f.value ? all.filter((q) => q.stored_status === f.value).length : all.length,
        }))}
      />

      <form method="get" style={{ margin: '0 0 1.1rem', display: 'flex', gap: '0.5rem' }}>
        {status ? <input type="hidden" name="status" value={status} /> : null}
        <input
          type="search"
          name="q"
          defaultValue={searchParams?.q || ''}
          placeholder="Search by number, title or customer"
          aria-label="Search quotes"
          style={{ maxWidth: '22rem' }}
        />
        <button type="submit" className="btn btn-ghost">
          Search
        </button>
      </form>

      <DataTable
        rows={quotes}
        rowKey={(q) => q.id}
        empty={
          <EmptyState
            title={
              all.length === 0 ? 'No quotes yet' : 'Nothing matches that'
            }
            action={
              all.length === 0 ? (
                <Link href={`${base}/new`} className="btn">
                  Write your first quote
                </Link>
              ) : (
                <Link href={base} className="btn btn-ghost">
                  Clear filters
                </Link>
              )
            }
          >
            {all.length === 0
              ? 'A quote is a priced offer with a validity date. Send one and the customer can accept it from a link — no account needed.'
              : 'Try a different status, or clear the search.'}
          </EmptyState>
        }
        columns={[
          {
            key: 'quote',
            header: 'Quote',
            render: (q) => (
              <Link href={`${base}/${q.id}`} style={{ fontWeight: 600 }}>
                {quoteRef(q)}
              </Link>
            ),
          },
          {
            key: 'for',
            header: 'For',
            render: (q) => (
              <span>
                {q.customer_contact_id ? names.get(q.customer_contact_id) || 'Customer' : '—'}
                {q.title ? (
                  <span style={{ display: 'block', color: 'var(--color-muted)', fontSize: '0.85rem' }}>
                    {q.title}
                  </span>
                ) : null}
              </span>
            ),
          },
          {
            key: 'status',
            header: 'Status',
            render: (q) => (
              <StatusPill value={statusLabel(q.status)} tone={STATUS_TONE[q.status]} />
            ),
          },
          {
            key: 'valid',
            header: 'Valid until',
            render: (q) => <ValidUntil quote={q} />,
          },
          {
            key: 'total',
            header: 'Total',
            align: 'num',
            render: (q) => <strong>{money(q.total, q.currency)}</strong>,
          },
        ]}
      />
    </div>
  )
}

/**
 * The validity date, with the urgency attached.
 *
 * A date alone makes the reader do arithmetic. What they actually want to know
 * is whether this one is about to lapse.
 */
function ValidUntil({ quote }: { quote: QuoteRow }) {
  if (!quote.valid_until) return <span style={{ color: 'var(--color-muted)' }}>—</span>
  const days = daysUntil(quote.valid_until)
  const urgent = quote.status === 'issued' && days !== null && days <= 3
  return (
    <span>
      {validityDate(quote.valid_until)}
      {quote.status === 'issued' && days !== null ? (
        <span
          style={{
            display: 'block',
            fontSize: '0.82rem',
            color: urgent ? 'var(--color-danger, #b3261e)' : 'var(--color-muted)',
          }}
        >
          {days < 0 ? 'lapsed' : days === 0 ? 'today' : `${days} day${days === 1 ? '' : 's'} left`}
        </span>
      ) : null}
    </span>
  )
}
