"""What generation is allowed to build, decided before the model is asked.

Generation used to hand the model a business name and a list of page titles and
hope. Two things were missing, and they turn out to be the same thing seen from
either end.

The model was never told what this business can actually do. A section type
belongs to a module — a menu needs the offerings catalogue, a timetable needs
bookings — and adding one by hand is refused server-side when that module is
off. Generation had no such check, which made the one path that writes an
entire website unattended the least governed path in the system. A draft could
open with a plans comparison for a business that has never had memberships
turned on, and nothing would notice until the page rendered with nothing in it.

And the model was never given anything to personalise. It invented a structure
from the business type every time, which is why every restaurant came out
shaped like every other restaurant. Templates already describe real
compositions the renderer knows how to draw; generation simply never used one.

A plan is both halves. A template is chosen as the reference, and the
capability inventory says which parts of it this business may actually have.
The model personalises inside that, and whatever comes back is pruned against
the same inventory afterwards — because a prompt is a request, not a guarantee,
and the check that matters is the one that runs on the answer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable

from platform_core.website.template_registry import (
    DEFAULT_TEMPLATE_ID,
    TEMPLATES_BY_ID,
    WebsiteTemplate,
    templates_for_business_type,
)

# The five the stylesheet actually implements — see `packages/ui/src/tokens.css`,
# `[data-locah-site][data-personality='...']`. A sixth value is not a new look,
# it is an unstyled site, because the selector never matches and the tenant's
# theme quietly stops applying.
PERSONALITIES = frozenset({"warm", "premium", "bold", "clean", "dark"})

_HEX = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


@dataclass(frozen=True)
class SectionCapability:
    """One section type, and whether this business may use it."""

    section_type_id: str
    label: str
    allowed_variants: tuple[str, ...]
    requires_module: str | None
    available: bool


@dataclass(frozen=True)
class GenerationPlan:
    """The reference composition and the boundary around it."""

    template: WebsiteTemplate
    template_reason: str
    active_modules: frozenset[str]
    capabilities: tuple[SectionCapability, ...]

    @property
    def available_ids(self) -> frozenset[str]:
        return frozenset(c.section_type_id for c in self.capabilities if c.available)

    @property
    def blocked(self) -> dict[str, str]:
        """Section type -> the module that would unlock it."""
        return {
            c.section_type_id: c.requires_module
            for c in self.capabilities
            if not c.available and c.requires_module
        }

    def variants_for(self, section_type_id: str) -> tuple[str, ...]:
        for capability in self.capabilities:
            if capability.section_type_id == section_type_id:
                return capability.allowed_variants
        return ()

    def theme_baseline(self) -> dict[str, Any]:
        """The template's palette, without any claim that it was used.

        `template_id` is deliberately not here. Stamping it is a statement
        about where a draft came from, and only the caller knows whether the
        template was actually the reference or whether the draft came from the
        deterministic fallback, which builds from the business type and never
        looks at a template at all.
        """
        return {
            "primary_color": self.template.primary_color,
            "accent_color": self.template.accent_color,
            "personality": self.template.personality,
        }


def capabilities_from_rows(rows: Iterable[dict[str, Any]]) -> tuple[SectionCapability, ...]:
    """Adapt `WebsiteCompositionService.available_section_types` rows.

    Deliberately reuses that call rather than re-deriving availability here:
    generation and hand-editing must agree about what this business may have,
    and the surest way to make two rules agree is to have one rule.
    """
    out: list[SectionCapability] = []
    for row in rows:
        out.append(
            SectionCapability(
                section_type_id=str(row.get("id") or ""),
                label=str(row.get("label") or row.get("id") or ""),
                allowed_variants=tuple(str(v) for v in (row.get("allowed_variants") or [])),
                requires_module=(
                    str(row["requires_module"]) if row.get("requires_module") else None
                ),
                available=bool(row.get("available")),
            )
        )
    return tuple(c for c in out if c.section_type_id)


def select_template(
    *, business_type: str | None, active_modules: Iterable[str]
) -> tuple[WebsiteTemplate, str]:
    """Pick the reference composition, and say why in the owner's terms.

    Suitability first, then affordability: a template that names this business
    type but needs a module the business has switched off is the wrong
    reference, because the model would be personalising sections that get
    pruned a moment later. The reason is recorded on the job, so that a support
    question about "why does my site look like this" has an answer.

    Each reason is written to complete the sentence "It was chosen because …",
    which is how the prompt and the audit trail both read it.
    """
    active = frozenset(active_modules)
    btype = (business_type or "").strip().lower()
    ranked = templates_for_business_type(btype)

    affordable = [t for t in ranked if set(t.required_modules) <= active]
    first_suited = next((t for t in ranked if btype and btype in t.suits), None)
    for template in affordable:
        if btype and btype in template.suits:
            reason = f"it suits a {btype.replace('_', ' ')}"
            if first_suited is not None and first_suited is not template:
                # A better fit exists but is switched off: still worth saying.
                missing = ", ".join(sorted(set(first_suited.required_modules) - active))
                reason += (
                    f"; {first_suited.name} would suit it even better, but needs "
                    f"{missing}, which is switched off"
                )
            return template, reason

    # Nothing both names this business type and fits inside what it has turned
    # on. Say which one it missed out on, because that is the useful half.
    blocked_match = next((t for t in ranked if btype and btype in t.suits), None)
    if blocked_match is not None and affordable:
        missing = ", ".join(sorted(set(blocked_match.required_modules) - active))
        return (
            affordable[0],
            f"{blocked_match.name} would suit this business better, but that "
            f"template needs {missing}, which is switched off",
        )
    if affordable:
        return affordable[0], "it is a general-purpose starting point"
    return TEMPLATES_BY_ID[DEFAULT_TEMPLATE_ID], "it is the only one that needs no extra modules"


def build_plan(
    *,
    business_type: str | None,
    active_modules: Iterable[str],
    capability_rows: Iterable[dict[str, Any]],
) -> GenerationPlan:
    active = frozenset(active_modules)
    template, reason = select_template(business_type=business_type, active_modules=active)
    return GenerationPlan(
        template=template,
        template_reason=reason,
        active_modules=active,
        capabilities=capabilities_from_rows(capability_rows),
    )


def reference_composition(plan: GenerationPlan) -> list[dict[str, Any]]:
    """The template's pages with sections this business cannot have removed.

    Pruning here rather than only afterwards matters. Telling the model to open
    the Rooms page with a rooms list and then silently deleting it produces a
    page the model wrote copy *around* — a hero promising "every room is below"
    above nothing at all. Better that it never hears about the section.
    """
    pages: list[dict[str, Any]] = []
    available = plan.available_ids
    for page in plan.template.pages:
        kept = [
            {"section_type_id": s.section_type_id, "layout_variant": s.layout_variant}
            for s in page.sections
            if s.section_type_id in available
        ]
        if not kept:
            continue
        pages.append(
            {
                "slug": page.slug,
                "title": page.title,
                "page_type": page.page_type,
                "sections": kept,
            }
        )
    return pages


def normalise_theme(
    theme: dict[str, Any],
    *,
    baseline: dict[str, Any] | None = None,
    template_id: str | None = None,
) -> dict[str, Any]:
    """Clamp a theme to something the stylesheet can actually render.

    `personality` and `primary_color` travel from this JSON into a CSS selector
    and a custom property with nothing else checking them on the way. A
    personality the model invented matches no selector, so the tenant's whole
    visual identity silently stops applying; a colour that is not a colour
    makes the custom property invalid and the site falls back mid-render. Both
    fail quietly and read as a rendering bug, so they are settled here.

    `template_id` is recorded only when the caller passes one, and the caller
    passes one only when a template really was the reference. The picker reads
    it to say "your site was built from this", which has to be true.
    """
    baseline = baseline or {}
    merged = {**baseline, **{k: v for k, v in (theme or {}).items() if v is not None}}

    personality = str(merged.get("personality") or "").strip().lower()
    if personality not in PERSONALITIES:
        merged["personality"] = str(baseline.get("personality") or "clean")
    else:
        merged["personality"] = personality

    for key in ("primary_color", "accent_color"):
        value = str(merged.get(key) or "").strip()
        if _HEX.match(value):
            merged[key] = value.lower()
        elif baseline.get(key):
            merged[key] = baseline[key]
        else:
            merged.pop(key, None)

    if template_id:
        merged["template_id"] = template_id
    else:
        merged.pop("template_id", None)
    return merged


def enforce_capabilities(
    payload: dict[str, Any], plan: GenerationPlan
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """Drop what this business is not entitled to build, and report what went.

    Runs on the model's answer and on the deterministic fallback alike. A page
    left with nothing on it goes too, along with its navigation entry — a nav
    link to an empty page is worse than one fewer page.
    """
    available = plan.available_ids
    blocked = plan.blocked
    dropped: list[dict[str, str]] = []

    kept_pages: list[dict[str, Any]] = []
    for page in payload.get("pages") or []:
        if not isinstance(page, dict):
            continue
        slug = str(page.get("slug") or "")
        sections = page.get("sections")
        if not isinstance(sections, list):
            kept_pages.append(page)
            continue
        kept_sections: list[Any] = []
        for section in sections:
            if not isinstance(section, dict):
                continue
            type_id = str(section.get("section_type_id") or "")
            if type_id and type_id not in available:
                dropped.append(
                    {
                        "page": slug,
                        "section_type_id": type_id,
                        "requires_module": blocked.get(type_id, "unknown"),
                    }
                )
                continue
            kept_sections.append(section)
        if not kept_sections:
            dropped.append({"page": slug, "section_type_id": "", "requires_module": "page_empty"})
            continue
        page["sections"] = kept_sections
        kept_pages.append(page)

    if not kept_pages:
        # Everything was pruned, which should be impossible — a hero belongs to
        # no module. Returning the payload untouched lets the caller's existing
        # fallback path deal with it rather than writing an empty website.
        return payload, dropped

    payload["pages"] = kept_pages
    surviving = {str(p.get("slug") or "") for p in kept_pages}
    navigation = payload.get("navigation")
    if isinstance(navigation, list):
        payload["navigation"] = [
            item
            for item in navigation
            if not isinstance(item, dict) or _nav_slug(item) in surviving
        ]
    return payload, dropped


def _nav_slug(item: dict[str, Any]) -> str:
    slug = str(item.get("path") or "/").strip().strip("/").lower()
    return slug or "home"


def describe_plan_for_prompt(plan: GenerationPlan) -> str:
    """The plan as the model reads it: a reference to work from, and a fence.

    Both halves are stated positively. "Here is the shape, here is what exists"
    produces a better draft than a list of prohibitions, and the prohibition is
    enforced on the way back regardless of whether the model was persuaded.
    """
    template = plan.template
    look = ", ".join(template.look) if template.look else template.personality
    lines = [
        "",
        "REFERENCE COMPOSITION",
        f'Start from the "{template.name}" layout — {template.tagline} '
        f"It was chosen because it {plan.template_reason}. The look is {look}.",
        "",
        "Keep its shape and its order unless a fact about this business "
        "genuinely argues otherwise. You may drop a section this business has "
        "nothing real to say in, and you may reorder. Write every word of the "
        "copy yourself: the reference describes the shape, not the sentences.",
        "",
    ]
    for page in reference_composition(plan):
        shape = ", ".join(
            s["section_type_id"] + (f" ({s['layout_variant']})" if s["layout_variant"] else "")
            for s in page["sections"]
        )
        lines.append(f"- {page['title']} (/{page['slug']}, page_type={page['page_type']}): {shape}")

    lines += [
        "",
        "AVAILABLE SECTION TYPES",
        "This business has these switched on, and you may use any of them: "
        + ", ".join(sorted(plan.available_ids))
        + ".",
    ]
    blocked = plan.blocked
    if blocked:
        lines.append(
            "These are NOT available to this business and must not appear — a "
            "section of one of these types is deleted before the draft is "
            "saved: "
            + ", ".join(f"{k} (needs {v})" for k, v in sorted(blocked.items()))
            + "."
        )

    lines += [
        "",
        "THEME",
        f"Start from primary_color {template.primary_color}, accent_color "
        f'{template.accent_color}, personality "{template.personality}". You '
        "may shift the colours to suit this particular business, and you may "
        "choose a different personality from exactly: "
        + ", ".join(sorted(PERSONALITIES))
        + ". Colours must be six-digit hex. Anything else is replaced with the "
        "starting values.",
    ]
    return "\n".join(lines)
