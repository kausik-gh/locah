"""Website templates: a named, previewable starting composition.

Why templates exist
-------------------
Generation was previously the only way to get a website, which means every
business waited on a model call to see anything at all, and a business that
knew exactly what it wanted still had to describe it. A template is the other
door: pick one, get a real site immediately, edit it, never touch the AI.

It is also what makes generation better. A template is a *reference* the model
personalises rather than a blank page it invents from — which is the difference
between "a website for a gym" and "this gym's website".

What a template is, precisely
-----------------------------
A composition, not a design file. Pages, the sections on them in order, the
variant each one uses, and a theme. Every section id and variant here must exist
in `website_section_types`, and that is asserted by the tests — a template can
only ever describe something the renderer already knows how to draw.

The visual difference between templates comes from three things working
together: the personality (which changes radius, type and section rhythm, not
just hue), the palette, and the *composition* — what leads, what follows, how
much the page asks of the reader. A gym opening on a full-bleed hero with a
plans comparison is a different product from a consultancy opening on a
left-aligned statement with a story.

Capability
----------
`required_modules` is what the template genuinely needs to be worth choosing —
a Menu-led restaurant template is pointless without an offerings catalogue.
Templates whose modules are off are still returned, marked unavailable with the
module named, so the owner can see what turning it on would give them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

TEMPLATE_VERSION = "1.0"


@dataclass(frozen=True)
class TemplateSection:
    """One section in a template's composition."""

    section_type_id: str
    layout_variant: str | None = None
    # Copy is a starting point the owner rewrites; it is written to sound like a
    # real business rather than like filler, because "Lorem ipsum" in a live
    # website is worse than nothing.
    content: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TemplatePage:
    slug: str
    title: str
    page_type: str
    sections: tuple[TemplateSection, ...]


@dataclass(frozen=True)
class WebsiteTemplate:
    id: str
    name: str
    tagline: str
    description: str
    # Which business types this suits. Ranking, not restriction — any business
    # may choose any template, because a caterer might genuinely want the
    # editorial one.
    suits: tuple[str, ...]
    personality: str
    primary_color: str
    accent_color: str
    pages: tuple[TemplatePage, ...]
    required_modules: tuple[str, ...] = ()
    # Two or three words describing the look, for the picker.
    look: tuple[str, ...] = ()

    def serialize(self, *, available: bool = True, missing: tuple[str, ...] = ()) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "tagline": self.tagline,
            "description": self.description,
            "suits": list(self.suits),
            "personality": self.personality,
            "primary_color": self.primary_color,
            "accent_color": self.accent_color,
            "look": list(self.look),
            "required_modules": list(self.required_modules),
            "available": available,
            "missing_modules": list(missing),
            "page_count": len(self.pages),
            "section_count": sum(len(p.sections) for p in self.pages),
            "pages": [
                {
                    "slug": p.slug,
                    "title": p.title,
                    "sections": [s.section_type_id for s in p.sections],
                }
                for p in self.pages
            ],
        }


def _contact(title: str = "Find us") -> TemplateSection:
    return TemplateSection("contact", "full", {"title": title, "show_map": True})


def _about(variant: str, title: str, body: str) -> TemplateSection:
    return TemplateSection("about", variant, {"title": title, "body": body})


