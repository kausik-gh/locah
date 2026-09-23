"""Fact-safe website composition from a confirmed Business Blueprint.

The design strategist may choose among platform-owned templates, variants,
ordering, emphasis, and real media. It never writes business facts, routes, or
mechanics. This module is the final authority: it turns those controlled
choices into the same structured payload the editor and renderer already use,
then validates the result before a WebsiteVersion can be written.
"""

from __future__ import annotations

import re
from typing import Any

from platform_core.interview.design_strategy import (
    ACTION_LABEL,
    ACTION_MODULE,
    ACTION_PATH,
    DESIGN_STRATEGY_VERSION,
    GENERATION_PLAN_VERSION,
    DesignStrategy,
    Goal,
    QualityIssue,
    QualityReport,
    SectionDecision,
    derive_strategy,
    validate_strategy,
)
from platform_core.interview.models import BusinessBlueprint
from platform_core.interview.website_copy import WebsiteCopy
from platform_core.validation.website import validate_generation_payload
from platform_core.website.generation_plan import GenerationPlan, normalise_theme


def headline_options(bp: BusinessBlueprint) -> list[str]:
    """Confirmed, owner-supplied hero options; never generated marketing copy."""
    name = bp.identity["display_name"].value[:120]
    offering = bp.known_facts.get("offerings")
    return [name, offering.value[:120] if offering and len(offering.value) <= 120 else name]


def _decision_map(strategy: DesignStrategy) -> dict[str, Any]:
    return {item.section_type_id: item for item in strategy.section_variants}


def _action_target(action: Goal, pages: list[dict[str, Any]]) -> tuple[str, str] | None:
    """Resolve only routes that existing platform mechanics can fulfil."""
    fixed = ACTION_PATH.get(action)
    if fixed:
        return ACTION_LABEL[action], fixed
    if action == "offerings":
        catalogue = {
            "offerings_list",
            "menu_section",
            "rooms_section",
            "plans_section",
            "classes_section",
        }
        for page in pages:
            if any(section["section_type_id"] in catalogue for section in page["sections"]):
                path = "/" if page["slug"] == "home" else f"/{page['slug']}"
                return ACTION_LABEL["offerings"], path
    if action == "join":
        for page in pages:
            if any(section["section_type_id"] == "plans_section" for section in page["sections"]):
                path = "/" if page["slug"] == "home" else f"/{page['slug']}"
                return ACTION_LABEL["join"], path
    if action in {"contact", "enquire"}:
        for page in pages:
            if any(section["section_type_id"] == "contact" for section in page["sections"]):
                # On the home page itself, "/" is the page the visitor is already
                # on — a button that goes nowhere. Scroll to the contact section.
                path = "#contact" if page["slug"] == "home" else f"/{page['slug']}"
                return ACTION_LABEL[action], path
    return None


