import { PERMISSIONS } from './identifiers'
import { PermissionTemplate } from './types'

export const TEMPLATES: Record<string, PermissionTemplate> = {
  tmpl_store_manager: {
    id: 'tmpl_store_manager',
    name: 'Store / Operations Manager',
    description: 'Full operations management including orders, bookings, customers, and inventory.',
    permissions: [
      // Orders
      PERMISSIONS.ORDERS_READ,
      PERMISSIONS.ORDERS_CREATE,
      PERMISSIONS.ORDERS_UPDATE_STATUS,
      PERMISSIONS.ORDERS_CANCEL,
      PERMISSIONS.ORDERS_REFUND_COORDINATE,
      // Bookings
      PERMISSIONS.BOOKINGS_READ,
      PERMISSIONS.BOOKINGS_CREATE,
      PERMISSIONS.BOOKINGS_UPDATE,
      PERMISSIONS.BOOKINGS_CANCEL,
      PERMISSIONS.BOOKINGS_MANAGE_AVAILABILITY,
      // Customers
      PERMISSIONS.CUSTOMERS_READ,
      PERMISSIONS.CUSTOMERS_UPDATE,
      PERMISSIONS.CUSTOMERS_MANAGE_NOTES,
      PERMISSIONS.CUSTOMERS_EXPORT,
      // Leads
      PERMISSIONS.LEADS_READ,
      PERMISSIONS.LEADS_CREATE,
      PERMISSIONS.LEADS_UPDATE_STATUS,
      PERMISSIONS.LEADS_ASSIGN,
      PERMISSIONS.LEADS_DELETE,
      // Inventory
      PERMISSIONS.INVENTORY_READ,
      PERMISSIONS.INVENTORY_ADJUST,
      PERMISSIONS.INVENTORY_EXPORT,
      // Fulfilment
      PERMISSIONS.FULFILMENT_READ,
      PERMISSIONS.FULFILMENT_UPDATE_STATUS,
      PERMISSIONS.FULFILMENT_MANAGE_CONFIG,
      // Read-only on catalog and workforce
      PERMISSIONS.OFFERINGS_READ,
      PERMISSIONS.WORKFORCE_READ,
      PERMISSIONS.WEBSITE_READ,
    ],
  },
  tmpl_cashier: {
    id: 'tmpl_cashier',
    name: 'Cashier / Checkout',
    description: 'Basic checkout and payment verification capability.',
    permissions: [PERMISSIONS.ORDERS_READ, PERMISSIONS.ORDERS_UPDATE_STATUS, PERMISSIONS.PAYMENTS_READ],
  },
  tmpl_content_editor: {
    id: 'tmpl_content_editor',
    name: 'Content / Marketing Editor',
    description: 'Manage offerings catalog, website content, and marketplace options.',
    permissions: [
      PERMISSIONS.OFFERINGS_READ,
      PERMISSIONS.OFFERINGS_CREATE,
      PERMISSIONS.OFFERINGS_UPDATE,
      PERMISSIONS.OFFERINGS_ARCHIVE,
      PERMISSIONS.OFFERINGS_MANAGE_AVAILABILITY,
      PERMISSIONS.WEBSITE_READ,
      PERMISSIONS.WEBSITE_EDIT,
      PERMISSIONS.MARKETPLACE_READ,
    ],
  },
  tmpl_inventory_manager: {
    id: 'tmpl_inventory_manager',
    name: 'Inventory / Stock Manager',
    description: 'Full inventory tracking and adjustment.',
    permissions: [
      PERMISSIONS.INVENTORY_READ,
      PERMISSIONS.INVENTORY_ADJUST,
      PERMISSIONS.INVENTORY_EXPORT,
      PERMISSIONS.OFFERINGS_READ,
    ],
  },
  tmpl_booking_coordinator: {
    id: 'tmpl_booking_coordinator',
    name: 'Reception / Bookings Coordinator',
    description: 'Manage booking calendar, availability, and customer timeline.',
    permissions: [
      PERMISSIONS.BOOKINGS_READ,
      PERMISSIONS.BOOKINGS_CREATE,
      PERMISSIONS.BOOKINGS_UPDATE,
      PERMISSIONS.BOOKINGS_CANCEL,
      PERMISSIONS.BOOKINGS_MANAGE_AVAILABILITY,
      PERMISSIONS.CUSTOMERS_READ,
      PERMISSIONS.WORKFORCE_READ,
      PERMISSIONS.NOTIFICATIONS_READ,
    ],
  },
  tmpl_workforce_manager: {
    id: 'tmpl_workforce_manager',
    name: 'Staff / Workforce Manager',
    description: 'Manage workforce profiles, schedules, and service mappings.',
    permissions: [
      PERMISSIONS.WORKFORCE_READ,
      PERMISSIONS.WORKFORCE_CREATE,
      PERMISSIONS.WORKFORCE_UPDATE,
      PERMISSIONS.WORKFORCE_MANAGE_AVAILABILITY,
      PERMISSIONS.WORKFORCE_DEACTIVATE,
      PERMISSIONS.BOOKINGS_READ,
      PERMISSIONS.LOCATIONS_READ,
    ],
  },
  tmpl_lead_handler: {
    id: 'tmpl_lead_handler',
    name: 'Sales / Lead Handler',
    description: 'Follow up on leads and enquiries.',
    permissions: [
      PERMISSIONS.LEADS_READ,
      PERMISSIONS.LEADS_CREATE,
      PERMISSIONS.LEADS_UPDATE_STATUS,
      PERMISSIONS.LEADS_ASSIGN,
      PERMISSIONS.LEADS_DELETE,
      PERMISSIONS.CUSTOMERS_READ,
      PERMISSIONS.OFFERINGS_READ,
    ],
  },
}
