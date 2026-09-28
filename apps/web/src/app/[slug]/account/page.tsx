import Link from 'next/link'
import { notFound } from 'next/navigation'
import { platformUrl } from '@platform/config'
import { RESERVED_SLUGS } from '@/lib/reserved-slugs'
import { fetchPublicWebsite } from '@/lib/public-website'
import { getAccessToken } from '@/lib/supabase/access-token'
import { siteThemeVars } from '@/components/website/WebsitePageView'

export const dynamic = 'force-dynamic'

type Account = {
  business: { id: string; slug: string; name: string }
  linked: boolean
  orders: { id: string; number: string; status: string; payment_status: string; total: number; placed_at: string; items: { title: string; quantity: number }[]; fulfilment: { mode: string; status: string } | null; track_url: string | null; bill_url: string | null; can_reorder: boolean }[]
  bookings: { id: string; number: string; title: string; status: string; starts_at: string; upcoming: boolean; manage_url: string | null }[]
  bills: { id: string; number: string; kind: string; status: string; issue_date: string | null; total: number; amount_due: number; url: string }[]
  quotes: { id: string; number: string; title: string | null; status: string; total: number; valid_until: string | null; url: string | null }[]
  memberships: { id: string; plan: string; status: string; starts_at: string; ends_at: string | null; days_left: number | null }[]
  khata: { balance: number; url: string } | null
}

const rupees = (v: number) => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 2 }).format(v)
const when = (s: string) => new Date(s).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
const at = (s: string) => new Date(s).toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' })
const ORDER_WORDS: Record<string, string> = {
  pending: 'Placed — waiting for the shop', accepted: 'Accepted', preparing: 'Being prepared', ready: 'Ready',
  completed: 'Completed', cancelled: 'Cancelled', rejected: 'Could not be taken',
}

/**
 * "My account" on a business's own website (Founder §12): one LOCAH sign-in,
 * this business's records only, in this business's own colours. The links are
 * the ones the business already sends — tracking, bill, statement, booking.
 */