def _quality_report(
    payload: dict[str, Any],
    bp: BusinessBlueprint,
    plan: GenerationPlan,
    strategy_quality: QualityReport,
) -> QualityReport:
    """Check the composed result, not merely the model's intermediate advice."""
    issues = list(strategy_quality.issues)
    allowed_variants = {
        section_id: set(plan.variants_for(section_id)) for section_id in plan.available_ids
    }
    known_media = {str(item.asset_id) for item in bp.media_assets}
    slugs = {str(page["slug"]) for page in payload["pages"]}
    seen_home_hero = False

    for page_index, page in enumerate(payload["pages"]):
        seen_types: set[str] = set()
        for section_index, section in enumerate(page["sections"]):
            section_id = str(section["section_type_id"])
            path = f"pages.{page_index}.sections.{section_index}"
            if section_id not in plan.available_ids:
                issues.append(
                    QualityIssue(
                        severity="error",
                        code="unavailable_section",
                        path=path,
                        message="A section escaped the capability plan.",
                        repaired=False,
                    )
                )
            if section_id in seen_types:
                issues.append(
                    QualityIssue(
                        severity="warning",
                        code="duplicate_section",
                        path=path,
                        message="The page repeats the same section type.",
                        repaired=False,
                    )
                )
            seen_types.add(section_id)
            variant = section.get("layout_variant")
            if variant and variant not in allowed_variants.get(section_id, set()):
                issues.append(
                    QualityIssue(
                        severity="error",
                        code="invalid_renderer_variant",
                        path=path,
                        message="The renderer does not expose this variant.",
                        repaired=False,
                    )
                )
            content = section.get("content") or {}
            media_ids = []
            if content.get("image_asset_id"):
                media_ids.append(str(content["image_asset_id"]))
            media_ids.extend(str(item) for item in content.get("image_asset_ids") or [])
            if any(item not in known_media for item in media_ids):
                issues.append(
                    QualityIssue(
                        severity="error",
                        code="unknown_payload_media",
                        path=path,
                        message="The website references media outside this Business Blueprint.",
                        repaired=False,
                    )
                )
            if page["slug"] == "home" and section_id == "hero":
                seen_home_hero = True

    if "home" in slugs and not seen_home_hero:
        issues.append(
            QualityIssue(
                severity="warning",
                code="home_without_hero",
                path="pages.home",
                message="The home page has no hero section.",
                repaired=False,
            )
        )
    for index, item in enumerate(payload["navigation"]):
        path = str(item.get("path") or "")
        target = path.strip("/") or "home"
        if not path.startswith("/") or target not in slugs:
            issues.append(
                QualityIssue(
                    severity="error",
                    code="broken_navigation",
                    path=f"navigation.{index}",
                    message="Navigation does not resolve to a generated page.",
                    repaired=False,
                )
            )

    return QualityReport(
        valid=not any(issue.severity == "error" and not issue.repaired for issue in issues),
        issues=issues,
        repair_count=sum(issue.repaired for issue in issues),
    )



_NAME_SUFFIXES = {"co", "co.", "ltd", "ltd.", "pvt", "pvt.", "llp", "inc", "inc.", "&", "and"}


def _first_sentence(text: str, limit: int) -> str:
    text = " ".join(text.split())
    match = re.match(r"(.+?[.!?])(\s|$)", text)
    sentence = match.group(1) if match else text
    return sentence[:limit].strip()


def _default_accent(name: str) -> str:
    """The word of a business name worth setting in the brand colour.

    "Meridian Multispeciality *Hospital*", "Teakwood *Furniture* Co" — the
    word that says what the place is, skipping legal suffixes.
    """
    words = name.split()
    while words and words[-1].casefold() in _NAME_SUFFIXES:
        words.pop()
    return words[-1] if len(words) >= 2 else ""


def _eyebrow(location: str) -> str:
    """A short place line above the headline — "COIMBATORE", "ANNA NAGAR, CHENNAI"."""
    text = " ".join(location.split()).strip(" .,")
    if not text:
        return ""
    if len(text) <= 40 and not re.search(r"\b(we|our|is|are|run|have)\b", text, re.I):
        return re.sub(r"^(?:in|at|near)\s+", "", text, flags=re.I)[:60]
    match = re.search(r"\b(?:in|at|near)\s+([A-Z][\w.'-]*(?:[ ,]+[A-Z][\w.'-]*){0,3})", text)
    return match.group(1).strip(" ,")[:60] if match else ""


def _offering_items(text: str) -> list[str]:
    """Split an owner's list of what they sell into tidy, owner-worded titles."""
    cleaned = re.sub(
        r"^(?:(?:we|i)\s+(?:mainly\s+|mostly\s+)?(?:sell|make|do|offer|serve|provide)\s+|"
        r"mostly\s+|mainly\s+|people come (?:to us )?(?:mainly )?for\s+)",
        "",
        " ".join(text.split()).strip(" ."),
        flags=re.I,
    )
    parts = re.split(r"\s*(?:[,;]|\band\b|&)\s*", cleaned)
    items: list[str] = []
    for part in parts:
        part = part.strip(" .")
        if len(part) < 3 or len(part) > 60 or re.search(r"\d", part):
            continue  # numbers belong in highlights, not in a list of services
        title = part[0].upper() + part[1:]
        if title.casefold() not in {item.casefold() for item in items}:
            items.append(title)
    return items[:8]


