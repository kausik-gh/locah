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

type LoyaltyProgram = {
  id: string
  name: string
  program_type: string
  points_per_rupee: number
  redemption_rupees_per_point: number
  min_redemption_points: number
  expiry_days: number | null
  status: string
}

/**
 * Doc 11 §9.6 Loyalty & Rewards — LY-01 Points, LY-02 Stamps, LY-03 Referrals,
 * LY-04 Gift Vouchers. Owner-facing hub for the loyalty programme.
 */
export default async function LoyaltyPage({ params }: { params: { businessId: string } }) {
  const token = await getAccessToken()
  if (!token) redirect('/login')

  const base = `/v1/platform/businesses/${params.businessId}`
  const progRes = await apiTry<LoyaltyProgram>(`${base}/loyalty/program`, token)

  if (!progRes.ok) {
    return (
      <div>
        <PageHeader title="Loyalty & Rewards" />
        <GateNotice error={progRes.error} businessId={params.businessId} moduleLabel="Loyalty" />
      </div>
    )
  }

  const prog = progRes.data

  return (
    <div>
      <PageHeader
        title="Loyalty & Rewards"
        description="Points, stamp cards, referrals, and gift vouchers for your customers."
      />

      <Section title="Points programme">
        <TABLE>
          <thead>
            <tr>
              <TH>Name</TH>
              <TH>Type</TH>
              <TH>Earn rate</TH>
              <TH>Redeem rate</TH>
              <TH>Min to redeem</TH>
              <TH>Expiry</TH>
              <TH>Status</TH>
            </tr>
          </thead>
          <tbody>
            <ROW>
              <TD>{prog.name}</TD>
              <TD style={{ textTransform: 'capitalize' }}>{prog.program_type}</TD>
              <TD>{prog.points_per_rupee} pt / ₹1</TD>
              <TD>₹{prog.redemption_rupees_per_point} / pt</TD>
              <TD>{prog.min_redemption_points} pts</TD>
              <TD>{prog.expiry_days ? `${prog.expiry_days} days` : 'No expiry'}</TD>
              <TD>
                <StatusPill status={prog.status} />
              </TD>
            </ROW>
          </tbody>
        </TABLE>
      </Section>

      <Section title="How it works">
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: '1rem' }}>
          {[
            {
              icon: '⭐',
              title: 'Points',
              desc: `Customers earn ${prog.points_per_rupee} point per ₹1 spent. Redeem for discounts.`,
            },
            {
              icon: '🎟️',
              title: 'Stamp cards',
              desc: 'Get a stamp on every qualifying visit. Collect enough for a free reward.',
            },
            {
              icon: '👥',
              title: 'Referrals',
              desc: 'Customers share a unique link. Both referrer and referee earn bonus points.',
            },
            {
              icon: '🎁',
              title: 'Gift vouchers',
              desc: 'Issue prepaid value cards. Recipients redeem at checkout, balance never expires unless set.',
            },
          ].map((card) => (
            <div
              key={card.title}
              style={{
                padding: '1rem 1.25rem',
                borderRadius: 'var(--radius)',
                background: 'var(--color-surface-2)',
                border: '1px solid var(--color-border)',
              }}
            >
              <div style={{ fontSize: '1.5rem', marginBottom: '0.4rem' }}>{card.icon}</div>
              <div style={{ fontWeight: 600, marginBottom: '0.25rem' }}>{card.title}</div>
              <div style={{ fontSize: '0.85rem', color: 'var(--color-muted)' }}>{card.desc}</div>
            </div>
          ))}
        </div>
      </Section>

      <Section title="Issue a gift voucher">
        <EmptyState
          title="No vouchers issued yet"
          description="Sell prepaid gift vouchers to customers directly. Recipients can redeem them at checkout."
          action={{ label: 'Issue voucher', href: `#vouchers-form` }}
        />
      </Section>
    </div>
  )
}
