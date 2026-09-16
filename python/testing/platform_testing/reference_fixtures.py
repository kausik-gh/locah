"""The 11 First-Launch reference Business models (Doc 11 §5.2, §15) as runnable
fixtures.

Not `business_type` string labels — each entry provisions a Business through the
real API: the canonical modules for that model enabled, a representative
offering of the right shape, a location, and a workforce provider where the
model needs one. Stage 8 runs its end-to-end journey against the result.

    from platform_testing.reference_fixtures import REFERENCE_MODELS, build_reference_business

    for model in REFERENCE_MODELS:
        bid = build_reference_business(client, owner_headers, model)
        # ... run model.workflow against bid

`model.canonical_modules` is the Doc 11 §5.2 "Primary canonical modules" list;
`build_reference_business` enables exactly those (plus their dependencies).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol, cast


class _Client(Protocol):
    def post(self, url: str, **kw: Any) -> Any: ...
    def get(self, url: str, **kw: Any) -> Any: ...


Headers = dict[str, str]


@dataclass(frozen=True)
class OfferingSpec:
    title: str
    offering_type: str  # product | service | class_session
    price_amount: float
    track_inventory: bool = False


@dataclass(frozen=True)
class ReferenceModel:
    number: int
    key: str
    name: str
    business_type: str
    # Doc 11 §5.2 "First Launch path", for readability in reports.
    path: str
    # Doc 11 §5.2 "Primary canonical modules".
    canonical_modules: tuple[str, ...]
    offering: OfferingSpec
    needs_provider: bool = False
    needs_membership_plan: bool = False
    extra_setup: Callable[[_Client, Headers, str], None] | None = field(default=None, repr=False)


# Dependency graph — enabling a module enables its chain.
_MODULE_DEPS: dict[str, tuple[str, ...]] = {
    "orders": ("offerings-catalog",),
    "bookings": ("offerings-catalog",),
    "payments": ("orders",),
    "inventory": ("offerings-catalog",),
    "fulfilment": ("orders", "inventory"),
    "memberships": ("payments", "orders", "offerings-catalog"),
    "customer-relationships": (),
    "leads": (),
    "workforce": ("core-team-access",),
    "offerings-catalog": (),
}


def _with_deps(modules: tuple[str, ...]) -> list[str]:
    seen: list[str] = []

    def visit(mid: str) -> None:
        for dep in _MODULE_DEPS.get(mid, ()):
            if dep.startswith("core-"):
                continue
            visit(dep)
        if mid not in seen:
            seen.append(mid)

    for m in modules:
        visit(m)
    return seen


REFERENCE_MODELS: tuple[ReferenceModel, ...] = (
    ReferenceModel(
        1, "retail", "Retail commerce", "retail",
        "Products -> discovery -> purchase/enquiry -> payment -> order -> fulfilment",
        ("offerings-catalog", "orders", "payments", "inventory", "fulfilment", "leads"),
        OfferingSpec("Oak Dining Table", "product", 12000.0, track_inventory=True),
    ),
    ReferenceModel(
        2, "supermarket", "High-frequency retail", "retail",
        "Products -> stock -> cart -> checkout -> COD/online -> pickup/delivery",
        ("offerings-catalog", "orders", "payments", "inventory", "fulfilment", "customer-relationships"),
        OfferingSpec("1kg Basmati Rice", "product", 180.0, track_inventory=True),
    ),
    ReferenceModel(
        3, "food", "Food business", "restaurant",
        "Menu -> order -> payment/COD -> pickup/delivery; optional table reservation",
        ("offerings-catalog", "orders", "payments", "inventory", "fulfilment", "bookings"),
        OfferingSpec("Paneer Butter Masala", "product", 320.0, track_inventory=True),
    ),
    ReferenceModel(
        4, "accommodation", "Accommodation", "hotel",
        "Room offering -> dates/guests -> availability -> reservation -> deposit/full/pay-at-property",
        ("offerings-catalog", "bookings", "payments", "customer-relationships"),
        OfferingSpec("Deluxe Double Room", "service", 4500.0),
    ),
    ReferenceModel(
        5, "appointments", "Appointment-based services", "salon",
        "Service -> provider/availability -> slot -> booking -> payment/deposit",
        ("offerings-catalog", "bookings", "payments", "workforce", "customer-relationships"),
        OfferingSpec("Haircut & Style", "service", 800.0),
        needs_provider=True,
    ),
    ReferenceModel(
        6, "membership", "Membership-based business", "gym",
        "Plan/class -> enrolment -> payment -> validity -> class/session booking",
        ("offerings-catalog", "memberships", "payments", "bookings", "workforce"),
        OfferingSpec("Group HIIT Class", "class_session", 0.0),
        needs_provider=True,
        needs_membership_plan=True,
    ),
    ReferenceModel(
        7, "professional", "Professional/general business", "professional_service",
        "Website/search -> service -> enquiry -> lead follow-up",
        ("offerings-catalog", "leads", "customer-relationships"),
        OfferingSpec("Monthly Bookkeeping Retainer", "service", 15000.0),
    ),
    ReferenceModel(
        8, "lead_driven", "Lead-driven business", "professional_service",
        "Listing/service -> enquiry -> lead -> contact -> qualify -> won/lost",
        ("offerings-catalog", "leads", "customer-relationships"),
        OfferingSpec("3BHK Apartment, Indiranagar", "service", 9500000.0),
    ),
    ReferenceModel(
        9, "education", "Education/cohort business", "education",
        "Course/class/plan -> enrolment/payment -> membership validity -> scheduled class",
        ("offerings-catalog", "memberships", "payments", "bookings", "workforce"),
        OfferingSpec("Class 10 Maths - Term Course", "class_session", 0.0),
        needs_provider=True,
        needs_membership_plan=True,
    ),
    ReferenceModel(
        10, "repair", "Repair/home services", "professional_service",
        "Service request -> lead or booking -> provider/schedule -> completion -> payment",
        ("offerings-catalog", "bookings", "payments", "workforce", "customer-relationships", "leads"),
        OfferingSpec("Geyser Repair Visit", "service", 600.0),
        needs_provider=True,
    ),
    ReferenceModel(
        11, "rental", "Rental/resource business", "studio",
        "Resource -> period availability -> reservation -> deposit/full payment -> return/completion",
        ("offerings-catalog", "bookings", "payments", "inventory"),
        OfferingSpec("Photography Studio - Half Day", "service", 3500.0, track_inventory=True),
    ),
)

REFERENCE_MODELS_BY_KEY: dict[str, ReferenceModel] = {m.key: m for m in REFERENCE_MODELS}


def _json(resp: Any) -> dict[str, Any]:
    assert resp.status_code == 200, f"{resp.status_code}: {resp.text}"
    return cast(dict[str, Any], resp.json())


def build_reference_business(
    client: _Client, owner_headers: Headers, model: ReferenceModel
) -> str:
    """Provision a Business for `model` and return its id. Idempotent-ish only
    per fresh owner — call with a distinct owner per model."""
    created = _json(
        client.post(
            "/v1/platform/businesses",
            json={
                "display_name": f"{model.name} {uuid.uuid4().hex[:8]}",
                "business_type": model.business_type,
            },
            headers=owner_headers,
        )
    )
    bid = cast(str, created["data"]["business"]["id"])

    for module_id in _with_deps(model.canonical_modules):
        enabled = client.post(f"/v1/b/{bid}/modules/{module_id}/enable", headers=owner_headers)
        assert enabled.status_code == 200, f"enable {module_id}: {enabled.text}"

    offering = _json(
        client.post(
            f"/v1/platform/businesses/{bid}/products",
            json={
                "title": model.offering.title,
                "offering_type": model.offering.offering_type,
                "status": "active",
                "price_amount": model.offering.price_amount,
                "track_inventory": model.offering.track_inventory,
            },
            headers=owner_headers,
        )
    )
    offering_id = offering["data"]["id"]

    locations = _json(client.get(f"/v1/platform/businesses/{bid}/locations", headers=owner_headers))
    location_id = next(loc["id"] for loc in locations["data"] if loc["is_primary"])

    if model.offering.track_inventory:
        client.post(
            f"/v1/platform/businesses/{bid}/inventory/opening-stock",
            json={"offering_id": offering_id, "location_id": location_id, "quantity": 100},
            headers=owner_headers,
        )

    if model.needs_provider:
        provider = client.post(
            f"/v1/platform/businesses/{bid}/workforce/members",
            json={
                "display_name": "Reference Provider",
                "location_ids": [location_id],
                "primary_location_id": location_id,
            },
            headers=owner_headers,
        )
        assert provider.status_code == 200, provider.text
        member_id = provider.json()["data"]["id"]
        client.post(
            f"/v1/platform/businesses/{bid}/workforce/members/{member_id}/services",
            json={"offering_id": offering_id},
            headers=owner_headers,
        )

    if model.needs_membership_plan:
        client.post(
            f"/v1/platform/businesses/{bid}/membership-plans",
            json={
                "name": "Reference Monthly Plan",
                "price_amount": 1500.0,
                "duration_days": 30,
                "status": "active",
                "visibility": "public",
                "offering_access": [offering_id],
            },
            headers=owner_headers,
        )

    if model.extra_setup is not None:
        model.extra_setup(client, owner_headers, bid)

    return bid
