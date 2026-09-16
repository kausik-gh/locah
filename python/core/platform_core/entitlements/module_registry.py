"""Immutable module registry (Document 08 §21)."""

from __future__ import annotations

from platform_core.entitlements.models import ModuleDefinition
from platform_core.permissions import PLATFORM_CORE_MODULE_IDS


def _mod(
    module_id: str,
    display_name: str,
    module_class: str,
    description: str,
    dependencies: tuple[str, ...] = (),
    *,
    features: tuple[str, ...] = (),
) -> ModuleDefinition:
    return ModuleDefinition(
        module_id=module_id,
        display_name=display_name,
        module_class=module_class,
        description=description,
        dependencies=dependencies,
        features=features,
    )


_CORE_MODULES: dict[str, ModuleDefinition] = {
    mid: _mod(
        mid,
        display_name=mid.replace("core-", "").replace("-", " ").title(),
        module_class="platform_core",
        description="Platform Core capability",
        dependencies=() if mid == "core-business-identity" else ("core-business-identity",),
    )
    for mid in PLATFORM_CORE_MODULE_IDS
}

_OPTIONAL_MODULES: dict[str, ModuleDefinition] = {
    "offerings-catalog": _mod(
        "offerings-catalog",
        "Offerings Catalog",
        "optional",
        "Products, services, menu items, packages, and classes",
        ("core-business-profile",),
        features=("offerings-catalog.core", "offerings-catalog.variants"),
    ),
    "orders": _mod(
        "orders",
        "Orders",
        "optional",
        "Cart, purchase intent, and order lifecycle",
        ("offerings-catalog",),
        features=("orders.core", "orders.refunds"),
    ),
    "bookings": _mod(
        "bookings",
        "Bookings",
        "optional",
        "Appointments, reservations, and scheduled sessions",
        ("offerings-catalog",),
        features=("bookings.core", "bookings.availability"),
    ),
    "queue-operations": _mod(
        "queue-operations",
        "Queue Operations",
        "optional",
        "Walk-in queue and token management",
        ("core-team-access",),
        features=("queue-operations.core",),
    ),
    "customer-relationships": _mod(
        "customer-relationships",
        "Customer Relationships",
        "optional",
        "Customer records, history, and notes",
        ("core-business-identity",),
        features=("customer-relationships.core", "customer-relationships.timeline"),
    ),
    "leads": _mod(
        "leads",
        "Leads",
        "optional",
        "Enquiry capture and pipeline management",
        ("core-business-profile",),
        features=("leads.core", "leads.pipeline"),
    ),
    "inventory": _mod(
        "inventory",
        "Inventory",
        "optional",
        "Stock management by location",
        ("offerings-catalog",),
        features=(
            "inventory.core",
            "inventory.barcode",
            "inventory.stock_transfer",
            "inventory.purchase_orders",
            "inventory.batch_tracking",
            "inventory.expiry",
        ),
    ),
    "payments": _mod(
        "payments",
        "Payments",
        "optional",
        "Merchant payment collection and refunds",
        ("orders",),
        features=("payments.core", "payments.refunds"),
    ),
    "invoicing": _mod(
        "invoicing",
        "Invoicing",
        "optional",
        "Invoices and receivables",
        ("core-business-profile",),
        features=("invoicing.core",),
    ),
    "fulfilment": _mod(
        "fulfilment",
        "Fulfilment",
        "optional",
        "Pickup, delivery, and shipping orchestration",
        ("orders", "inventory"),
        features=("fulfilment.core", "fulfilment.delivery_zones"),
    ),
    "memberships": _mod(
        "memberships",
        "Memberships",
        "optional",
        "Customer membership plans and enrolment",
        ("payments",),
        features=("memberships.core", "memberships.renewals"),
    ),
    "loyalty": _mod(
        "loyalty",
        "Loyalty",
        "optional",
        "Points, tiers, and rewards",
        ("customer-relationships",),
        features=("loyalty.core",),
    ),
    "workforce": _mod(
        "workforce",
        "Workforce",
        "optional",
        "Staff and provider scheduling",
        ("core-team-access",),
        features=("workforce.core", "workforce.availability"),
    ),
    "payroll": _mod(
        "payroll",
        "Payroll",
        "optional",
        "Compensation and payout coordination",
        ("workforce",),
        features=("payroll.core",),
    ),
    "messaging": _mod(
        "messaging",
        "Messaging",
        "optional",
        "External messaging channels",
        ("core-notifications",),
        features=("messaging.core",),
    ),
    "marketing": _mod(
        "marketing",
        "Marketing",
        "optional",
        "Campaigns and promotional audiences",
        ("customer-relationships",),
        features=("marketing.core",),
    ),
    "reviews": _mod(
        "reviews",
        "Reviews",
        "optional",
        "Transaction-linked feedback",
        ("orders",),
        features=("reviews.core",),
    ),
    "analytics": _mod(
        "analytics",
        "Analytics",
        "optional",
        "Business reporting and insights",
        ("core-workspace",),
        features=("analytics.core", "analytics.advanced"),
    ),
    "business-passport": _mod(
        "business-passport",
        "Business Passport",
        "optional",
        "Verified credential dossier",
        ("core-business-profile",),
        features=("business-passport.core",),
    ),
    "business-community": _mod(
        "business-community",
        "Business Community",
        "optional",
        "Community posts and follows",
        ("core-marketplace-presence",),
        features=("business-community.core",),
    ),
    "b2b-network": _mod(
        "b2b-network",
        "B2B Network",
        "optional",
        "Supplier and partner discovery",
        ("core-business-profile",),
        features=("b2b-network.core",),
    ),
}

_MODULES: dict[str, ModuleDefinition] = {**_CORE_MODULES, **_OPTIONAL_MODULES}


class ModuleRegistry:
    @staticmethod
    def list_modules(*, module_class: str | None = None) -> list[dict[str, str]]:
        items: list[dict[str, str]] = []
        for module in sorted(_MODULES.values(), key=lambda m: m.module_id):
            if module_class and module.module_class != module_class:
                continue
            items.append(
                {
                    "module_id": module.module_id,
                    "display_name": module.display_name,
                    "module_class": module.module_class,
                }
            )
        return items

    @staticmethod
    def get(module_id: str) -> ModuleDefinition | None:
        return _MODULES.get(module_id.strip())

    @staticmethod
    def get_or_raise(module_id: str) -> ModuleDefinition:
        module = ModuleRegistry.get(module_id)
        if module is None:
            from platform_core.exceptions import ValidationError

            raise ValidationError(
                f"Unknown module '{module_id}'",
                details={"field": "module_id", "module_id": module_id},
            )
        return module

    @staticmethod
    def dependencies_satisfied(
        module_id: str, entitled_modules: frozenset[str]
    ) -> tuple[bool, tuple[str, ...]]:
        module = ModuleRegistry.get(module_id)
        if module is None:
            return False, (module_id,)
        missing = tuple(dep for dep in module.dependencies if dep not in entitled_modules)
        return len(missing) == 0, missing

    @staticmethod
    def platform_core_ids() -> frozenset[str]:
        return frozenset(PLATFORM_CORE_MODULE_IDS)
