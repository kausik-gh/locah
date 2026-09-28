"""Role templates (Capability Universe §7.2–§7.3; Business OS Guide §5).

"A role is not just a sidebar label. It is permissions + scope + default
surface." Each template below is one row of the §7.2 table: what the person
sees and does (as permissions that exist today), their scope, the surface they
work on and the question their home screen answers.

A template is only offered to an owner when its phase is current, its surface
exists and the business runs a module it is about — the rest stay in the
registry, invisible, until they ship (Guide §4: never present something as
working before its data, API, permissions and UI are complete).
"""

from __future__ import annotations

from dataclasses import dataclass

import platform_core.permissions as p

SCOPES = ("business", "location", "assignment", "self")
SCOPE_WORDS = {
    "business": "All records in the business",
    "location": "Records at the locations you choose",
    "assignment": "Only records assigned to them",
    "self": "Only their own profile and time",
}
SURFACES = {"workspace": "Workspace", "pos": "Counter billing (POS)", "crew": "Crew app", "kitchen": "Kitchen display"}
# Surfaces that exist today (POS since P1-05); crew and kitchen join in P2.
BUILT_SURFACES = frozenset({"workspace", "pos"})
CURRENT_PHASES = frozenset({"P1"})


@dataclass(frozen=True)
class RoleTemplate:
    key: str
    label: str
    does: str  # §7.2 "Sees and does", owner words
    scope: str
    surface: str
    home: str  # §7.2 "Home screen answers"
    permissions: frozenset[str]
    about: tuple[str, ...]  # modules that make this role relevant (any one); () = always
    phase: str
    system_role: str = p.ROLE_MEMBER

    def offered(self, operational_modules: set[str] | frozenset[str]) -> bool:
        return (
            self.phase in CURRENT_PHASES
            and self.surface in BUILT_SURFACES
            and (not self.about or any(m in operational_modules for m in self.about))
        )


_READ_BASICS = frozenset({p.BUSINESS_READ, p.LOCATIONS_READ, p.NOTIFICATIONS_READ})

