'use client'

import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { useEffect, useMemo, useState } from 'react'
import { visibleAreas } from '@/lib/workspace-nav'

/* ========================================================================
   Workspace layout shell. Persistent left sidebar: business switcher, then the
   Business OS Guide §3 areas in their fixed order, each showing only what this
   business runs and this person may open (lib/workspace-nav). Collapse
   persists. Current route always visibly active. No data fetching here — the
   server layout passes everything in.
   ======================================================================== */

export type NavBusiness = { id: string; display_name: string; slug?: string }

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
  permissions,
  unreadCount,
}: {
  businessId: string
  businesses: NavBusiness[]
  moduleStates: Record<string, string>
  permissions: string[] | null
  unreadCount: number
}) {
  const pathname = usePathname()
  const router = useRouter()
  const [collapsed, setCollapsed] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  // A phone uses a drawer independently of the owner's desktop collapse preference.
  const [narrow, setNarrow] = useState(false)

  useEffect(() => {
    try {
      if (localStorage.getItem(STORAGE_KEY) === '1') setCollapsed(true)
    } catch {
      /* private mode — default expanded */
    }
  }, [])

  useEffect(() => setMobileOpen(false), [pathname])

  useEffect(() => {
    // A 248px sidebar beside the page pushed Workspace to ~530px of content in
    // a 375px viewport, so every page scrolled sideways on a phone. Below this
    // width it becomes an off-canvas drawer.
    const mq = window.matchMedia('(max-width: 720px)')
    const apply = () => { setNarrow(mq.matches); setMobileOpen(false) }
    apply()
    mq.addEventListener('change', apply)
    return () => mq.removeEventListener('change', apply)
  }, [])

  const railed = !narrow && collapsed

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
  const areas = useMemo(() => visibleAreas(moduleStates, permissions), [moduleStates, permissions])
  // The most specific link that matches the page is the active one, so
  // Settings › Automations does not also light up Business settings.
  const activeHref = useMemo(() => {
    const hrefs = [...areas.flatMap((a) => a.children.map((c) => c.href)), '/notifications']
    let best: string | null = null
    for (const href of hrefs) {
      const full = `${base}${href}`
      const hit = href === '' ? pathname === base || pathname === `${base}/` : pathname === full || pathname.startsWith(`${full}/`)
      if (hit && (best === null || href.length > best.length)) best = href
    }
    return best
  }, [areas, base, pathname])
  const isActive = (href: string) => activeHref === href

  const current = businesses.find((b) => b.id === businessId)

  return (
    <>
    <div className="ws-mobile-bar">
      <button type="button" className="ws-mobile-bar__toggle" aria-label={mobileOpen ? 'Close navigation' : 'Open navigation'} aria-expanded={mobileOpen} aria-controls="ws-primary-navigation" onClick={() => setMobileOpen(v => !v)}>
        <span aria-hidden="true">{mobileOpen ? '×' : '☰'}</span>
      </button>
      <span className="ws-mobile-bar__name">{current?.display_name ?? 'Workspace'}</span>
      <Link href={`${base}/notifications`} className="ws-mobile-bar__alerts" aria-label={unreadCount > 0 ? `${unreadCount} unread notifications` : 'Notifications'}>Alerts{unreadCount > 0 ? <span>{unreadCount > 99 ? '99+' : unreadCount}</span> : null}</Link>
    </div>
    {narrow && mobileOpen ? <button type="button" className="ws-mobile-scrim" aria-label="Close navigation" onClick={() => setMobileOpen(false)} /> : null}
    <aside
      id="ws-primary-navigation"
      aria-label="Workspace navigation"
      className="ws-sidebar"
      data-collapsed={railed || undefined}
      data-mobile-open={mobileOpen || undefined}
      style={{
        width: railed ? 'var(--sidebar-w-collapsed)' : 'var(--sidebar-w)',
        flex: 'none',
        borderRight: '1px solid var(--color-border)',
        background: 'var(--color-surface)',
        display: 'flex',
        flexDirection: 'column',
        height: '100vh',
      }}
    >
      <button type="button" className="ws-sidebar__close" aria-label="Close navigation" onClick={() => setMobileOpen(false)}>×</button>
      {/* Business switcher */}
      <div className="ws-sidebar__business" style={{ padding: railed ? '0.75rem 0.5rem' : '0.85rem 0.75rem', borderBottom: '1px solid var(--color-border)' }}>
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
        {areas.map((area) =>
          area.key === 'home' ? (
            <div key="home" style={{ display: 'grid', gap: '0.1rem', marginTop: '0.3rem' }}>
              <NavLink href={base} label="Home" active={isActive('')} collapsed={railed} />
              <NavLink
                href={`${base}/notifications`}
                label="Notifications"
                active={isActive('/notifications')}
                collapsed={railed}
                badge={unreadCount}
              />
            </div>
          ) : (
            <div key={area.key} role="group" aria-label={area.label}>
              <GroupLabel collapsed={railed}>{area.label}</GroupLabel>
              {area.children.map((item) => (
                <NavLink
                  key={item.href}
                  href={`${base}${item.href}`}
                  label={item.label}
                  active={isActive(item.href)}
                  collapsed={railed}
                />
              ))}
            </div>
          ),
        )}
      </nav>

      {/* Collapse toggle */}
      {!narrow ? <button
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
      </button> : null}
    </aside>
    </>
  )
}
