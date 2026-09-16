"""Structured website-generation questionnaire (Doc 12 §12.7).

A skippable, business-type-aware intake form. Every answered field is folded
into ONE `generate_structured` call (see `website_generation.py`); skipped
fields fall through to the deterministic generator. Nothing here is a
per-field AI helper and there is no conversation — this is a one-shot brief.

Design rules (Doc 12 §12.7):
  * every question maps to content one of the 13 seeded SectionTypes can render;
  * every field is optional and carries a concrete example, never a blank box;
  * two tiers — `universal` (every Business) and `type_specific` (per profile);
  * colour is a curated preset, NOT logo extraction (deferred).

This module is pure data + two pure functions. It follows the immutable
registry pattern of `business_type_profiles` — definitions are module-level
constants, resolved by a small accessor.
"""

from __future__ import annotations

from typing import Any

from platform_core.business_types import SUPPORTED_BUSINESS_TYPES
from platform_core.validation.website import assert_no_unsafe_content

QUESTIONNAIRE_VERSION = "v1"

# --- curated option sets -------------------------------------------------------

# Curated palettes only. Logo-colour extraction is explicitly a later pass.
PALETTE_PRESETS: dict[str, dict[str, str]] = {
    "sage": {"primary": "#4B6B5A", "accent": "#C6A15B", "label": "Sage & brass"},
    "ink": {"primary": "#1F2933", "accent": "#3B82F6", "label": "Ink & blue"},
    "terracotta": {"primary": "#9C4A2E", "accent": "#E8B04B", "label": "Terracotta & ochre"},
    "plum": {"primary": "#5B3A5B", "accent": "#D98BA6", "label": "Plum & rose"},
    "forest": {"primary": "#14532D", "accent": "#84CC16", "label": "Forest & lime"},
    "charcoal": {"primary": "#27272A", "accent": "#F59E0B", "label": "Charcoal & amber"},
    "ocean": {"primary": "#0E7490", "accent": "#F97316", "label": "Ocean & coral"},
    "classic": {"primary": "#1C5F57", "accent": "#F59E0B", "label": "Classic teal (default)"},
}

# `upload` writes an asset id. `generate` asks the platform to produce a
# picture after the structured draft exists. `curated` is still deferred.
_IMAGE_CHOICES = [
    {"value": "upload", "label": "I'll upload one"},
    {"value": "generate", "label": "Generate one for me"},
    {"value": "skip", "label": "Skip — generate a picture if I don't upload one"},
]


def _q(
    qid: str,
    kind: str,
    label: str,
    *,
    help: str = "",
    example: str = "",
    optional: bool = True,
    **extra: Any,
) -> dict[str, Any]:
    q: dict[str, Any] = {
        "id": qid,
        "kind": kind,
        "label": label,
        "optional": optional,
    }
    if help:
        q["help"] = help
    if example:
        q["example"] = example
    q.update(extra)
    return q


# --- universal questions (every Business) ------------------------------------

# Shown first. The rest of the universal set is behind "more detail".
ESSENTIAL_QUESTIONS: list[dict[str, Any]] = [
    _q(
        "lead_with",
        "single_select",
        "What should the homepage lead with?",
        help="Sets which section sits at the top of your home page.",
        example="A café usually leads with the menu; a consultant leads with services.",
        options=[
            {"value": "story", "label": "Our story / what we're about"},
            {"value": "offerings", "label": "What we sell or offer"},
            {"value": "booking", "label": "Booking / making an appointment"},
            {"value": "contact", "label": "How to reach us / visit"},
            {"value": "gallery", "label": "Photos of our work or space"},
        ],
    ),
    _q(
        "palette",
        "palette_select",
        "Pick a colour direction",
        help="Curated presets only for now — matching colours to your logo comes later.",
        example="'Sage & brass' suits calm, premium services; 'Ocean & coral' suits lively food.",
        options=[
            {"value": key, "label": val["label"], "primary": val["primary"], "accent": val["accent"]}
            for key, val in PALETTE_PRESETS.items()
        ],
    ),
    _q(
        "logo",
        "asset_choice",
        "Do you have a logo?",
        example="If you skip, we use your business name set in the chosen typeface.",
        options=[
            {"value": "upload", "label": "I'll upload one"},
            {"value": "skip", "label": "Skip — use the business name"},
        ],
    ),
    _q(
        "hero_image",
        "asset_choice",
        "Main image for the top of the homepage",
        example="A photo of your space, your product, or your team works well.",
        options=_IMAGE_CHOICES,
    ),
]


