"""Pricing what a customer chose (Capability Universe §6.3, §12.6 "cart price =
catalogue price").

The server prices every line from the catalogue: the variant or base price,
the chosen pack for goods sold by weight (price per kg × pack weight), the
price changes of chosen cuts, modifiers and add-ons, or — for a cause only —
the amount the giver chose above its smallest gift. The browser's numbers are
never used.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from platform_core.catalog.offering_kinds import KINDS
from platform_core.exceptions import ValidationError
from platform_core.models import Offering, OfferingVariant

PAISE = Decimal("0.01")
MAX_GIFT = Decimal("10000000")


@dataclass(frozen=True)
class PricedLine:
    unit_price: Decimal
    stock_per_unit: int  # in the offering's stock unit (piece, g or ml)
    title_suffix: str
    options: dict[str, Any]


def _bad(message: str) -> ValidationError:
    return ValidationError(message, details={"errors": [{"field": "options", "message": message}]})


def price_selection(
    offering: Offering, variant: OfferingVariant | None, selection: dict[str, Any] | None
) -> PricedLine:
    sel = dict(selection or {})
    k = KINDS.get(offering.offering_type)
    parts: list[str] = []
    record: dict[str, Any] = {}

    if k is not None and k.flow == "give":
        attrs = offering.attributes or {}
        try:
            amount = Decimal(str(sel.get("amount"))).quantize(PAISE)
        except Exception:  # noqa: BLE001
            raise _bad("Choose how much to give") from None
        minimum = Decimal(str(attrs.get("min_amount") or "1"))
        if amount < minimum or amount > MAX_GIFT:
            raise _bad(f"Gifts start at ₹{minimum:,.0f}")
        return PricedLine(amount, 1, "", {"amount": str(amount)})

    base = variant.price_amount if variant is not None and variant.price_amount is not None else offering.price_amount
    if base is None:
        raise ValidationError("This item has no price yet", details={"offering_id": str(offering.id)})
    price = Decimal(str(base))
    stock = 1

    packs = list(offering.sell_units or [])
    if packs:
        chosen = next((p for p in packs if p["label"] == sel.get("pack")), None)
        if chosen is None:
            raise _bad("Choose a pack size")
        per = (offering.attributes or {}).get("price_per", "kg")
        # price is per kg / litre; packs are counted in grams / millilitres
        price = (price * Decimal(chosen["qty"]) / Decimal(1000)).quantize(PAISE, ROUND_HALF_UP)
        stock = int(chosen["qty"])
        parts.append(chosen["label"])
        record["pack"] = chosen["label"]
        record["price_per"] = per

    groups = list(offering.option_groups or [])
    picked = sel.get("choices") or {}
    written = sel.get("notes") or {}
    if not isinstance(picked, dict) or not isinstance(written, dict):
        raise _bad("Choices must be listed by group")
    unknown = set(picked) - {g["name"] for g in groups if not g.get("text")}
    unknown |= set(written) - {g["name"] for g in groups if g.get("text")}
    if unknown:
        raise _bad(f"{sorted(unknown)[0]} is not one of this item's choices")
    record_choices: dict[str, list[str]] = {}
    record_notes: dict[str, str] = {}
    for g in groups:
        if g.get("text"):
            value = " ".join(str(written.get(g["name"]) or "").split())
            if g["required"] and not value:
                raise _bad(f"Write the {g['name'].lower()}")
            if len(value) > int(g["max_length"]):
                raise _bad(f"{g['name']}: up to {g['max_length']} letters")
            if value:
                record_notes[g["name"]] = value
                parts.append(f"“{value}”")
            continue
        labels = picked.get(g["name"]) or []
        labels = [labels] if isinstance(labels, str) else list(labels)
        if g["required"] and not labels:
            raise _bad(f"Choose {g['name'].lower()}")
        if len(labels) > g["max"] or len(set(labels)) != len(labels):
            raise _bad(f"Choose up to {g['max']} for {g['name'].lower()}")
        by_label = {c["label"]: c for c in g["choices"]}
        for label in labels:
            if label not in by_label:
                raise _bad(f"{label} is not a choice for {g['name'].lower()}")
            price += Decimal(by_label[label]["price_delta"])
        if labels:
            record_choices[g["name"]] = labels
            parts.append(", ".join(labels))
    if record_choices:
        record["choices"] = record_choices
    if record_notes:
        record["notes"] = record_notes
    return PricedLine(price.quantize(PAISE), stock, " · ".join(parts), record)
