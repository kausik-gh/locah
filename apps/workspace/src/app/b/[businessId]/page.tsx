import Link from 'next/link'
import { redirect } from 'next/navigation'
import { getAccessToken } from '@/lib/supabase/access-token'
import { apiTry, businessHeaders } from '@/lib/api'
import { Card, PageHeader } from '@/components/ui'

export const dynamic = 'force-dynamic'

type Context = {
  permissions: string[]
  entitled_modules: string[]
  module_states: Record<string, string>
  location_id: string | null
}

type Business = {
  display_name: string
  state: string
  status: string
  visibility: string
}

type HomeCard = {
  key: string
  title: string
  detail: string
  href: string
  cta: string
  urgent?: boolean
}

/** Module ids are developer identifiers; owners must never see them. */
const MODULE_NAMES: Record<string, string> = {
  orders: 'Orders',
  bookings: 'Bookings',
  leads: 'Leads',
  inventory: 'Inventory',
  payments: 'Payments',
  memberships: 'Memberships',
  'customer-relationships': 'Customers',
  'offerings-catalog': 'Offerings',
  workforce: 'Workforce',
  fulfilment: 'Fulfilment',
}

function moduleName(id: string): string {
  return MODULE_NAMES[id] || id.replace(/-/g, ' ')
}

const OPERATIONAL_MODULES = [
  'orders',
  'bookings',
  'leads',
  'inventory',
  'payments',
  'memberships',
  'customer-relationships',
  'offerings-catalog',
  'workforce',
  'fulfilment',
]

function isOperational(states: Record<string, string>, moduleId: string): boolean {
  const state = states[moduleId]
  return state === 'active' || state === 'ready'
}

type OrderRow = {
  id: string
  order_number: string
  status: string
  payment_status: string
  currency: string
  total_amount: number
  created_at: string
}

type BookingRow = {
  id: string
  booking_number: string
  status: string
  title?: string | null
  starts_at: string
  created_at?: string
}

const DAY = 24 * 60 * 60 * 1000

function money(amount: number, currency: string) {
  try {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: currency || 'INR',
      maximumFractionDigits: 0,
    }).format(amount)
  } catch {
    return `${currency} ${Math.round(amount)}`
  }
}

/** "3 hours ago" / "in 2 days" — relative time without pulling in a library. */
function when(iso: string): string {
  const then = new Date(iso).getTime()
  if (Number.isNaN(then)) return ''
  const diff = then - Date.now()
  const abs = Math.abs(diff)
  const rtf = new Intl.RelativeTimeFormat('en', { numeric: 'auto' })
  if (abs < 60 * 60 * 1000) return rtf.format(Math.round(diff / (60 * 1000)), 'minute')
  if (abs < DAY) return rtf.format(Math.round(diff / (60 * 60 * 1000)), 'hour')
  return rtf.format(Math.round(diff / DAY), 'day')
}

function Stat({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="ws-stat">
      <p className="ws-stat__label">{label}</p>
      <p className="ws-stat__value">{value}</p>
      {note ? <p className="ws-stat__note">{note}</p> : null}
    </div>
  )
}

/**
 * Doc 09 CORE-001 Workspace Home. Restyled to the design system; the five-state
 * selection logic (Doc 09 §9.1) and the double-gate per card (Doc 11 §17.7) are
 * unchanged.
 */
