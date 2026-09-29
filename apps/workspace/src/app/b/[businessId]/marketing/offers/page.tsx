import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import {
  EmptyState,
  GateNotice,
  PageHeader,
  Section,
  StatusPill,
  TABLE,
  TH,
  TD,
  ROW,
} from '@/components/ModuleState'

export const dynamic = 'force-dynamic'

type Offer = {
  id: string
  code: string
  name: string
  kind: string
  discount_value: number
  min_order_amount_paise: number
  max_discount_paise: number | null
  times_used: number
  status: string
}

function offerKindLabel(kind: string): string {
  const labels: Record<string, string> = {
    percentage_discount: 'Percentage off',
    flat_discount: 'Flat off',
    free_delivery: 'Free delivery',
    buy_x_get_y: 'Buy X get Y',
    free_item: 'Free item',
  }
  return labels[kind] ?? kind
}

function fmtDiscount(offer: Offer): string {
  if (offer.kind === 'percentage_discount') return `${offer.discount_value}%`
  if (offer.kind === 'flat_discount') return `₹${offer.discount_value}`
  return String(offer.discount_value)
}

/**
 * Doc 11 §9.7 Marketing Offers (MK-07). Coupon codes and discount offers
 * that can be attached to marketing campaigns or shared directly.
 */
export default async function OffersPage({ params }: { params: { businessId: string } }) {
  const token = await getAccessToken()
  if (!token) redirect('/login')

  const base = `/v1/platform/businesses/${params.businessId}`
  const offersRes = await apiTry<{ offers: Offer[] }>(`${base}/marketing/offers`, token)

  if (!offersRes.ok) {
    return (
      <div>
        <PageHeader title="Offers & Coupons" />
        <GateNotice error={offersRes.error} businessId={params.businessId} moduleLabel="Marketing" />
      </div>
    )
  }

  const offers = offersRes.data.offers ?? []

  return (
    <div>
      <PageHeader
        title="Offers & Coupons"
        description="Coupon codes and discount offers you can attach to campaigns or share directly."
        action={{ label: 'New offer', href: `/b/${params.businessId}/marketing/offers/new` }}
      />

      <Section title="Active offers">
        {offers.length === 0 ? (
          <EmptyState
            title="No offers yet"
            description="Create a coupon code or discount offer to attach to a campaign or share with customers."
            action={{ label: 'New offer', href: `/b/${params.businessId}/marketing/offers/new` }}
          />
        ) : (
          <TABLE>
            <thead>
              <tr>
                <TH>Code</TH>
                <TH>Name</TH>
                <TH>Type</TH>
                <TH>Discount</TH>
                <TH>Min order</TH>
                <TH>Times used</TH>
                <TH>Status</TH>
              </tr>
            </thead>
            <tbody>
              {offers.map((o) => (
                <ROW key={o.id}>
                  <TD>
                    <code
                      style={{
                        background: 'var(--color-surface-2)',
                        padding: '0.1rem 0.4rem',
                        borderRadius: 'var(--radius-sm)',
                        fontSize: '0.85rem',
                        fontFamily: 'monospace',
                      }}
                    >
                      {o.code}
                    </code>
                  </TD>
                  <TD>{o.name}</TD>
                  <TD>{offerKindLabel(o.kind)}</TD>
                  <TD>{fmtDiscount(o)}</TD>
                  <TD>
                    {o.min_order_amount_paise > 0
                      ? `₹${(o.min_order_amount_paise / 100).toFixed(0)}+`
                      : 'No minimum'}
                  </TD>
                  <TD>{o.times_used}</TD>
                  <TD>
                    <StatusPill status={o.status} />
                  </TD>
                </ROW>
              ))}
            </tbody>
          </TABLE>
        )}
      </Section>
    </div>
  )
}
