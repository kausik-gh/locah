"""Compose a business's website from its creative direction and its own truth.

The page is not a template with slots. Its sections follow from what the
business is (the archetype) and what is actually known about it:

* a range with named items becomes browsable product cards, grouped by category
  (a meat shop's cuts, a kitchen's dishes, a developer's projects, a gym's plans);
* a range known only as categories becomes image-led category cards;
* how people order, how it reaches them and how they pay — the owner's answers —
  become a short ordering strip and the hero's fact chips;
* the owner's story (and any line they asked the site to say) becomes a story
  section with that line as a pull quote;
* contact comes last, with Call / WhatsApp / directions from what they gave.

Nothing is added that was not said: no ratings, counts, awards, prices or
promises; a section with nothing true to show is left out. Headings and short
lines are editorial and may be the model's, after governance.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote

from platform_core.interview.creative_director import CreativeDirection
from platform_core.interview.media_director import picture_for, slug
from platform_core.interview.models import BusinessBlueprint, CatalogueGroup
from platform_core.interview.taxonomy import normalise_name
from platform_core.interview.website_copy import WebsiteCopy
from platform_core.validation.website import validate_generation_payload

COMPOSER_VERSION = "creative-composer-v2"

# What the browse section is called, by archetype. "What we do" is for services
# only — for a shop it hides the fact that there are things to buy.
BROWSE_TITLE = {
    "product_commerce": "Shop by category", "menu_commerce": "Our menu",
    "membership_fitness": "Programmes", "real_estate_projects": "Featured projects",
    "service_appointment": "Services", "b2b_rfq": "What we supply",
    "project_portfolio": "What we make", "local_service": "Services",
}
NAV_BROWSE = {
    "product_commerce": "Shop", "menu_commerce": "Menu", "membership_fitness": "Programmes",
    "real_estate_projects": "Projects", "service_appointment": "Services", "b2b_rfq": "Products",
    "project_portfolio": "Work", "local_service": "Services",
}
_COMMERCE = {"product_commerce", "menu_commerce"}
_GENERIC_TITLE = re.compile(r"^\s*(what we do|our services|what we offer|our offerings)\s*$", re.I)


def _facts(bp: BusinessBlueprint) -> dict[str, str]:
    return {k: f.value for k, f in {**bp.known_facts, **bp.unconfirmed_facts}.items()}


def _answer(bp: BusinessBlueprint, target: str) -> str:
    state = bp.discovery.get(target)
    if not state or state.status not in {"answered", "partial"}:
        return ""
    return f"{state.summary} {state.quote}".strip()


def _display_phone(text: str) -> str:
    digits = re.sub(r"\D", "", text or "")
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    if len(digits) == 10:
        return f"+91 {digits[:5]} {digits[5:]}"
    return ""


def _place(text: str) -> str:
    """A tidy place name from "In nookampalayam road" -> "Nookampalayam Road"."""
    text = re.sub(r"^\s*(?:in|at|near|on)\s+", "", " ".join((text or "").split()), flags=re.I).strip(" .,")
    if not text or len(text) > 60:
        return ""
    small = {"and", "of", "the", "near", "to", "in", "on"}
    return " ".join(
        w if w.isupper() or any(c.isdigit() for c in w) else w.lower() if i and w.lower() in small
        else w.capitalize()
        for i, w in enumerate(text.split())
    )


def _join(names: list[str], word: str = "and") -> str:
    names = [n for n in names if n]
    if len(names) <= 1:
        return "".join(names)
    return ", ".join(names[:-1]) + f" {word} " + names[-1]


def _seen(bp: BusinessBlueprint, business_type: str | None) -> set[str]:
    from platform_core.interview.discovery import characteristics

    return {c for c, how in characteristics(bp, business_type).items() if how == "observed"}


# ----------------------------------------------------------------- facts


def ordering_facts(bp: BusinessBlueprint, business_type: str | None) -> list[dict[str, str]]:
    """How buying works, from the owner's answers — each item a real fact."""
    seen = _seen(bp, business_type)
    units = _answer(bp, "offerings.units").lower()
    mode = _answer(bp, "fulfilment.mode").lower()
    area_state = bp.discovery.get("fulfilment.area")
    payment = _answer(bp, "commerce.payment").lower()
    location = _place(_facts(bp).get("locations", ""))
    items: list[dict[str, str]] = []
    if re.search(r"\b(kg|kilo|weight|gram)", units):
        items.append({"kind": "weight", "title": "Choose your weight",
                      "body": "Pick the cut, pick the quantity — ordered by the kg."})
    elif units:
        items.append({"kind": "order", "title": "Choose what you need",
                      "body": (bp.discovery["offerings.units"].summary or "")[:160]})
    delivers = "delivers" in seen or re.search(r"\bdeliver", mode)
    pickup = "pickup" in seen or re.search(r"pick ?up|collect|takeaway", mode)
    if delivers:
        where = ""
        if area_state and area_state.status == "answered":
            raw = area_state.quote or area_state.summary
            raw = re.sub(r"^(?:we deliver\s+)?(?:around|in|to|within)\s+", "", raw.strip(), flags=re.I)
            where = _place(raw) if len(raw) <= 60 else ""
        items.append({"kind": "delivery", "title": "Home delivery",
                      "body": f"Delivered around {where}." if where else "Brought to your door."})
    if pickup:
        items.append({"kind": "pickup", "title": "Store pickup",
                      "body": f"Collect your order at {location}." if location else "Collect your order from the shop."})
    if payment:
        online = re.search(r"\b(online|upi|card|gpay|phonepe)\b", payment)
        cash = re.search(r"\b(cash|cod)\b", payment)
        if online and cash:
            items.append({"kind": "payment", "title": "Pay your way",
                          "body": "Pay online, or cash on delivery."})
        elif online:
            items.append({"kind": "payment", "title": "Pay online", "body": "Pay securely when you order."})
        elif cash:
            items.append({"kind": "payment", "title": "Cash on delivery", "body": "Pay when your order arrives."})
    return items[:4]