OPTIONAL_QUESTIONS: list[dict[str, Any]] = [
    _q(
        "tone",
        "slider_pair",
        "How should it read?",
        help="Drag each slider. This nudges word choice and layout density — nothing more.",
        example="Most independent shops land warm + a little playful.",
        pairs=[
            {"id": "warm_minimal", "left": "Warm", "right": "Minimal"},
            {"id": "playful_serious", "left": "Playful", "right": "Serious"},
            {"id": "modern_classic", "left": "Modern", "right": "Classic"},
            {"id": "bold_understated", "left": "Bold", "right": "Understated"},
        ],
    ),
    _q(
        "words_prefer",
        "text",
        "Words or phrases we should use",
        help="Comma-separated. Things you'd genuinely say about yourself.",
        example="hand-rolled, small-batch, family-run, walk-ins welcome",
    ),
    _q(
        "words_avoid",
        "text",
        "Words we should avoid",
        help="Comma-separated.",
        example="cheap, discount, world-class, revolutionary",
    ),
    _q(
        "contact_display",
        "multi_toggle",
        "What to show on the contact section",
        help="We already have your business details — this just controls what's public.",
        example="A home studio might show a phone number but not a street address.",
        toggles=[
            {"id": "show_phone", "label": "Phone number", "default": True},
            {"id": "show_email", "label": "Email address", "default": True},
            {"id": "show_address", "label": "Street address", "default": True},
            {"id": "show_map", "label": "Map", "default": False},
            {"id": "show_hours", "label": "Opening hours", "default": True},
        ],
    ),
    _q(
        "hours",
        "text",
        "Opening hours (if you want them shown)",
        example="Mon–Sat 9:00–18:00, Sun closed",
    ),
    _q(
        "social",
        "social_links",
        "Social links",
        help="Handles or full URLs — we'll normalise them.",
        example="instagram: @yourshop   ·   facebook: facebook.com/yourshop",
        networks=["instagram", "facebook", "whatsapp", "youtube", "linkedin"],
    ),
]


UNIVERSAL_QUESTIONS = ESSENTIAL_QUESTIONS + OPTIONAL_QUESTIONS


# --- type-specific question builders ----------------------------------------


def _repeatable(
    qid: str,
    label: str,
    item_label: str,
    fields: list[dict[str, Any]],
    *,
    help: str = "",
    max_items: int = 30,
) -> dict[str, Any]:
    return _q(
        qid,
        "repeatable",
        label,
        help=help or "Add as many or as few as you like. Every field is a suggestion.",
        item_label=item_label,
        max_items=max_items,
        fields=fields,
    )


def _f(fid: str, label: str, example: str, *, kind: str = "text", optional: bool = True) -> dict[str, Any]:
    return {"id": fid, "kind": kind, "label": label, "example": example, "optional": optional}


_MENU_ITEMS = _repeatable(
    "menu_items",
    "Add a few menu items",
    "menu item",
    [
        _f("name", "Name", "Ragi dosa", optional=False),
        _f("description", "Description", "Stone-ground finger millet, crisp, served with three chutneys"),
        _f("health_benefits", "Health benefits", "High fibre, naturally gluten-free"),
        _f("dietary_tags", "Dietary tags", "vegan, gluten-free, nut-free"),
        _f("spice_level", "Spice level", "mild / medium / hot"),
        _f("serving_size", "Serving size", "Serves 1 · 2 pieces"),
    ],
)

_SERVICES = _repeatable(
    "services",
    "Add a few services",
    "service",
    [
        _f("name", "Name", "Cut & finish", optional=False),
        _f("description", "Description", "Consultation, wash, precision cut, and style"),
        _f("duration_hint", "Roughly how long", "About 45 minutes"),
        _f("differentiator", "What makes yours different", "We only use sulphate-free products"),
    ],
)

_PRODUCTS = _repeatable(
    "products",
    "Add a few products",
    "product",
    [
        _f("name", "Name", "Linen throw", optional=False),
        _f("description", "Description", "Stonewashed pure linen, 130 × 170 cm"),
        _f("materials_care", "Materials & care", "100% linen · cold wash · line dry"),
    ],
)