export default async function WorkspaceHomePage({
  params,
}: {
  params: { businessId: string }
}) {
  const token = await getAccessToken()
  if (!token) redirect('/login')

  const base = `/b/${params.businessId}`
  const bh = businessHeaders(params.businessId)
  const [contextRes, businessRes] = await Promise.all([
    apiTry<{ data: Context }>('/v1/me/context', token, bh),
    apiTry<{ data: Business }>(`/v1/b/${params.businessId}`, token),
  ])

  const context = contextRes.ok ? contextRes.data.data : null
  const business = businessRes.ok ? businessRes.data.data : null
  const permissions = new Set(context?.permissions ?? [])
  const moduleStates = context?.module_states ?? {}
  const can = (permission: string) => permissions.has(permission)
  const active = (moduleId: string) => isOperational(moduleStates, moduleId)

  // STATE 1 — Commercial recovery
  if (business && business.status && business.status !== 'in_good_standing') {
    const suspended = business.status === 'suspended'
    return (
      <div>
        <PageHeader title={business.display_name} />
        <Card tone="danger" style={{ maxWidth: '46rem' }}>
          <h2 style={{ marginBottom: '0.4rem' }}>
            {suspended ? 'This business is suspended' : 'This business is under review'}
          </h2>
          <p style={{ color: 'var(--status-bad-fg)' }}>
            {suspended
              ? 'New orders, bookings and payments are not being accepted right now. Your data is safe and nothing has been deleted.'
              : 'Your account is being reviewed. Everything keeps working normally while that happens.'}
          </p>
          <p style={{ color: 'var(--color-muted)' }}>
            Contact support to resolve this. They can tell you exactly what is needed.
          </p>
          <div style={{ display: 'flex', gap: '0.6rem', marginTop: '0.9rem', flexWrap: 'wrap' }}>
            <Link href={`${base}/settings`} className="btn btn-ghost">
              Business settings
            </Link>
            <Link href={`${base}/modules`} className="btn btn-ghost">
              Modules and plan
            </Link>
          </div>
        </Card>
      </div>
    )
  }

  const cards: HomeCard[] = []
  let pendingWork = 0

  const bp = `/v1/platform/businesses/${params.businessId}`
  const wants = {
    orders: active('orders') && can('orders.read'),
    bookings: active('bookings') && can('bookings.read'),
    leads: active('leads') && can('leads.read'),
    inventory: active('inventory') && can('inventory.read'),
  }

  const wantsCustomers =
    active('customer-relationships') && can('customers.read')

  const [
    ordersR,
    bookingsR,
    leadsR,
    inventoryR,
    notifR,
    websiteR,
    allOrdersR,
    allBookingsR,
    customersR,
  ] = await Promise.all([
    wants.orders ? apiTry<{ data: unknown[] }>(`${bp}/orders?status=pending`, token) : null,
    wants.bookings ? apiTry<{ data: unknown[] }>(`${bp}/bookings?status=pending`, token) : null,
    wants.leads ? apiTry<{ data: unknown[] }>(`${bp}/leads?status=new`, token) : null,
    wants.inventory
      ? apiTry<{ data: Array<{ stock_status: string }> }>(`${bp}/inventory`, token)
      : null,
    apiTry<{ data: { unread_count: number } }>(`${bp}/notifications/unread-count`, token),
    apiTry<{ data: { website: { status: string }; draft: { pages: unknown[] } } }>(
      `/v1/b/${params.businessId}/website`,
      token
    ),
    // Unfiltered lists back the summary strip and the activity feed. There is
    // no aggregate endpoint, so the totals are computed here from the same
    // records the Orders and Bookings pages show.
    wants.orders ? apiTry<{ data: OrderRow[] }>(`${bp}/orders`, token) : null,
    wants.bookings ? apiTry<{ data: BookingRow[] }>(`${bp}/bookings`, token) : null,
    wantsCustomers ? apiTry<{ data: unknown[] }>(`${bp}/customers`, token) : null,
  ])

  if (wants.orders) {
    const count = ordersR?.ok ? (ordersR.data.data || []).length : 0
    pendingWork += count
    cards.push({
      key: 'orders',
      title: 'Orders',
      detail: count > 0 ? `${count} waiting to be accepted` : 'Nothing waiting',
      href: `${base}/orders`,
      cta: count > 0 ? 'Review orders' : 'Open orders',
      urgent: count > 0,
    })
  }
  if (wants.bookings) {
    const count = bookingsR?.ok ? (bookingsR.data.data || []).length : 0
    pendingWork += count
    cards.push({
      key: 'bookings',
      title: 'Bookings',
      detail: count > 0 ? `${count} to confirm` : 'Nothing to confirm',
      href: `${base}/bookings`,
      cta: count > 0 ? 'Confirm bookings' : 'Open bookings',
      urgent: count > 0,
    })
  }
  if (wants.leads) {
    const count = leadsR?.ok ? (leadsR.data.data || []).length : 0
    pendingWork += count
    cards.push({
      key: 'leads',
      title: 'Leads',
      detail: count > 0 ? `${count} new enquiry${count === 1 ? '' : 's'}` : 'No new enquiries',
      href: `${base}/leads`,
      cta: count > 0 ? 'Follow up' : 'Open leads',
      urgent: count > 0,
    })
  }
  if (wants.inventory) {
    const low = inventoryR?.ok
      ? (inventoryR.data.data || []).filter((row) => row.stock_status !== 'in_stock').length
      : 0
    pendingWork += low
    cards.push({
      key: 'inventory',
      title: 'Stock',
      detail: low > 0 ? `${low} item${low === 1 ? '' : 's'} need restocking` : 'Stock levels fine',
      href: `${base}/inventory`,
      cta: low > 0 ? 'Restock' : 'Open inventory',
      urgent: low > 0,
    })
  }

  const unread = notifR.ok ? notifR.data.data.unread_count : 0
  if (unread > 0) {
    cards.push({
      key: 'notifications',
      title: 'Notifications',
      detail: `${unread} unread`,
      href: `${base}/notifications`,
      cta: 'Read them',
    })
  }

  const websiteStatus = websiteR.ok ? websiteR.data.data.website.status : null
  const websiteUnpublished = websiteStatus !== null && websiteStatus !== 'published'
  const activeModuleCount = OPERATIONAL_MODULES.filter(active).length

  // STATE 2 — New: still being set up
  const isNew =
    (business && (business.state === 'draft' || business.state === 'onboarding')) ||
    activeModuleCount === 0

  if (isNew) {
    const steps = [
      { label: 'Add what you sell or offer', href: `${base}/offerings`, done: active('offerings-catalog') },
      { label: 'Turn on the modules you need', href: `${base}/modules`, done: activeModuleCount > 0 },
      { label: 'Complete your business profile', href: `${base}/profile`, done: false },
      { label: 'Publish your website', href: `${base}/website/publish`, done: !websiteUnpublished },
    ]
    return (
      <div>
        <PageHeader
          title={business?.display_name ?? 'Your business'}
          subtitle="Let's get you set up. Each step here unlocks something real."
        />
        <div style={{ display: 'grid', gap: '0.6rem', maxWidth: '44rem' }}>
          {steps.map((step) => (
            <Link key={step.label} href={step.href} className="ws-card ws-card--interactive" style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              gap: '1rem',
              background: 'var(--color-surface)',
              border: '1px solid var(--color-border)',
              borderRadius: 'var(--radius)',
              boxShadow: 'var(--shadow-card)',
              padding: '0.9rem 1.1rem',
              textDecoration: 'none',
              color: 'var(--color-foreground)',
            }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                <span
                  aria-hidden
                  style={{
                    width: 18,
                    height: 18,
                    borderRadius: '50%',
                    display: 'grid',
                    placeItems: 'center',
                    fontSize: '0.7rem',
                    border: `1.5px solid ${step.done ? 'var(--status-good-fg)' : 'var(--color-border-strong)'}`,
                    color: 'var(--status-good-fg)',
                  }}
                >
                  {step.done ? '✓' : ''}
                </span>
                <span style={{ opacity: step.done ? 0.6 : 1, fontWeight: 500 }}>{step.label}</span>
              </span>
              <span style={{ color: 'var(--color-primary)', fontSize: '0.88rem', fontWeight: 500 }}>
                {step.done ? 'Review' : 'Start'}
              </span>
            </Link>
          ))}
        </div>
      </div>
    )
  }

  // Partial / restricted
  const entitledButOff = OPERATIONAL_MODULES.filter(
    (moduleId) => !active(moduleId) && (context?.entitled_modules ?? []).includes(moduleId)
  )
  const restrictedNotice =
    cards.length === 0 && activeModuleCount > 0 ? (
      <Card style={{ maxWidth: '46rem' }}>
        <h2 style={{ marginBottom: '0.4rem' }}>Not much to show you here</h2>
        <p style={{ color: 'var(--color-muted)' }}>
          This business is running, but your role does not include access to the areas that would
          appear on this page. Someone with owner or manager access can change that from Team.
        </p>
        <Link href={`${base}/team`} className="btn btn-ghost" style={{ marginTop: '0.8rem' }}>
          Open Team
        </Link>
      </Card>
    ) : null

  const locationNotice = context?.location_id ? (
    <p style={{ color: 'var(--color-muted)', marginBottom: '1.25rem' }}>
      Showing one location only. Numbers below exclude your other locations.
    </p>
  ) : null

  // STATE 3 — Active / STATE 4 — Quiet
  const quiet = pendingWork === 0 && cards.every((card) => !card.urgent)

  // ---- Summary strip -----------------------------------------------------
  const allOrders: OrderRow[] = allOrdersR?.ok ? allOrdersR.data.data || [] : []
  const allBookings: BookingRow[] = allBookingsR?.ok ? allBookingsR.data.data || [] : []
  const customerCount = customersR?.ok ? (customersR.data.data || []).length : null

  const since = Date.now() - 7 * DAY
  const recentOrders = allOrders.filter(
    (o) => new Date(o.created_at).getTime() >= since && o.status !== 'cancelled'
  )
  const currency = allOrders[0]?.currency || 'INR'
  const revenue7d = recentOrders.reduce((sum, o) => sum + (Number(o.total_amount) || 0), 0)
  const upcoming = allBookings
    .filter((b) => new Date(b.starts_at).getTime() >= Date.now() && b.status !== 'cancelled')
    .sort((a, b) => a.starts_at.localeCompare(b.starts_at))

  const stats: Array<{ label: string; value: string; note?: string }> = []
  if (wants.orders) {
    stats.push({
      label: 'Revenue · 7 days',
      value: money(revenue7d, currency),
      note: `${recentOrders.length} order${recentOrders.length === 1 ? '' : 's'}`,
    })
  }
  if (wants.bookings) {
    stats.push({
      label: 'Upcoming bookings',
      value: String(upcoming.length),
      note: upcoming[0] ? `Next ${when(upcoming[0].starts_at)}` : 'Nothing booked yet',
    })
  }
  if (wantsCustomers && customerCount !== null) {
    stats.push({ label: 'Customers', value: String(customerCount), note: 'All time' })
  }

  // ---- Recent activity ---------------------------------------------------
  type Activity = {
    key: string
    href: string
    title: string
    meta: string
    amount?: string
    at: number
  }
  const activity: Activity[] = [
    ...allOrders.map((o) => ({
      key: `o-${o.id}`,
      href: `${base}/orders/${o.id}`,
      title: `Order ${o.order_number}`,
      meta: `${o.status.replace(/_/g, ' ')} · ${when(o.created_at)}`,
      amount: money(Number(o.total_amount) || 0, o.currency),
      at: new Date(o.created_at).getTime(),
    })),
    ...allBookings.map((b) => ({
      key: `b-${b.id}`,
      href: `${base}/bookings/${b.id}`,
      title: b.title || `Booking ${b.booking_number}`,
      meta: `${b.status.replace(/_/g, ' ')} · starts ${when(b.starts_at)}`,
      at: new Date(b.created_at || b.starts_at).getTime(),
    })),
  ]
    .filter((a) => !Number.isNaN(a.at))
    .sort((a, b) => b.at - a.at)
    .slice(0, 6)

  return (
    <div>
      <PageHeader
        title={business?.display_name ?? 'Workspace'}
        subtitle={
          quiet
            ? 'Nothing needs you right now.'
            : `${pendingWork} thing${pendingWork === 1 ? '' : 's'} need your attention.`
        }
      />

      {locationNotice}
      {restrictedNotice}

      {stats.length > 0 ? (
        <div className="ws-stats">
          {stats.map((s) => (
            <Stat key={s.label} label={s.label} value={s.value} note={s.note} />
          ))}
        </div>
      ) : null}

      {cards.length > 0 ? (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(16rem, 1fr))',
            gap: '0.9rem',
          }}
        >
          {[...cards]
            .sort((a, b) => Number(b.urgent ?? false) - Number(a.urgent ?? false))
            .map((card) => (
              <Link key={card.key} href={card.href} className="ws-card ws-card--interactive" style={{
                background: 'var(--color-surface)',
                border: `1px solid ${card.urgent ? 'var(--status-warn-bd)' : 'var(--color-border)'}`,
                borderRadius: 'var(--radius)',
                boxShadow: 'var(--shadow-card)',
                padding: '1rem 1.1rem',
                textDecoration: 'none',
                color: 'var(--color-foreground)',
                display: 'block',
              }}>
                <h2 style={{ fontSize: '1rem', marginBottom: '0.25rem' }}>{card.title}</h2>
                <p style={{ color: 'var(--color-muted)', margin: '0 0 0.6rem' }}>{card.detail}</p>
                <span style={{ color: 'var(--color-primary)', fontSize: '0.88rem', fontWeight: 500 }}>
                  {card.cta} →
                </span>
              </Link>
            ))}
        </div>
      ) : null}

      {activity.length > 0 ? (
        <section style={{ marginTop: '1.75rem' }}>
          <h2 style={{ fontSize: '1rem', marginBottom: '0.6rem' }}>Latest activity</h2>
          <div className="ws-activity">
            {activity.map((a) => (
              <Link key={a.key} href={a.href} className="ws-activity__row">
                <span className="ws-activity__main">
                  <span className="ws-activity__title">{a.title}</span>
                  <br />
                  <span className="ws-activity__meta">{a.meta}</span>
                </span>
                {a.amount ? <span className="ws-activity__amount">{a.amount}</span> : null}
              </Link>
            ))}
          </div>
        </section>
      ) : null}

      {quiet && cards.length > 0 ? (
        <p style={{ marginTop: '1.5rem', color: 'var(--color-muted)', maxWidth: '40rem' }}>
          Everything is up to date. This is a good time to look at what is not urgent — your website,
          your offerings, or the modules you have not turned on yet.
        </p>
      ) : null}

      {websiteUnpublished && can('website.publish') ? (
        <Card style={{ marginTop: '1.5rem', maxWidth: '40rem' }}>
          <h2 style={{ fontSize: '1rem', marginBottom: '0.25rem' }}>Your website is not live</h2>
          <p style={{ color: 'var(--color-muted)' }}>Customers cannot find you until you publish it.</p>
          <Link href={`${base}/website/publish`} className="btn btn-ghost" style={{ marginTop: '0.7rem' }}>
            Preview and publish
          </Link>
        </Card>
      ) : null}

      {entitledButOff.length > 0 && can('modules.enable') ? (
        <Card style={{ marginTop: '1.5rem', maxWidth: '40rem' }}>
          <h2 style={{ fontSize: '1rem', marginBottom: '0.25rem' }}>Included in your plan, not turned on</h2>
          <p style={{ color: 'var(--color-muted)' }}>
            {entitledButOff.slice(0, 4).map(moduleName).join(', ')}
            {entitledButOff.length > 4 ? `, and ${entitledButOff.length - 4} more` : ''}.
          </p>
          <Link href={`${base}/modules`} className="btn btn-ghost" style={{ marginTop: '0.7rem' }}>
            See what they do
          </Link>
        </Card>
      ) : null}
    </div>
  )
}
