# Canonical permission identifiers — must match packages/permissions/src/identifiers.ts

BUSINESS_READ = "business.read"
BUSINESS_UPDATE = "business.update"
BUSINESS_PUBLISH = "business.publish"
BUSINESS_CLOSE = "business.close"

LOCATIONS_READ = "locations.read"
LOCATIONS_CREATE = "locations.create"
LOCATIONS_UPDATE = "locations.update"
LOCATIONS_DELETE = "locations.delete"

TEAM_READ = "team.read"
TEAM_INVITE = "team.invite"
TEAM_UPDATE_ROLE = "team.update_role"
TEAM_REMOVE = "team.remove"
TEAM_MANAGE_TEMPLATES = "team.manage_templates"

SETTINGS_READ = "settings.read"
SETTINGS_UPDATE = "settings.update"

CONFIGURATION_READ = "configuration.read"
CONFIGURATION_UPDATE = "configuration.update"

ENTITLEMENTS_READ = "entitlements.read"
ENTITLEMENTS_UPDATE = "entitlements.update"

PERMISSIONS_READ = "permissions.read"
PERMISSIONS_UPDATE = "permissions.update"

WEBSITE_READ = "website.read"
WEBSITE_EDIT = "website.edit"
WEBSITE_PUBLISH = "website.publish"
WEBSITE_UNPUBLISH = "website.unpublish"

MODULES_READ = "modules.read"
MODULES_ENABLE = "modules.enable"
MODULES_CONFIGURE = "modules.configure"
MODULES_DEACTIVATE = "modules.deactivate"

NOTIFICATIONS_READ = "notifications.read"
NOTIFICATIONS_MANAGE_PREFERENCES = "notifications.manage_preferences"

MARKETPLACE_READ = "marketplace.read"
MARKETPLACE_CONFIGURE = "marketplace.configure"

COMMERCIAL_READ = "commercial.read"
COMMERCIAL_MANAGE = "commercial.manage"

OFFERINGS_READ = "offerings.read"
OFFERINGS_CREATE = "offerings.create"
OFFERINGS_UPDATE = "offerings.update"
OFFERINGS_ARCHIVE = "offerings.archive"
OFFERINGS_MANAGE_AVAILABILITY = "offerings.manage_availability"

ORDERS_READ = "orders.read"
ORDERS_CREATE = "orders.create"
ORDERS_UPDATE_STATUS = "orders.update_status"
ORDERS_CANCEL = "orders.cancel"
ORDERS_REFUND_COORDINATE = "orders.refund_coordinate"

BOOKINGS_READ = "bookings.read"
BOOKINGS_CREATE = "bookings.create"
BOOKINGS_UPDATE = "bookings.update"
BOOKINGS_CANCEL = "bookings.cancel"
BOOKINGS_MANAGE_AVAILABILITY = "bookings.manage_availability"

PAYMENTS_READ = "payments.read"
PAYMENTS_REFUND = "payments.refund"
PAYMENTS_MANAGE_CONNECTION = "payments.manage_connection"
PAYMENTS_EXPORT = "payments.export"

MEMBERSHIPS_READ = "memberships.read"
MEMBERSHIPS_CREATE_PLAN = "memberships.create_plan"
MEMBERSHIPS_UPDATE_PLAN = "memberships.update_plan"
MEMBERSHIPS_MANAGE_ENROLMENT = "memberships.manage_enrolment"
MEMBERSHIPS_CANCEL_ENROLMENT = "memberships.cancel_enrolment"

CUSTOMERS_READ = "customers.read"
CUSTOMERS_UPDATE = "customers.update"
CUSTOMERS_MANAGE_NOTES = "customers.manage_notes"
CUSTOMERS_EXPORT = "customers.export"

LEADS_READ = "leads.read"
LEADS_CREATE = "leads.create"
LEADS_UPDATE_STATUS = "leads.update_status"
LEADS_ASSIGN = "leads.assign"
LEADS_DELETE = "leads.delete"

INVENTORY_READ = "inventory.read"
INVENTORY_ADJUST = "inventory.adjust"
INVENTORY_EXPORT = "inventory.export"

FULFILMENT_READ = "fulfilment.read"
FULFILMENT_UPDATE_STATUS = "fulfilment.update_status"
FULFILMENT_MANAGE_CONFIG = "fulfilment.manage_config"