_CLINICAL_SERVICES = _repeatable(
    "services",
    "Add a few services",
    "service",
    [
        _f("name", "Name", "Initial consultation", optional=False),
        _f("description", "Description", "A full assessment and a written plan you take home"),
        _f("what_to_expect", "What to expect", "45 minutes, no referral needed, bring past reports"),
    ],
)

_ROOMS = _repeatable(
    "rooms",
    "Add your room types",
    "room type",
    [
        _f("name", "Name", "Garden room", optional=False),
        _f("description", "Description", "Queen bed, private veranda facing the garden, sleeps 2"),
        _f("occupancy_hint", "Occupancy", "2 adults + 1 child"),
    ],
)

_CLASSES = _repeatable(
    "classes",
    "Add a few classes or plans",
    "class or plan",
    [
        _f("name", "Name", "Beginners' pottery — 6 weeks", optional=False),
        _f("description", "Description", "Hand-building and the wheel, all materials included, max 8 people"),
        _f("schedule_hint", "When it runs", "Tuesdays 18:30–20:30"),
    ],
)

_TYPE_SPECIFIC: dict[str, dict[str, Any]] = {
    "restaurant": {"title": "Your menu", "questions": [_MENU_ITEMS]},
    "cafe": {"title": "Your menu", "questions": [_MENU_ITEMS]},
    "salon": {"title": "Your services", "questions": [_SERVICES]},
    "spa": {"title": "Your treatments", "questions": [_SERVICES]},
    "retail": {"title": "Your products", "questions": [_PRODUCTS]},
    "clinic": {"title": "Your services", "questions": [_CLINICAL_SERVICES]},
    "professional_service": {"title": "Your services", "questions": [_CLINICAL_SERVICES]},
    "hotel": {"title": "Your rooms", "questions": [_ROOMS]},
    "homestay": {"title": "Your rooms", "questions": [_ROOMS]},
    "gym": {"title": "Your classes & plans", "questions": [_CLASSES]},
    "studio": {"title": "Your classes", "questions": [_CLASSES]},
    "education": {"title": "Your courses", "questions": [_CLASSES]},
    # other / not_sure: universal questions only
}

_REPEATABLE_KEYS = {"menu_items", "services", "products", "rooms", "classes"}


def get_questionnaire(business_type: str | None) -> dict[str, Any]:
    """Return the full question schema for a business type (universal + specific)."""
    btype = (business_type or "not_sure").strip().lower()
    if btype not in SUPPORTED_BUSINESS_TYPES:
        btype = "not_sure"
    sections: list[dict[str, Any]] = []
    specific = _TYPE_SPECIFIC.get(btype)
    if specific:
        sections.append(
            {
                "id": "type_specific",
                "title": specific["title"],
                "subtitle": "Optional, but this is what makes the site yours. Skip anything you would rather add later.",
                "questions": specific["questions"],
            }
        )
    sections.append(
        {
            "id": "essentials",
            "title": "Look and feel",
            "subtitle": "Optional. Skip anything and we'll fill it in from your business details.",
            "questions": ESSENTIAL_QUESTIONS,
        }
    )
    sections.append(
        {
            "id": "optional",
            "title": "More detail",
            "subtitle": "Skip this entire section if you like — it only refines voice and contact.",
            "collapsed": True,
            "questions": OPTIONAL_QUESTIONS,
        }
    )
    return {
        "version": QUESTIONNAIRE_VERSION,
        "business_type": btype,
        "sections": sections,
    }


# --- answer validation -------------------------------------------------------

_MAX_TEXT = 500
_MAX_REPEATABLE = 30


