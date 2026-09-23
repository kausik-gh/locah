"""What Locah shows it has understood — structured, never a field dump.

The side panel used to print each fact as the owner typed it, which reads as a
form that was copied back. This builds the panel from state: what kind of
business it is, what customers can do, the truth Locah holds with where it
came from, what is still worth knowing, and the logo. Website wording lives in
`website_draft` and is shown beside this, labelled as a suggestion.
"""

from __future__ import annotations

import re
from typing import Any

from platform_core.interview.discovery import characteristics, rank
from platform_core.interview.models import BusinessBlueprint

_TRAITS = (
    ("sells_products", "Sells products"),
    ("provides_services", "Offers services"),
    ("accepts_orders", "Online orders"),
    ("accepts_appointments", "Bookings"),
    ("quote_led", "Quotes first"),
    ("serves_businesses", "Sells to businesses"),
    ("delivers", "Delivers"),
    ("pickup", "Pickup"),
    ("has_memberships", "Memberships"),
    ("made_to_order", "Made to order"),
    ("walk_in", "Walk-in"),
)

_TRUTH = (
    ("contact.location", "locations", "Where"),
    ("offerings.main", "offerings", "Sells"),
    ("offerings.units", None, "Sold"),
    ("fulfilment.mode", None, "Delivery"),
    ("fulfilment.area", None, "Delivers to"),
    ("commerce.payment", None, "Payment"),
    ("operations.hours", "opening_hours", "Hours"),
    ("b2b.customers", None, "Supplies"),
    ("bookings.format", None, "Bookings"),
    ("brand.story", None, "Story"),
    ("contact.phone", "phone", "Phone"),
)


def _steps(text: str) -> list[str]:
    parts = re.split(r",|;|\bthen\b|\band then\b|\band\b|→", text, flags=re.I)
    steps = []
    for part in parts:
        part = re.sub(r"^\s*(customers?|people|they|guests|patients)\s+(can\s+|will\s+|should\s+)?",
                      "", part.strip(), flags=re.I).strip(" .")
        if 2 < len(part) <= 80:
            steps.append(part[0].upper() + part[1:])
    return steps[:4]


def understanding(
    bp: BusinessBlueprint, business_type: str | None = None, logo_url: str | None = None
) -> dict[str, Any]:
    chars = characteristics(bp, business_type)
    seen = {c for c, how in chars.items() if how == "observed"}
    facts = {**bp.known_facts, **bp.unconfirmed_facts}
    state = bp.discovery

    def answer(target: str) -> str:
        s = state.get(target)
        return (s.summary or s.quote) if s and s.status in {"answered", "partial"} else ""

    identity = answer("business.identity")
    kind = identity or (facts["classification"].value if "classification" in facts else "")
    items = []
    for target, fact, label in _TRUTH:
        value = answer(target) or (facts[fact].value if fact and fact in facts else "")
        if not value:
            continue
        # "These details are correct" covers everything shown, including what
        # lives only as a discovery answer (how it is sold, delivery, payment).
        confirmed = bool(fact and fact in bp.known_facts) or bp.completion_state.confirmed
        items.append({
            "label": label,
            "value": value[:200],
            "status": "confirmed" if confirmed else "from_you",
            "target": target,
        })
    action = answer("commerce.action") or (facts["customer_actions"].value if "customer_actions" in facts else "")
    open_targets = [
        {"id": r.target.id, "label": r.target.label, "essential": r.essential}
        for r in rank(bp, business_type)[:5]
        if not r.target.id.startswith("media.")
    ]
    logo_request = next((r for r in bp.media_generation_requests if r.role == "logo"), None)
    logo_asset = next((m for m in reversed(bp.media_assets) if m.role == "logo"), None)
    if logo_asset:
        logo = {"state": "ready", "source": logo_asset.source, "url": logo_url}
    elif logo_request:
        logo = {"state": logo_request.status, "reason": logo_request.reason}
    else:
        logo = {"state": "none"}
    return {
        "kind": kind[:160],
        "traits": [label for key, label in _TRAITS if key in seen],
        "customer_steps": _steps(action) if action else [],
        "items": items,
        "still_worth_knowing": open_targets[:4],
        "readiness": bp.readiness.model_dump(),
        "logo": logo,
    }
