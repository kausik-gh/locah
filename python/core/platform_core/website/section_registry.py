"""Platform-defined website section types (Doc 12 §11.1)."""

from __future__ import annotations

from typing import Any

# Minimal in-process schemas used when DB seed is unavailable (tests / bootstrap).
CORE_SECTION_SCHEMAS: dict[str, dict[str, Any]] = {
    "hero": {
        "type": "object",
        "required": ["headline"],
        "properties": {
            "headline": {"type": "string", "maxLength": 120},
            "subheadline": {"type": "string", "maxLength": 300},
            "cta_label": {"type": "string", "maxLength": 60},
            "cta_url": {"type": "string", "maxLength": 200},
            "image_asset_id": {"type": "string", "format": "uuid"},
        },
    },
    "about": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "maxLength": 120},
            "body": {"type": "string", "maxLength": 2000},
            "image_asset_id": {"type": "string", "format": "uuid"},
        },
    },
    "contact": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "maxLength": 120},
            "address": {"type": "string", "maxLength": 500},
            "phone": {"type": "string", "maxLength": 50},
            "email": {"type": "string", "maxLength": 200},
            "hours_summary": {"type": "string", "maxLength": 500},
            "show_map": {"type": "boolean"},
        },
    },
    "text_block": {
        "type": "object",
        "required": ["body"],
        "properties": {
            "title": {"type": "string", "maxLength": 120},
            "body": {"type": "string", "maxLength": 5000},
        },
    },
    "location_list": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "maxLength": 120},
            "show_hours": {"type": "boolean"},
            "show_map": {"type": "boolean"},
        },
    },
    "offerings_list": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "maxLength": 120},
            "subtitle": {"type": "string", "maxLength": 300},
            "offering_types": {"type": "array", "items": {"type": "string"}},
            "max_items": {"type": "integer", "minimum": 1, "maximum": 50},
        },
    },
    "cta_band": {
        "type": "object",
        "required": ["headline", "cta_label"],
        "properties": {
            "headline": {"type": "string", "maxLength": 200},
            "body": {"type": "string", "maxLength": 500},
            "cta_label": {"type": "string", "maxLength": 60},
            "cta_url": {"type": "string", "maxLength": 200},
        },
    },
}

ALLOWED_SECTION_TYPE_IDS = frozenset(CORE_SECTION_SCHEMAS.keys())

WEBSITE_GENERATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["pages", "navigation", "theme_hints"],
    "properties": {
        "pages": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["slug", "title", "page_type", "sections"],
                "properties": {
                    "slug": {"type": "string"},
                    "title": {"type": "string"},
                    "page_type": {"type": "string"},
                    "seo_title": {"type": "string"},
                    "seo_description": {"type": "string"},
                    "sections": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["section_type_id", "content"],
                            "properties": {
                                "section_type_id": {"type": "string"},
                                "layout_variant": {"type": "string"},
                                "content": {"type": "object"},
                                "module_binding": {"type": "object"},
                                "is_visible": {"type": "boolean"},
                            },
                        },
                    },
                },
            },
        },
        "navigation": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["label", "path"],
                "properties": {
                    "label": {"type": "string"},
                    "path": {"type": "string"},
                },
            },
        },
        "theme_hints": {"type": "object"},
    },
}

