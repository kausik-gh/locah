"""What Locah shows it has understood — typed, never a field dump.

The panel used to print strings: whatever landed in `customer_actions` was
split on commas into "What a customer does", so "GYm equipment, available
trainers, dumbells, contact section" appeared as four customer steps, and a
delivery area filed as opening hours read "Hours: All india".

Every value here has a type and is re-derived from the owner's own words
through the reader's checks:

* OFFERING — something sold or provided (from the structured range);
* CUSTOMER ACTION — something a customer does, canonical (order on WhatsApp,
  book a table, ask for a quote…);
* CONTENT — a part of the website the owner asked for ("contact section");
* OPERATING FACT — how buying works: units, delivery, pickup, payment;
* LOCATION — where the business is; SERVICE AREA — where it delivers or serves;
* HOURS — only an actual schedule;
* MODULE — a recommended tool.

A value that fails its type check is not shown. Nothing is split on commas.
"""

from __future__ import annotations

import re
from typing import Any

from platform_core.interview.models import BusinessBlueprint, TargetState
from platform_core.interview.reader import (
    ACTION_LABELS,
    canonical_actions,
    fulfilment_modes,
    location_text,
    looks_like_hours,
    offering_names,
    payment_methods,
    phone_number,
    service_area,
    units,
)
from platform_core.interview.taxonomy import catalogue_lines

# Characteristics seen in the owner's words, shown as quiet chips.
_TRAITS = (
    ("sells_products", "Sells products"),
    ("provides_services", "Offers services"),
    ("accepts_orders", "Takes orders"),
    ("accepts_appointments", "Takes bookings"),
    ("quote_led", "Quotes first"),
    ("serves_businesses", "Sells to businesses"),
    ("has_memberships", "Memberships"),
    ("made_to_order", "Made to order"),
    ("walk_in", "Walk-ins"),
)


def _state(bp: BusinessBlueprint, target: str) -> TargetState:
    return bp.discovery.get(target) or TargetState()


def _heard(bp: BusinessBlueprint, target: str) -> str:
    """The owner's own words for a discovery target (quote first, then summary)."""
    s = _state(bp, target)
    if s.status not in {"answered", "partial"}:
        return ""
    # Separate sentences: joined without a stop, "…call" + "Order online" read
    # as "call to order".
    return ". ".join(part.strip(" .") for part in (s.quote, s.summary) if part)


def _facts(bp: BusinessBlueprint) -> dict[str, str]:
    return {k: f.value for k, f in {**bp.known_facts, **bp.unconfirmed_facts}.items()}


# ----------------------------------------------------------------- typed parts


def customer_actions(bp: BusinessBlueprint) -> list[str]:
    """Canonical customer actions, from the owner's words (or their correction)."""
    if bp.owner_choices.actions is not None:
        return [a for a in bp.owner_choices.actions if a in ACTION_LABELS]
    facts = _facts(bp)
    # The owner's words only — the model's one-line summary ("Table bookings
    # and takeaway orders") is a paraphrase and loses the channel.
    state = _state(bp, "commerce.action")
    said = state.quote if state.status in {"answered", "partial"} else ""
    sources = [said or _heard(bp, "commerce.action"), facts.get("customer_actions", "")]
    sources += [e.quote for e in bp.operating_patterns
                if e.pattern in {"order_led", "appointment_led", "quote_led", "lead_generation", "walk_in"}]
    found: list[str] = []
    for text in sources:
        for action in canonical_actions(text):
            if action not in found:
                found.append(action)
    # A specific way of doing something makes the bare channel redundant.
    if {"order_whatsapp", "book_whatsapp"} & set(found) and "whatsapp" in found:
        found.remove("whatsapp")
    if {"order_call", "book_call"} & set(found) and "call" in found:
        found.remove("call")
    return found[:5]


def fulfilment(bp: BusinessBlueprint) -> list[str]:
    """How orders reach customers — only what the owner said."""
    if bp.owner_choices.fulfilment is not None:
        return list(bp.owner_choices.fulfilment)
    facts = _facts(bp)
    text = " ".join([_heard(bp, "fulfilment.mode"), _heard(bp, "fulfilment.area"),
                     facts.get("operational_characteristics", "")])
    modes = fulfilment_modes(text)
    for evidence in bp.operating_patterns:
        mode = {"local_delivery": "delivery", "delivery": "delivery", "pickup": "pickup",
                "shipping": "shipping"}.get(evidence.pattern)
        if mode and mode not in modes:
            modes.append(mode)
    return list(modes)


