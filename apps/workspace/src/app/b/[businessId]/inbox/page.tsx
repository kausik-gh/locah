import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry, businessHeaders } from '@/lib/api'
import { GateNotice, PageHeader } from '@/components/ui'
import { Inbox } from './Inbox'
import type { Conversation, Setup, Thread } from '../whatsapp/types'

export const dynamic = 'force-dynamic'

const VIEWS = ['waiting', 'mine', 'open', 'order', 'booking', 'lead', 'closed'] as const

/**
 * The WhatsApp inbox (Capability Universe §12.5): every customer chat in one
 * list, those waiting for a person first; the chat beside what the business
 * knows about the customer — orders, bookings, khata, membership.
 */
export default async function InboxPage({
  params,
  searchParams,
}: {
  params: { businessId: string }
  searchParams: { view?: string; q?: string; c?: string }
}) {
  const token = await getAccessToken()
  if (!token) redirect('/login')
  const b = params.businessId
  const base = `/v1/platform/businesses/${b}`
  const view = (VIEWS as readonly string[]).includes(searchParams.view ?? '') ? searchParams.view! : 'open'
  const q = new URLSearchParams({ view })
  if (searchParams.q) q.set('q', searchParams.q)
  const [list, thread, quick, me, team, setup] = await Promise.all([
    apiTry<{ data: { conversations: Conversation[]; counts: Record<string, number> } }>(`${base}/messaging/conversations?${q}`, token),
    searchParams.c ? apiTry<{ data: Thread }>(`${base}/messaging/conversations/${searchParams.c}`, token) : Promise.resolve(null),
    apiTry<{ data: { id: string; title: string; body: string }[] }>(`${base}/messaging/quick-replies`, token),
    apiTry<{ data: { permissions: string[]; identity_id: string } }>('/v1/me/context', token, businessHeaders(b)),
    apiTry<{ data: { members: { identity_id: string; name: string; status: string }[] } }>(`${base}/team`, token),
    apiTry<{ data: Setup }>(`${base}/messaging/setup`, token),
  ])
  const header = (
    <PageHeader
      title="WhatsApp inbox"
      subtitle="Every customer chat in one place — the ones waiting for a person come first."
      actions={<Link className="btn btn-ghost" href={`/b/${b}/whatsapp`}>WhatsApp settings</Link>}
    />
  )
  if (!list.ok) {
    return <div className="bos-page">{header}<GateNotice error={list.error} businessId={b} moduleLabel="WhatsApp & messages" /></div>
  }
  const perms = me.ok ? me.data.data.permissions ?? [] : []
  const connected = setup.ok && setup.data.data.channel?.status === 'connected'
  return (
    <div className="bos-page bos-inbox-page">
      {header}
      {!connected ? (
        <p className="bos-wa-activation" role="status">
          No WhatsApp number is connected yet. <Link href={`/b/${b}/whatsapp`}>Connect your number</Link> to receive chats here.
        </p>
      ) : null}
      <Inbox
        businessId={b}
        view={view}
        q={searchParams.q ?? ''}
        list={list.data.data}
        thread={thread && thread.ok ? thread.data.data : null}
        quickReplies={quick.ok ? quick.data.data : []}
        canReply={perms.includes('messaging.reply')}
        me={me.ok ? me.data.data.identity_id : ''}
        team={team.ok ? team.data.data.members.filter((m) => m.status === 'active') : []}
        sandbox={Boolean(setup.ok && setup.data.data.channel?.sandbox)}
      />
    </div>
  )
}
