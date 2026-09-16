"""Platform capability definitions consumed by PlatformCapabilityResolver."""

from __future__ import annotations

from platform_core.entitlements.models import CapabilityDefinition

CAPABILITIES: dict[str, CapabilityDefinition] = {
    "use_inventory": CapabilityDefinition(
        "use_inventory",
        "Use Inventory",
        required_module_id="inventory",
        required_feature_id="inventory.core",
    ),
    "use_crm": CapabilityDefinition(
        "use_crm",
        "Use CRM",
        required_module_id="customer-relationships",
        required_feature_id="customer-relationships.core",
    ),
    "use_pos": CapabilityDefinition(
        "use_pos",
        "Use Point of Sale / Orders",
        required_module_id="orders",
        required_feature_id="orders.core",
    ),
    "create_locations": CapabilityDefinition(
        "create_locations",
        "Create Locations",
        required_module_id="core-locations",
        limit_key="locations",
    ),
    "create_employees": CapabilityDefinition(
        "create_employees",
        "Create Employees / Workforce",
        required_module_id="workforce",
        required_feature_id="workforce.core",
        limit_key="employees",
    ),
    "use_bookings": CapabilityDefinition(
        "use_bookings",
        "Use Bookings",
        required_module_id="bookings",
        required_feature_id="bookings.core",
        limit_key="bookings",
    ),
    "use_analytics": CapabilityDefinition(
        "use_analytics",
        "Use Analytics",
        required_module_id="analytics",
        required_feature_id="analytics.core",
    ),
    "use_payments": CapabilityDefinition(
        "use_payments",
        "Use Payments",
        required_module_id="payments",
        required_feature_id="payments.core",
    ),
    "use_memberships": CapabilityDefinition(
        "use_memberships",
        "Use Memberships",
        required_module_id="memberships",
        required_feature_id="memberships.core",
    ),
    "use_leads": CapabilityDefinition(
        "use_leads",
        "Use Leads",
        required_module_id="leads",
        required_feature_id="leads.core",
    ),
    "use_fulfilment": CapabilityDefinition(
        "use_fulfilment",
        "Use Fulfilment",
        required_module_id="fulfilment",
        required_feature_id="fulfilment.core",
    ),
}


class CapabilityRegistry:
    @staticmethod
    def list_capabilities() -> list[dict[str, str]]:
        return [
            {
                "capability_id": cap.capability_id,
                "display_name": cap.display_name,
            }
            for cap in CAPABILITIES.values()
        ]

    @staticmethod
    def get(capability_id: str) -> CapabilityDefinition | None:
        return CAPABILITIES.get(capability_id.strip())
