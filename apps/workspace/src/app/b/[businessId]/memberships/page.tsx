import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import {
  EmptyState,
  GateNotice,
  PageHeader,
  ROW,
  StatusPill,
  TABLE,
  TD,
  TH,
} from '@/components/ModuleState'
import { archivePlan, createPlan, transitionEnrolment } from './actions'

export const dynamic = 'force-dynamic'

type Plan = {
  id: string
  name: string
  description: string | null
  price_amount: number
  currency: string
  duration_days: number | null
  billing_model: string
  status: string
  visibility: string
}

type Enrolment = {
  id: string
  plan_id: string
  customer_contact_id: string
  status: string
  payment_status: string | null
  starts_at: string | null
  ends_at: string | null
}

const ENROLMENT_ACTIONS: Record<string, Array<{ action: string; label: string }>> = {
  active: [
    { action: 'pause', label: 'Pause' },
    { action: 'cancel', label: 'Cancel' },
  ],
  paused: [
    { action: 'resume', label: 'Resume' },
    { action: 'cancel', label: 'Cancel' },
  ],
  pending: [{ action: 'cancel', label: 'Cancel' }],
}

/** Doc 11 §9.5 Memberships — fixed-duration plans and their enrolments. */
export default async function MembershipsPage({ params }: { params: { businessId: string } }) {
  const token = await getAccessToken()
  if (!token) redirect('/login')

  const base = `/v1/platform/businesses/${params.businessId}`
  const plansRes = await apiTry<{ data: Plan[] }>(`${base}/membership-plans`, token)
  if (!plansRes.ok) {
    return (
      <div>
        <PageHeader title="Memberships" />
        <GateNotice error={plansRes.error} businessId={params.businessId} moduleLabel="Memberships" />
      </div>
    )
  }
  const plans = plansRes.data.data || []

  const enrolRes = await apiTry<{ data: Enrolment[] }>(`${base}/membership-enrolments`, token)
  const enrolments = enrolRes.ok ? enrolRes.data.data || [] : []
  const planName = new Map(plans.map((plan) => [plan.id, plan.name]))

  return (
    <div>
      <PageHeader
        title="Memberships"
        subtitle="Fixed-duration plans and the members enrolled on them."
      />

      <section>
        <h2 >Plans</h2>
        <table style={TABLE}>
          <thead>
            <tr>
              <th style={TH}>Plan</th>
              <th style={TH}>Price</th>
              <th style={TH}>Duration</th>
              <th style={TH}>Status</th>
              <th style={TH}>Visibility</th>
              <th style={TH} />
            </tr>
          </thead>
          <tbody>
            {plans.map((plan) => (
              <tr key={plan.id} style={ROW}>
                <td style={TD}>{plan.name}</td>
                <td style={{ ...TD, fontVariantNumeric: 'tabular-nums' }}>
                  {plan.price_amount > 0 ? `${plan.currency} ${plan.price_amount}` : 'Free'}
                </td>
                <td style={TD}>{plan.duration_days ? `${plan.duration_days} days` : '—'}</td>
                <td style={TD}>
                  <StatusPill value={plan.status} />
                </td>
                <td style={TD}>{plan.visibility}</td>
                <td style={TD}>
                  {plan.status !== 'archived' ? (
                    <form action={archivePlan}>
                      <input type="hidden" name="businessId" value={params.businessId} />
                      <input type="hidden" name="planId" value={plan.id} />
                      <button type="submit" style={LINK_BUTTON}>
                        Archive
                      </button>
                    </form>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {plans.length === 0 ? (
          <EmptyState>No plans yet. Create one below to start enrolling members.</EmptyState>
        ) : null}
      </section>

      <section style={{ marginTop: '2.25rem' }}>
        <h2 >Enrolments</h2>
        <table style={TABLE}>
          <thead>
            <tr>
              <th style={TH}>Plan</th>
              <th style={TH}>Status</th>
              <th style={TH}>Payment</th>
              <th style={TH}>Ends</th>
              <th style={TH} />
            </tr>
          </thead>
          <tbody>
            {enrolments.map((enrolment) => (
              <tr key={enrolment.id} style={ROW}>
                <td style={TD}>{planName.get(enrolment.plan_id) || enrolment.plan_id}</td>
                <td style={TD}>
                  <StatusPill value={enrolment.status} />
                </td>
                <td style={TD}>{enrolment.payment_status || '—'}</td>
                <td style={TD}>
                  {enrolment.ends_at ? new Date(enrolment.ends_at).toLocaleDateString() : '—'}
                </td>
                <td style={{ ...TD, display: 'flex', gap: '0.5rem' }}>
                  {(ENROLMENT_ACTIONS[enrolment.status] || []).map((item) => (
                    <form key={item.action} action={transitionEnrolment}>
                      <input type="hidden" name="businessId" value={params.businessId} />
                      <input type="hidden" name="enrolmentId" value={enrolment.id} />
                      <input type="hidden" name="action" value={item.action} />
                      {item.action === 'cancel' ? (
                        <input type="hidden" name="reason" value="Cancelled by Business" />
                      ) : null}
                      <button type="submit" style={LINK_BUTTON}>
                        {item.label}
                      </button>
                    </form>
                  ))}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {enrolments.length === 0 ? <EmptyState>Nobody is enrolled yet.</EmptyState> : null}
      </section>

      <section style={{ marginTop: '2.25rem', maxWidth: '32rem' }}>
        <h2 >Create a plan</h2>
        <p style={{ opacity: 0.75, fontSize: '0.9rem' }}>
          Plans run for a fixed period and are renewed manually. Automatic recurring billing is not
          available yet.
        </p>
        <form action={createPlan} style={{ display: 'grid', gap: '0.6rem' }}>
          <input type="hidden" name="businessId" value={params.businessId} />
          <input name="name" placeholder="Plan name" required style={INPUT} />
          <textarea name="description" placeholder="What it includes" style={INPUT} />
          <input
            name="price_amount"
            type="number"
            step="0.01"
            min="0"
            placeholder="Price (0 for free)"
            style={INPUT}
          />
          <input
            name="duration_days"
            type="number"
            min="1"
            placeholder="Duration in days"
            required
            style={INPUT}
          />
          <select name="status" style={INPUT} defaultValue="draft">
            <option value="draft">Save as draft</option>
            <option value="active">Make active</option>
          </select>
          <select name="visibility" style={INPUT} defaultValue="private">
            <option value="private">Private — staff enrol members</option>
            <option value="public">Public — shown on the website</option>
          </select>
          <button type="submit" style={BUTTON}>
            Create plan
          </button>
        </form>
      </section>
    </div>
  )
}

const INPUT: React.CSSProperties = {
  width: '100%',
}
const BUTTON: React.CSSProperties = {
  justifySelf: 'start',
}
const LINK_BUTTON: React.CSSProperties = {
  background: 'none',
  border: 'none',
  color: 'var(--color-primary)',
  cursor: 'pointer',
  font: 'inherit',
  fontWeight: 500,
  padding: 0,
  minHeight: 'auto',
  textDecoration: 'underline',
}
