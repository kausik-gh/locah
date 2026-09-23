"""The website brief: what a designer would want to know, derived — never asked.

Built from the Blueprint on every turn and handed to website generation, so the
site is composed from what the conversation actually established — how
customers buy, what is sold and how, the story the owner wants told, the
wording the owner approved — rather than from a name, a type and a sentence.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from platform_core.interview.discovery import characteristics
from platform_core.interview.models import BusinessBlueprint


class BriefOffering(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    description: str = ""
    locked: bool = False  # the owner edited or approved it


class WebsiteBrief(BaseModel):
    model_config = ConfigDict(extra="forbid")
    primary_goal: str = ""  # order | book | enquire | quote | visit | call
    primary_cta: str = ""
    secondary_cta: str = ""
    offerings: list[BriefOffering] = Field(default_factory=list)
    sold_by: str = ""  # "by weight — customers choose the kg"
    fulfilment: str = ""
    payment: str = ""
    story: str = ""
    owner_claims: list[str] = Field(default_factory=list)
    tone: str = ""
    brand_direction: str = ""
    hero_headline: str = ""
    hero_subheadline: str = ""
    about: str = ""
    locked_fields: list[str] = Field(default_factory=list)
    media_state: str = ""
    section_priorities: list[str] = Field(default_factory=list)
    module_backed: list[str] = Field(default_factory=list)


_GOALS = (
    ("accepts_orders", "order", "Order now"),
    ("accepts_appointments", "book", "Book now"),
    ("quote_led", "quote", "Request a quote"),
    ("enquiry_led", "enquire", "Send an enquiry"),
    ("walk_in", "visit", "Visit us"),
)


def build_brief(bp: BusinessBlueprint, business_type: str | None = None) -> WebsiteBrief:
    chars = characteristics(bp, business_type)
    seen = {c for c, how in chars.items() if how == "observed"}
    facts = {**bp.known_facts, **bp.unconfirmed_facts}
    wd = bp.website_draft
    goal, cta = "call", "Call us"
    for characteristic, name, label in _GOALS:
        if characteristic in seen:
            goal, cta = name, label
            break
    if wd.cta_label:
        cta = wd.cta_label.text

    def summary(target: str) -> str:
        state = bp.discovery.get(target)
        return state.summary if state and state.status in {"answered", "partial"} else ""

    locked = [
        field for field in ("hero_headline", "hero_subheadline", "about", "cta_label")
        if getattr(wd, field) and getattr(wd, field).provenance in {"owner_edited", "owner_approved"}
    ]
    priorities = ["hero"]
    if wd.offerings or "offerings" in facts:
        priorities.append("offerings")
    if summary("brand.story") or wd.about:
        priorities.append("story")
    if goal in {"order", "book"}:
        priorities.append("how_it_works")
    priorities.append("contact")
    logo = "generated" if bp.logo_state == "generated" else (
        "uploaded" if any(m.role == "logo" for m in bp.media_assets) else
        "requested" if bp.logo_state == "generation_requested" else "none")
    return WebsiteBrief(
        primary_goal=goal,
        primary_cta=cta,
        secondary_cta="Call or WhatsApp" if "phone" in facts else "",
        offerings=[
            BriefOffering(
                name=o.name,
                description=o.description.text if o.description else "",
                locked=bool(o.description and o.description.provenance in {"owner_edited", "owner_approved"}),
            )
            for o in wd.offerings
        ],
        sold_by=summary("offerings.units"),
        fulfilment=" ".join(x for x in (summary("fulfilment.mode"), summary("fulfilment.area")) if x),
        payment=summary("commerce.payment"),
        story=summary("brand.story"),
        owner_claims=[c.claim for c in wd.owner_claims],
        tone=facts["tone"].value[:200] if "tone" in facts else "",
        brand_direction=facts["brand"].value[:200] if "brand" in facts else summary("brand.feel"),
        hero_headline=wd.hero_headline.text if wd.hero_headline else "",
        hero_subheadline=wd.hero_subheadline.text if wd.hero_subheadline else "",
        about=wd.about.text if wd.about else "",
        locked_fields=locked,
        media_state=f"logo: {logo}; photos: {sum(1 for m in bp.media_assets if m.role != 'logo')}",
        section_priorities=priorities,
        module_backed=[r.module_id for r in bp.recommended_modules if r.choice == "approved"],
    )
