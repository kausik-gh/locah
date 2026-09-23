"""What a business sells, as a structure — not a comma list.

"We sell chicken, mutton, fish different varieties" used to become three
website cards, one of them titled "Fish different varieties". A merchandiser
reads the same sentence as: Chicken, Mutton and Fish are *groups*; the owner
keeps several kinds of fish without having named them yet; and whether people
choose cuts is still unknown. That reading decides what the site shows (a
category grid, a product grid, chips) and what is worth asking next ("which
fish do you usually keep?"), so it is kept here as first-class state.

The model proposes the grouping each turn; this module decides what is kept:

* item names must be built from the owner's own words;
* a group label may be Locah's ("Fish & Seafood") only when it groups items
  the owner named, and it is marked as a suggestion;
* phrases like "different varieties", "all kinds", "etc" are signals that a
  group has depth, never item names;
* prices and units are kept only when every number in them is the owner's.

Nothing here branches on a kind of business.
"""

from __future__ import annotations

import re

from platform_core.interview.models import (
    BusinessBlueprint,
    CatalogueEdit,
    CatalogueGroup,
    CatalogueItem,
    GroupProposal,
)
from platform_core.interview.website_copy import _built_from_owner_words, _grounded, owner_corpus

# Phrases that say "there are more of these" without naming them.
_DEPTH = re.compile(
    r"\b(?:(?:all|different|various|many|several|lots of|every)\s+(?:types?|kinds?|sorts?|varieties|variety|items?)(?:\s+of)?|"
    r"(?:different|various|many)\s+varieties|varieties|variety|and\s+more|and\s+others?|etc\.?|"
    r"so\s+on|everything)\b",
    re.I,
)
_LEAD = re.compile(
    r"^(?:(?:we|i)\s+(?:also\s+)?(?:mainly\s+|mostly\s+|usually\s+)?(?:sell|make|do|offer|serve|provide|keep|have)\s+|"
    r"(?:mostly|mainly|also|and)\s+)",
    re.I,
)
_UNIT_WORDS = re.compile(
    r"\b(kg|kilo\w*|g|gm|grams?|piece|pieces|pcs|pack|packs|jar|jars|bottle|litre|liter|l|ml|"
    r"plate|plates|box|boxes|dozen|each|per|portion|serving|sq\.?\s?ft|sqft|bhk|month|months|year|"
    r"session|sessions|class|classes)\b",
    re.I,
)
_DIGITS = re.compile(r"\d[\d,.]*")


def normalise_name(text: str) -> tuple[str, bool]:
    """(clean name, whether the owner signalled more of it).

    "fish different varieties" -> ("Fish", True); "all types of meat" ->
    ("Meat", True); "chicken" -> ("Chicken", False).
    """
    raw = " ".join((text or "").split()).strip(" .,;:-")
    raw = _LEAD.sub("", raw)
    deep = bool(_DEPTH.search(raw))
    name = _DEPTH.sub(" ", raw)
    name = re.sub(r"\b(?:of|and|the)\s*$", "", " ".join(name.split()), flags=re.I).strip(" .,;:-")
    if not name:
        return "", deep
    return name[0].upper() + name[1:], deep


def split_listing(text: str) -> list[str]:
    """An owner's list of what they sell, as separate phrases."""
    cleaned = _LEAD.sub("", " ".join((text or "").split()).strip(" ."))
    parts = re.split(r"\s*(?:[,;/]|\band\b|&|\bplus\b)\s*", cleaned, flags=re.I)
    return [p.strip(" .") for p in parts if p.strip(" .")]


def taxonomy_from_listing(text: str) -> list[CatalogueGroup]:
    """The plain reading when the model offered none: one group per phrase."""
    groups: list[CatalogueGroup] = []
    for part in split_listing(text):
        name, deep = normalise_name(part)
        if not name or len(name) > 60 or re.search(r"\d", name):
            continue
        if any(g.name.casefold() == name.casefold() for g in groups):
            continue
        groups.append(CatalogueGroup(name=name[:80], needs=["varieties"] if deep else []))
    return groups[:12]


