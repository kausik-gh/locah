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
    derive_strategy,
    validate_strategy,
)
from platform_core.interview.models import BusinessBlueprint
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
                path = "/" if page["slug"] == "home" else f"/{page['slug']}"
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


def build_preview(
    bp: BusinessBlueprint,
    plan: GenerationPlan,
    strategy: DesignStrategy | None = None,
) -> dict[str, Any]:
    """Build an immediate, editable preview from truth plus controlled design choices."""
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
                content = {
                    "headline": headline_options(bp)[1 if use_offering else 0],
                    "subheadline": value("description", 300),
                }
                if hero_asset:
                    content["image_asset_id"] = hero_asset
            elif kind in {"about", "text_block"}:
                body_parts = [part for part in (value("description"), value("offerings")) if part]
                content = {
                    "title": f"About {name}"[:120],
                    "body": "\n\n".join(dict.fromkeys(body_parts))[:2000],
                }
                if not content["body"]:
                    continue
                if about_asset and kind == "about":
                    content["image_asset_id"] = about_asset
            elif kind == "contact":
                content = {"title": "Contact", "show_map": False}
                for source, content_field, limit in (
                    ("locations", "address", 500),
                    ("phone", "phone", 50),
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
                content = {"headline": name, "cta_label": "", "cta_url": ""}
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
                content = {"title": page.title}
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

    resolved_target = _action_target(primary_action, pages)
    for page in pages:
        kept: list[dict[str, Any]] = []
        for section in page["sections"]:
            if section["section_type_id"] == "hero" and resolved_target:
                section["content"].update(
                    {"cta_label": resolved_target[0], "cta_url": resolved_target[1]}
                )
            if section["section_type_id"] == "cta_band":
                if not resolved_target or not selected.cta_hierarchy.repeat_primary:
                    continue
                section["content"].update(
                    {"cta_label": resolved_target[0], "cta_url": resolved_target[1]}
                )
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
            "design_strategy": selected.model_dump(mode="json"),
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