def _story(facts: dict[str, str], *, skip_offerings: bool) -> str:
    keys = ["description", "operating_model", "operational_characteristics"]
    if not skip_offerings:
        keys.append("offerings")
    parts = [facts[key].strip() for key in keys if facts.get(key)]
    return "\n\n".join(dict.fromkeys(parts))[:2000]


def _plain(text: str) -> str:
    return " ".join(re.sub(r"[^\w\s]", " ", text.casefold()).split())


def _display_phone(text: str) -> str:
    """A number as a visitor should read it — not the sentence it was said in.

    "ஃபோன் நம்பர் 98765-43210" is what the owner said; "+91 98765 43210" is
    what belongs on their site. Anything that is not a phone number is left out.
    """
    digits = re.sub(r"\D", "", text or "")
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    if len(digits) == 10:
        return f"+91 {digits[:5]} {digits[5:]}"
    if 8 <= len(digits) <= 13:
        return "+" + digits if (text or "").strip().startswith("+") else digits
    return ""


def _after_first_sentence(text: str) -> str:
    """Everything after the opening sentence, or nothing."""
    first, _, others = text.strip().partition("\n\n")
    parts = re.split(r"(?<=[.!?])\s+", first, maxsplit=1)
    rest = parts[1] if len(parts) == 2 else ""
    return "\n\n".join(p for p in (rest.strip(), others.strip()) if p)