def delivery_area(bp: BusinessBlueprint) -> str:
    s = _state(bp, "fulfilment.area")
    if s.status != "answered":
        return ""
    return str(service_area(s.quote) or service_area(s.summary))


def payments(bp: BusinessBlueprint) -> list[str]:
    if bp.owner_choices.payment is not None:
        return list(bp.owner_choices.payment)
    return list(payment_methods(_heard(bp, "commerce.payment")))


def sold_by(bp: BusinessBlueprint) -> str:
    kind = units(_heard(bp, "offerings.units"))
    if not kind:
        kind = next((units(g.sold_by) for g in bp.taxonomy.groups if units(g.sold_by)), "")
    return {"weight": "By the kg", "packs": "In fixed packs"}.get(kind, "")


def location(bp: BusinessBlueprint) -> str:
    raw = _facts(bp).get("locations", "")
    places = [location_text(part) for part in raw.split(";")]
    places = [p for p in places if p]
    # Most specific last: "Chennai; Nookampalayam Road" -> "Nookampalayam Road, Chennai".
    unique: list[str] = []
    for place in places:
        if all(place.casefold() != u.casefold() for u in unique):
            unique.append(place)
    unique = [p for p in unique if not any(p != o and p.casefold() in o.casefold() for o in unique)]
    return ", ".join(reversed(unique))[:120]


def phone(bp: BusinessBlueprint) -> str:
    digits = phone_number(_facts(bp).get("phone", ""))
    return f"+91 {digits[:5]} {digits[5:]}" if digits else ""


def hours(bp: BusinessBlueprint) -> str:
    value = _facts(bp).get("opening_hours", "")
    return value[:120] if value and looks_like_hours(value) else ""


def offer_groups(bp: BusinessBlueprint) -> list[dict[str, Any]]:
    """What is sold, as groups with items — the structured range when there is one."""
    lines = catalogue_lines(bp)
    if lines:
        return [{"name": str(line["name"]), "items": list(line["items"])[:10],
                 "price": str(line.get("price") or ""), "needs": list(line.get("needs") or [])}
                for line in lines]
    names = offering_names(_facts(bp).get("offerings", ""))
    return [{"name": name, "items": [], "price": "", "needs": []} for name in names]


def _join(names: list[str]) -> str:
    names = [n for n in names if n]
    if len(names) <= 1:
        return "".join(names)
    return ", ".join(names[:-1]) + " and " + names[-1]


def offer_summary(bp: BusinessBlueprint) -> str:
    groups = [g["name"] for g in offer_groups(bp)][:5]
    if not groups:
        return ""
    text = _join([groups[0]] + [g[:1].lower() + g[1:] if not g.isupper() else g for g in groups[1:]])
    how = sold_by(bp)
    return f"{text}, {how[:1].lower() + how[1:]}" if how else text


def buying(bp: BusinessBlueprint) -> list[dict[str, str]]:
    """How customers buy, one plain line per fact."""
    rows: list[dict[str, str]] = []
    how = sold_by(bp)
    if how:
        rows.append({"kind": "units", "text": how})
    modes = fulfilment(bp)
    area = delivery_area(bp)
    if "delivery" in modes or "shipping" in modes:
        where = f" around {area}" if area and "delivery" in modes and "shipping" not in modes else \
            f" — {area}" if area else ""
        label = "Delivery" if "shipping" not in modes else "Delivery and shipping"
        rows.append({"kind": "delivery", "text": f"{label}{where}"})
    if "pickup" in modes:
        rows.append({"kind": "pickup", "text": "Pickup"})
    if "dine_in" in modes:
        rows.append({"kind": "dine_in", "text": "Dine-in"})
    if "on_site" in modes:
        rows.append({"kind": "on_site", "text": "At the customer's place" + (f" — {area}" if area else "")})
    pay = payments(bp)
    if pay:
        rows.append({"kind": "payment", "text": _join(pay[:1] + [p[:1].lower() + p[1:] if p != "UPI" else p
                                                              for p in pay[1:]])})
    return rows