export default async function AccountPage({ params }: { params: { slug: string } }) {
  if (RESERVED_SLUGS.has(params.slug)) notFound()
  const site = await fetchPublicWebsite(params.slug)
  if (!site) notFound()
  const theme = siteThemeVars(site)
  const name = site.business.display_name
  const token = await getAccessToken()
  const shell = (body: React.ReactNode) => (
    <div data-locah-site="" data-palette={theme.paletteMode} style={theme.styleVars}>
      <main className="ls-section">
        <div className="ls-inner ls-account">
          <p><Link href={`/${params.slug}`}>← {name}</Link></p>
          {body}
        </div>
      </main>
    </div>
  )
  if (!token) {
    return shell(
      <section className="ls-account__signin">
        <h1 className="ls-title">Your orders and bookings with {name}</h1>
        <p className="ls-meta">Sign in to see what you have ordered and booked here, open your bills and track a delivery. The same sign-in works on every business that uses LOCAH.</p>
        <p><a className="ls-btn" href={`/login?destination=${encodeURIComponent(`/${params.slug}/account`)}`}>Sign in</a></p>
      </section>,
    )
  }
  const res = await fetch(`${platformUrl('api')}/v1/me/businesses/${encodeURIComponent(params.slug)}/account`, {
    headers: { Authorization: `Bearer ${token}` }, cache: 'no-store',
  })
  if (!res.ok) {
    return shell(<><h1 className="ls-title">Your account with {name}</h1><p className="ls-meta">We could not load your records just now. Nothing is lost — try again in a moment.</p></>)
  }
  const a = ((await res.json()) as { data: Account }).data
  const upcoming = a.bookings.filter((b) => b.upcoming)
  const past = a.bookings.filter((b) => !b.upcoming)
  const empty = !a.orders.length && !a.bookings.length && !a.bills.length && !a.quotes.length && !a.memberships.length && !a.khata
  return shell(
    <>
      <header className="ls-account__head">
        <h1 className="ls-title">Your account with {name}</h1>
        <p className="ls-meta">Only your own orders, bookings and bills here.</p>
        <form action="/auth/logout" method="post"><button type="submit" className="ls-btn ls-btn--outline">Sign out</button></form>
      </header>
      {empty ? <div className="ls-account__card"><p><strong>Nothing with {name} yet.</strong></p>
        <p className="ls-meta">Orders and bookings you make while signed in appear here — and earlier ones made with the email you signed in with.</p>
        <p><Link className="ls-btn" href={`/${params.slug}`}>See what {name} offers</Link></p></div> : null}

      {a.memberships.length ? <section className="ls-account__block" aria-labelledby="acc-m"><h2 id="acc-m">Membership</h2>
        {a.memberships.map((m) => <div key={m.id} className="ls-account__card"><p><strong>{m.plan}</strong> · {m.status}</p>
          <p className="ls-meta">From {when(m.starts_at)}{m.ends_at ? ` to ${when(m.ends_at)}` : ''}{m.days_left !== null ? ` · ${m.days_left} day${m.days_left === 1 ? '' : 's'} left` : ''}</p></div>)}</section> : null}

      {upcoming.length ? <section className="ls-account__block" aria-labelledby="acc-b"><h2 id="acc-b">Coming up</h2>
        {upcoming.map((b) => <div key={b.id} className="ls-account__card"><p><strong>{b.title}</strong> · {at(b.starts_at)}</p>
          <p className="ls-meta">Booking {b.number} · {b.status}</p>{b.manage_url ? <p><a className="ls-btn ls-btn--outline" href={b.manage_url}>Change or cancel</a></p> : null}</div>)}</section> : null}

      {a.orders.length ? <section className="ls-account__block" aria-labelledby="acc-o"><h2 id="acc-o">Orders</h2>
        {a.orders.map((o) => <div key={o.id} className="ls-account__card">
          <p className="ls-account__row"><strong>Order {o.number}</strong><span>{rupees(o.total)}</span></p>
          <p className="ls-meta">{when(o.placed_at)} · {ORDER_WORDS[o.status] ?? o.status}{o.fulfilment ? ` · ${o.fulfilment.mode === 'delivery' ? 'delivery' : 'pickup'}` : ''}</p>
          <ul className="ls-account__items">{o.items.map((i, n) => <li key={n}>{i.quantity} × {i.title}</li>)}</ul>
          <p className="ls-account__actions">
            {o.track_url && !['completed', 'cancelled', 'rejected'].includes(o.status) ? <a className="ls-btn ls-btn--outline" href={o.track_url}>Track</a> : null}
            {o.bill_url ? <a className="ls-btn ls-btn--outline" href={o.bill_url}>Bill</a> : null}
            {o.can_reorder ? <Link className="ls-btn" href={`/${params.slug}/checkout?reorder=${o.id}`}>Order again</Link> : null}
          </p></div>)}</section> : null}

      {a.khata ? <section className="ls-account__block" aria-labelledby="acc-k"><h2 id="acc-k">Your khata</h2>
        <div className="ls-account__card"><p className="ls-account__row"><strong>{a.khata.balance > 0 ? 'You owe' : a.khata.balance < 0 ? 'In your favour' : 'Settled'}</strong><span>{rupees(Math.abs(a.khata.balance))}</span></p>
          <p><a className="ls-btn ls-btn--outline" href={a.khata.url}>Statement{a.khata.balance > 0 ? ' and pay' : ''}</a></p></div></section> : null}

      {a.bills.length ? <section className="ls-account__block" aria-labelledby="acc-i"><h2 id="acc-i">Bills</h2>
        <ul className="ls-account__list">{a.bills.map((d) => <li key={d.id}><a href={d.url}>{d.number}</a><span className="ls-meta">{d.issue_date ? when(d.issue_date) : ''}{d.status === 'cancelled' ? ' · cancelled' : d.amount_due > 0 ? ` · ${rupees(d.amount_due)} due` : ''}</span><strong>{rupees(d.total)}</strong></li>)}</ul></section> : null}

      {a.quotes.length ? <section className="ls-account__block" aria-labelledby="acc-q"><h2 id="acc-q">Quotes</h2>
        <ul className="ls-account__list">{a.quotes.map((q) => <li key={q.id}>{q.url ? <a href={q.url}>{q.title || q.number}</a> : <span>{q.title || q.number}</span>}<span className="ls-meta">{q.status}{q.valid_until ? ` · valid until ${when(q.valid_until)}` : ''}</span><strong>{rupees(q.total)}</strong></li>)}</ul></section> : null}

      {past.length ? <section className="ls-account__block" aria-labelledby="acc-p"><h2 id="acc-p">Past bookings</h2>
        <ul className="ls-account__list">{past.map((b) => <li key={b.id}><span>{b.title}</span><span className="ls-meta">{at(b.starts_at)} · {b.status}</span></li>)}</ul></section> : null}
    </>,
  )
}
