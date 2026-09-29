/**
 * Workspace navigation (Business OS Guide §3 "Recommended Workspace navigation
 * model"). Twelve areas in a fixed order; what sits inside each depends on the
 * tools this business runs and what this person may do. An area with nothing
 * inside for this person is not shown — "the Workspace expands only as
 * relevant capabilities become active". This only decides what is shown; the
 * API decides what anyone may actually do.
 */

/** `href` is relative to the business (`/orders` → /b/{id}/orders); a leading `~`
 *  names another full-screen surface (`~/pos` → /pos/{id}). */
export type NavChild = {
  href: string
  label: string
  perm?: string
  anyPerm?: string[]
  module?: string
  /** 'solo': only when one person runs the business; 'team': never then (OM-21). */
  shape?: 'solo' | 'team'
}
export type NavArea = { key: string; label: string; children: NavChild[] }

export const AREAS: NavArea[] = [
  {
    key: 'home',
    label: 'Home',
    children: [
      { href: '', label: 'Home' },
      // One person, one calendar (MD §22 "Solo professionals … one calendar").
      { href: '/calendar', label: 'Calendar', shape: 'solo' },
    ],
  },
  {
    key: 'presence',
    label: 'Business presence',
    children: [
      { href: '/profile', label: 'Profile', perm: 'business.update' },
      { href: '/website', label: 'Website', perm: 'website.edit' },
      { href: '/brand', label: 'Brand & media', perm: 'business.update' },
      { href: '/marketplace', label: 'Marketplace', perm: 'marketplace.configure' },
      { href: '/locations', label: 'Locations', perm: 'locations.update' },
    ],
  },
  {
    key: 'operate',
    label: 'Sell & serve',
    children: [
      { href: '~/pos', label: 'Counter (POS)', perm: 'pos.use', module: 'pos' },
      { href: '/orders', label: 'Orders', perm: 'orders.read', module: 'orders' },
      { href: '/bookings', label: 'Bookings', perm: 'bookings.read', module: 'bookings' },
      { href: '/fulfilment', label: 'Deliveries & pickup', perm: 'fulfilment.read', module: 'fulfilment' },
      { href: '/memberships', label: 'Memberships', perm: 'memberships.read', module: 'memberships' },
      { href: '/quotes', label: 'Quotes', perm: 'quotes.read', module: 'quotes' },
      { href: '/projects', label: 'Projects', perm: 'projects.read', module: 'projects' },
      { href: '/jobs', label: 'Job cards', perm: 'jobs.read', module: 'jobs' },
      { href: '/academics', label: 'Courses & batches', perm: 'academics.read', module: 'academics' },
    ],
  },
  {
    key: 'offerings',
    label: 'Offerings',
    children: [
      { href: '/offerings', label: 'Products & services', perm: 'offerings.read', module: 'offerings-catalog' },
      { href: '/inventory', label: 'Stock', perm: 'inventory.read', module: 'inventory' },
    ],
  },
  {
    key: 'customers',
    label: 'Customers',
    children: [
      { href: '/customers', label: 'Customers', perm: 'customers.read', module: 'customer-relationships' },
      { href: '/leads', label: 'Enquiries', perm: 'leads.read', module: 'leads' },
      { href: '/reviews', label: 'Reviews', perm: 'reviews.read', module: 'reviews' },
    ],
  },
  {
    key: 'money',
    label: 'Money',
    children: [
      { href: '/invoices', label: 'Bills & invoices', perm: 'invoices.read', module: 'invoicing' },
      { href: '/payments', label: 'Payments', perm: 'payments.read', module: 'payments' },
      { href: '/khata', label: 'Khata (credit book)', perm: 'ledger.read', module: 'ledger' },
      { href: '/invoices/tax-rates', label: 'Tax rates', perm: 'invoices.read', module: 'invoicing' },
      { href: '/pos/shifts', label: 'Counter shifts', perm: 'pos.approve', module: 'pos' },
      { href: '/invoices/reports', label: 'Reports for your CA', perm: 'invoices.export', module: 'invoicing' },
    ],
  },
  {
    key: 'team',
    label: 'Team',
    children: [
      { href: '/team', label: 'People', perm: 'team.read', shape: 'team' },
      { href: '/team/roles', label: 'Roles', perm: 'team.read', shape: 'team' },
      { href: '/workforce', label: 'Staff & rota', perm: 'workforce.read', module: 'workforce', shape: 'team' },
    ],
  },
  // AI Employees join as their tools ship (P3); campaigns join Reach in P3.
  // Until then they have nothing to show.
  {
    key: 'reach',
    label: 'Reach',
    children: [
      { href: '/inbox', label: 'WhatsApp inbox', perm: 'messaging.read', module: 'messaging' },
      { href: '/whatsapp', label: 'WhatsApp', perm: 'messaging.read', module: 'messaging' },
    ],
  },
  {
    key: 'insights',
    label: 'Insights',
    // Basic insights from real data (IS-01) are part of the Workspace; the deeper Analytics tool comes later.
    children: [{ href: '/insights', label: 'Your numbers', anyPerm: ['orders.read', 'bookings.read', 'invoices.read', 'payments.read'] }],
  },
  { key: 'ai', label: 'AI employees', children: [] },
  {
    key: 'modules',
    label: 'Modules & integrations',
    children: [{ href: '/modules', label: 'Tools', perm: 'modules.read' }],
  },
  {
    key: 'settings',
    label: 'Settings',
    children: [
      { href: '/settings', label: 'Business settings', perm: 'settings.read' },
      { href: '/settings/business', label: 'How your business works', perm: 'settings.read' },
      { href: '/settings/invoicing', label: 'Tax & invoicing', perm: 'invoices.read', module: 'invoicing' },
      { href: '/settings/counter', label: 'Counter billing', perm: 'pos.use', module: 'pos' },
      { href: '/settings/automations', label: 'Automations', perm: 'settings.read' },
      { href: '/compliance', label: 'Licences & due dates', perm: 'compliance.read', module: 'compliance' },
      { href: '/settings/usage', label: 'Usage & limits', perm: 'settings.read' },
      // A solo business has no team menus; this is how a second person joins.
      { href: '/team', label: 'Invite someone', perm: 'team.read', shape: 'solo' },
    ],
  },
]

const OPERATIONAL = new Set(['active', 'ready', 'enabled'])

/** "Sell & serve" reads as what this business actually does. */
function operateLabel(on: (m: string) => boolean): string {
  const sells = on('orders') || on('quotes') || on('pos')
  const serves = on('bookings') || on('memberships')
  if (sells && serves) return 'Sell & serve'
  if (serves) return 'Serve'
  if (sells) return 'Sell'
  return 'Operate'
}

export function visibleAreas(
  moduleStates: Record<string, string>,
  permissions: string[] | null,
  solo = false,
): { key: string; label: string; children: { href: string; label: string }[] }[] {
  const on = (m: string) => OPERATIONAL.has(moduleStates[m] ?? '')
  // Before the context loads (or if it fails) show only Home, never a guess.
  const perms = permissions ? new Set(permissions) : null
  const may = (c: NavChild) =>
    (!c.shape || (c.shape === 'solo') === solo) &&
    (!c.module || on(c.module)) &&
    (!c.perm || (perms !== null && perms.has(c.perm))) &&
    (!c.anyPerm || (perms !== null && c.anyPerm.some((p) => perms.has(p))))
  return AREAS.map((a) => ({
    key: a.key,
    label: a.key === 'operate' ? operateLabel(on) : a.label,
    children: a.children.filter(may).map(({ href, label }) => ({ href, label })),
  })).filter((a) => a.children.length > 0)
}