# Doc 12 §11.4 typical page sets by business type
PAGES_BY_BUSINESS_TYPE: dict[str, list[tuple[str, str, str]]] = {
    "restaurant": [
        ("home", "Home", "home"),
        ("menu", "Menu", "menu"),
        ("about", "About", "about"),
        ("contact", "Contact", "contact"),
    ],
    "cafe": [
        ("home", "Home", "home"),
        ("menu", "Menu", "menu"),
        ("about", "About", "about"),
        ("contact", "Contact", "contact"),
    ],
    "retail": [
        ("home", "Home", "home"),
        ("products", "Products", "offerings"),
        ("about", "About", "about"),
        ("contact", "Contact", "contact"),
    ],
    "salon": [
        ("home", "Home", "home"),
        ("services", "Services", "services"),
        ("about", "About", "about"),
        ("contact", "Contact", "contact"),
    ],
    "spa": [
        ("home", "Home", "home"),
        ("services", "Services", "services"),
        ("about", "About", "about"),
        ("contact", "Contact", "contact"),
    ],
    "hotel": [
        ("home", "Home", "home"),
        ("rooms", "Rooms", "rooms"),
        ("about", "About", "about"),
        ("contact", "Contact", "contact"),
    ],
    "homestay": [
        ("home", "Home", "home"),
        ("rooms", "Rooms", "rooms"),
        ("about", "About", "about"),
        ("contact", "Contact", "contact"),
    ],
    "gym": [
        ("home", "Home", "home"),
        ("plans", "Plans", "plans"),
        ("classes", "Classes", "classes"),
        ("about", "About", "about"),
        ("contact", "Contact", "contact"),
    ],
    "studio": [
        ("home", "Home", "home"),
        ("classes", "Classes", "classes"),
        ("about", "About", "about"),
        ("contact", "Contact", "contact"),
    ],
    "professional_service": [
        ("home", "Home", "home"),
        ("services", "Services", "services"),
        ("about", "About", "about"),
        ("contact", "Contact", "contact"),
        ("enquire", "Enquire", "enquire"),
    ],
    "education": [
        ("home", "Home", "home"),
        ("courses", "Courses", "offerings"),
        ("about", "About", "about"),
        ("contact", "Contact", "contact"),
    ],
}

DEFAULT_PAGES: list[tuple[str, str, str]] = [
    ("home", "Home", "home"),
    ("about", "About", "about"),
    ("contact", "Contact", "contact"),
]


# ---------------------------------------------------------------------------
# Prompt-side section catalogue for AI generation.
#
# WEBSITE_GENERATION_SCHEMA only describes the envelope (a section has a
# `section_type_id` and an opaque `content` object). Without the per-type field
# list, the model invents section types ("booking_section") and fields
# ("cta_primary_label"). This spec is the authoritative description handed to
# the model. Keep it in sync with `website_section_types` (seed 00_platform.sql)
# and the DB `page_type` CHECK constraint.
# ---------------------------------------------------------------------------

SECTION_CATALOGUE_PROMPT = """\
SECTION TYPES — use ONLY these `section_type_id` values, and inside each
section's `content` use ONLY the fields listed for that type. Do not invent
section types or content fields.

- hero: headline (REQUIRED), subheadline, cta_label, cta_url
    layout_variant: centered | left_aligned | image_left | image_right | full_width
- about: title, body
    layout_variant: text_only | image_left | image_right
- text_block: body (REQUIRED), title
    layout_variant: default | highlighted
- cta_band: headline (REQUIRED), cta_label (REQUIRED), body, cta_url
    layout_variant: centered | left_aligned
- contact: title, address, phone, email, hours_summary, show_map (boolean)
    layout_variant: full | compact
- enquiry_form: title, subtitle
    layout_variant: default | compact
- gallery: title
    layout_variant: grid | masonry | carousel
- offerings_list: title, subtitle, max_items (integer), offering_types (array of strings)
    layout_variant: cards | list | grid
- menu_section: title, show_prices (boolean), category_filter
    layout_variant: categorized | simple
- plans_section: title, subtitle
    layout_variant: cards | comparison
- rooms_section: title, subtitle
    layout_variant: cards | list
- classes_section: title, max_items (integer), show_upcoming_only (boolean)
    layout_variant: schedule | cards
- location_list: title, show_map (boolean), show_hours (boolean)
    layout_variant: cards | list

The list sections (offerings_list, menu_section, plans_section, rooms_section,
classes_section, location_list) render the business's own live records — write
only their title/subtitle, never the individual items. Do not include image
fields; images are added separately.

`page_type` must be exactly one of:
home, about, contact, locations, offerings, services, menu, rooms, plans,
classes, enquire, custom

`cta_url` and any path must be a relative path like "/contact" or "/services" —
never an absolute URL.
"""