def _numbers_owned(text: str, corpus: str) -> bool:
    owned = {re.sub(r"[,.]", "", n) for n in _DIGITS.findall(corpus)}
    return all(re.sub(r"[,.]", "", n) in owned for n in _DIGITS.findall(text or ""))


def _price(value: str, corpus: str) -> str:
    value = " ".join((value or "").split())[:40]
    if not value or not _DIGITS.search(value) or not _numbers_owned(value, corpus):
        return ""
    return value


def _unit(value: str, corpus: str) -> str:
    value = " ".join((value or "").split())[:40]
    if not value or not _numbers_owned(value, corpus):
        return ""
    if _UNIT_WORDS.search(value) or _built_from_owner_words(value, corpus):
        return value
    return ""


def _find(groups: list[CatalogueGroup], name: str) -> CatalogueGroup | None:
    key = name.casefold()
    return next((g for g in groups if g.name.casefold() == key), None)


def govern_catalogue(bp: BusinessBlueprint, proposals: list[GroupProposal], heard: str) -> bool:
    """Fold the model's reading of the range into the Blueprint. Returns whether it changed."""
    if not proposals:
        return False
    corpus = " ".join([owner_corpus(bp), heard])
    groups = [g.model_copy(deep=True) for g in bp.taxonomy.groups]
    before = [g.model_dump() for g in groups]
    for proposal in proposals:
        label, label_deep = normalise_name(proposal.group)
        if not label or len(label.split()) > 5 or not _grounded(label, corpus):
            continue
        items: list[CatalogueItem] = []
        unknown = set(proposal.unknown)
        if label_deep:
            unknown.add("varieties")
        for raw in proposal.items:
            name, deep = normalise_name(raw.name)
            if deep:
                # "fish different varieties" inside a group: the group has depth.
                unknown.add("varieties")
                if not name or name.casefold() == label.casefold():
                    continue
            if not name or not _built_from_owner_words(name, corpus) or len(name) > 60:
                continue
            if any(i.name.casefold() == name.casefold() for i in items):
                continue
            items.append(CatalogueItem(
                name=name[:80], price=_price(raw.price, corpus), unit=_unit(raw.unit, corpus),
            ))
        owner_label = _built_from_owner_words(label, corpus)
        if not owner_label and not items:
            continue  # a label of Locah's own needs owner-named items under it
        group = _find(groups, label)
        if group is None:
            group = CatalogueGroup(name=label[:80], label_source="owner" if owner_label else "ai_suggestion")
            groups.append(group)
        for item in items:
            existing = next((i for i in group.items if i.name.casefold() == item.name.casefold()), None)
            if existing is None:
                if len(group.items) < 24:
                    group.items.append(item)
            elif existing.source != "owner_edited":
                existing.price = item.price or existing.price
                existing.unit = item.unit or existing.unit
            # An item that was a group of its own ("Crab") now lives inside
            # this one ("Fish & Seafood"): one place, not two.
            standalone = _find(groups, item.name)
            if standalone is not None and standalone is not group and not standalone.items:
                groups.remove(standalone)
        group.sold_by = " ".join(proposal.sold_by.split())[:80] if proposal.sold_by and _grounded(
            proposal.sold_by, corpus) else group.sold_by
        group.price = _price(proposal.price, corpus) or group.price
        group.unit = _unit(proposal.unit, corpus) or group.unit
        structural = [n for n in group.needs if n in {"varieties", "cuts", "sizes"}]
        if items and "varieties" in structural and "varieties" not in unknown:
            structural.remove("varieties")  # they named them
        for need in ("varieties", "cuts", "sizes"):
            if need in unknown and need not in structural:
                structural.append(need)
            elif need not in unknown and need in structural and need != "varieties":
                structural.remove(need)
        group.needs = structural + (["price"] if "price" in group.needs else [])
    groups = groups[:12]
    bp.taxonomy.groups = groups
    refresh_needs(bp)
    return [g.model_dump() for g in bp.taxonomy.groups] != before


