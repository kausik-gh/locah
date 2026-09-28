"""How a business sees its stock — one inventory domain, different work.

Capability Universe §15.1 lists who needs what: yield for meat, fish and
sweets; batches and expiry for pharmacy, dairy and packaged food; serials for
electronics; a size × colour grid for fashion; reorder points and counts for
everyone. §21 names the same per family ("inventory (yield)", "inventory
(batches, expiry)", "inventory (serials)").

The lenses below come from three facts, never from the business's name:
  1. its operating traits (§4.3: weight_based, perishable, serialised, ...),
  2. the inventory hint its §21 playbook family names,
  3. what it has actually configured (a batch-tracked item, a yield, ...).
Pure and deterministic: fixture-tested, no model call.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from platform_core.catalog.families import FAMILIES
from platform_core.catalog.source_tables import parse_module_list

LENS_ORDER = ("weighed", "batches", "serials", "variants", "ingredients", "counter")


@dataclass(frozen=True)
class Lens:
    key: str
    title: str  # what the page is about, in the owner's words
    primary_action: str
    empty: str  # a first step that fits this business


LENSES: dict[str, Lens] = {
    "weighed": Lens("weighed", "Today's counter, by weight",
                    "Record today's arrival",
                    "Add the items and cuts you actually sell by weight, then record what came in this morning."),
    "batches": Lens("batches", "Stock by batch and expiry",
                    "Receive a batch",
                    "Receive stock with its batch number and expiry date — LOCAH sells the earliest expiry first "
                    "and warns you before anything expires."),
    "serials": Lens("serials", "Units in stock, by serial number",
                    "Receive with serial numbers",
                    "Receive each unit with its serial or IMEI number so every sale carries its warranty."),
    "variants": Lens("variants", "Stock by size and colour",
                     "Receive stock",
                     "Give a product its sizes and colours, then record how many of each you have."),
    "ingredients": Lens("ingredients", "Ingredients and supplies",
                        "Record what came in",
                        "Add the ingredients you buy and track what arrives and what is wasted. Recipes that use "
                        "them up as you sell arrive with Recipes & BOM."),
    "counter": Lens("counter", "Stock at the counter",
                    "Receive stock",
                    "Record opening stock for the items you sell, set a reorder level, and LOCAH tells you what "
                    "is running low."),
}


def family_hints(family_key: str | None) -> frozenset[str]:
    """The §21 inventory hint words for a playbook family (e.g. {'yield'})."""
    if not family_key:
        return frozenset()
    family = next((f for f in FAMILIES if f.key == family_key), None)
    if family is None:
        return frozenset()
    words: set[str] = set()
    for text in (family.core, family.rec):
        for key, hint in parse_module_list(text):
            if key == "inventory" and hint:
                words.update(w.strip().lower() for w in hint.replace(";", ",").split(","))
    return frozenset(words)


def lenses(traits: Iterable[str], hints: Iterable[str], configured: Mapping[str, int]) -> list[str]:
    """Which stock views this business gets, most important first.

    `configured` counts real items: weighed, batch_tracked, serial_tracked,
    with_variants, yields."""
    t, h = set(traits), set(hints)
    on: set[str] = {"counter"}
    if "weight_based" in t or configured.get("weighed", 0) or "yield" in h or configured.get("yields", 0):
        on.add("weighed")
    if (h & {"batches", "expiry", "lots", "harvest lots"} or configured.get("batch_tracked", 0)
            or ("perishable" in t and "weight_based" not in t and "made_to_order" not in t)):
        on.add("batches")
    if "serialised" in t or "serials" in h or configured.get("serial_tracked", 0):
        on.add("serials")
    if "variant_based" in t or configured.get("with_variants", 0):
        on.add("variants")
    if "ingredient_based" in t:
        on.add("ingredients")
    return [k for k in LENS_ORDER if k in on]


def yield_offered(traits: Iterable[str], hints: Iterable[str], configured: Mapping[str, int]) -> bool:
    """Cut-and-portion runs make sense where the source names yield or goods are
    weighed and perishable (whole bird -> curry cut, milk -> paneer)."""
    t = set(traits)
    return "yield" in set(hints) or bool(configured.get("yields")) or {"weight_based", "perishable"} <= t


WASTAGE_REASONS: dict[str, str] = {
    "expired": "Expired", "damaged": "Damaged", "trim_loss": "Trim loss", "spoiled": "Spoiled",
    "theft": "Missing / theft", "sample": "Sample or tester", "other": "Other",
}


def wastage_reasons(active: list[str]) -> list[str]:
    """Reasons in the order this business will use them."""
    if "weighed" in active:
        return ["trim_loss", "spoiled", "damaged", "expired", "other"]
    if "batches" in active:
        return ["expired", "damaged", "sample", "theft", "other"]
    return ["damaged", "theft", "expired", "sample", "other"]