_TEMPLATES: tuple[WebsiteTemplate, ...] = (
    # ---------------------------------------------------------------- food
    WebsiteTemplate(
        id="menu-first",
        name="Menu First",
        tagline="The food leads. Everything else follows.",
        description=(
            "Opens straight onto what you serve, with the menu categorised and "
            "priced. Built for somewhere people already know they want to eat."
        ),
        suits=("restaurant", "cafe"),
        personality="warm",
        primary_color="#8A3A1E",
        accent_color="#C9762F",
        look=("warm", "appetising", "direct"),
        required_modules=("offerings-catalog",),
        pages=(
            TemplatePage(
                "home",
                "Home",
                "home",
                (
                    TemplateSection("hero", "full_width", {"headline": "", "cta_label": "See the menu"}),
                    TemplateSection("menu_section", "categorized", {"title": "What we serve", "show_prices": True}),
                    _about("image_right", "Our kitchen", ""),
                    TemplateSection("gallery", "masonry", {"title": "Inside"}),
                    _contact("Come and eat"),
                ),
            ),
            TemplatePage(
                "menu",
                "Menu",
                "menu",
                (TemplateSection("menu_section", "categorized", {"title": "Menu", "show_prices": True}),),
            ),
        ),
    ),
    # ----------------------------------------------------------- editorial
    WebsiteTemplate(
        id="quiet-authority",
        name="Quiet Authority",
        tagline="Space, type, and a clear argument.",
        description=(
            "A restrained editorial layout for work that sells on judgement "
            "rather than volume. Generous whitespace, a single strong statement, "
            "services stated plainly."
        ),
        suits=("professional_service", "clinic", "studio"),
        personality="premium",
        primary_color="#17457A",
        accent_color="#4A90A4",
        look=("restrained", "editorial", "confident"),
        pages=(
            TemplatePage(
                "home",
                "Home",
                "home",
                (
                    TemplateSection("hero", "left_aligned", {"headline": "", "cta_label": "Start a conversation"}),
                    _about("text_only", "What we do", ""),
                    TemplateSection("offerings_list", "list", {"title": "How we help"}),
                    TemplateSection("text_block", "highlighted", {"title": "How we work", "body": ""}),
                    TemplateSection("cta_band", "left_aligned", {"headline": "", "cta_label": "Get in touch"}),
                    _contact(),
                ),
            ),
            TemplatePage(
                "services",
                "Services",
                "services",
                (
                    TemplateSection("offerings_list", "list", {"title": "Services"}),
                    TemplateSection("enquiry_form", "default", {"title": "Tell us what you need"}),
                ),
            ),
        ),
    ),
    # ---------------------------------------------------------------- bold
    WebsiteTemplate(
        id="momentum",
        name="Momentum",
        tagline="High contrast, plans up front, one obvious next step.",
        description=(
            "Built to convert. A full-bleed opening, membership plans compared "
            "side by side, and a single repeated call to action."
        ),
        suits=("gym", "studio"),
        personality="bold",
        primary_color="#15161A",
        accent_color="#D64933",
        look=("high-contrast", "energetic", "direct"),
        pages=(
            TemplatePage(
                "home",
                "Home",
                "home",
                (
                    TemplateSection("hero", "full_width", {"headline": "", "cta_label": "See plans"}),
                    TemplateSection("plans_section", "comparison", {"title": "Memberships"}),
                    TemplateSection("classes_section", "schedule", {"title": "Timetable"}),
                    _about("image_left", "The place", ""),
                    TemplateSection("cta_band", "centered", {"headline": "", "cta_label": "Join"}),
                    _contact(),
                ),
            ),
        ),
    ),
    # -------------------------------------------------------------- stay
    WebsiteTemplate(
        id="long-view",
        name="Long View",
        tagline="Photography first, rooms second, everything unhurried.",
        description=(
            "For places people choose with their eyes. Large imagery, calm "
            "pacing, rooms presented as rooms rather than as inventory."
        ),
        suits=("hotel", "homestay", "spa"),
        personality="premium",
        primary_color="#2C4A52",
        accent_color="#C2A878",
        look=("photographic", "calm", "spacious"),
        pages=(
            TemplatePage(
                "home",
                "Home",
                "home",
                (
                    TemplateSection("hero", "full_width", {"headline": "", "cta_label": "Check availability"}),
                    _about("text_only", "The place", ""),
                    TemplateSection("rooms_section", "cards", {"title": "Rooms"}),
                    TemplateSection("gallery", "grid", {"title": "Around the property"}),
                    _contact("Getting here"),
                ),
            ),
            TemplatePage(
                "rooms",
                "Rooms",
                "offerings",
                (TemplateSection("rooms_section", "list", {"title": "Rooms"}),),
            ),
        ),
    ),
    # ------------------------------------------------------------- retail
    WebsiteTemplate(
        id="shopfront",
        name="Shopfront",
        tagline="Products in a grid, found fast.",
        description=(
            "A clean catalogue layout for businesses with things to sell. "
            "Products lead; the story sits underneath where it belongs."
        ),
        suits=("retail",),
        personality="clean",
        primary_color="#20304A",
        accent_color="#D98A3C",
        look=("clean", "gridded", "practical"),
        required_modules=("offerings-catalog",),
        pages=(
            TemplatePage(
                "home",
                "Home",
                "home",
                (
                    TemplateSection("hero", "image_right", {"headline": "", "cta_label": "Browse"}),
                    TemplateSection("offerings_list", "grid", {"title": "What we stock"}),
                    _about("image_left", "About us", ""),
                    _contact(),
                ),
            ),
            TemplatePage(
                "products",
                "Products",
                "offerings",
                (TemplateSection("offerings_list", "grid", {"title": "Everything"}),),
            ),
        ),
    ),
    # ---------------------------------------------------------- appointment
    WebsiteTemplate(
        id="by-appointment",
        name="By Appointment",
        tagline="Services, the people who do them, and a way to book.",
        description=(
            "For work done one customer at a time. Services priced openly, the "
            "room shown honestly, and booking never more than one tap away."
        ),
        suits=("salon", "spa", "clinic"),
        personality="premium",
        primary_color="#1F3D34",
        accent_color="#B08D57",
        look=("polished", "personal", "calm"),
        pages=(
            TemplatePage(
                "home",
                "Home",
                "home",
                (
                    TemplateSection("hero", "image_left", {"headline": "", "cta_label": "Book"}),
                    TemplateSection("offerings_list", "cards", {"title": "Treatments"}),
                    _about("text_only", "About", ""),
                    TemplateSection("gallery", "carousel", {"title": "The room"}),
                    TemplateSection("cta_band", "centered", {"headline": "", "cta_label": "Book a time"}),
                    _contact(),
                ),
            ),
            TemplatePage(
                "services",
                "Services",
                "services",
                (TemplateSection("offerings_list", "list", {"title": "Every treatment"}),),
            ),
        ),
    ),
    # -------------------------------------------------------------- classes
    WebsiteTemplate(
        id="term-time",
        name="Term Time",
        tagline="Courses, schedules and enrolment, clearly laid out.",
        description=(
            "For teaching. What is taught, when it runs, and how to enrol — in "
            "that order, without making a parent hunt."
        ),
        suits=("education",),
        personality="clean",
        primary_color="#0F766E",
        accent_color="#F59E0B",
        look=("clear", "organised", "reassuring"),
        pages=(
            TemplatePage(
                "home",
                "Home",
                "home",
                (
                    TemplateSection("hero", "centered", {"headline": "", "cta_label": "See courses"}),
                    TemplateSection("classes_section", "cards", {"title": "What we teach"}),
                    _about("image_right", "Our approach", ""),
                    TemplateSection("enquiry_form", "default", {"title": "Ask about enrolment"}),
                    _contact(),
                ),
            ),
            TemplatePage(
                "courses",
                "Courses",
                "offerings",
                (TemplateSection("classes_section", "schedule", {"title": "Timetable"}),),
            ),
        ),
    ),
    # -------------------------------------------------------------- neutral
    WebsiteTemplate(
        id="plain-and-good",
        name="Plain and Good",
        tagline="Everything a business needs, nothing it does not.",
        description=(
            "The dependable one. Works for any business, says what you do, "
            "shows what you offer, and tells people how to reach you."
        ),
        suits=("other", "not_sure"),
        personality="clean",
        primary_color="#0F766E",
        accent_color="#F59E0B",
        look=("simple", "dependable", "quick"),
        pages=(
            TemplatePage(
                "home",
                "Home",
                "home",
                (
                    TemplateSection("hero", "centered", {"headline": "", "cta_label": "Get in touch"}),
                    _about("text_only", "About us", ""),
                    TemplateSection("offerings_list", "cards", {"title": "What we offer"}),
                    _contact(),
                ),
            ),
        ),
    ),
)