def apply_edits(bp: BusinessBlueprint, edits: list[CatalogueEdit]) -> list[str]:
    """Apply what the owner typed. They are the source; nothing is checked against the chat."""
    touched: list[str] = []
    for edit in edits:
        group = _find(bp.taxonomy.groups, " ".join(edit.group.split()))
        if group is None:
            continue
        price = " ".join(edit.price.split())[:40]
        unit = " ".join(edit.unit.split())[:40]
        if price and not re.search(r"\d", price):
            raise ValueError("A price needs a number")
        if edit.item:
            item = next((i for i in group.items if i.name.casefold() == edit.item.casefold()), None)
            if item is None:
                continue
            item.price, item.unit, item.source = price or item.price, unit or item.unit, "owner_edited"
        elif price or unit:
            group.price, group.unit = price or group.price, unit or group.unit
        for raw in edit.add_items:
            name, vague = normalise_name(raw)
            if name and not vague and all(i.name.casefold() != name.casefold() for i in group.items):
                group.items.append(CatalogueItem(name=name[:80], source="owner_edited"))
                group.needs = [n for n in group.needs if n != "varieties"]
        touched.append(group.name)
    refresh_needs(bp)
    return touched


def refresh_needs(bp: BusinessBlueprint) -> None:
    """Price is needed where nothing in a group has one; structure needs stay as read."""
    for group in bp.taxonomy.groups:
        needs = [n for n in group.needs if n != "price"]
        if not group.price and not any(i.price for i in group.items):
            needs.append("price")
        group.needs = needs[:5]


def ensure_taxonomy(bp: BusinessBlueprint) -> None:
    """A structure exists whenever the owner has said what they sell."""
    if bp.taxonomy.groups:
        return
    facts = {**bp.known_facts, **bp.unconfirmed_facts}
    if "offerings" in facts:
        bp.taxonomy.groups = taxonomy_from_listing(facts["offerings"].value)
        refresh_needs(bp)


def open_structure(bp: BusinessBlueprint) -> list[CatalogueGroup]:
    """Groups whose shape is still unknown — varieties, cuts or sizes."""
    return [g for g in bp.taxonomy.groups if {"varieties", "cuts", "sizes"} & set(g.needs)]


def _names(groups: list[CatalogueGroup]) -> str:
    names = [g.name.lower() for g in groups]
    return str(names[0]) if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def structure_question(bp: BusinessBlueprint, style: str = "en") -> str:
    """Ask for the structure the website needs, in one or two linked parts."""
    pending = open_structure(bp)
    varieties = [g for g in pending if "varieties" in g.needs]
    cuts = [g for g in pending if "cuts" in g.needs]
    sizes = [g for g in pending if "sizes" in g.needs and g not in cuts]
    tamil = style.startswith("ta")
    parts: list[str] = []
    if cuts:
        parts.append(
            f"{_names(cuts).capitalize()}-la customers cuts select pannuvaangalaa?" if tamil
            else f"For {_names(cuts)}, do people choose cuts too?"
        )
    if varieties:
        parts.append(
            f"{_names(varieties).capitalize()}-la endha varieties usual-aa vechiruppeenga?" if tamil
            else f"And for {_names(varieties)}, which varieties do you usually keep?" if parts
            else f"You mentioned different {_names(varieties)} varieties. Which ones do you usually keep?"
        )
    if sizes and len(parts) < 2:
        parts.append(
            f"{_names(sizes).capitalize()} endha sizes-la kidaikkum?" if tamil
            else f"What sizes do {_names(sizes)} come in?"
        )
    return " ".join(parts[:2])


def catalogue_lines(bp: BusinessBlueprint) -> list[dict[str, object]]:
    """The structure as the owner reads it in the panel."""
    labels = {"varieties": "varieties", "cuts": "cuts", "sizes": "sizes", "price": "price", "photo": "photo"}
    out: list[dict[str, object]] = []
    for group in bp.taxonomy.groups:
        out.append({
            "name": group.name,
            "suggested_label": group.label_source == "ai_suggestion",
            "items": [i.name for i in group.items][:12],
            "sold_by": group.sold_by,
            "price": (f"{group.price} {group.unit}".strip() if group.price else ""),
            "needs": [labels[n] for n in group.needs],
        })
    return out
