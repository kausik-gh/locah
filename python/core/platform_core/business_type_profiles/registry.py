"""Immutable Business-Type Profile registry (Document 07 §10 — First Launch subset)."""

from __future__ import annotations

from platform_core.business_type_profiles.models import (
    PROFILE_VERSION,
    BusinessTypeProfile,
    DashboardSeed,
    ModuleSeed,
    NavigationSeed,
    OperationalDefaults,
)
from platform_core.business_types import DEFAULT_BUSINESS_TYPE, SUPPORTED_BUSINESS_TYPES


def _nav(*groups: tuple[str, str, tuple[str, ...]]) -> NavigationSeed:
    return NavigationSeed(
        groups=tuple(
            {"id": gid, "label": label, "emphasis_modules": list(mods)} for gid, label, mods in groups
        )
    )


def _profile(
    type_id: str,
    *,
    display_name: str,
    description: str,
    category: str,
    characteristics: tuple[str, ...],
    modules: tuple[tuple[str, str, int], ...],
    terminology: dict[str, str],
    dashboard: tuple[str, ...],
    operational: OperationalDefaults,
    navigation: NavigationSeed | None = None,
) -> BusinessTypeProfile:
    return BusinessTypeProfile(
        type_id=type_id,
        version=PROFILE_VERSION,
        display_name=display_name,
        description=description,
        category=category,
        characteristics=characteristics,
        module_seeds=tuple(
            ModuleSeed(module_id=mid, rationale=reason, rank=rank) for mid, reason, rank in modules
        ),
        navigation=navigation
        or _nav(
            ("operations", "Operations", tuple(m[0] for m in modules[:3])),
            ("growth", "Growth", tuple(m[0] for m in modules[3:5])),
        ),
        terminology=terminology,
        dashboard=DashboardSeed(emphasis=dashboard),
        operational_defaults=operational,
    )


_PLATFORM_DEFAULT = _profile(
    "not_sure",
    display_name="General Business",
    description="Neutral platform default when no specific type is selected.",
    category="platform_default",
    characteristics=("provides_services", "has_team"),
    modules=(
        ("core-website", "Establish public presence", 1),
        ("customer-relationships", "Manage customer relationships", 2),
    ),
    terminology={
        "customer": "Customer",
        "order": "Order",
        "product": "Product",
        "appointment": "Appointment",
        "staff": "Team Member",
    },
    dashboard=("setup_progress", "recent_activity"),
    operational=OperationalDefaults(),
)