WORKFORCE_READ = "workforce.read"
WORKFORCE_CREATE = "workforce.create"
WORKFORCE_UPDATE = "workforce.update"
WORKFORCE_MANAGE_AVAILABILITY = "workforce.manage_availability"
WORKFORCE_DEACTIVATE = "workforce.deactivate"

ALL_PERMISSIONS: frozenset[str] = frozenset(
    str(v) for k, v in globals().items() if k.isupper() and isinstance(v, str) and "." in v
)

PRIMARY_OWNER_ONLY: frozenset[str] = frozenset({BUSINESS_CLOSE, COMMERCIAL_MANAGE})

ROLE_PRIMARY_OWNER = "primary_owner"
ROLE_MANAGER = "manager"
ROLE_MEMBER = "member"

# Built-in permission templates (Doc 12 §8.3)
TEMPLATES: dict[str, frozenset[str]] = {
    "tmpl_store_manager": frozenset(
        {
            ORDERS_READ,
            ORDERS_CREATE,
            ORDERS_UPDATE_STATUS,
            ORDERS_CANCEL,
            ORDERS_REFUND_COORDINATE,
            BOOKINGS_READ,
            BOOKINGS_CREATE,
            BOOKINGS_UPDATE,
            BOOKINGS_CANCEL,
            BOOKINGS_MANAGE_AVAILABILITY,
            CUSTOMERS_READ,
            CUSTOMERS_UPDATE,
            CUSTOMERS_MANAGE_NOTES,
            CUSTOMERS_EXPORT,
            LEADS_READ,
            LEADS_CREATE,
            LEADS_UPDATE_STATUS,
            LEADS_ASSIGN,
            LEADS_DELETE,
            INVENTORY_READ,
            INVENTORY_ADJUST,
            INVENTORY_EXPORT,
            FULFILMENT_READ,
            FULFILMENT_UPDATE_STATUS,
            FULFILMENT_MANAGE_CONFIG,
            OFFERINGS_READ,
            WORKFORCE_READ,
            WEBSITE_READ,
        }
    ),
    "tmpl_cashier": frozenset({ORDERS_READ, ORDERS_UPDATE_STATUS, PAYMENTS_READ}),
    "tmpl_content_editor": frozenset(
        {
            OFFERINGS_READ,
            OFFERINGS_CREATE,
            OFFERINGS_UPDATE,
            OFFERINGS_ARCHIVE,
            OFFERINGS_MANAGE_AVAILABILITY,
            WEBSITE_READ,
            WEBSITE_EDIT,
            MARKETPLACE_READ,
        }
    ),
    "tmpl_inventory_manager": frozenset(
        {INVENTORY_READ, INVENTORY_ADJUST, INVENTORY_EXPORT, OFFERINGS_READ}
    ),
    "tmpl_booking_coordinator": frozenset(
        {
            BOOKINGS_READ,
            BOOKINGS_CREATE,
            BOOKINGS_UPDATE,
            BOOKINGS_CANCEL,
            BOOKINGS_MANAGE_AVAILABILITY,
            CUSTOMERS_READ,
            WORKFORCE_READ,
            NOTIFICATIONS_READ,
        }
    ),
    "tmpl_workforce_manager": frozenset(
        {
            WORKFORCE_READ,
            WORKFORCE_CREATE,
            WORKFORCE_UPDATE,
            WORKFORCE_MANAGE_AVAILABILITY,
            WORKFORCE_DEACTIVATE,
            BOOKINGS_READ,
            LOCATIONS_READ,
        }
    ),
    "tmpl_lead_handler": frozenset(
        {
            LEADS_READ,
            LEADS_CREATE,
            LEADS_UPDATE_STATUS,
            LEADS_ASSIGN,
            LEADS_DELETE,
            CUSTOMERS_READ,
            OFFERINGS_READ,
        }
    ),
}

PLATFORM_CORE_MODULE_IDS: tuple[str, ...] = (
    "core-business-identity",
    "core-business-profile",
    "core-website",
    "core-workspace",
    "core-settings",
    "core-locations",
    "core-team-access",
    "core-module-management",
    "core-notifications",
    "core-marketplace-presence",
)
