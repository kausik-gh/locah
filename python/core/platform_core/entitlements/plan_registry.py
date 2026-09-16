"""Immutable plan registry (Document 08 §5 — illustrative First Launch packaging)."""

from __future__ import annotations

from platform_core.entitlements.models import REGISTRY_VERSION, PlanDefinition, UsageLimit

_FOUNDATION_MODULES = frozenset(
    {
        "offerings-catalog",
        "orders",
        "bookings",
        "payments",
        "memberships",
        "customer-relationships",
        "leads",
        "inventory",
        "fulfilment",
        "workforce",
    }
)

_FOUNDATION_FEATURES = frozenset(
    {
        "offerings-catalog.core",
        "offerings-catalog.variants",
        "orders.core",
        "orders.refunds",
        "bookings.core",
        "bookings.availability",
        "payments.core",
        "payments.refunds",
        "memberships.core",
        "memberships.renewals",
        "customer-relationships.core",
        "customer-relationships.timeline",
        "leads.core",
        "leads.pipeline",
        "inventory.core",
        "inventory.barcode",
        "fulfilment.core",
        "fulfilment.delivery_zones",
        "workforce.core",
        "workforce.availability",
    }
)

_GROWTH_MODULES = _FOUNDATION_MODULES | frozenset({"analytics", "messaging", "marketing", "reviews"})
_GROWTH_FEATURES = _FOUNDATION_FEATURES | frozenset(
    {
        "analytics.core",
        "messaging.core",
        "marketing.core",
        "reviews.core",
        "inventory.stock_transfer",
        "inventory.purchase_orders",
    }
)

_FOUNDATION_LIMITS = (
    UsageLimit("employees", "Team members", 10),
    UsageLimit("customers", "Customers", 1000),
    UsageLimit("locations", "Locations", 3),
    UsageLimit("products", "Products / offerings", 500),
    UsageLimit("bookings", "Bookings per month", None),
    UsageLimit("storage_mb", "Storage", 1024),
    UsageLimit("api_calls", "API calls per month", None),
    UsageLimit("reservations", "Reservations per month", None),
)

_GROWTH_LIMITS = (
    UsageLimit("employees", "Team members", 50),
    UsageLimit("customers", "Customers", 10000),
    UsageLimit("locations", "Locations", 10),
    UsageLimit("products", "Products / offerings", 5000),
    UsageLimit("bookings", "Bookings per month", None),
    UsageLimit("storage_mb", "Storage", 5120),
    UsageLimit("api_calls", "API calls per month", None),
    UsageLimit("reservations", "Reservations per month", None),
)

DEFAULT_PLAN_ID = "foundation"

_PLANS: dict[str, PlanDefinition] = {
    "foundation": PlanDefinition(
        plan_id="foundation",
        version=REGISTRY_VERSION,
        display_name="Foundation",
        description="First Launch base plan with Platform Core and launch-ready optional modules.",
        module_ids=_FOUNDATION_MODULES,
        feature_ids=_FOUNDATION_FEATURES,
        usage_limits=_FOUNDATION_LIMITS,
    ),
    "growth": PlanDefinition(
        plan_id="growth",
        version=REGISTRY_VERSION,
        display_name="Growth",
        description="Expanded module and limit package for growing businesses.",
        module_ids=_GROWTH_MODULES,
        feature_ids=_GROWTH_FEATURES,
        usage_limits=_GROWTH_LIMITS,
    ),
}


class PlanRegistry:
    @staticmethod
    def list_plans() -> list[dict[str, str]]:
        return [
            {
                "plan_id": plan.plan_id,
                "display_name": plan.display_name,
                "version": plan.version,
                "status": plan.status,
            }
            for plan_id in sorted(_PLANS)
            if (plan := _PLANS.get(plan_id)) is not None
        ]

    @staticmethod
    def get(plan_id: str) -> PlanDefinition | None:
        return _PLANS.get(plan_id.strip().lower())

    @staticmethod
    def get_or_default(plan_id: str | None) -> PlanDefinition:
        if not plan_id:
            return _PLANS[DEFAULT_PLAN_ID]
        return _PLANS.get(plan_id.strip().lower(), _PLANS[DEFAULT_PLAN_ID])

    @staticmethod
    def get_or_raise(plan_id: str) -> PlanDefinition:
        plan = PlanRegistry.get(plan_id)
        if plan is None:
            from platform_core.exceptions import ValidationError

            raise ValidationError(
                f"Unknown plan '{plan_id}'",
                details={"field": "plan_id", "plan_id": plan_id},
            )
        if plan.status != "active":
            from platform_core.exceptions import ValidationError

            raise ValidationError(
                f"Plan '{plan_id}' is not active",
                details={"field": "plan_id", "status": plan.status},
            )
        return plan
