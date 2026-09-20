import Link from 'next/link'
import { redirect } from 'next/navigation'
import { platformUrl } from '@platform/config'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import { Card, GateNotice, PageHeader, StatusPill } from '@/components/ui'
import { LocalTime } from '@/components/LocalTime'
import { QuoteEditor } from '../QuoteEditor'
import { ShareLink as ShareLinkPanel } from './ShareLink'
import {
  cancelQuote,
  issueQuote,
  recordQuoteDecision,
  reviseQuote,
  saveQuoteDraft,
} from '../actions'
import {
  availableActions,
  daysUntil,
  money,
  qty,
  quoteRef,
  statusLabel,
  validityDate,
  STATUS_TONE,
  type QuoteRow,
} from '../shared'

export const dynamic = 'force-dynamic'

type Customer = { id: string; display_name: string; email?: string | null; phone?: string | null }
type Offering = {
  id: string
  title: string
  price_amount?: number | null
  tax_rate?: number | null
  unit_of_measure?: string | null
}

/**
 * One quote.
 *
 * A draft is a thing being written, so it opens as the editor. Everything after
 * issuing is a commitment already made, so it opens as the document — the same
 * figures the customer is looking at — with the actions that are still open to
 * the business beside it. The two are not the same page wearing different
 * clothes: what an owner needs from a draft and from a sent quote is different.
 */
export default async function QuoteDetailPage({
  params,
}: {
  params: { businessId: string; quoteId: string }
}) {
  const token = await getAccessToken()
  if (!token) {
    redirect(
      `/login?destination=${encodeURIComponent(`/b/${params.businessId}/quotes/${params.quoteId}`)}`
    )
  }

  const base = `/b/${params.businessId}/quotes`
  const apiBase = `/v1/platform/businesses/${params.businessId}/quotes/${params.quoteId}`

  const res = await apiTry<{ data: QuoteRow }>(apiBase, token)
  if (!res.ok) {
    return (
      <div>
        <PageHeader title="Quote" breadcrumb={<Link href={base}>← Quotes</Link>} />
        <GateNotice error={res.error} businessId={params.businessId} moduleLabel="Quotations" />
      </div>
    )
  }

  const quote = res.data.data
  const actions = availableActions(quote.status)

  const [customersRes, offeringsRes, shareRes] = await Promise.all([
    apiTry<{ data: Customer[] }>(`/v1/platform/businesses/${params.businessId}/customers`, token),
    actions.canEdit
      ? apiTry<{ data: Offering[] }>(
          `/v1/platform/businesses/${params.businessId}/products?status=active`,
          token
        )
      : Promise.resolve({ ok: false as const, error: { status: 0, code: 'SKIPPED', message: '' } }),
    // The share credential is fetched only when there is one to show. It is
    // never part of the quote payload, so it costs a deliberate request.
    actions.canShare
      ? apiTry<{ data: { token: string | null; expires_at: string | null } }>(
          `${apiBase}/share-link`,
          token
        )
      : Promise.resolve({ ok: false as const, error: { status: 0, code: 'SKIPPED', message: '' } }),
  ])

  const customers = customersRes.ok ? customersRes.data.data || [] : []
  const customer = quote.customer_contact_id
    ? customers.find((c) => c.id === quote.customer_contact_id)
    : undefined
  const shareToken = shareRes.ok ? shareRes.data.data?.token : null
  const shareUrl = shareToken ? platformUrl('web', `/q/${shareToken}`) : null

  return (
    <div>
      <PageHeader
        title={quoteRef(quote)}
        subtitle={quote.title || undefined}
        breadcrumb={<Link href={base}>← Quotes</Link>}
        actions={<StatusPill value={statusLabel(quote.status)} tone={STATUS_TONE[quote.status]} />}
      />

      <Summary quote={quote} customer={customer} />

      {actions.canEdit ? (
        <>
          <IssuePanel businessId={params.businessId} quote={quote} />
          <h2 style={{ fontSize: '1.05rem', margin: '1.75rem 0 0.75rem' }}>Edit this draft</h2>
          <QuoteEditor
            businessId={params.businessId}
            quote={quote}
            customers={customers}
            offerings={offeringsRes.ok ? offeringsRes.data.data || [] : []}
            action={saveQuoteDraft}
            submitLabel="Save draft"
            cancelHref={base}
          />
        </>
      ) : (
        <Document quote={quote} />
      )}

      {shareUrl ? (
        <Card style={{ marginTop: '1.5rem', display: 'grid', gap: '0.6rem' }}>
          <h2 style={{ fontSize: '1.05rem', margin: 0 }}>Customer link</h2>
          <p style={{ color: 'var(--color-muted)', margin: 0 }}>
            Send this to your customer. They can read the quote and accept or decline it without
            an account.
          </p>
          <ShareLinkPanel url={shareUrl} expiresAt={shareRes.ok ? shareRes.data.data?.expires_at : null} />
        </Card>
      ) : null}

      <LifecyclePanel businessId={params.businessId} quote={quote} />

      {quote.supersedes_quote_id ? (
        <p style={{ marginTop: '1.25rem', color: 'var(--color-muted)' }}>
          This replaces{' '}
          <Link href={`${base}/${quote.supersedes_quote_id}`}>an earlier version</Link>.
        </p>
      ) : null}
    </div>
  )
}

