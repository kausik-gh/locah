import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry } from '@/lib/api'
import { GateNotice, PageHeader } from '@/components/ui'
import { CounterSettings, type CounterSetup, type ToVerify } from './CounterSettings'

export const dynamic = 'force-dynamic'

/**
 * Counter billing (Capability Universe §14.1–§14.3): the owner's counter
 * rules — UPI ID for the QR, discount limits per role, the return window,
 * how many bill numbers a register keeps for offline use, the scale's label
 * format — plus a manager's approval PIN and UPI taken without confirmation.
 */
export default async function CounterSettingsPage({ params }: { params: { businessId: string } }) {
  const token = await getAccessToken()
  if (!token) redirect('/login')
  const b = params.businessId
  const [setup, me, verify] = await Promise.all([
    apiTry<{ data: CounterSetup }>(`/v1/platform/businesses/${b}/pos/setup`, token),
    apiTry<{ data: { permissions: string[] } }>(`/v1/me/context`, token, { 'X-Operating-Context': 'business', 'X-Business-Id': b }),
    apiTry<{ data: ToVerify[] }>(`/v1/platform/businesses/${b}/pos/upi-to-verify`, token),
  ])
  const header = (
    <PageHeader
      title="Counter billing"
      breadcrumb={<Link href={`/b/${b}/settings`}>← Settings</Link>}
      subtitle="How your counter works: UPI, discount limits, returns, offline bill numbers and scale labels."
      actions={<a className="btn" href={`/pos/${b}`}>Open the counter</a>}
    />
  )
  if (!setup.ok) {
    return <div className="bos-page">{header}<GateNotice error={setup.error} businessId={b} moduleLabel="Counter billing" /></div>
  }
  const perms = new Set(me.ok ? me.data.data.permissions ?? [] : [])
  return (
    <div className="bos-page">
      {header}
      <CounterSettings businessId={b} setup={setup.data.data} canConfigure={perms.has('pos.configure')}
        canApprove={perms.has('pos.approve')} toVerify={verify.ok ? verify.data.data : null} />
    </div>
  )
}
