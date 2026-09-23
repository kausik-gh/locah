"""The creative composer: one system, four very different websites.

No network. Blueprints are built the way the interview builds them (facts,
answers, the owner's catalogue); pictures come from a fake drawer. What is
checked is the design decision — archetype, reference profile, which sections
exist and in what shape — and the truth rules: no vague items, no generic
"What we do" for things people buy, chips only from the owner's answers, no
cart language anywhere in the content.
"""

from __future__ import annotations

import json
from uuid import uuid4

import pytest

from platform_core.interview.creative_director import (
    PROFILES_FOR,
    CreativeChoices,
    contrast,
    derive_archetype,
    direct,
)
from platform_core.interview.media_director import draw_missing, picture_for, plan_slots, record
from platform_core.interview.models import (
    BusinessBlueprint,
    CatalogueGroup,
    CatalogueItem,
    Fact,
    OwnerClaim,
    PatternEvidence,
    TargetState,
)
from platform_core.interview.site_composer import compose_site
from platform_core.interview.website import with_draft
from platform_core.interview.website_copy import NamedLine, WebsiteCopy
from platform_core.website.image_generation import GeneratedImage

ACTIVE = frozenset({"offerings-catalog", "orders", "payments", "inventory", "fulfilment"})


def _bp(name: str, facts: dict[str, str], patterns: list[tuple[str, str]],
        answers: dict[str, tuple[str, str]], groups: list[CatalogueGroup]) -> BusinessBlueprint:
    bp = BusinessBlueprint(
        business_id=uuid4(),
        identity={"display_name": Fact(value=name, source="PLATFORM", confirmation="confirmed")},
    )
    bp.known_facts = {k: Fact(value=v, source="USER_STATEMENT", confirmation="confirmed") for k, v in facts.items()}
    bp.operating_patterns = [PatternEvidence(pattern=p, quote=q) for p, q in patterns]  # type: ignore[arg-type]
    for target, (summary, quote) in answers.items():
        bp.discovery[target] = TargetState(status="answered", summary=summary, quote=quote)
    bp.taxonomy.groups = groups
    return bp


def meat() -> BusinessBlueprint:
    bp = _bp(
        "Ishant Proteins",
        {"offerings": "chicken, mutton, fish, crab and squid", "locations": "In nookampalayam road",
         "phone": "8754722026", "customer_actions": "People select the meat and kg and order"},
        [("product_led", "We sell chicken"), ("order_led", "and order"), ("local_delivery", "We deliver"),
         ("pickup", "people can pick up too")],
        {"offerings.units": ("Sold by weight.", "select the meat and kg"),
         "fulfilment.mode": ("You deliver and offer pickup.", "We deliver ourselves, people can pick up too"),
         "fulfilment.area": ("Nookampalayam and Perumbakkam", "around Nookampalayam and Perumbakkam"),
         "commerce.payment": ("Online and cash on delivery.", "Both online and cash on delivery")},
        [CatalogueGroup(name="Chicken", items=[CatalogueItem(name="Whole chicken"), CatalogueItem(name="Curry cut"),
                                               CatalogueItem(name="Boneless")], price="₹240", unit="per kg"),
         CatalogueGroup(name="Mutton", items=[CatalogueItem(name="Curry cut"), CatalogueItem(name="Chops")]),
         CatalogueGroup(name="Fish & Seafood", label_source="ai_suggestion",
                        items=[CatalogueItem(name="Seer fish"), CatalogueItem(name="Pomfret"),
                               CatalogueItem(name="Fish different varieties"), CatalogueItem(name="Crab"),
                               CatalogueItem(name="Squid")])],
    )
    bp.website_draft.owner_claims = [OwnerClaim(claim="Fresh meat from the farm to your house",
                                                quote="we sell fresh meat from farm to ur house")]
    return bp