ROLE_TEMPLATES: dict[str, RoleTemplate] = {t.key: t for t in (
    RoleTemplate(
        "manager", "Manager", "Runs day-to-day operations: orders, bookings, stock, staff rota and customers",
        "location", "workspace", "What is late or stuck at my location?",
        _READ_BASICS | {
            p.ORDERS_READ, p.ORDERS_CREATE, p.ORDERS_UPDATE_STATUS, p.ORDERS_CANCEL, p.ORDERS_REFUND_COORDINATE,
            p.BOOKINGS_READ, p.BOOKINGS_CREATE, p.BOOKINGS_UPDATE, p.BOOKINGS_CANCEL, p.BOOKINGS_MANAGE_AVAILABILITY,
            p.QUOTES_READ, p.QUOTES_CREATE, p.QUOTES_UPDATE, p.QUOTES_ISSUE,
            p.CUSTOMERS_READ, p.CUSTOMERS_UPDATE, p.CUSTOMERS_MANAGE_NOTES,
            p.LEADS_READ, p.LEADS_CREATE, p.LEADS_UPDATE_STATUS, p.LEADS_ASSIGN,
            p.PROJECTS_READ, p.PROJECTS_CREATE, p.PROJECTS_UPDATE, p.PROJECTS_MANAGE_LIFECYCLE, p.PROJECTS_ASSIGN,
            p.INVENTORY_READ, p.INVENTORY_ADJUST, p.INVENTORY_EXPORT, p.INVENTORY_APPROVE, p.INVENTORY_COST,
            p.FULFILMENT_READ, p.FULFILMENT_UPDATE_STATUS, p.FULFILMENT_MANAGE_CONFIG,
            p.OFFERINGS_READ, p.OFFERINGS_UPDATE, p.OFFERINGS_MANAGE_AVAILABILITY,
            p.MEMBERSHIPS_READ, p.MEMBERSHIPS_MANAGE_ENROLMENT, p.MEMBERSHIPS_CANCEL_ENROLMENT,
            p.WORKFORCE_READ, p.WORKFORCE_UPDATE, p.WORKFORCE_MANAGE_AVAILABILITY,
            p.PAYMENTS_READ, p.WEBSITE_READ, p.MARKETPLACE_READ, p.TEAM_READ, p.SETTINGS_READ, p.MODULES_READ,
            p.INVOICES_READ, p.INVOICES_ISSUE, p.INVOICES_CANCEL, p.INVOICES_RECORD_PAYMENT,
            p.POS_USE, p.POS_APPROVE, p.LEDGER_READ, p.LEDGER_RECORD,
            p.MESSAGING_READ, p.MESSAGING_REPLY, p.REVIEWS_READ, p.REVIEWS_REPLY, p.COMPLIANCE_READ,
        },
        (), "P1", system_role=p.ROLE_MANAGER,
    ),
    RoleTemplate(
        "store_keeper", "Store keeper", "Looks after stock: counts, adjustments and what is running low",
        "location", "workspace", "What is low, what arrived",
        _READ_BASICS | {p.INVENTORY_READ, p.INVENTORY_ADJUST, p.INVENTORY_EXPORT, p.OFFERINGS_READ},
        ("inventory",), "P1",
    ),
    RoleTemplate(
        "accountant", "Accountant", "Sees money in and out, and exports it; never messages customers",
        "business", "workspace", "Unpaid, unsynced, due",
        _READ_BASICS | {
            p.PAYMENTS_READ, p.PAYMENTS_EXPORT, p.ORDERS_READ, p.QUOTES_READ, p.MEMBERSHIPS_READ,
            p.CUSTOMERS_READ, p.INVENTORY_READ, p.INVENTORY_EXPORT, p.INVENTORY_COST, p.SETTINGS_READ,
            p.INVOICES_READ, p.INVOICES_ISSUE, p.INVOICES_CANCEL, p.INVOICES_RECORD_PAYMENT, p.INVOICES_EXPORT,
            p.INVOICES_CONFIGURE, p.LEDGER_READ, p.LEDGER_RECORD, p.LEDGER_MANAGE,
            p.COMPLIANCE_READ, p.COMPLIANCE_MANAGE,
        },
        ("payments", "orders", "quotes", "memberships", "invoicing", "ledger", "compliance"), "P1",
    ),
    RoleTemplate(
        "cashier", "Cashier", "Bills at the counter, takes payments, handles returns under a limit and the cash shift",
        "location", "pos", "Open shift, bills, drawer balance",
        _READ_BASICS | {p.ORDERS_READ, p.ORDERS_CREATE, p.ORDERS_UPDATE_STATUS, p.PAYMENTS_READ,
                        p.CUSTOMERS_READ, p.OFFERINGS_READ, p.INVOICES_READ, p.INVOICES_ISSUE, p.POS_USE,
                        p.LEDGER_READ, p.LEDGER_RECORD},
        ("pos",), "P1",
    ),
    # ---- later phases: kept here so the registry mirrors §7.2, never offered yet.
    RoleTemplate(
        "front_desk", "Front desk", "Bookings, queue, check-ins, customers and collecting payments",
        "location", "workspace", "Who is here, who is next, who owes?",
        _READ_BASICS | {p.BOOKINGS_READ, p.BOOKINGS_CREATE, p.BOOKINGS_UPDATE, p.BOOKINGS_CANCEL,
                        p.CUSTOMERS_READ, p.CUSTOMERS_UPDATE, p.CUSTOMERS_MANAGE_NOTES, p.PAYMENTS_READ,
                        p.MEMBERSHIPS_READ, p.MEMBERSHIPS_MANAGE_ENROLMENT},
        ("bookings", "memberships"), "P2",
    ),
    RoleTemplate(
        "provider", "Provider", "Their own schedule, appointments and booking notes",
        "assignment", "workspace", "My next appointment and my day",
        _READ_BASICS | {p.BOOKINGS_READ, p.BOOKINGS_UPDATE, p.CUSTOMERS_READ},
        ("bookings",), "P2",
    ),
    RoleTemplate(
        "kitchen", "Kitchen", "Tickets for their station; no prices or phone numbers",
        "location", "kitchen", "What to cook next", frozenset({p.ORDERS_READ}), ("orders",), "P2",
    ),
    RoleTemplate(
        "dispatcher", "Dispatcher", "Dispatch board: assign crew, reassign failed jobs",
        "location", "workspace", "Unassigned and late deliveries",
        _READ_BASICS | {p.FULFILMENT_READ, p.FULFILMENT_UPDATE_STATUS, p.ORDERS_READ, p.WORKFORCE_READ},
        ("fulfilment",), "P2",
    ),
    RoleTemplate(
        "delivery_partner", "Delivery partner", "Their assigned deliveries; the customer's phone only while the job is active",
        "assignment", "crew", "My next drop", frozenset({p.FULFILMENT_READ, p.FULFILMENT_UPDATE_STATUS}),
        ("fulfilment",), "P2",
    ),
    RoleTemplate(
        "technician", "Technician", "Assigned job cards, parts used, photos and that asset's service history",
        "assignment", "crew", "My next job", frozenset(), (), "P5",
    ),
    RoleTemplate(
        "housekeeping", "Housekeeping", "Assigned room and area tasks",
        "assignment", "crew", "Rooms to turn around", frozenset(), (), "P2",
    ),
    RoleTemplate(
        "sales_executive", "Sales executive", "Assigned leads, quotes and site visits",
        "assignment", "workspace", "Follow-ups due today",
        _READ_BASICS | {p.LEADS_READ, p.LEADS_CREATE, p.LEADS_UPDATE_STATUS, p.QUOTES_READ, p.QUOTES_CREATE,
                        p.QUOTES_UPDATE, p.CUSTOMERS_READ},
        ("leads", "quotes"), "P2",
    ),
    RoleTemplate(
        "teacher", "Teacher", "Own batches: attendance, assessments, announcements",
        "assignment", "workspace", "Today's classes", frozenset(), (), "P5",
    ),
    RoleTemplate(
        "marketer", "Marketer", "Campaigns and audiences as counts; cannot export phone numbers",
        "business", "workspace", "What is running and what it earned",
        _READ_BASICS | {p.OFFERINGS_READ, p.WEBSITE_READ, p.MARKETPLACE_READ, p.REVIEWS_READ}, (), "P3",
    ),
)}

