import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import { DetailShell, GateNotice, PageHeader, StatusPill } from '@/components/ui'
import { MoneySection } from '@/components/MoneySection'
import { LocalTime } from '@/components/LocalTime'
import { money, paidWords } from '../../orders/labels'

export const dynamic = 'force-dynamic'

type Enrolment = {
  id: string
  plan_id: string
  customer_contact_id: string
  status: string
  payment_status: string | null
  starts_at: string | null
  ends_at: string | null
}
type Plan = { id: string; name: string; price_amount: number; currency: string; duration_days: number | null }

/**
 * One member's membership and its money (Founder refinement — Payments §5, §10):
 * the fee, what was paid, what remains, a payment link or money taken at the
 * desk. Renewals, freezes and the lifecycle arrive with Memberships (P2).
 */
export default async function EnrolmentPage({ params }: { params: { businessId: string; enrolmentId: string } }) {
  const token = await getAccessToken()
  if (!token) redirect('/login')
  const base = `/v1/platform/businesses/${params.businessId}`
  const res = await apiTry<{ data: Enrolment }>(`${base}/membership-enrolments/${params.enrolmentId}`, token)
  if (!res.ok) {
    return (
      <div>
        <PageHeader title="Membership" />
        <GateNotice error={res.error} businessId={params.businessId} moduleLabel="Memberships" />
      </div>
    )
  }
  const enrolment = res.data.data
  const [planRes, contactRes] = await Promise.all([
    apiTry<{ data: Plan }>(`${base}/membership-plans/${enrolment.plan_id}`, token),
    apiTry<{ data: { display_name: string | null } }>(`${base}/customers/${enrolment.customer_contact_id}`, token),
  ])
  const plan = planRes.ok ? planRes.data.data : null
  const member = contactRes.ok ? contactRes.data.data.display_name || 'Member' : 'Member'
  return (
    <DetailShell
      breadcrumb={<Link href={`/b/${params.businessId}/memberships`}>← Memberships</Link>}
      title={`${member} · ${plan?.name ?? 'Membership'}`}
      status={<StatusPill value={enrolment.status} />}
      meta={[
        ['Fee', plan ? money(Number(plan.price_amount) || 0, plan.currency) : '—'],
        ['Payment', paidWords(enrolment.payment_status)],
        ['From', <LocalTime key="s" value={enrolment.starts_at} mode="date" />],
        ['Until', <LocalTime key="e" value={enrolment.ends_at} mode="date" />],
      ]}
    >
      <p>
        <Link href={`/b/${params.businessId}/customers/${enrolment.customer_contact_id}`}>Open {member}’s customer page</Link>
      </p>
      <MoneySection businessId={params.businessId} token={token} sourceType="membership" sourceId={enrolment.id}
        path={`/b/${params.businessId}/memberships/${enrolment.id}`} />
    </DetailShell>
  )
}