def _without_repeats(sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Say each thing once per page.

    A one-sentence description would otherwise appear as the hero's supporting
    line, again as "Our story", and again in a text block — the clearest tell
    that a page was assembled rather than written. A story that only repeats
    what the page already said is dropped; one that starts with it keeps only
    what is new.
    """
    said: list[str] = []
    kept: list[dict[str, Any]] = []
    for section in sections:
        content = section["content"]
        if section["section_type_id"] == "hero" and content.get("subheadline"):
            said.append(_plain(content["subheadline"]))
        if section["section_type_id"] in {"about", "text_block"}:
            body = str(content.get("body") or "")
            for earlier in said:
                if earlier and _plain(body) == earlier:
                    body = ""
                    break
                if earlier and _plain(body).startswith(earlier):
                    body = _after_first_sentence(body)
                    break
            if not body or _plain(body) in said:
                continue
            content["body"] = body
            said.append(_plain(body))
        kept.append(section)
    return kept


def _accent_of(headline: str) -> str:
    """The part after the comma in "Fresh meat, closer to home." — if there is one."""
    head, sep, tail = headline.partition(",")
    tail = tail.strip().rstrip(".!")
    return tail if sep and 2 <= len(tail) <= 40 and head.strip() else ""


def with_draft(bp: BusinessBlueprint, copy: WebsiteCopy | None) -> WebsiteCopy:
    """The wording the site uses: the owner's draft first, then personalisation.

    Draft text is what the owner saw — and possibly edited — beside the
    conversation. A later model pass may fill what the draft leaves empty, but
    it never replaces a line the owner has already looked at.
    """
    data = (copy or WebsiteCopy()).model_dump()
    wd = bp.website_draft
    if wd.hero_headline:
        data["headline"] = wd.hero_headline.text[:90]
        data["headline_accent"] = _accent_of(wd.hero_headline.text)
    if wd.hero_subheadline:
        data["subheadline"] = wd.hero_subheadline.text[:220]
    if wd.about:
        data["about_body"] = wd.about.text[:800]
    if len(wd.offerings) >= 2:
        # An item the draft names without a line keeps personalisation's line for it.
        written = {str(f.get("title", "")).casefold(): str(f.get("body", "")) for f in data.get("features") or []}
        data["features"] = [
            {"title": o.name[:80],
             "body": (o.description.text if o.description else written.get(o.name.casefold(), ""))[:240]}
            for o in wd.offerings[:8]
        ]
    return WebsiteCopy.model_validate(data)


def build_preview(
    bp: BusinessBlueprint,
    plan: GenerationPlan,
    strategy: DesignStrategy | None = None,
    copy: WebsiteCopy | None = None,
) -> dict[str, Any]:
    """Build an immediate, editable preview from truth plus controlled design choices.

    `copy` is the governed model-written wording, when personalisation has run.
    Every field of it is optional: whatever is missing falls back to the owner's
    own words, so the immediate preview (no copy) and the personalised one use
    exactly the same composition rules.
    """
    words = with_draft(bp, copy)
    selected, strategy_quality = validate_strategy(strategy or derive_strategy(bp, plan), bp, plan)
    decisions = _decision_map(selected)
    facts = bp.known_facts
    name = bp.identity["display_name"].value

    def value(key: str, limit: int = 2000) -> str:
        return facts[key].value[:limit] if key in facts else ""

    hero_asset = (
        str(selected.media_strategy.hero_asset_id)
        if selected.media_strategy.hero_asset_id
        else None
    )
    gallery_assets = [str(item) for item in selected.media_strategy.gallery_asset_ids]
    supporting_assets = [
        str(item.asset_id)
        for item in bp.media_assets
        if item.role not in {"logo", "hero"} and str(item.asset_id) not in gallery_assets
    ]
    about_asset = (
        supporting_assets[0] if supporting_assets else gallery_assets[0] if gallery_assets else None
    )
    primary_action = selected.cta_hierarchy.primary
    primary_module = ACTION_MODULE[primary_action]
    if primary_module and primary_module not in plan.active_modules:
        primary_action = "discover"

    pages: list[dict[str, Any]] = []
    for page in plan.template.pages:
        sections: list[dict[str, Any]] = []
        for source_index, section in enumerate(page.sections):
            kind = section.section_type_id
            decision = decisions.get(kind)
            if kind not in plan.available_ids or not decision or not decision.include:
                continue
            content: dict[str, Any]
            if kind == "hero":
                use_offering = (
                    selected.visual_priority.primary_customer_action == "offerings"
                    and headline_options(bp)[1] != name
                )
                headline = words.headline or headline_options(bp)[1 if use_offering else 0]
                accent = (
                    words.headline_accent
                    if words.headline and words.headline_accent
                    else _default_accent(headline) if headline == name else ""
                )
                content = {
                    "headline": headline,
                    "subheadline": words.subheadline or _first_sentence(value("description"), 300),
                }
                if accent and accent in headline:
                    content["headline_accent"] = accent
                eyebrow = _eyebrow(value("locations"))
                if eyebrow:
                    content["eyebrow"] = eyebrow
                if hero_asset:
                    content["image_asset_id"] = hero_asset
            elif kind in {"about", "text_block"}:
                if copy is not None and not words.about_body:
                    # Personalisation ran and its story did not survive
                    # governance. The hero, the cards and the steps already say
                    # what the business does; a raw paste of mixed-script
                    # quotes under a polished heading reads worse than nothing.
                    continue
                content = {
                    "title": (words.about_title or "Our story")[:120],
                    "body": (words.about_body or _story(
                        {k: f.value for k, f in facts.items()},
                        skip_offerings=len(_offering_items(value("offerings"))) >= 2,
                    ))[:2000],
                }
                if not content["body"]:
                    continue
                if about_asset and kind == "about":
                    content["image_asset_id"] = about_asset
            elif kind == "contact":
                content = {
                    "title": words.contact_title
                    or ("Visit us" if value("locations") else "Get in touch"),
                    "show_map": False,
                }
                phone = _display_phone(value("phone"))
                if phone:
                    content["phone"] = phone
                for source, content_field, limit in (
                    ("locations", "address", 500),
                    ("email", "email", 200),
                    ("opening_hours", "hours_summary", 500),
                ):
                    if value(source):
                        content[content_field] = value(source, limit)
                if len(content) == 2:
                    continue
            elif kind == "gallery":
                media_ids = gallery_assets or ([hero_asset] if hero_asset else [])
                if not media_ids:
                    continue
                content = {"title": "Gallery", "image_asset_ids": media_ids}
            elif kind == "cta_band":
                # Filled only after retained pages are known, so it cannot link
                # to a page removed for lack of real content.
                content = {
                    "headline": words.closing_headline or f"Talk to {name}"[:200],
                    "cta_label": "",
                    "cta_url": "",
                }
                if words.closing_body:
                    content["body"] = words.closing_body
            elif kind == "location_list":
                # Interview prose is not a configured Location record.
                continue
            elif kind == "enquiry_form":
                # The Leads module is owner-facing today; it has no anonymous
                # public write endpoint. Do not render a form whose POST route
                # merely looks real. A confirmed contact section remains the
                # honest public enquiry path until that mechanic exists.
                continue
            else:
                # Live-record sections contain labels only. Inventory, prices,
                # availability, people, rooms, and plans come from live modules.
                # On the home page the page's own name ("Home") is not a heading.
                home_titles = {"offerings_list": "Order online", "menu_section": "Menu",
                               "rooms_section": "Rooms", "plans_section": "Plans",
                               "classes_section": "Classes"}
                content = {"title": page.title if page.slug != "home" else home_titles.get(kind, page.title)}
            sections.append(
                {
                    "section_type_id": kind,
                    "layout_variant": decision.variant,
                    "content": content,
                    "is_visible": True,
                    "_order": decision.order,
                    "_source": source_index,
                }
            )
        if sections:
            sections.sort(key=lambda item: (item.pop("_order"), item.pop("_source")))
            sections = _without_repeats(sections)
            pages.append(
                {
                    "slug": page.slug,
                    "title": page.title,
                    "page_type": page.page_type,
                    "sections": sections,
                    "seo_title": (name if page.slug == "home" else f"{page.title} | {name}")[:160],
                    "seo_description": value("description", 300),
                }
            )
    if not pages:
        raise ValueError("The selected template has no available sections.")

    extra_decisions = _inject_truthful_sections(pages, bp, plan, selected, words)

    resolved_target = _action_target(primary_action, pages)
    cta_label = (
        bp.website_draft.cta_label.text[:60]
        if bp.website_draft.cta_label and resolved_target else resolved_target[0] if resolved_target else ""
    )
    # A phone number the owner gave is a real way to reach them. The renderer
    # turns it into Call and WhatsApp buttons, so a closing band is worth
    # keeping for it even when no platform action backs the band.
    reachable = bool(value("phone"))
    for page in pages:
        kept: list[dict[str, Any]] = []
        for section in page["sections"]:
            if section["section_type_id"] == "hero" and resolved_target:
                section["content"].update(
                    {"cta_label": cta_label, "cta_url": resolved_target[1]}
                )
            if section["section_type_id"] == "cta_band":
                if resolved_target and selected.cta_hierarchy.repeat_primary:
                    section["content"].update(
                        {"cta_label": resolved_target[0], "cta_url": resolved_target[1]}
                    )
                elif reachable:
                    section["content"].update({"cta_label": "Call or WhatsApp", "cta_url": ""})
                else:
                    continue
            kept.append(section)
        page["sections"] = kept
    pages = [page for page in pages if page["sections"]]

    theme = normalise_theme(
        {**plan.theme_baseline(), "personality": selected.visual_personality},
        baseline=plan.theme_baseline(),
        template_id=plan.template.id,
    )
    colours = re.findall(r"#[0-9a-fA-F]{6}\b", value("colours"))
    if colours:
        theme["primary_color"] = colours[0].lower()
    if len(colours) > 1:
        theme["accent_color"] = colours[1].lower()
    theme.update(
        {
            "design_strategy_version": DESIGN_STRATEGY_VERSION,
            "generation_plan_version": GENERATION_PLAN_VERSION,
            "design_strategy": selected.model_copy(
                update={"section_variants": [*selected.section_variants, *extra_decisions]}
            ).model_dump(mode="json"),
            "typography_direction": selected.typography_direction,
            "content_density": selected.composition.content_density,
            "hero_density": selected.composition.hero_density,
            "motion_preference": selected.motion_preference,
            "mobile_priority": selected.mobile_priority,
            "navigation_style": selected.navigation_style,
        }
    )
    payload: dict[str, Any] = validate_generation_payload(
        {
            "pages": pages,
            "navigation": [
                {
                    "label": page["title"],
                    "path": "/" if page["slug"] == "home" else f"/{page['slug']}",
                }
                for page in pages
            ],
            "theme_hints": theme,
        }
    )
    quality = _quality_report(payload, bp, plan, strategy_quality)
    if not quality.valid:
        raise ValueError("Website quality validation rejected the generated composition.")
    payload["theme_hints"]["quality"] = quality.model_dump(mode="json")
    return payload


def _inject_truthful_sections(
    pages: list[dict[str, Any]],
    bp: BusinessBlueprint,
    plan: GenerationPlan,
    strategy: DesignStrategy,
    words: WebsiteCopy,
) -> list[SectionDecision]:
    """Add the sections a template cannot know about, from the owner's own facts.

    Templates describe structure; they cannot know that this hospital said
    "200-bed" or that this workshop listed four things it makes. Each section
    here appears only when the registry has it and the owner supplied the
    material — no numbers means no stats strip, one offering means no grid.
    Returns the emphasis decisions for the renderer.
    """
    if not pages:
        return []
    home = next((page for page in pages if page["slug"] == "home"), pages[0])
    sections = home["sections"]
    decisions: list[SectionDecision] = []
    facts = {key: fact.value for key, fact in bp.known_facts.items()}
    goal = strategy.cta_hierarchy.primary
    hero_at = next(
        (i for i, section in enumerate(sections) if section["section_type_id"] == "hero"), -1
    )
    position = hero_at + 1

    if "highlights" in plan.available_ids and len(bp.highlights) >= 2:
        variants = plan.variants_for("highlights")
        sections.insert(position, {
            "section_type_id": "highlights",
            "layout_variant": "strip" if "strip" in variants else (variants[0] if variants else None),
            "content": {"items": [{"value": h.value, "label": h.label} for h in bp.highlights[:6]]},
            "is_visible": True,
        })
        decisions.append(SectionDecision(
            section_type_id="highlights", emphasis="supporting", variant="strip", order=position,
        ))
        position += 1

    if "feature_grid" in plan.available_ids:
        variants = plan.variants_for("feature_grid")
        items = [
            {"title": item.title, **({"body": item.body} if item.body else {})}
            for item in words.features
        ] or [{"title": title} for title in _offering_items(facts.get("offerings", ""))]
        if len(items) >= 2 and "cards" in variants:
            content: dict[str, Any] = {
                "title": words.offerings_title or "What we do",
                "items": items[:9],
            }
            if words.offerings_subtitle:
                content["subtitle"] = words.offerings_subtitle
            sections.insert(position, {
                "section_type_id": "feature_grid",
                "layout_variant": "cards",
                "content": content,
                "is_visible": True,
            })
            # What a business does is the point of its site when the visitor's
            # next step is to choose something from it.
            emphasis = "primary" if goal in {"offerings", "order", "enquire", "discover"} else "supporting"
            decisions.append(SectionDecision(
                section_type_id="feature_grid", emphasis=emphasis, variant="cards", order=position,
            ))
        if len(words.steps) >= 2 and "steps" in variants:
            closing = next(
                (
                    i for i, section in enumerate(sections)
                    if section["section_type_id"] in {"contact", "cta_band"}
                ),
                len(sections),
            )
            sections.insert(closing, {
                "section_type_id": "feature_grid",
                "layout_variant": "steps",
                "content": {
                    "title": words.steps_title or "How it works",
                    "items": [
                        {"title": step.title, **({"body": step.body} if step.body else {})}
                        for step in words.steps
                    ],
                },
                "is_visible": True,
            })
    return decisions
