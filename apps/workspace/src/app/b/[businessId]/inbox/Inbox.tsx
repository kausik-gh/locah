'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useEffect, useRef, useState, useTransition } from 'react'
import { addQuickReply, assign, markRead, reply, setState } from '../whatsapp/whatsapp-actions'
import { clock, rupees, until, type Conversation, type Thread } from '../whatsapp/types'

const TABS: [string, string][] = [
  ['waiting', 'Waiting for a person'], ['mine', 'Mine'], ['open', 'All open'], ['order', 'Orders'],
  ['booking', 'Bookings'], ['lead', 'Enquiries'], ['closed', 'Closed'],
]
const TICKS: Record<string, string> = { queued: 'Sending', sent: 'Sent', delivered: 'Delivered', read: 'Read', failed: 'Failed', blocked: 'Not sent', received: '' }

export function Inbox({ businessId, view, q, list, thread, quickReplies, canReply, me, team, sandbox }: {
  businessId: string
  view: string
  q: string
  list: { conversations: Conversation[]; counts: Record<string, number> }
  thread: Thread | null
  quickReplies: { id: string; title: string; body: string }[]
  canReply: boolean
  me: string
  team: { identity_id: string; name: string }[]
  sandbox: boolean
}) {
  const router = useRouter()
  const [pending, start] = useTransition()
  const [text, setText] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [savingQuick, setSavingQuick] = useState(false)
  const end = useRef<HTMLDivElement>(null)
  const base = `/b/${businessId}/inbox`
  const href = (o: { view?: string; c?: string | null }) => {
    const p = new URLSearchParams()
    p.set('view', o.view ?? view)
    if (q) p.set('q', q)
    if (o.c) p.set('c', o.c)
    return `${base}?${p}`
  }

  // New messages arrive through the webhook: look again every 15 seconds.
  useEffect(() => {
    const t = setInterval(() => { if (document.visibilityState === 'visible') router.refresh() }, 15000)
    return () => clearInterval(t)
  }, [router])
  useEffect(() => {
    if (thread && thread.unread > 0) void markRead(businessId, thread.id)
    end.current?.scrollIntoView({ block: 'end' })
  }, [businessId, thread])

  const act = (fn: () => Promise<{ ok: boolean; message?: string }>, after?: () => void) =>
    start(async () => {
      setError(null)
      const r = await fn()
      if (!r.ok) return setError(r.message ?? 'That did not work')
      after?.()
      router.refresh()
    })

  const count = (k: string) => (k === 'waiting' ? list.counts.waiting : k === 'mine' ? list.counts.mine : k === 'open' ? list.counts.open : undefined)

  return (
    <div className={`bos-inbox${thread ? ' has-thread' : ''}`}>
      <section className="bos-inbox__list" aria-label="Chats">
        <nav className="bos-inbox__tabs" aria-label="Which chats">
          {TABS.map(([k, label]) => (
            <Link key={k} href={href({ view: k, c: null })} aria-current={view === k ? 'page' : undefined} className={view === k ? 'is-on' : ''}>
              {label}{count(k) ? <span>{count(k)}</span> : null}
            </Link>
          ))}
        </nav>
        <form className="bos-inbox__search" role="search">
          <input type="hidden" name="view" value={view} />
          <label className="sr-only" htmlFor="inbox-q">Search chats</label>
          <input id="inbox-q" name="q" defaultValue={q} placeholder="Name or number" />
        </form>
        {list.conversations.length ? (
          <ul>
            {list.conversations.map((c) => (
              <li key={c.id}>
                <Link href={href({ c: c.id })} className={`bos-inbox__row${thread?.id === c.id ? ' is-on' : ''}`}>
                  <span className="bos-inbox__who">
                    <strong>{c.name}</strong>
                    <small>{clock(c.updated_at)}</small>
                  </span>
                  <span className="bos-inbox__preview">{c.last_preview ?? ''}</span>
                  <span className="bos-inbox__chips">
                    {c.needs_person ? <span className="bos-chip bos-chip--bad">Needs a person{c.waiting_minutes ? ` · ${c.waiting_minutes} min` : ''}</span> : null}
                    {!c.needs_person && c.handler === 'bot' && c.state === 'open' ? <span className="bos-chip">LOCAH replying</span> : null}
                    {c.topic ? <span className="bos-chip">{c.topic}</span> : null}
                    {c.assigned_name ? <span className="bos-chip">{c.assigned_to === me ? 'You' : c.assigned_name}</span> : null}
                    {c.unread ? <span className="bos-chip bos-chip--count" aria-label={`${c.unread} unread`}>{c.unread}</span> : null}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        ) : (
          <p className="bos-empty">{view === 'waiting' ? 'Nobody is waiting for a person.' : q ? 'No chat matches.' : 'No chats here yet.'}{sandbox && view !== 'closed' && !q ? ' Try a message from WhatsApp settings.' : ''}</p>
        )}
      </section>

      {thread ? (
        <section className="bos-inbox__thread" aria-label={`Chat with ${thread.name}`}>
          <header className="bos-inbox__head">
            <Link className="bos-inbox__back" href={href({ c: null })}>← Chats</Link>
            <div>
              <h2>{thread.name}</h2>
              <p>{thread.phone}{thread.window_open ? ` · can reply until ${until(thread.window_closes_at)}` : ' · reply window closed'}</p>
            </div>
            {canReply ? (
              <div className="bos-inbox__actions">
                <label className="sr-only" htmlFor="assign">Handled by</label>
                <select id="assign" value={thread.assigned_to ?? ''} disabled={pending}
                  onChange={(e) => act(() => assign(businessId, thread.id, e.target.value || null))}>
                  <option value="">Not assigned</option>
                  {me && !team.some((m) => m.identity_id === me) ? <option value={me}>Me</option> : null}
                  {team.map((m) => <option key={m.identity_id} value={m.identity_id}>{m.identity_id === me ? `${m.name} (me)` : m.name}</option>)}
                </select>
                {thread.handler === 'person' && thread.state === 'open' ? (
                  <button type="button" className="btn-ghost" disabled={pending} onClick={() => act(() => setState(businessId, thread.id, { handler: 'bot' }))}>Hand back to LOCAH</button>
                ) : null}
                <button type="button" className="btn-ghost" disabled={pending}
                  onClick={() => act(() => setState(businessId, thread.id, { state: thread.state === 'open' ? 'closed' : 'open' }))}>
                  {thread.state === 'open' ? 'Close chat' : 'Reopen'}
                </button>
              </div>
            ) : null}
          </header>
          {thread.bot_paused_until ? <p className="bos-inbox__note">A person is handling this chat — LOCAH’s automatic replies wait until {until(thread.bot_paused_until)}.</p> : null}
          <div className="bos-inbox__messages" role="log" aria-live="polite">
            {thread.messages.map((m) => (
              <div key={m.id} className={`bos-bubble bos-bubble--${m.direction}${m.status === 'failed' || m.status === 'blocked' ? ' is-bad' : ''}`}>
                {m.template_key ? <small className="bos-bubble__tag">Template</small> : null}
                {m.kind === 'location' && m.payload.latitude !== undefined ? (
                  <a href={`https://www.google.com/maps?q=${m.payload.latitude},${m.payload.longitude}`} target="_blank" rel="noreferrer">📍 {m.body}</a>
                ) : <p>{m.body}</p>}
                <small className="bos-bubble__meta">
                  {m.direction === 'out' ? (m.sent_via === 'workspace' ? m.sent_by_name ?? 'Team' : m.sent_via === 'business_app' ? 'WhatsApp Business app' : 'LOCAH') + ' · ' : ''}
                  {clock(m.at)}{TICKS[m.status] ? ` · ${TICKS[m.status]}` : ''}{m.error ? ` — ${m.error}` : ''}
                </small>
              </div>
            ))}
            <div ref={end} />
          </div>
          {canReply ? (
            thread.window_open ? (
              <form className="bos-inbox__reply" onSubmit={(e) => { e.preventDefault(); act(() => reply(businessId, thread.id, text), () => setText('')) }}>
                {quickReplies.length ? (
                  <select aria-label="Quick replies" value="" onChange={(e) => { const r = quickReplies.find((x) => x.id === e.target.value); if (r) setText(r.body) }}>
                    <option value="">Quick replies</option>
                    {quickReplies.map((r) => <option key={r.id} value={r.id}>{r.title}</option>)}
                  </select>
                ) : null}
                <label className="sr-only" htmlFor="reply-box">Reply</label>
                <textarea id="reply-box" rows={2} value={text} onChange={(e) => setText(e.target.value)} placeholder="Write a reply"
                  onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey && text.trim()) { e.preventDefault(); e.currentTarget.form?.requestSubmit() } }} />
                <button type="submit" disabled={pending || !text.trim()}>Send</button>
                {text.trim() && !quickReplies.some((r) => r.body === text) ? (
                  <button type="button" className="btn-quiet" disabled={savingQuick}
                    onClick={async () => { const title = prompt('Name this quick reply'); if (!title) return; setSavingQuick(true); await addQuickReply(businessId, title, text); setSavingQuick(false); router.refresh() }}>
                    Save as quick reply
                  </button>
                ) : null}
              </form>
            ) : (
              <p className="bos-inbox__note">WhatsApp lets a business write freely only within 24 hours of the customer’s last message. Send them a bill or a statement from its page, or wait for them to write.</p>
            )
          ) : <p className="bos-inbox__note">You can read this chat; replying needs permission from the owner.</p>}
          {error ? <p className="bos-status bos-error" role="alert">{error}</p> : null}
        </section>
      ) : (
        <section className="bos-inbox__thread bos-inbox__empty"><p className="bos-empty">Choose a chat.</p></section>
      )}

      {thread ? (
        <aside className="bos-inbox__side" aria-label="About this customer">
          <h3>{thread.customer.name ?? thread.name}</h3>
          <p className="bos-hint">{thread.customer.phone ?? thread.phone}</p>
          {thread.customer.contact_id ? <Link href={`/b/${businessId}/customers/${thread.customer.contact_id}`}>Customer profile</Link> : null}
          {thread.customer.khata !== undefined ? (
            <div className="bos-inbox__block">
              <h4>Khata</h4>
              {thread.customer.khata ? (
                <p><Link href={`/b/${businessId}/khata/${thread.customer.khata.account_id}`}>
                  {thread.customer.khata.balance > 0 ? `Owes ${rupees(thread.customer.khata.balance)}` : 'Nothing owed'}</Link>
                  {thread.customer.khata.credit_limit !== null ? <small> · limit {rupees(thread.customer.khata.credit_limit)}</small> : null}</p>
              ) : <p className="bos-hint">No khata</p>}
            </div>
          ) : null}
          {thread.customer.orders ? (
            <div className="bos-inbox__block">
              <h4>Orders</h4>
              {thread.customer.orders.length ? (
                <ul>{thread.customer.orders.map((o) => <li key={o.id}><Link href={`/b/${businessId}/orders/${o.id}`}>{o.number}</Link> <small>{o.status} · {rupees(o.total)}</small></li>)}</ul>
              ) : <p className="bos-hint">No orders yet</p>}
            </div>
          ) : null}
          {thread.customer.bookings ? (
            <div className="bos-inbox__block">
              <h4>Bookings</h4>
              {thread.customer.bookings.length ? (
                <ul>{thread.customer.bookings.map((x) => <li key={x.id}><Link href={`/b/${businessId}/bookings/${x.id}`}>{x.title}</Link> <small>{x.status} · {clock(x.at)}</small></li>)}</ul>
              ) : <p className="bos-hint">No bookings yet</p>}
            </div>
          ) : null}
          {thread.customer.membership ? (
            <div className="bos-inbox__block">
              <h4>Membership</h4>
              <p>{thread.customer.membership.plan} <small>· {thread.customer.membership.status}</small></p>
            </div>
          ) : null}
        </aside>
      ) : null}
    </div>
  )
}
