/**
 * Canonical Permission Identifiers
 * Grammar: <resource>.<action> (lowercase, dot-separated, no spaces/hyphens)
 */
export const PERMISSIONS = {
  // Platform Core: Business Identity
  BUSINESS_READ: 'business.read',
  BUSINESS_UPDATE: 'business.update',
  BUSINESS_PUBLISH: 'business.publish',
  BUSINESS_CLOSE: 'business.close',

  // Platform Core: Locations
  LOCATIONS_READ: 'locations.read',
  LOCATIONS_CREATE: 'locations.create',
  LOCATIONS_UPDATE: 'locations.update',
  LOCATIONS_DELETE: 'locations.delete',

  // Platform Core: Team & Access
  TEAM_READ: 'team.read',
  TEAM_INVITE: 'team.invite',
  TEAM_UPDATE_ROLE: 'team.update_role',
  TEAM_REMOVE: 'team.remove',
  TEAM_MANAGE_TEMPLATES: 'team.manage_templates',

  // Platform Core: Settings
  SETTINGS_READ: 'settings.read',
  SETTINGS_UPDATE: 'settings.update',

  // Platform Core: Business-Type Configuration
  CONFIGURATION_READ: 'configuration.read',
  CONFIGURATION_UPDATE: 'configuration.update',

  // Platform Core: Entitlements
  ENTITLEMENTS_READ: 'entitlements.read',
  ENTITLEMENTS_UPDATE: 'entitlements.update',

  // Platform Core: Permissions
  PERMISSIONS_READ: 'permissions.read',
  PERMISSIONS_UPDATE: 'permissions.update',

  // Platform Core: Website
  WEBSITE_READ: 'website.read',
  WEBSITE_EDIT: 'website.edit',
  WEBSITE_PUBLISH: 'website.publish',
  WEBSITE_UNPUBLISH: 'website.unpublish',

  // Platform Core: Module Management
  MODULES_READ: 'modules.read',
  MODULES_ENABLE: 'modules.enable',
  MODULES_CONFIGURE: 'modules.configure',
  MODULES_DEACTIVATE: 'modules.deactivate',

  // Platform Core: Notifications
  NOTIFICATIONS_READ: 'notifications.read',
  NOTIFICATIONS_MANAGE_PREFERENCES: 'notifications.manage_preferences',

  // Platform Core: Marketplace Presence
  MARKETPLACE_READ: 'marketplace.read',
  MARKETPLACE_CONFIGURE: 'marketplace.configure',

  // Module: offerings-catalog
  OFFERINGS_READ: 'offerings.read',
  OFFERINGS_CREATE: 'offerings.create',
  OFFERINGS_UPDATE: 'offerings.update',
  OFFERINGS_ARCHIVE: 'offerings.archive',
  OFFERINGS_MANAGE_AVAILABILITY: 'offerings.manage_availability',

  // Module: orders
  ORDERS_READ: 'orders.read',
  ORDERS_CREATE: 'orders.create',
  ORDERS_UPDATE_STATUS: 'orders.update_status',
  ORDERS_CANCEL: 'orders.cancel',
  ORDERS_REFUND_COORDINATE: 'orders.refund_coordinate',

  // Module: bookings
  BOOKINGS_READ: 'bookings.read',
  BOOKINGS_CREATE: 'bookings.create',
  BOOKINGS_UPDATE: 'bookings.update',
  BOOKINGS_CANCEL: 'bookings.cancel',
  BOOKINGS_MANAGE_AVAILABILITY: 'bookings.manage_availability',

  // Module: payments
  PAYMENTS_READ: 'payments.read',
  PAYMENTS_REFUND: 'payments.refund',
  PAYMENTS_MANAGE_CONNECTION: 'payments.manage_connection',
  PAYMENTS_EXPORT: 'payments.export',

  // Module: memberships
  MEMBERSHIPS_READ: 'memberships.read',
  MEMBERSHIPS_CREATE_PLAN: 'memberships.create_plan',
  MEMBERSHIPS_UPDATE_PLAN: 'memberships.update_plan',
  MEMBERSHIPS_MANAGE_ENROLMENT: 'memberships.manage_enrolment',
  MEMBERSHIPS_CANCEL_ENROLMENT: 'memberships.cancel_enrolment',

  // Module: customer-relationships
  CUSTOMERS_READ: 'customers.read',
  CUSTOMERS_UPDATE: 'customers.update',
  CUSTOMERS_MANAGE_NOTES: 'customers.manage_notes',
  CUSTOMERS_EXPORT: 'customers.export',

  // Module: leads
  LEADS_READ: 'leads.read',
  LEADS_CREATE: 'leads.create',
  LEADS_UPDATE_STATUS: 'leads.update_status',
  LEADS_ASSIGN: 'leads.assign',
  LEADS_DELETE: 'leads.delete',

  // Module: inventory
  INVENTORY_READ: 'inventory.read',
  INVENTORY_ADJUST: 'inventory.adjust',
  INVENTORY_EXPORT: 'inventory.export',

  // Module: fulfilment
  FULFILMENT_READ: 'fulfilment.read',
  FULFILMENT_UPDATE_STATUS: 'fulfilment.update_status',
  FULFILMENT_MANAGE_CONFIG: 'fulfilment.manage_config',

  // Module: workforce
  WORKFORCE_READ: 'workforce.read',
  WORKFORCE_CREATE: 'workforce.create',
  WORKFORCE_UPDATE: 'workforce.update',
  WORKFORCE_MANAGE_AVAILABILITY: 'workforce.manage_availability',
  WORKFORCE_DEACTIVATE: 'workforce.deactivate',

  // Sensitive / Owner operations
  COMMERCIAL_READ: 'commercial.read',
  COMMERCIAL_MANAGE: 'commercial.manage',
} as const

export type PermissionIdentifier = typeof PERMISSIONS[keyof typeof PERMISSIONS]
export const ALL_PERMISSIONS: PermissionIdentifier[] = Object.values(PERMISSIONS)
