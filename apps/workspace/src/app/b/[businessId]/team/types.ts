export type RoleOption = {
  key: string
  label: string
  does?: string | null
  scope: string
  scope_words: string
  surface_words?: string
  home?: string | null
  permissions: string[]
  based_on_label?: string | null
  holders?: number
  id?: string
}

export type RoleCatalogue = {
  owner: RoleOption
  templates: RoleOption[]
  custom: RoleOption[]
  permission_words: Record<string, string>
  scopes: Record<string, string>
  locations: { id: string; name: string }[]
}

export type Member = {
  id: string
  identity_id: string
  email: string | null
  name: string
  status: string
  role: { key: string | null; label: string; scope: string; home: string | null }
  locations: { id: string; name: string }[]
}

export type Invited = {
  invitation_id: string
  name: string
  email: string
  role_label: string
  locations: string[]
  expires_at: string
  expired: boolean
}

export const AREA_WORDS: Record<string, string> = {
  orders: 'Orders', bookings: 'Bookings', payments: 'Payments', customers: 'Customers', leads: 'Enquiries',
  quotes: 'Quotes', projects: 'Projects', inventory: 'Stock', fulfilment: 'Deliveries', offerings: 'Products & services',
  memberships: 'Memberships', workforce: 'Staff & rota', website: 'Website', marketplace: 'Marketplace',
  team: 'Team', locations: 'Locations', settings: 'Settings', notifications: 'Notifications', business: 'Business',
  modules: 'Tools', commercial: 'LOCAH plan', entitlements: 'LOCAH plan', permissions: 'Access',
  configuration: 'Configuration',
}

export function groupPermissions(ids: string[], words: Record<string, string>) {
  const groups = new Map<string, { id: string; label: string }[]>()
  for (const id of ids) {
    const area = id.split('.')[0]
    const list = groups.get(area) ?? []
    list.push({ id, label: words[id] ?? id })
    groups.set(area, list)
  }
  return [...groups.entries()].map(([area, items]) => ({ area, label: AREA_WORDS[area] ?? area, items }))
}