/* ------------------------------------------------------------------ summary */

function Summary({ quote, customer }: { quote: QuoteRow; customer?: Customer }) {
  const days = daysUntil(quote.valid_until)
  const facts: [string, React.ReactNode][] = [
    ['Customer', customer?.display_name || (quote.customer_contact_id ? 'Customer' : 'Not set')],
    [
      'Valid until',
      quote.valid_until ? (
        <>
          {validityDate(quote.valid_until)}
          {quote.status === 'issued' && days !== null ? (
            <span style={{ color: 'var(--color-muted)' }}>
              {' '}
              ({days < 0 ? 'lapsed' : days === 0 ? 'today' : `${days} days left`})
            </span>
          ) : null}
        </>
      ) : (
        'No expiry'
      ),
    ],
    ['Sent', quote.issued_at ? <LocalTime value={quote.issued_at} /> : 'Not yet'],
  ]
  if (quote.accepted_at) facts.push(['Accepted', <LocalTime key="a" value={quote.accepted_at} />])
  if (quote.rejected_at) facts.push(['Declined', <LocalTime key="r" value={quote.rejected_at} />])
  if (quote.cancelled_at) facts.push(['Cancelled', <LocalTime key="c" value={quote.cancelled_at} />])

  return (
    <Card style={{ display: 'grid', gap: '1rem' }}>
      <div
        style={{
          display: 'flex',
          gap: '1.5rem',
          flexWrap: 'wrap',
          alignItems: 'baseline',
          justifyContent: 'space-between',
        }}
      >
        <dl
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(10rem, 1fr))',
            gap: '0.9rem',
            margin: 0,
            flex: '1 1 24rem',
          }}
        >
          {facts.map(([label, value]) => (
            <div key={label}>
              <dt style={{ fontSize: '0.82rem', color: 'var(--color-muted)' }}>{label}</dt>
              <dd style={{ margin: '0.15rem 0 0' }}>{value}</dd>
            </div>
          ))}
        </dl>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: '0.82rem', color: 'var(--color-muted)' }}>Total</div>
          <div style={{ fontSize: '1.6rem', fontWeight: 650, fontVariantNumeric: 'tabular-nums' }}>
            {money(quote.total, quote.currency)}
          </div>
          {Number(quote.deposit_amount) > 0 ? (
            <div style={{ fontSize: '0.85rem', color: 'var(--color-muted)' }}>
              {money(quote.deposit_amount, quote.currency)} deposit
            </div>
          ) : null}
        </div>
      </div>
      {quote.decision_reason ? (
        <p style={{ margin: 0, color: 'var(--color-muted)' }}>
          Reason given: {quote.decision_reason}
        </p>
      ) : null}
    </Card>
  )
}

/* ----------------------------------------------------------------- document */

/** What was offered, as it stands. Read-only: these figures are the ones the
 *  business is already bound by. */