def hero_badges(bp: BusinessBlueprint, business_type: str | None) -> list[str]:
    """Short true chips under the headline — never a rating, a count or an award."""
    badges: list[str] = []
    for item in ordering_facts(bp, business_type):
        label = {"weight": "Sold by the kg", "delivery": "Home delivery", "pickup": "Store pickup",
                 "payment": item["body"].rstrip(".").replace("Pay online, or cash on delivery",
                                                               "Online or cash on delivery")}.get(item["kind"])
        if label and label not in badges:
            badges.append(label[:40])
    return badges[:3]


# ------------------------------------------------------------- sections


def _group_meta(group: CatalogueGroup) -> str:
    if group.price:
        return f"From {group.price} {group.unit}".strip()[:60]
    if re.search(r"\b(kg|kilo|weight)", group.sold_by, re.I):
        return "Sold by the kg"
    return ""


def _line(copy: WebsiteCopy, name: str, kind: str) -> str:
    lines = copy.category_lines if kind == "category" else copy.item_lines
    return next((c.line for c in lines if c.name.casefold() == name.casefold()), "")


def browse_sections(
    bp: BusinessBlueprint, direction: CreativeDirection, copy: WebsiteCopy, order_label: str
) -> list[dict[str, Any]]:
    """Categories and items, presented the way this kind of site browses."""
    groups = [g for g in bp.taxonomy.groups if g.name]
    if not groups:
        return []
    arche = direction.archetype
    title = copy.products_title or copy.categories_title or BROWSE_TITLE[arche]
    if _GENERIC_TITLE.match(title) and arche not in {"service_appointment", "local_service"}:
        title = BROWSE_TITLE[arche]
    drafts = {o.name.casefold(): o for o in bp.website_draft.offerings}
    items: list[dict[str, Any]] = []
    for group in groups:
        for item in group.items:
            name, vague = normalise_name(item.name)
            if not name or vague:
                continue  # "fish different varieties" is not a product
            entry: dict[str, Any] = {"name": name[:80], "category": group.name[:80]}
            description = item.description or _line(copy, name, "item")
            draft = drafts.get(name.casefold())
            if not description and draft and draft.description:
                description = draft.description.text
            if description:
                entry["description"] = description[:200]
            if item.price:
                entry["price"] = item.price[:40]
                if item.unit:
                    entry["unit"] = item.unit[:40]
            picture = picture_for(bp, f"item:{slug(name)}") or picture_for(bp, f"project:{slug(name)}")
            if picture:
                entry["image_asset_id"] = picture
            items.append(entry)
    categories: list[dict[str, Any]] = []
    for group in groups:
        card: dict[str, Any] = {"name": group.name[:80]}
        description = group.description or _line(copy, group.name, "category")
        draft = drafts.get(group.name.casefold())
        if not description and draft and draft.description:
            description = draft.description.text
        if description:
            card["description"] = description[:200]
        tags = [i.name for i in group.items if not normalise_name(i.name)[1]][:6]
        if tags:
            card["tags"] = tags
        meta = _group_meta(group)
        if meta:
            card["meta"] = meta
        picture = picture_for(bp, f"category:{slug(group.name)}")
        if picture:
            card["image_asset_id"] = picture
        categories.append(card)

    subtitle = copy.offerings_subtitle
    out: list[dict[str, Any]] = []
    has_item_pictures = sum(1 for i in items if i.get("image_asset_id")) >= 2
    if items:
        variant = direction.product_variant
        if arche == "product_commerce" and not has_item_pictures:
            variant = "category_boards"  # a board per category: one picture, its cuts listed
        elif variant == "menu_grid" and not has_item_pictures:
            variant = "category_boards" if any(c.get("image_asset_id") for c in categories) else "compact_list"
        content: dict[str, Any] = {
            "title": title[:120], "anchor": "shop", "items": items[:48],
            "categories": categories[:12], "filters": [g.name[:40] for g in groups][:10],
        }
        if subtitle:
            content["subtitle"] = subtitle[:300]
        if order_label:
            content["order_label"] = order_label[:40]
        out.append({"section_type_id": "product_showcase", "layout_variant": variant, "content": content})
    else:
        variant = direction.category_variant
        if variant == "image_cards" and not any(c.get("image_asset_id") for c in categories):
            variant = "tiles"
        if variant == "chips":
            variant = "image_cards" if any(c.get("image_asset_id") for c in categories) else "tiles"
        content = {"title": title[:120], "anchor": "shop", "items": categories[:8]}
        if subtitle:
            content["subtitle"] = subtitle[:300]
        out.append({"section_type_id": "category_showcase", "layout_variant": variant, "content": content})
    return out