def identity_line(bp: BusinessBlueprint) -> str:
    """One line on what the business is: the owner's words, else their category."""
    s = _state(bp, "business.identity")
    said = (s.summary or s.quote) if s.status in {"answered", "partial"} else ""
    if said and len(said) <= 160 and not canonical_actions(said):
        return said
    if bp.category and bp.category.label:
        return str(bp.category.label)
    facts = _facts(bp)
    return (facts.get("classification") or "")[:160]


def actions(bp: BusinessBlueprint) -> list[dict[str, str]]:
    return [{"id": a, "label": ACTION_LABELS[a]} for a in customer_actions(bp)]


def synthesis(bp: BusinessBlueprint) -> str:
    """One short "so far" line, built only from typed understanding."""
    parts: list[str] = []
    offer = offer_summary(bp)
    if offer:
        parts.append(offer)
    acts = [ACTION_LABELS[a] if ACTION_LABELS[a].startswith("WhatsApp") else
            ACTION_LABELS[a][:1].lower() + ACTION_LABELS[a][1:] for a in customer_actions(bp)[:2]]
    if acts:
        parts.append("customers can " + " or ".join(acts))
    for row in buying(bp):
        if row["kind"] in {"delivery", "pickup"}:
            parts.append(row["text"][:1].lower() + row["text"][1:])
    place = location(bp)
    if place and len(parts) < 4:
        parts.append(f"in {place}")
    return "; ".join(parts[:4])


# ------------------------------------------------------------------ the panel


def understanding(
    bp: BusinessBlueprint, business_type: str | None = None, logo_url: str | None = None
) -> dict[str, Any]:
    from platform_core.interview.coverage import dimensions, worth_knowing
    from platform_core.interview.discovery import characteristics

    chars = characteristics(bp, business_type)
    seen = {c for c, how in chars.items() if how == "observed"}
    name = bp.identity["display_name"].value if "display_name" in bp.identity else ""
    logo_request = next((r for r in bp.media_generation_requests if r.role == "logo"), None)
    logo_asset = next((m for m in reversed(bp.media_assets) if m.role == "logo"), None)
    if logo_asset:
        logo: dict[str, Any] = {"state": "ready", "source": logo_asset.source, "url": logo_url}
    elif logo_request:
        logo = {"state": logo_request.status, "reason": logo_request.reason}
    else:
        logo = {"state": "none"}
    contact = {"location": location(bp), "phone": phone(bp), "hours": hours(bp)}
    tools = [
        {"id": m.module_id, "label": m.label, "why": _tool_reason(m.reason), "choice": m.choice}
        for m in bp.recommended_modules if m.strength != "dependency"
    ][:5]
    return {
        "business": {"name": name, "kind": identity_line(bp),
                     "category": bp.category.label if bp.category else ""},
        "offer": {"summary": offer_summary(bp), "groups": offer_groups(bp)},
        "actions": actions(bp),
        "buying": buying(bp),
        "contact": contact,
        "content": list(bp.content_wishes),
        "traits": [label for key, label in _TRAITS if key in seen],
        "worth_knowing": worth_knowing(bp, business_type),
        "tools": tools,
        "progress": dimensions(bp, business_type),
        "readiness": bp.readiness.model_dump(),
        "logo": logo,
        "synthesis": synthesis(bp),
        # Kept for older clients: the same typed facts, flattened.
        "kind": identity_line(bp)[:160],
        "catalogue": _with_photo_needs(bp),
    }


def _tool_reason(reason: str) -> str:
    """The owner-facing why, without the module jargon."""
    reason = re.sub(r"^Because you said “[^”]*”\.\s*", "", reason or "")
    return reason[:160]


def _with_photo_needs(bp: BusinessBlueprint) -> list[dict[str, Any]]:
    """A group still needs a picture until it has a real photo or a draft visual."""
    from platform_core.interview.media_director import picture_for, slug

    lines = catalogue_lines(bp)
    for line in lines:
        needs = list(line["needs"])
        if not picture_for(bp, f"category:{slug(str(line['name']))}") and "photo" not in needs:
            needs.append("photo")
        line["needs"] = needs
    return list(lines)
