'use client'

import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { useEffect, useState } from 'react'

/* ========================================================================
   Workspace layout shell (Frontend Design Work Order, Prompt B, item 1).
   Persistent left sidebar. Business switcher · Core · Modules (active only) ·
   Notifications. Collapse persists. Current route always visibly active.
   No data fetching here — the server layout passes everything in.
   ======================================================================== */

export type NavBusiness = { id: string; display_name: string; slug?: string }

type Item = { href: string; label: string }

const CORE: Item[] = [
  { href: '', label: 'Home' },
  { href: '/website', label: 'Website' },
  { href: '/profile', label: 'Profile' },
  { href: '/brand', label: 'Brand & Media' },
  { href: '/locations', label: 'Locations' },
  { href: '/team', label: 'Team' },
  { href: '/marketplace', label: 'Marketplace' },
  { href: '/settings', label: 'Settings' },
]

/** module id -> the workspace route it unlocks. Only rendered when the module
 *  is operational for this business (read from module_states, never invented). */
const MODULE_NAV: { module: string; href: string; label: string }[] = [
  { module: 'offerings-catalog', href: '/offerings', label: 'Offerings' },
  { module: 'inventory', href: '/inventory', label: 'Inventory' },
  { module: 'orders', href: '/orders', label: 'Orders' },
  { module: 'fulfilment', href: '/fulfilment', label: 'Fulfilment' },
  { module: 'bookings', href: '/bookings', label: 'Bookings' },
  { module: 'workforce', href: '/workforce', label: 'Workforce' },
  { module: 'customer-relationships', href: '/customers', label: 'Customers' },
  { module: 'leads', href: '/leads', label: 'Leads' },
  { module: 'quotes', href: '/quotes', label: 'Quotes' },
  { module: 'projects', href: '/projects', label: 'Projects' },
  { module: 'memberships', href: '/memberships', label: 'Memberships' },
  { module: 'payments', href: '/payments', label: 'Payments' },
]

const OPERATIONAL = new Set(['active', 'ready'])
const STORAGE_KEY = 'ws-sidebar-collapsed'

function NavLink({
  href,
  label,
  active,
  collapsed,
  badge,
}: {
  href: string
  label: string
  active: boolean
  collapsed: boolean
  badge?: number
}) {
  return (
    <Link
      href={href}
      aria-current={active ? 'page' : undefined}
      title={collapsed ? label : undefined}
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: collapsed ? 'center' : 'space-between',
        gap: '0.5rem',
        padding: collapsed ? '0.5rem' : '0.45rem 0.6rem',
        borderRadius: 'var(--radius-sm)',
        fontSize: '0.88rem',
        fontWeight: active ? 600 : 450,
        textDecoration: 'none',
        color: active ? 'var(--color-primary)' : 'var(--color-foreground)',
        background: active ? 'var(--color-surface-2)' : 'transparent',
        boxShadow: active ? 'inset 2px 0 0 var(--color-primary)' : 'none',
      }}
    >
      <span
        style={{
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}
      >
        {collapsed ? label.slice(0, 1) : label}
      </span>
      {!collapsed && badge && badge > 0 ? (
        <span
          style={{
            fontSize: '0.72rem',
            fontWeight: 600,
            fontVariantNumeric: 'tabular-nums',
            background: 'var(--color-primary)',
            color: 'var(--color-primary-fg)',
            borderRadius: '999px',
            padding: '0.05rem 0.4rem',
            minWidth: '1.15rem',
            textAlign: 'center',
          }}
        >
          {badge > 99 ? '99+' : badge}
        </span>
      ) : null}
    </Link>
  )
}

function GroupLabel({ children, collapsed }: { children: string; collapsed: boolean }) {
  if (collapsed) return <div style={{ height: 1, background: 'var(--color-border)', margin: '0.5rem 0.4rem' }} />
  return (
    <div
      style={{
        fontSize: '0.68rem',
        fontWeight: 600,
        textTransform: 'uppercase',
        letterSpacing: '0.07em',
        color: 'var(--color-muted)',
        padding: '0.9rem 0.6rem 0.35rem',
      }}
    >
      {children}
    </div>
  )
}