def validate_intake(business_type: str | None, answers: Any) -> dict[str, Any]:
    """Sanity-check + clamp questionnaire answers. Not a schema engine — the
    real guarantee is `validate_generation_payload` on the generated draft."""
    if answers is None:
        return {}
    if not isinstance(answers, dict):
        raise ValueError("intake answers must be an object")

    cleaned: dict[str, Any] = {}
    for key, value in answers.items():
        if not isinstance(key, str) or len(key) > 64:
            raise ValueError("invalid intake field name")
        if value in (None, "", [], {}):
            continue
        if key in _REPEATABLE_KEYS:
            if not isinstance(value, list):
                raise ValueError(f"{key} must be a list")
            items: list[dict[str, Any]] = []
            for row in value[:_MAX_REPEATABLE]:
                if not isinstance(row, dict):
                    raise ValueError(f"{key} items must be objects")
                row_clean = {
                    str(k)[:64]: str(v).strip()[:_MAX_TEXT]
                    for k, v in row.items()
                    if v not in (None, "")
                }
                if row_clean:
                    items.append(row_clean)
            if items:
                cleaned[key] = items
            continue
        if isinstance(value, str):
            cleaned[key] = value.strip()[:_MAX_TEXT]
        elif isinstance(value, (int, float, bool)):
            cleaned[key] = value
        elif isinstance(value, dict):
            cleaned[key] = {
                str(k)[:64]: (str(v).strip()[:_MAX_TEXT] if isinstance(v, str) else v)
                for k, v in value.items()
                if v not in (None, "")
            }
        elif isinstance(value, list):
            cleaned[key] = [str(v).strip()[:_MAX_TEXT] for v in value if isinstance(v, str)]
        # anything else: dropped

    # Same content-safety bar as generated content — no markup, no external URLs
    # smuggled through an answer (social handles are normalised separately, not here).
    for key, value in cleaned.items():
        if key == "social":
            continue
        assert_no_unsafe_content(value, path=f"intake.{key}")
    return cleaned


# --- prompt assembly --------------------------------------------------------


def _pairs_to_words(tone: dict[str, Any]) -> list[str]:
    out: list[str] = []
    labels = {
        "warm_minimal": ("warm and personable", "spare and minimal"),
        "playful_serious": ("playful", "serious and precise"),
        "modern_classic": ("modern", "classic and traditional"),
        "bold_understated": ("bold and confident", "quiet and understated"),
    }
    for pid, (low, high) in labels.items():
        v = tone.get(pid)
        if not isinstance(v, (int, float)):
            continue
        if v <= 35:
            out.append(low)
        elif v >= 65:
            out.append(high)
    return out


def build_intake_brief(context: dict[str, Any], intake: dict[str, Any] | None) -> str:
    """Human-readable brief appended to the generation prompt. Only answered
    fields appear — a skipped questionnaire produces an empty brief."""
    if not intake:
        return ""
    lines: list[str] = []

    if intake.get("lead_with"):
        lines.append(f"- Lead the home page with: {intake['lead_with']}.")
    tone_words = _pairs_to_words(intake.get("tone") or {})
    if tone_words:
        lines.append(f"- Voice: {', '.join(tone_words)}.")
    if intake.get("palette"):
        preset = PALETTE_PRESETS.get(str(intake["palette"]))
        if preset:
            lines.append(
                f"- Colour direction: {preset['label']} "
                f"(primary {preset['primary']}, accent {preset['accent']})."
            )
    if intake.get("words_prefer"):
        lines.append(f"- Prefer these words/phrases where natural: {intake['words_prefer']}.")
    if intake.get("words_avoid"):
        lines.append(f"- Do NOT use these words: {intake['words_avoid']}.")
    cd = intake.get("contact_display") or {}
    if cd:
        shown = [k.replace("show_", "") for k, v in cd.items() if v]
        hidden = [k.replace("show_", "") for k, v in cd.items() if not v]
        if shown:
            lines.append(f"- Contact section shows: {', '.join(shown)}.")
        if hidden:
            lines.append(f"- Contact section hides: {', '.join(hidden)}.")
    if intake.get("hours"):
        lines.append(f"- Opening hours: {intake['hours']}.")

    for key, heading in (
        ("menu_items", "Menu items"),
        ("services", "Services"),
        ("products", "Products"),
        ("rooms", "Room types"),
        ("classes", "Classes / plans"),
    ):
        rows = intake.get(key)
        if not rows:
            continue
        lines.append(f"- {heading} to feature (write these up in the business's voice):")
        for row in rows:
            parts = [f"{k}: {v}" for k, v in row.items()]
            lines.append(f"    * {'; '.join(parts)}")

    if not lines:
        return ""
    return (
        "\n\nThe owner answered an intake form. Honour every answer below. "
        "Anything not mentioned, choose a sensible default:\n" + "\n".join(lines)
    )