_PROFILES: dict[str, BusinessTypeProfile] = {
    "restaurant": _profile(
        "restaurant",
        display_name="Restaurant / Food Service",
        description="Menu-led food service with orders, reservations, and fulfilment.",
        category="food_service",
        characteristics=(
            "sells_products",
            "accepts_orders",
            "accepts_appointments",
            "has_physical_locations",
            "delivers",
        ),
        modules=(
            ("core-website", "Publish menu and location information", 1),
            ("offerings-catalog", "Publish your menu", 2),
            ("orders", "Receive and manage orders", 3),
            ("bookings", "Table reservations", 4),
            ("fulfilment", "Delivery and pickup coordination", 5),
            ("customer-relationships", "Guest relationship management", 6),
        ),
        terminology={
            "customer": "Guest",
            "order": "Order",
            "product": "Menu Item",
            "appointment": "Reservation",
            "staff": "Staff",
        },
        dashboard=("current_orders", "preparation_status", "reservations", "fulfilment_exceptions"),
        operational=OperationalDefaults(
            booking_enabled=True,
            inventory_enabled=False,
            delivery_enabled=True,
            working_mode="multi_location",
            location_behavior="physical_required",
        ),
        navigation=_nav(
            ("kitchen", "Kitchen & Orders", ("offerings-catalog", "orders")),
            ("front_of_house", "Front of House", ("bookings", "customer-relationships")),
            ("fulfilment", "Fulfilment", ("fulfilment",)),
        ),
    ),
    "cafe": _profile(
        "cafe",
        display_name="Café / Small Food Business",
        description="Small menu-led operation with pickup or delivery.",
        category="food_service",
        characteristics=("sells_products", "accepts_orders", "delivers"),
        modules=(
            ("core-website", "Publish menu and availability", 1),
            ("offerings-catalog", "Publish your menu", 2),
            ("orders", "Manage orders", 3),
            ("fulfilment", "Pickup and delivery", 4),
            ("customer-relationships", "Customer communication", 5),
        ),
        terminology={
            "customer": "Customer",
            "order": "Order",
            "product": "Menu Item",
            "appointment": "Pickup Slot",
            "staff": "Staff",
        },
        dashboard=("new_orders", "preparation", "availability"),
        operational=OperationalDefaults(
            booking_enabled=False,
            delivery_enabled=True,
            working_mode="single_location",
            location_behavior="physical_optional",
        ),
    ),
    "retail": _profile(
        "retail",
        display_name="Retail / Commerce",
        description="Product-led commerce with inventory and fulfilment.",
        category="commerce",
        characteristics=("sells_products", "accepts_orders", "has_physical_locations"),
        modules=(
            ("core-website", "Storefront presence", 1),
            ("offerings-catalog", "Product catalogue", 2),
            ("orders", "Receive and manage orders", 3),
            ("inventory", "Stock management", 4),
            ("fulfilment", "Shipping and pickup", 5),
            ("customer-relationships", "Customer retention", 6),
        ),
        terminology={
            "customer": "Customer",
            "order": "Order",
            "product": "Product",
            "appointment": "Appointment",
            "staff": "Staff",
        },
        dashboard=("orders", "low_stock", "fulfilment", "sales_activity"),
        operational=OperationalDefaults(
            inventory_enabled=True,
            delivery_enabled=True,
            working_mode="multi_location",
            location_behavior="physical_optional",
        ),
    ),
    "clinic": _profile(
        "clinic",
        display_name="Clinic / Healthcare Service",
        description="Provider-led scheduled healthcare services.",
        category="healthcare",
        characteristics=("provides_services", "accepts_appointments", "has_team"),
        modules=(
            ("core-website", "Services and provider information", 1),
            ("bookings", "Appointment scheduling", 2),
            ("workforce", "Provider availability", 3),
            ("customer-relationships", "Patient follow-up", 4),
        ),
        terminology={
            "customer": "Patient",
            "order": "Visit",
            "product": "Service",
            "appointment": "Appointment",
            "staff": "Provider",
        },
        dashboard=("upcoming_appointments", "provider_availability", "follow_up"),
        operational=OperationalDefaults(
            booking_enabled=True,
            default_service_duration_minutes=30,
            working_mode="multi_location",
            location_behavior="physical_required",
        ),
    ),
    "gym": _profile(
        "gym",
        display_name="Gym / Fitness",
        description="Membership-led fitness with classes and trainers.",
        category="fitness",
        characteristics=("has_memberships", "runs_classes", "has_team"),
        modules=(
            ("core-website", "Membership and class presentation", 1),
            ("memberships", "Membership plans", 2),
            ("bookings", "Classes and sessions", 3),
            ("customer-relationships", "Member relationships", 4),
        ),
        terminology={
            "customer": "Member",
            "order": "Enrollment",
            "product": "Membership",
            "appointment": "Session",
            "staff": "Trainer",
        },
        dashboard=("todays_classes", "attendance", "expiring_memberships", "renewals"),
        operational=OperationalDefaults(
            booking_enabled=True,
            working_mode="multi_location",
            location_behavior="physical_required",
        ),
    ),
    "salon": _profile(
        "salon",
        display_name="Salon / Personal Care",
        description="Appointment-led personal care services.",
        category="personal_care",
        characteristics=("provides_services", "accepts_appointments", "has_team"),
        modules=(
            ("core-website", "Services and team presentation", 1),
            ("bookings", "Appointment scheduling", 2),
            ("customer-relationships", "Client follow-up", 3),
        ),
        terminology={
            "customer": "Client",
            "order": "Booking",
            "product": "Service",
            "appointment": "Appointment",
            "staff": "Stylist",
        },
        dashboard=("todays_appointments", "staff_schedule", "availability_gaps"),
        operational=OperationalDefaults(
            booking_enabled=True,
            default_service_duration_minutes=60,
            working_mode="single_location",
        ),
    ),
    "spa": _profile(
        "spa",
        display_name="Spa / Wellness",
        description="Wellness and treatment appointments.",
        category="personal_care",
        characteristics=("provides_services", "accepts_appointments", "has_team"),
        modules=(
            ("core-website", "Treatments and wellness presentation", 1),
            ("bookings", "Treatment appointments", 2),
            ("customer-relationships", "Guest wellness journey", 3),
        ),
        terminology={
            "customer": "Guest",
            "order": "Booking",
            "product": "Treatment",
            "appointment": "Appointment",
            "staff": "Therapist",
        },
        dashboard=("todays_appointments", "therapist_schedule", "packages"),
        operational=OperationalDefaults(
            booking_enabled=True,
            default_service_duration_minutes=90,
            working_mode="single_location",
        ),
    ),
    "hotel": _profile(
        "hotel",
        display_name="Hotel / Hospitality",
        description="Accommodation-led hospitality with bookings.",
        category="hospitality",
        characteristics=("provides_services", "accepts_appointments", "has_physical_locations"),
        modules=(
            ("core-website", "Property and room presentation", 1),
            ("bookings", "Room reservations", 2),
            ("customer-relationships", "Guest relationships", 3),
        ),
        terminology={
            "customer": "Guest",
            "order": "Reservation",
            "product": "Room",
            "appointment": "Check-in",
            "staff": "Staff",
        },
        dashboard=("arrivals", "departures", "occupancy", "guest_requests"),
        operational=OperationalDefaults(
            booking_enabled=True,
            working_mode="multi_location",
            location_behavior="physical_required",
        ),
    ),
    "homestay": _profile(
        "homestay",
        display_name="Homestay / Short Stay",
        description="Small-scale accommodation and guest stays.",
        category="hospitality",
        characteristics=("provides_services", "accepts_appointments"),
        modules=(
            ("core-website", "Listing and availability", 1),
            ("bookings", "Stay reservations", 2),
            ("customer-relationships", "Guest communication", 3),
        ),
        terminology={
            "customer": "Guest",
            "order": "Booking",
            "product": "Stay",
            "appointment": "Check-in",
            "staff": "Host",
        },
        dashboard=("upcoming_stays", "availability", "guest_messages"),
        operational=OperationalDefaults(
            booking_enabled=True,
            working_mode="single_location",
            location_behavior="physical_required",
        ),
    ),
    "studio": _profile(
        "studio",
        display_name="Studio",
        description="Class and session-based studio operations.",
        category="fitness",
        characteristics=("runs_classes", "accepts_appointments", "has_team"),
        modules=(
            ("core-website", "Classes and schedule", 1),
            ("bookings", "Class bookings", 2),
            ("customer-relationships", "Member and attendee management", 3),
        ),
        terminology={
            "customer": "Member",
            "order": "Booking",
            "product": "Class",
            "appointment": "Session",
            "staff": "Instructor",
        },
        dashboard=("todays_sessions", "attendance", "schedule"),
        operational=OperationalDefaults(booking_enabled=True),
    ),
    "professional_service": _profile(
        "professional_service",
        display_name="Professional Services",
        description="Expertise-led services with enquiries and appointments.",
        category="professional",
        characteristics=("provides_services", "accepts_appointments"),
        modules=(
            ("core-website", "Credibility and services", 1),
            ("leads", "Enquiry capture", 2),
            ("bookings", "Consultation scheduling", 3),
            ("customer-relationships", "Client relationships", 4),
        ),
        terminology={
            "customer": "Client",
            "order": "Engagement",
            "product": "Service",
            "appointment": "Consultation",
            "staff": "Consultant",
        },
        dashboard=("new_enquiries", "follow_ups", "appointments"),
        operational=OperationalDefaults(
            booking_enabled=True,
            working_mode="single_location",
            location_behavior="online_only",
        ),
    ),
    "education": _profile(
        "education",
        display_name="Education / Training",
        description="Courses, classes, and cohort-based learning.",
        category="education",
        characteristics=("runs_classes", "has_team"),
        modules=(
            ("core-website", "Programs and courses", 1),
            ("bookings", "Classes and cohorts", 2),
            ("customer-relationships", "Learner relationships", 3),
        ),
        terminology={
            "customer": "Learner",
            "order": "Enrollment",
            "product": "Course",
            "appointment": "Class",
            "staff": "Instructor",
        },
        dashboard=("upcoming_classes", "enrollments", "attendance"),
        operational=OperationalDefaults(booking_enabled=True),
    ),
    "other": _profile(
        "other",
        display_name="Other",
        description="Generic profile for businesses without a specific vertical.",
        category="general",
        characteristics=("provides_services",),
        modules=(
            ("core-website", "Establish public presence", 1),
            ("customer-relationships", "Manage customer relationships", 2),
        ),
        terminology={
            "customer": "Customer",
            "order": "Order",
            "product": "Product",
            "appointment": "Appointment",
            "staff": "Team Member",
        },
        dashboard=("setup_progress", "recent_activity"),
        operational=OperationalDefaults(),
    ),
}