def home_food() -> BusinessBlueprint:
    return _bp(
        "Amma's Pantry",
        {"offerings": "thokku, podi and pickles", "locations": "Mylapore, Chennai", "phone": "9840012345",
         "customer_actions": "Customers choose jars and order on WhatsApp"},
        [("product_led", "We make thokku"), ("order_led", "order on WhatsApp"), ("local_delivery", "we deliver")],
        {"fulfilment.mode": ("You deliver.", "we deliver in Chennai"),
         "commerce.payment": ("UPI or cash.", "UPI or cash")},
        [CatalogueGroup(name="Thokku", items=[CatalogueItem(name="Vazhaipoo thokku", price="₹250", unit="250g"),
                                              CatalogueItem(name="Nellikai poondu thokku", price="₹250", unit="250g")]),
         CatalogueGroup(name="Podi", items=[CatalogueItem(name="Idli podi", price="₹180", unit="200g")]),
         CatalogueGroup(name="Pickles", items=[CatalogueItem(name="Mango pickle", price="₹220", unit="250g")])],
    )


def gym() -> BusinessBlueprint:
    return _bp(
        "Iron Temple Fitness",
        {"offerings": "monthly memberships, strength classes and personal training", "locations": "Velachery",
         "phone": "9000044321"},
        [("membership_led", "monthly memberships"), ("runs_classes", "strength classes")],
        {},
        [CatalogueGroup(name="Memberships", items=[CatalogueItem(name="Monthly membership", price="₹2500",
                                                                 unit="per month")]),
         CatalogueGroup(name="Classes", items=[CatalogueItem(name="Strength classes")]),
         CatalogueGroup(name="Personal training")],
    )


def real_estate() -> BusinessBlueprint:
    return _bp(
        "SkyNest Homes",
        {"offerings": "villa projects and apartments in OMR", "locations": "OMR, Chennai", "phone": "9840098400",
         "customer_actions": "Buyers call us to book a site visit"},
        [("lead_generation", "call us")],
        {},
        [CatalogueGroup(name="Villa projects", items=[CatalogueItem(name="Palm Grove Villas"),
                                                      CatalogueItem(name="Lake View Residency")]),
         CatalogueGroup(name="Apartments", items=[CatalogueItem(name="Skyline Towers")])],
    )


def compose(bp: BusinessBlueprint, copy: WebsiteCopy | None = None, contact: dict | None = None) -> dict:
    return compose_site(bp, direct(bp, "other"), with_draft(bp, copy), business_type="other",
                        contact=contact or {"phone": "+91" + bp.known_facts["phone"].value},
                        active_modules=ACTIVE)


def sections(payload: dict) -> dict[str, dict]:
    return {s["section_type_id"]: s for s in payload["pages"][0]["sections"]}


def test_four_businesses_get_four_different_websites():
    looks = {}
    for build, arche, profile in (
        (meat, "product_commerce", "bold_food_commerce"),
        (home_food, "menu_commerce", "editorial_home_food"),
        (gym, "membership_fitness", "cinematic_fitness"),
        (real_estate, "real_estate_projects", "airy_real_estate"),
    ):
        bp = build()
        assert derive_archetype(bp, "other") == arche
        payload = compose(bp)
        theme = payload["theme_hints"]
        assert theme["reference_profile"] == profile
        assert theme["quality"]["valid"], theme["quality"]["issues"]
        looks[arche] = (theme["hero_style"], theme["type_system"], theme["palette_mode"],
                        sections(payload)["hero"]["layout_variant"])
    # Not one site in four colours: hero, type and ground all differ.
    assert len({v[0] for v in looks.values()}) == 4
    assert len({v[1] for v in looks.values()}) == 4


def test_the_meat_shop_is_a_shop():
    payload = compose(meat())
    found = sections(payload)
    hero = found["hero"]
    assert hero["layout_variant"] == "commerce_split"
    assert hero["content"]["eyebrow"] == "Nookampalayam Road"
    assert hero["content"]["badges"] == ["Sold by the kg", "Home delivery", "Store pickup"]
    assert hero["content"]["cta_url"] == "#shop"
    shop = found["product_showcase"]
    assert shop["layout_variant"] == "category_boards"
    assert shop["content"]["title"] == "Shop by category"
    names = [i["name"] for i in shop["content"]["items"]]
    assert "Fish different varieties" not in names and "Seer fish" in names
    chicken = next(c for c in shop["content"]["categories"] if c["name"] == "Chicken")
    assert chicken["meta"] == "From ₹240 per kg"
    assert shop["content"]["order_label"] == "Call to order"  # no WhatsApp was mentioned
    strip = found["fulfilment_strip"]["content"]["items"]
    assert [i["kind"] for i in strip] == ["weight", "delivery", "pickup", "payment"]
    assert strip[1]["body"] == "Delivered around Nookampalayam and Perumbakkam."
    assert [n["path"] for n in payload["navigation"]] == ["/", "/#shop", "/#contact"]
    text = json.dumps(payload).lower()
    assert "what we do" not in text and "add to cart" not in text and "cart" not in text