function Document({ quote }: { quote: QuoteRow }) {
  const items = quote.items || []
  const charges = quote.charges || []
  return (
    <Card style={{ marginTop: '1.25rem', display: 'grid', gap: '1rem' }}>
      <h2 style={{ fontSize: '1.05rem', margin: 0 }}>What was quoted</h2>
      <div className="ws-tablewrap">
        <table>
          <thead>
            <tr>
              <th>Item</th>
              <th data-num>Qty</th>
              <th data-num>Unit</th>
              <th data-num>Tax</th>
              <th data-num>Line total</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id}>
                <td>
                  {item.title || 'Item'}
                  {item.description ? (
                    <span style={{ display: 'block', color: 'var(--color-muted)', fontSize: '0.85rem' }}>
                      {item.description}
                    </span>
                  ) : null}
                </td>
                <td data-num>
                  {qty(item.quantity)}
                  {item.unit_label ? ` ${item.unit_label}` : ''}
                </td>
                <td data-num>{money(item.unit_price, quote.currency)}</td>
                <td data-num>{qty(item.tax_rate)}%</td>
                <td data-num>{money(item.line_total, quote.currency)}</td>
              </tr>
            ))}
            {charges.map((charge) => (
              <tr key={charge.id}>
                <td colSpan={4}>{charge.label}</td>
                <td data-num>{money(charge.amount, quote.currency)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <dl style={{ display: 'grid', gap: '0.35rem', margin: 0, maxWidth: '22rem', marginLeft: 'auto' }}>
        <Total label="Subtotal" value={money(quote.subtotal, quote.currency)} />
        {Number(quote.discount_amount) > 0 ? (
          <Total label="Discount" value={`− ${money(quote.discount_amount, quote.currency)}`} />
        ) : null}
        {Number(quote.charges_amount) > 0 ? (
          <Total label="Charges" value={money(quote.charges_amount, quote.currency)} />
        ) : null}
        {Number(quote.tax_amount) > 0 ? (
          <Total label="Tax" value={money(quote.tax_amount, quote.currency)} />
        ) : null}
        <Total label="Total" value={money(quote.total, quote.currency)} strong />
      </dl>

      {quote.terms ? (
        <section>
          <h3 style={{ fontSize: '0.95rem', margin: '0 0 0.35rem' }}>Terms</h3>
          <p style={{ margin: 0, whiteSpace: 'pre-wrap', color: 'var(--color-muted)' }}>
            {quote.terms}
          </p>
        </section>
      ) : null}
      {quote.notes ? (
        <section>
          <h3 style={{ fontSize: '0.95rem', margin: '0 0 0.35rem' }}>Notes</h3>
          <p style={{ margin: 0, whiteSpace: 'pre-wrap', color: 'var(--color-muted)' }}>
            {quote.notes}
          </p>
        </section>
      ) : null}
    </Card>
  )
}

function Total({ label, value, strong }: { label: string; value: string; strong?: boolean }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem' }}>
      <dt style={{ color: strong ? undefined : 'var(--color-muted)' }}>{label}</dt>
      <dd
        style={{
          margin: 0,
          fontVariantNumeric: 'tabular-nums',
          fontWeight: strong ? 650 : undefined,
          fontSize: strong ? '1.1rem' : undefined,
        }}
      >
        {value}
      </dd>
    </div>
  )
}

/* ------------------------------------------------------------------ actions */

function IssuePanel({ businessId, quote }: { businessId: string; quote: QuoteRow }) {
  return (
    <Card tone="urgent" style={{ marginTop: '1.25rem', display: 'grid', gap: '0.6rem' }}>
      <h2 style={{ fontSize: '1.05rem', margin: 0 }}>Send this quote</h2>
      <p style={{ color: 'var(--color-muted)', margin: 0 }}>
        Sending fixes the prices and creates the customer&apos;s link. After that the quote can be
        revised, but not edited.
      </p>
      <form
        action={issueQuote}
        style={{ display: 'flex', gap: '0.6rem', alignItems: 'end', flexWrap: 'wrap' }}
      >
        <input type="hidden" name="businessId" value={businessId} />
        <input type="hidden" name="quoteId" value={quote.id} />
        <label style={{ display: 'flex', flexDirection: 'column', gap: '0.3rem' }}>
          <span style={{ fontSize: '0.85rem', color: 'var(--color-muted)' }}>
            Valid for (days)
          </span>
          <input
            type="number"
            name="valid_days"
            min="1"
            max="365"
            placeholder={quote.valid_until ? 'Keep the date above' : '30'}
            style={{ width: '10rem' }}
          />
        </label>
        <button type="submit" className="btn">
          Send quote
        </button>
      </form>
    </Card>
  )
}

function LifecyclePanel({ businessId, quote }: { businessId: string; quote: QuoteRow }) {
  const actions = availableActions(quote.status)
  if (!actions.canDecide && !actions.canCancel && !actions.canRevise) return null

  return (
    <Card style={{ marginTop: '1.5rem', display: 'grid', gap: '1rem' }}>
      <h2 style={{ fontSize: '1.05rem', margin: 0 }}>Record what happened</h2>

      {actions.canDecide ? (
        <form
          action={recordQuoteDecision}
          style={{ display: 'grid', gap: '0.6rem', maxWidth: '34rem' }}
        >
          <input type="hidden" name="businessId" value={businessId} />
          <input type="hidden" name="quoteId" value={quote.id} />
          <p style={{ color: 'var(--color-muted)', margin: 0 }}>
            If the customer answered on the phone or in person, record it here. If they use their
            link instead, it lands by itself.
          </p>
          <div style={{ display: 'flex', gap: '0.6rem', flexWrap: 'wrap' }}>
            <input
              name="decided_by_name"
              placeholder="Who told you"
              style={{ flex: '1 1 12rem', minWidth: 0 }}
            />
            <input name="reason" placeholder="Reason (optional)" style={{ flex: '1 1 12rem', minWidth: 0 }} />
          </div>
          <div style={{ display: 'flex', gap: '0.6rem', flexWrap: 'wrap' }}>
            <button type="submit" name="decision" value="accepted" className="btn">
              They accepted
            </button>
            <button type="submit" name="decision" value="rejected" className="btn btn-ghost">
              They declined
            </button>
          </div>
        </form>
      ) : null}

      <div style={{ display: 'flex', gap: '0.6rem', flexWrap: 'wrap' }}>
        {actions.canRevise ? (
          <form action={reviseQuote}>
            <input type="hidden" name="businessId" value={businessId} />
            <input type="hidden" name="quoteId" value={quote.id} />
            <button type="submit" className="btn btn-ghost">
              Revise as a new version
            </button>
          </form>
        ) : null}
        {actions.canCancel ? (
          <form action={cancelQuote} style={{ display: 'flex', gap: '0.5rem' }}>
            <input type="hidden" name="businessId" value={businessId} />
            <input type="hidden" name="quoteId" value={quote.id} />
            <input name="reason" placeholder="Reason (optional)" />
            <button type="submit" className="btn btn-danger">
              Cancel quote
            </button>
          </form>
        ) : null}
      </div>
    </Card>
  )
}