def compose_site(
    bp: BusinessBlueprint,
    direction: CreativeDirection,
    copy: WebsiteCopy,
    *,
    business_type: str | None,
    contact: dict[str, Any],
    active_modules: frozenset[str],
    capability_rows: list[dict[str, Any]] | None = None,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """The whole website payload: pages, navigation and theme."""
    facts = _facts(bp)
    name = bp.identity["display_name"].value if "display_name" in bp.identity else "Our business"
    arche = direction.archetype
    phone = contact.get("phone", "")
    whatsapp = contact.get("whatsapp", "")
    wa_link = (f"https://wa.me/{re.sub(r'\D', '', whatsapp)}?text=" + quote(f"Hi {name}, ")) if whatsapp else ""

    # What a visitor can actually do. A cart only where ordering is switched on
    # AND there are live items to put in it — decided at render time.
    order_label = ""
    if arche in _COMMERCE:
        order_label = "Order on WhatsApp" if whatsapp else "Call to order" if phone else ""
    elif arche == "real_estate_projects":
        order_label = "Enquire on WhatsApp" if whatsapp else "Call to enquire" if phone else ""
    browse = browse_sections(bp, direction, copy, order_label)
    booking = "bookings" in active_modules and arche in {"service_appointment", "membership_fitness"}
    if booking:
        primary = (copy_cta(bp) or "Book now", "/book")
    elif browse:
        default = {"menu_commerce": "See the menu", "real_estate_projects": "View projects",
                   "membership_fitness": "See programmes"}.get(arche, "Shop now")
        primary = (copy_cta(bp) or default, "#shop")
    elif wa_link:
        primary = ("Message on WhatsApp", wa_link)
    else:
        primary = ("", "")

    sections: list[dict[str, Any]] = []
    hero: dict[str, Any] = {
        "headline": (copy.headline or name)[:120],
        "subheadline": (copy.subheadline or _first_sentence(facts.get("description", "")))[:300],
    }
    if copy.headline and copy.headline_accent and copy.headline_accent in copy.headline:
        hero["headline_accent"] = copy.headline_accent[:60]
    place = _place(facts.get("locations", ""))
    if place:
        hero["eyebrow"] = place[:60]
    if primary[0] and primary[1]:
        hero["cta_label"], hero["cta_url"] = primary[0][:60], primary[1][:500]
    badges = hero_badges(bp, business_type)
    if badges:
        hero["badges"] = badges
    hero_picture = picture_for(bp, "hero")
    if hero_picture:
        hero["image_asset_id"] = hero_picture
    if not hero["subheadline"]:
        hero.pop("subheadline")
    sections.append({"section_type_id": "hero", "layout_variant": direction.hero, "content": hero})
    sections.extend(browse)

    ordering = ordering_facts(bp, business_type)
    if len(ordering) >= 2:
        sections.append({
            "section_type_id": "fulfilment_strip", "layout_variant": "icons",
            "content": {"title": (copy.steps_title or ("How ordering works" if arche in _COMMERCE
                                                     else "Good to know"))[:120],
                        "anchor": "ordering", "items": ordering},
        })

    story_body = copy.about_body
    claims = [c.claim for c in bp.website_draft.owner_claims]
    if story_body:
        story: dict[str, Any] = {"title": (copy.about_title or "Our story")[:120], "body": story_body[:2000],
                                 "eyebrow": "Our story", "anchor": "story"}
        if claims:
            story["quote"] = claims[0][:200]
        picture = picture_for(bp, "category:" + slug(bp.taxonomy.groups[-1].name)) if bp.taxonomy.groups else None
        picture = picture or hero_picture
        if picture:
            story["image_asset_id"] = picture
        sections.append({"section_type_id": "about",
                         "layout_variant": direction.story_variant if picture else "text_only",
                         "content": story})

    if phone or whatsapp or (primary[0] and primary[1]):
        band: dict[str, Any] = {
            "headline": (copy.closing_headline or _closing(arche, name))[:200],
            "cta_label": (primary[0] or ("Call now" if phone else ""))[:60] or "Get in touch",
            "cta_url": primary[1][:500],
        }
        if copy.closing_body:
            band["body"] = copy.closing_body[:500]
        if hero_picture:
            band["image_asset_id"] = hero_picture
        sections.append({"section_type_id": "cta_band",
                         "layout_variant": "image_banner" if hero_picture else "centered",
                         "content": band})

    contact_section: dict[str, Any] = {"title": (copy.contact_title or ("Visit us" if place else "Get in touch"))[:120],
                                       "show_map": False}
    display = _display_phone(facts.get("phone", ""))
    if display:
        contact_section["phone"] = display
    if facts.get("locations"):
        contact_section["address"] = facts["locations"][:500]
    if facts.get("email"):
        contact_section["email"] = facts["email"][:200]
    if facts.get("opening_hours"):
        contact_section["hours_summary"] = facts["opening_hours"][:500]
    if len(contact_section) > 2:
        sections.append({"section_type_id": "contact", "layout_variant": "full", "content": contact_section})

    for section in sections:
        section["is_visible"] = True

    anchors = {s["content"].get("anchor") for s in sections}
    navigation = [{"label": "Home", "path": "/"}]
    if "shop" in anchors:
        navigation.append({"label": NAV_BROWSE[arche], "path": "/#shop"})
    if "story" in anchors:
        navigation.append({"label": "About", "path": "/#story"})
    if any(s["section_type_id"] == "contact" for s in sections):
        navigation.append({"label": "Contact", "path": "/#contact"})

    palette = direction.palette
    theme: dict[str, Any] = {
        # Kept for the renderer's older paths; the direction below is what it reads now.
        "personality": "dark" if palette.mode == "dark" else "clean",
        "primary_color": palette.primary,
        "accent_color": palette.accent,
        "background_color": palette.surface,
        "text_color": palette.ink,
        "surface_alt_color": palette.surface_alt,
        "muted_color": palette.muted,
        "palette_mode": palette.mode,
        "site_archetype": arche,
        "reference_profile": direction.reference_profile,
        "type_system": direction.type_system,
        "hero_style": direction.hero,
        "card_style": direction.cards,
        "nav_style": direction.nav,
        "motion_preference": "subtle",
        "motion_intensity": direction.motion,
        # The type system below chooses the faces; the older direction must
        # not layer its serif and weights on top of it.
        "typography_direction": "modern_sans",
        "creative_direction": direction.model_dump(mode="json"),
        "composer_version": COMPOSER_VERSION,
        "generation": meta or {},
    }
    if primary[0] and primary[1]:
        theme["nav_cta"] = {"label": primary[0][:40], "href": primary[1][:500]}
    utility: list[str] = []
    for item in ordering:
        if item["kind"] == "delivery":
            utility.append(item["body"].rstrip("."))
    if display:
        utility.append(display)
    if utility and direction.nav == "commerce":
        theme["utility_bar"] = utility[:2]

    home = {
        "slug": "home", "title": "Home", "page_type": "home", "sections": sections,
        "seo_title": name[:160],
        "seo_description": (hero.get("subheadline") or facts.get("description", ""))[:300],
    }
    payload: dict[str, Any] = validate_generation_payload(
        {"pages": [home], "navigation": navigation, "theme_hints": theme}
    )
    issues = quality_issues(payload, arche)
    payload["theme_hints"]["quality"] = {"valid": not issues, "issues": issues, "repair_count": 0}
    return payload


def copy_cta(bp: BusinessBlueprint) -> str:
    return bp.website_draft.cta_label.text[:40] if bp.website_draft.cta_label else ""


def _first_sentence(text: str) -> str:
    text = " ".join((text or "").split())
    match = re.match(r"(.+?[.!?])(\s|$)", text)
    return (match.group(1) if match else text)[:300]


def _closing(arche: str, name: str) -> str:
    return {
        "product_commerce": "Ready when you are.", "menu_commerce": "Hungry already?",
        "membership_fitness": "Your first session starts here.",
        "real_estate_projects": "Find the home that fits.",
    }.get(arche, f"Talk to {name}.")


def quality_issues(payload: dict[str, Any], archetype: str) -> list[dict[str, str]]:
    """What a reviewer would reject: generic headings, vague items, dead anchors."""
    issues: list[dict[str, str]] = []
    page = payload["pages"][0]
    anchors = {str(s["content"].get("anchor")) for s in page["sections"] if s["content"].get("anchor")}
    anchors.add("contact")
    for section in page["sections"]:
        content = section["content"]
        title = str(content.get("title") or "")
        if archetype in _COMMERCE and _GENERIC_TITLE.match(title):
            issues.append({"code": "generic_commerce_heading", "path": section["section_type_id"]})
        for item in content.get("items") or []:
            name = str(item.get("name") or item.get("title") or "") if isinstance(item, dict) else ""
            if name and normalise_name(name)[1]:
                issues.append({"code": "vague_item_name", "path": name})
    for item in payload["navigation"]:
        path = str(item.get("path") or "")
        if path.startswith("/#") and path[2:] not in anchors:
            issues.append({"code": "dead_anchor", "path": path})
    return issues