def test_a_generic_heading_from_the_model_is_replaced_for_a_shop():
    copy = WebsiteCopy(headline="Meat, by the kilo.", products_title="What we do",
                       category_lines=[NamedLine(name="Chicken", line="Everyday cuts for curries.")])
    shop = sections(compose(meat(), copy))["product_showcase"]
    assert shop["content"]["title"] == "Shop by category"


def test_the_owner_story_becomes_a_story_with_their_line():
    bp = meat()
    copy = WebsiteCopy(about_title="From the farm to your home",
                       about_body="Ishant Proteins brings fresh meat from the farm to your house.")
    story = sections(compose(bp, copy))["about"]
    assert story["content"]["quote"] == "Fresh meat from the farm to your house"
    assert story["content"]["anchor"] == "story"


def test_home_food_shows_a_priced_menu():
    shop = sections(compose(home_food()))["product_showcase"]
    menu = {i["name"]: i for i in shop["content"]["items"]}
    assert menu["Vazhaipoo thokku"]["price"] == "₹250" and menu["Vazhaipoo thokku"]["unit"] == "250g"
    assert shop["content"]["filters"] == ["Thokku", "Podi", "Pickles"]
    assert shop["content"]["title"] == "Our menu"


def test_whatsapp_only_when_the_owner_said_it():
    shop = sections(compose(home_food(), contact={"phone": "+919840012345", "whatsapp": "+919840012345"}))
    assert shop["product_showcase"]["content"]["order_label"] == "Order on WhatsApp"


def test_the_palette_keeps_buttons_readable():
    bp = meat()
    for colour in ("#1a1a1a", "#222222"):  # would vanish on the charcoal ground
        direction = direct(bp, "other", CreativeChoices(reference_profile="bold_food_commerce",
                                                        primary_color=colour))
        assert contrast(direction.palette.primary, direction.palette.surface) >= 3.0
        assert "primary_contrast" in direction.repairs
    wrong = direct(bp, "other", CreativeChoices(reference_profile="cinematic_fitness"))
    assert wrong.reference_profile in PROFILES_FOR["product_commerce"]


PNG = GeneratedImage(mime_type="image/png", bytes=b"png", model="m", latency_ms=1, prompt="p")


@pytest.mark.asyncio
async def test_draft_visuals_need_consent_and_are_drawn_once():
    bp = meat()
    direction = direct(bp, "other")
    calls: list[str] = []

    async def draw(prompt: str, aspect: str):
        calls.append(prompt)
        return PNG, ""

    assert await draw_missing(bp, direction, "a meat shop", draw=draw) == []  # no consent, no spend
    bp.visual_consent = "draft_visuals"
    drawn = await draw_missing(bp, direction, "a meat shop", draw=draw)
    assert [s.key for s, _, _ in drawn] == ["hero", "category:chicken", "category:mutton",
                                           "category:fish-seafood"]
    assert all("No text" in p and "people" in p for p in calls)
    assert all("farm" not in p.lower() and "240" not in p for p in calls)
    for slot, _, _ in drawn:
        record(bp, slot, uuid4())
    assert await draw_missing(bp, direction, "a meat shop", draw=draw) == []  # cached
    payload = compose(bp)
    found = sections(payload)
    assert found["hero"]["content"]["image_asset_id"] == picture_for(bp, "hero")
    boards = found["product_showcase"]["content"]["categories"]
    assert all(c.get("image_asset_id") for c in boards)
    assert all(m.source == "AI_GENERATED" and m.label.startswith("Draft visual") for m in bp.media_assets)


def test_media_budget_follows_the_archetype():
    for build, count in ((meat, 4), (home_food, 5), (gym, 1), (real_estate, 4)):
        bp = build()
        assert len(plan_slots(bp, direct(bp, "other"))) == count, build.__name__