# Alias platform default for not_sure
_PROFILES["not_sure"] = BusinessTypeProfile(
    type_id="not_sure",
    version=_PLATFORM_DEFAULT.version,
    display_name="Not sure yet",
    description="Skipped type selection; neutral recommendations apply.",
    category=_PLATFORM_DEFAULT.category,
    characteristics=_PLATFORM_DEFAULT.characteristics,
    module_seeds=_PLATFORM_DEFAULT.module_seeds,
    navigation=_PLATFORM_DEFAULT.navigation,
    terminology=_PLATFORM_DEFAULT.terminology,
    dashboard=_PLATFORM_DEFAULT.dashboard,
    operational_defaults=_PLATFORM_DEFAULT.operational_defaults,
)


class BusinessTypeProfileRegistry:
    """Immutable versioned registry of supported Business-Type profiles."""

    @staticmethod
    def list_types() -> list[dict[str, str]]:
        return [
            {
                "type_id": profile.type_id,
                "display_name": profile.display_name,
                "category": profile.category,
                "version": profile.version,
                "status": profile.status,
            }
            for type_id in sorted(SUPPORTED_BUSINESS_TYPES)
            if (profile := _PROFILES.get(type_id)) is not None
        ]

    @staticmethod
    def get(type_id: str) -> BusinessTypeProfile | None:
        normalized = type_id.strip().lower()
        if normalized not in SUPPORTED_BUSINESS_TYPES:
            return None
        return _PROFILES.get(normalized, _PROFILES[DEFAULT_BUSINESS_TYPE])

    @staticmethod
    def get_or_default(type_id: str | None) -> BusinessTypeProfile:
        if not type_id:
            return _PROFILES[DEFAULT_BUSINESS_TYPE]
        profile = BusinessTypeProfileRegistry.get(type_id)
        return profile if profile is not None else _PROFILES[DEFAULT_BUSINESS_TYPE]
