import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry, businessHeaders } from '@/lib/api'
import { GateNotice, PageHeader } from '@/components/ui'
import { WhatsAppSetup } from './WhatsAppSetup'
import { ConnectionPanel } from './ConnectionPanel'
import type { CallRow, Setup } from './types'

export const dynamic = 'force-dynamic'

/**
 * WhatsApp (Capability Universe §9.1, §12.4): the business's own number,
 * what customers are sent automatically and in which language, the message
 * templates WhatsApp must approve, each person's own alerts, and this month's
 * message count.
 */
export default async function WhatsAppPage({ params }: { params: { businessId: string } }) {
  const token = await getAccessToken()
  if (!token) redirect('/login')
  const b = params.businessId
  const [setup, me, calling] = await Promise.all([
    apiTry<{ data: Setup }>(`/v1/platform/businesses/${b}/messaging/setup`, token),
    apiTry<{ data: { permissions: string[] } }>('/v1/me/context', token, businessHeaders(b)),
    apiTry<{ data: { calls: CallRow[] } }>(`/v1/platform/businesses/${b}/messaging/calling`, token),
  ])
  const header = (
    <PageHeader
      title="WhatsApp"
      subtitle="Your business number on LOCAH: order and booking updates, reminders, and one inbox for customer chats."
      actions={<Link className="btn btn-ghost" href={`/b/${b}/inbox`}>Open the inbox</Link>}
    />
  )
  if (!setup.ok) {
    return <div className="bos-page">{header}<GateNotice error={setup.error} businessId={b} moduleLabel="WhatsApp & messages" /></div>
  }
  const perms = new Set(me.ok ? me.data.data.permissions ?? [] : [])
  return (
    <div className="bos-page">
      {header}
      {setup.data.data.connection ? (
        <ConnectionPanel businessId={b} connection={setup.data.data.connection}
          calls={calling.ok ? calling.data.data.calls : []} canConfigure={perms.has('messaging.configure')} />
      ) : null}
      <WhatsAppSetup businessId={b} setup={setup.data.data} canConfigure={perms.has('messaging.configure')} />
    </div>
  )
}
