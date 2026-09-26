"""Structured "Change" from the side panel — a correction, not another interview.

Each slot has a type, and the owner's new value is checked against it before
anything is kept: opening hours must be a schedule, a phone number must have
digits, customer actions come from a fixed list. What the owner sets here is
their word and wins over anything extracted later.
"""

from __future__ import annotations

import re

from platform_core.interview import reader as rd
from platform_core.interview.models import (
    BusinessBlueprint,
    CatalogueGroup,
    Fact,
    TargetState,
)

FULFILMENT = ("delivery", "pickup", "shipping", "dine_in", "on_site")
PAYMENTS = ("UPI", "Cash", "Cash on delivery", "Card", "Online", "Bank transfer")
PRICE_VISIBILITY = ("show", "from", "on_request", "hidden")


class CorrectionError(ValueError):
    """The value is not the right kind of thing for this slot — said plainly."""


def _answer(bp: BusinessBlueprint, target: str, summary: str, quote: str = "") -> None:
    state = bp.discovery.setdefault(target, TargetState())
    state.status = "answered"
    state.summary = summary[:240]
    state.quote = (quote or summary)[:600]


def _fact(bp: BusinessBlueprint, field: str, value: str) -> None:
    bp.unconfirmed_facts.pop(field, None)
    bp.known_facts[field] = Fact(value=value[:4000], evidence=value[:4000], source="USER_STATEMENT",
                                 confirmation="confirmed")


def apply_correction(bp: BusinessBlueprint, slot: str, values: list[str], text: str = "") -> None:
    """Apply one typed correction in place. Raises CorrectionError when it doesn't fit."""
    text = " ".join((text or "").split())
    clean = [" ".join(v.split()) for v in values if v and v.strip()]
    if slot == "actions":
        chosen = [v for v in clean if v in rd.ACTION_LABELS]
        if not chosen:
            raise CorrectionError("Choose at least one thing customers can do.")
        bp.owner_choices.actions = chosen[:6]
        _answer(bp, "commerce.action", ", ".join(rd.action_labels(chosen)))
        return
    if slot == "fulfilment":
        chosen = [v for v in clean if v in FULFILMENT]
        bp.owner_choices.fulfilment = chosen
        if chosen:
            _answer(bp, "fulfilment.mode", ", ".join(chosen))
        else:
            bp.discovery.setdefault("fulfilment.mode", TargetState()).status = "declined"
        return
    if slot == "payment":
        chosen = [v for v in clean if v in PAYMENTS]
        if not chosen:
            raise CorrectionError("Choose how customers pay.")
        bp.owner_choices.payment = chosen
        _answer(bp, "commerce.payment", ", ".join(chosen))
        return
    if slot == "price_visibility":
        choice = clean[0] if clean else text
        if choice not in PRICE_VISIBILITY:
            raise CorrectionError("Choose how prices should appear.")
        bp.owner_choices.price_visibility = choice
        _answer(bp, "offerings.pricing", {"show": "Show prices", "from": "Show a starting price",
                                          "on_request": "Price on request", "hidden": "No prices"}[choice])
        return
    if slot == "offerings":
        names = [n for v in (clean or [text]) for n in rd.offering_names(v)]
        if not names:
            raise CorrectionError("List what you sell or offer — for example \"chicken, mutton, fish\".")
        keep = {g.name.casefold(): g for g in bp.taxonomy.groups}
        bp.taxonomy.groups = [
            keep.get(n.casefold()) or CatalogueGroup(name=n[:80]) for n in names[:12]
        ]
        _fact(bp, "offerings", ", ".join(names))
        _answer(bp, "offerings.main", ", ".join(names))
        return
    if slot == "area":
        area = rd.service_area(text) or text
        if not area or len(area) > 100 or rd.looks_like_hours(area):
            raise CorrectionError("Name the areas you deliver to or serve — for example \"Velachery and Adyar\".")
        _answer(bp, "fulfilment.area", area)
        return
    if slot == "location":
        place = rd.location_text(text)
        if not place:
            raise CorrectionError("That doesn't look like a place — the area and city is enough.")
        _fact(bp, "locations", place)
        _answer(bp, "contact.location", place)
        return
    if slot == "phone":
        digits = rd.phone_number(text)
        if not digits:
            raise CorrectionError("That doesn't look like a phone number — a 10-digit mobile works best.")
        _fact(bp, "phone", digits)
        _answer(bp, "contact.phone", digits)
        return
    if slot == "hours":
        if not rd.valid_for("opening_hours", text):
            raise CorrectionError(
                "That doesn't look like opening hours — try \"9 am to 8 pm, Monday to Saturday\".")
        _fact(bp, "opening_hours", text)
        _answer(bp, "operations.hours", text)
        return
    if slot == "story":
        if len(re.findall(r"\w+", text)) < 3:
            raise CorrectionError("Say a little more — a sentence is enough.")
        _answer(bp, "brand.story", text[:240], text)
        return
    if slot == "description":
        if len(re.findall(r"\w+", text)) < 2 or rd.looks_like_hours(text):
            raise CorrectionError("Describe the business in a few words.")
        _fact(bp, "description", text)
        _answer(bp, "business.identity", text[:240], text)
        return
    raise CorrectionError("That part can't be changed here yet.")