export function AppSidebar({
  businessId,
  businesses,
  moduleStates,
  unreadCount,
}: {
  businessId: string
  businesses: NavBusiness[]
  moduleStates: Record<string, string>
  unreadCount: number
}) {
  const pathname = usePathname()
  const router = useRouter()
  const [collapsed, setCollapsed] = useState(false)
  // Narrow screens are not a preference the owner expressed, so they are
  // tracked separately from `collapsed`: a phone gets the rail whatever the
  // stored choice was, and that choice is still there on a wide screen later.
  const [narrow, setNarrow] = useState(false)

  useEffect(() => {
    try {
      if (localStorage.getItem(STORAGE_KEY) === '1') setCollapsed(true)
    } catch {
      /* private mode — default expanded */
    }
  }, [])

  useEffect(() => {
    // A 248px sidebar beside the page pushed Workspace to ~530px of content in
    // a 375px viewport, so every page scrolled sideways on a phone. Below this
    // width the sidebar becomes the icon rail it already knows how to be.
    const mq = window.matchMedia('(max-width: 720px)')
    const apply = () => setNarrow(mq.matches)
    apply()
    mq.addEventListener('change', apply)
    return () => mq.removeEventListener('change', apply)
  }, [])

  const railed = collapsed || narrow

  const toggle = () => {
    setCollapsed((c) => {
      const next = !c
      try {
        localStorage.setItem(STORAGE_KEY, next ? '1' : '0')
      } catch {
        /* ignore */
      }
      return next
    })
  }

  const base = `/b/${businessId}`
  const isActive = (href: string) => {
    const full = `${base}${href}`
    if (href === '') return pathname === base || pathname === `${base}/`
    return pathname === full || pathname.startsWith(`${full}/`)
  }

  const current = businesses.find((b) => b.id === businessId)
  const activeModules = MODULE_NAV.filter((m) => OPERATIONAL.has(moduleStates[m.module] ?? ''))

  return (
    <aside
      data-collapsed={railed || undefined}
      style={{
        width: railed ? 'var(--sidebar-w-collapsed)' : 'var(--sidebar-w)',
        flex: 'none',
        borderRight: '1px solid var(--color-border)',
        background: 'var(--color-surface)',
        display: 'flex',
        flexDirection: 'column',
        height: '100vh',
        position: 'sticky',
        top: 0,
      }}
    >
      {/* Business switcher */}
      <div style={{ padding: railed ? '0.75rem 0.5rem' : '0.85rem 0.75rem', borderBottom: '1px solid var(--color-border)' }}>
        {railed ? (
          <div
            title={current?.display_name}
            style={{
              width: 32,
              height: 32,
              borderRadius: 'var(--radius-sm)',
              background: 'var(--color-primary)',
              color: 'var(--color-primary-fg)',
              display: 'grid',
              placeItems: 'center',
              fontWeight: 700,
              margin: '0 auto',
            }}
          >
            {(current?.display_name ?? '?').slice(0, 1).toUpperCase()}
          </div>
        ) : (
          <label style={{ display: 'grid', gap: '0.25rem' }}>
            <span style={{ fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--color-muted)' }}>
              Business
            </span>
            {businesses.length > 1 ? (
              <select
                value={businessId}
                onChange={(e) => router.push(`/b/${e.target.value}`)}
                style={{ width: '100%', minHeight: 36, fontWeight: 600 }}
              >
                {businesses.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.display_name}
                  </option>
                ))}
              </select>
            ) : (
              <span style={{ fontWeight: 600, fontSize: '0.95rem' }}>
                {current?.display_name ?? 'Workspace'}
              </span>
            )}
          </label>
        )}
      </div>

      {/* Nav */}
      <nav style={{ flex: 1, overflowY: 'auto', padding: '0.4rem 0.5rem 1rem', display: 'flex', flexDirection: 'column', gap: '0.1rem' }}>
        <GroupLabel collapsed={railed}>Core</GroupLabel>
        {CORE.map((item) => (
          <NavLink
            key={item.href || 'home'}
            href={`${base}${item.href}`}
            label={item.label}
            active={isActive(item.href)}
            collapsed={railed}
          />
        ))}

        {activeModules.length > 0 ? (
          <>
            <GroupLabel collapsed={railed}>Modules</GroupLabel>
            {activeModules.map((m) => (
              <NavLink
                key={m.href}
                href={`${base}${m.href}`}
                label={m.label}
                active={isActive(m.href)}
                collapsed={railed}
              />
            ))}
          </>
        ) : null}

        <GroupLabel collapsed={railed}>Alerts</GroupLabel>
        <NavLink
          href={`${base}/notifications`}
          label="Notifications"
          active={isActive('/notifications')}
          collapsed={railed}
          badge={unreadCount}
        />
        <NavLink
          href={`${base}/modules`}
          label="All modules"
          active={isActive('/modules')}
          collapsed={railed}
        />
      </nav>

      {/* Collapse toggle */}
      <button
        type="button"
        onClick={toggle}
        aria-label={railed ? 'Expand sidebar' : 'Collapse sidebar'}
        className="btn-ghost"
        style={{
          margin: '0.5rem',
          minHeight: 34,
          borderRadius: 'var(--radius-sm)',
          fontSize: '0.8rem',
        }}
      >
        {railed ? '»' : '« Collapse'}
      </button>
    </aside>
  )
}