TEMPLATES_BY_ID: dict[str, WebsiteTemplate] = {t.id: t for t in _TEMPLATES}
ALL_TEMPLATE_IDS = frozenset(TEMPLATES_BY_ID)

# Where a business type has no template naming it, this is what it gets. It is
# never a failure state — "Plain and Good" is a genuinely fine website.
DEFAULT_TEMPLATE_ID = "plain-and-good"


def templates_for_business_type(business_type: str | None) -> list[WebsiteTemplate]:
    """Every template, with the ones suited to this business type first.

    All of them are returned rather than only the matching ones: a caterer may
    legitimately want the editorial layout, and hiding it would be the system
    deciding taste on the owner's behalf.
    """
    btype = (business_type or "").strip().lower()
    suited = [t for t in _TEMPLATES if btype and btype in t.suits]
    rest = [t for t in _TEMPLATES if t not in suited]
    return suited + rest


def default_template_for_business_type(business_type: str | None) -> WebsiteTemplate:
    ranked = templates_for_business_type(business_type)
    btype = (business_type or "").strip().lower()
    for template in ranked:
        if btype and btype in template.suits:
            return template
    return TEMPLATES_BY_ID[DEFAULT_TEMPLATE_ID]


def template_to_generation_payload(
    template: WebsiteTemplate,
    *,
    business_name: str,
    description: str | None = None,
) -> dict[str, Any]:
    """Render a template into the same payload shape generation produces.

    Deliberately the same shape, so a template goes through exactly the
    validation, draft-replacement and versioning that a generated site does.
    There is one website pipeline, entered two ways.

    Empty copy is filled from what the business actually told us. Nothing is
    invented: where there is no description, the section simply carries less
    text rather than plausible-sounding fiction.
    """
    pages: list[dict[str, Any]] = []
    for page in template.pages:
        sections: list[dict[str, Any]] = []
        for section in page.sections:
            content = dict(section.content)
            if section.section_type_id == "hero" and not content.get("headline"):
                content["headline"] = business_name
                if description:
                    content["subheadline"] = description[:300]
            if section.section_type_id == "about" and not content.get("body"):
                content["body"] = description or f"{business_name}."
            if section.section_type_id == "text_block" and not content.get("body"):
                content["body"] = description or f"More about {business_name}."
            if section.section_type_id == "cta_band" and not content.get("headline"):
                content["headline"] = f"Work with {business_name}"
            sections.append(
                {
                    "section_type_id": section.section_type_id,
                    "layout_variant": section.layout_variant,
                    "content": content,
                    "is_visible": True,
                }
            )
        pages.append(
            {
                "slug": page.slug,
                "title": page.title,
                "page_type": page.page_type,
                "seo_title": f"{page.title} | {business_name}" if page.slug != "home" else business_name,
                "seo_description": (description or "")[:300] or None,
                "sections": sections,
            }
        )

    navigation = [
        {"label": page.title, "path": "/" if page.slug == "home" else f"/{page.slug}"}
        for page in template.pages
    ]

    return {
        "pages": pages,
        "navigation": navigation,
        "theme_hints": {
            "primary_color": template.primary_color,
            "accent_color": template.accent_color,
            "personality": template.personality,
            "template_id": template.id,
        },
    }