OWNER = RoleTemplate(
    "owner", "Owner", "Everything, approvals, billing and AI limits", "business", "workspace",
    "Needs you now · Today · Your business", frozenset(p.ALL_PERMISSIONS), (), "P1",
    system_role=p.ROLE_PRIMARY_OWNER,
)

# Every permission in the words an owner reads when adjusting a role.
PERMISSION_WORDS: dict[str, str] = {
    "bookings.read": "See bookings", "bookings.create": "Make bookings", "bookings.update": "Change bookings",
    "bookings.cancel": "Cancel bookings", "bookings.manage_availability": "Set booking hours and slots",
    "business.read": "See the business profile", "business.update": "Edit the business profile",
    "business.publish": "Publish the business", "business.close": "Close the business",
    "commercial.read": "See the LOCAH plan", "commercial.manage": "Change the LOCAH plan",
    "configuration.read": "See configuration", "configuration.update": "Change configuration",
    "customers.read": "See customers", "customers.update": "Edit customers",
    "customers.manage_notes": "Write customer notes", "customers.export": "Export customer details",
    "entitlements.read": "See what the plan includes", "entitlements.update": "Change what the plan includes",
    "fulfilment.read": "See deliveries and pickups", "fulfilment.update_status": "Update delivery status",
    "fulfilment.manage_config": "Set delivery zones and fees",
    "ledger.read": "See who owes what (khata)", "ledger.record": "Give credit and record money received",
    "ledger.manage": "Set credit limits and correct accounts",
    "messaging.read": "See WhatsApp chats", "messaging.reply": "Reply to customers on WhatsApp",
    "messaging.configure": "Connect WhatsApp and choose automatic messages",
    "reviews.read": "See reviews", "reviews.reply": "Reply to reviews publicly",
    "reviews.manage": "Feature reviews on the website and report violations to LOCAH",
    "compliance.read": "See licences and filing dates", "compliance.manage": "Record and renew licences and filings",
    "pos.use": "Bill at the counter and run a cash shift", "pos.approve": "Approve counter overrides with a PIN",
    "pos.configure": "Set counter billing rules",
    "invoices.read": "See bills and invoices", "invoices.issue": "Issue bills and credit notes",
    "invoices.cancel": "Cancel bills", "invoices.record_payment": "Record money received on bills",
    "invoices.export": "Export for the CA", "invoices.configure": "Set up GST and tax rates",
    "inventory.read": "See stock", "inventory.adjust": "Adjust stock", "inventory.export": "Export stock",
    "inventory.approve": "Approve stock count differences", "inventory.cost": "See what stock cost and is worth",
    "leads.read": "See enquiries", "leads.create": "Add enquiries", "leads.update_status": "Move enquiries along",
    "leads.assign": "Assign enquiries", "leads.delete": "Delete enquiries",
    "locations.read": "See locations", "locations.create": "Add locations", "locations.update": "Edit locations",
    "locations.delete": "Remove locations",
    "marketplace.read": "See the Marketplace listing", "marketplace.configure": "Change the Marketplace listing",
    "memberships.read": "See plans and members", "memberships.create_plan": "Create membership plans",
    "memberships.update_plan": "Edit membership plans", "memberships.manage_enrolment": "Enrol and renew members",
    "memberships.cancel_enrolment": "Cancel memberships",
    "modules.read": "See tools", "modules.enable": "Switch tools on", "modules.deactivate": "Switch tools off",
    "modules.configure": "Set up tools",
    "notifications.read": "Get notifications", "notifications.manage_preferences": "Change notification settings",
    "offerings.read": "See products and services", "offerings.create": "Add products and services",
    "offerings.update": "Edit products and services", "offerings.archive": "Remove products and services",
    "offerings.manage_availability": "Mark items in or out of stock",
    "orders.read": "See orders", "orders.create": "Take orders", "orders.update_status": "Move orders along",
    "orders.cancel": "Cancel orders", "orders.refund_coordinate": "Arrange refunds",
    "payments.read": "See payments", "payments.export": "Export payments", "payments.refund": "Refund payments",
    "payments.manage_connection": "Connect the payment account",
    "permissions.read": "See who can do what", "permissions.update": "Change who can do what",
    "projects.read": "See projects", "projects.create": "Start projects", "projects.update": "Edit projects",
    "projects.manage_lifecycle": "Open and close projects", "projects.assign": "Assign project work",
    "quotes.read": "See quotes", "quotes.create": "Write quotes", "quotes.update": "Edit quotes",
    "quotes.issue": "Send quotes",
    "settings.read": "See settings", "settings.update": "Change settings",
    "team.read": "See the team", "team.invite": "Add people", "team.update_role": "Change people's roles",
    "team.remove": "Remove people", "team.manage_templates": "Create custom roles",
    "website.read": "See the website", "website.edit": "Edit the website", "website.publish": "Publish the website",
    "website.unpublish": "Take the website offline",
    "workforce.read": "See staff and schedules", "workforce.create": "Add staff profiles",
    "workforce.update": "Edit staff and rota", "workforce.deactivate": "Deactivate staff",
    "workforce.manage_availability": "Set staff availability",
}


def role_permissions(key: str) -> frozenset[str]:
    tpl = ROLE_TEMPLATES.get(key)
    return tpl.permissions if tpl else frozenset()


def describe(tpl: RoleTemplate) -> dict[str, object]:
    return {
        "key": tpl.key, "label": tpl.label, "does": tpl.does, "scope": tpl.scope,
        "scope_words": SCOPE_WORDS[tpl.scope], "surface": tpl.surface, "surface_words": SURFACES[tpl.surface],
        "home": tpl.home, "permissions": sorted(tpl.permissions),
    }
