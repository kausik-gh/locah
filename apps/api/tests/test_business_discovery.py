"""Business discovery: the conversation understands, then asks what still matters.

No network. Each model answer is a scripted `TurnIntelligence` of the kind
Gemini returns — including the bad ones (a generic re-ask, an invented claim,
no answer at all) — so what is tested is Locah's own discipline: what it keeps,
what it asks next, what it recommends and when it says it has enough.

The Ishant Proteins conversation is the one that failed on staging:
"We sell all types of meat" was answered with "What do people come to you
for?" — twice.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from platform_core.interview.capabilities import resolve_recommendations
from platform_core.interview.discovery import TARGETS_BY_ID, rank, readiness
from platform_core.interview.models import BusinessBlueprint, Fact, TargetState
from platform_core.interview.orchestrator import BusinessInterviewOrchestrator as Engine
from platform_core.interview.understanding import understanding

from test_business_interview import entitlements


class Model:
    """Scripted model: one answer per turn, and a record of what it was shown."""

    provider_name = "fixture"
    model_name = "fixture"
    last_usage = {"prompt_tokens": 1, "completion_tokens": 1}

    def __init__(self, *answers: dict) -> None:
        self.answers = list(answers)
        self.payloads: list[str] = []

    async def generate_structured(self, prompt, schema, model_config, timeout_seconds):
        self.payloads.append(prompt)
        return self.answers.pop(0) if self.answers else {}


class Down:
    provider_name = "gemini"
    model_name = "gemini-3.8-flash"
    last_usage: dict = {}

    async def generate_structured(self, *args, **kwargs):
        raise RuntimeError("503 high demand")


def blueprint(name: str = "Ishant Proteins") -> BusinessBlueprint:
    bp = BusinessBlueprint(
        business_id=uuid4(),
        identity={"display_name": Fact(value=name, source="PLATFORM", confirmation="confirmed")},
    )
    bp.messages = []
    return bp


async def say(bp: BusinessBlueprint, text: str, answer: dict, *, image: bool = True,
              business_type: str = "retail") -> BusinessBlueprint:
    bp = await Engine.turn(bp, text, provider=Model(answer), business_type=business_type,
                           image_available=image)
    resolve_recommendations(bp, entitlements(), business_type)
    return bp


def fact(name: str, quote: str) -> dict:
    return {"field": name, "quote": quote}


def ans(target: str, summary: str, quote: str, status: str = "answered") -> dict:
    return {"target": target, "summary": summary, "quote": quote, "status": status}


def pat(pattern: str, quote: str) -> dict:
    return {"pattern": pattern, "quote": quote}


def reply(bp: BusinessBlueprint) -> str:
    return bp.messages[-1].text


def recommended(bp: BusinessBlueprint, strength: str | None = None) -> set[str]:
    return {r.module_id for r in bp.recommended_modules if strength is None or r.strength == strength}


GENERIC = "what do people come to you for"

# ------------------------------------------------------------ the scripted run

T1 = {
    "language": "en",
    "facts": [{"field": "offerings", "quote": "all types of meat"}],
    "answered": [
        {"target": "business.identity", "summary": "A meat retailer selling many kinds of meat.",
         "quote": "We sell all types of meat"},
        {"target": "offerings.main", "status": "partial",
         "summary": "All kinds of meat — the exact items are not named yet.", "quote": "all types of meat"},
    ],
    "operating_patterns": [{"pattern": "product_led", "quote": "We sell all types of meat"}],
    "draft": {"hero_headline": "Every kind of meat, in one place.",
              "about": "Ishant Proteins sells a wide range of meat, so customers can find what they need."},
    "acknowledgement": "Understood — a meat shop.",
    "next_target": "offerings.main",
    "next_question": "Which meats should customers see first — chicken, mutton, fish or others? "
                     "And do they choose the cut?",
}
T2 = {
    "owner_signal": "redundant",
    "acknowledgement": "Right — let me be more specific.",
    "next_target": "offerings.main",
    "next_question": "What kinds of meat do you usually sell, and can customers choose the cut and weight?",
}
T3 = {
    "facts": [{"field": "customer_actions", "quote": "Select meat and then select kg and then order"}],
    "answered": [
        {"target": "commerce.action", "summary": "Customers pick the meat, choose the weight in kg and order online.",
         "quote": "Select meat and then select kg and then order"},
        {"target": "offerings.units", "summary": "Sold by weight — customers choose the kg.",
         "quote": "select kg"},
    ],
    "operating_patterns": [{"pattern": "order_led", "quote": "then order"},
                           {"pattern": "catalogue_led", "quote": "Select meat"}],
    "intents": [{"intent": "orders", "original_request": "Select meat and then select kg and then order"}],
    # "Fresh" was never said: governance must drop this headline.
    "draft": {"hero_headline": "Fresh cuts, by the kilo.",
              "hero_subheadline": "Pick the meat, choose the weight and order in a few taps.",
              "cta_label": "Order now"},
    "acknowledgement": "Perfect — so it's sold by weight.",
    "next_target": "fulfilment.mode",
    "next_question": "Do you deliver orders, offer pickup from the shop, or both?",
}
T4 = {"facts": [{"field": "locations", "quote": "nookampalayam road"}],
      "answered": [{"target": "contact.location", "summary": "Nookampalayam Road", "quote": "nookampalayam road"}],
      "acknowledgement": "Ah, okay.", "next_target": "contact.phone",
      "next_question": "What number should customers call or WhatsApp?"}
T5 = {"facts": [{"field": "phone", "quote": "8754722026"}],
      "answered": [{"target": "contact.phone", "summary": "8754722026", "quote": "8754722026"}],
      "acknowledgement": "Noted.", "next_target": "fulfilment.mode",
      "next_question": "Do you deliver orders, offer pickup from the shop, or both?"}
T6 = {"facts": [{"field": "operational_characteristics",
                 "quote": "We deliver ourselves around Nookampalayam and Perumbakkam, people can pick up too"}],
      "answered": [
          {"target": "fulfilment.mode", "summary": "Delivery by their own staff, and pickup.",
           "quote": "We deliver ourselves around Nookampalayam and Perumbakkam, people can pick up too"},
          {"target": "fulfilment.area", "summary": "Nookampalayam and Perumbakkam",
           "quote": "around Nookampalayam and Perumbakkam"},
          {"target": "fulfilment.operator", "summary": "Their own staff", "quote": "We deliver ourselves"}],
      "operating_patterns": [{"pattern": "local_delivery", "quote": "We deliver ourselves"},
                             {"pattern": "pickup", "quote": "people can pick up too"}],
      "acknowledgement": "Right — delivery and pickup.", "next_target": "commerce.payment",
      "next_question": "How would you like customers to pay — online, cash on delivery, or both?"}
T7 = {"answered": [{"target": "commerce.payment", "summary": "Online payment and cash on delivery.",
                    "quote": "Both online and cash on delivery"}],
      "acknowledgement": "Understood.", "next_target": "offerings.main",
      "next_question": "Which meats should customers see first?"}
STORY = ("I want website customized for me. With enough texts that we sell fresh meat etc. "
         "And about us saying we sell fresh meat from farm to ur house like that")
T8 = {"answered": [{"target": "brand.story", "summary": "Fresh meat, from the farm to the customer's home.",
                    "quote": "we sell fresh meat from farm to ur house"}],
      "draft": {"hero_headline": "Fresh meat, closer to home.",
                "about": "At Ishant Proteins, we make fresh meat easy to order. Choose what you need, "
                         "select the quantity and we bring it from the farm to your home.",
                "owner_claims": [{"claim": "Fresh meat from the farm to your house",
                                  "quote": "we sell fresh meat from farm to ur house"}]},
      "acknowledgement": "Lovely — that's the story.", "next_target": "offerings.main",
      "next_question": "Which meats should customers see first — chicken, mutton, fish?"}
T9 = {"facts": [{"field": "offerings", "quote": "Chicken, mutton and fish", "mode": "replace"}],
      "answered": [{"target": "offerings.main", "summary": "Chicken, mutton and fish.",
                    "quote": "Chicken, mutton and fish"}],
      "draft": {"offerings": [
          {"name": "Chicken", "description": "Choose your preferred chicken cut and quantity for curries, "
                                             "grills and everyday meals."},
          {"name": "Mutton", "description": "Antibiotic-free mutton for slow-cooked dishes."},
          {"name": "Fish", "description": "Pick the fish and the weight you need for tonight's dinner."}]},
      "acknowledgement": "Right.", "next_target": "media.logo",
      "next_question": "Do you have a logo you can upload, or should I create a simple one for you?"}
T10 = {"media_intent": "none", "acknowledgement": "Sure."}  # the model misses it; context does not


@pytest.mark.asyncio
async def test_the_original_failure_is_not_repeated():
    """ "We sell all types of meat" once got "What do people come to you for?" — twice."""
    bp = blueprint()
    bp = await say(bp, "We sell all types of meat", T1)
    assert GENERIC not in reply(bp).lower()
    assert bp.last_asked_target == "offerings.main"
    assert "chicken, mutton, fish" in reply(bp)
    assert bp.discovery["offerings.main"].status == "partial"
    assert [g.name for g in bp.taxonomy.groups] == ["Meat"]
    assert "varieties" in bp.taxonomy.groups[0].needs  # "all types" names no items

    bp = await say(bp, "Obviously to get meat only.", T2)
    assert reply(bp).startswith("Right — let me be more specific.")
    assert GENERIC not in reply(bp).lower()

    # The model proposes delivery; the range is still unknown, so Locah asks for it.
    bp = await say(bp, "Select meat and then select kg and then order", T3)
    assert bp.discovery["offerings.units"].status == "answered"
    assert {"offerings-catalog", "orders", "payments", "inventory"} <= recommended(bp, "strong")
    assert bp.last_asked_target == "offerings.structure"
    assert "varieties" in reply(bp)


# ------------------------------------------- the improved conversation (brief §57)

N1 = {
    "facts": [fact("offerings", "chicken, mutton, fish, crab and squid"),
              fact("customer_actions", "People select the meat and kg and order")],
    "answered": [ans("business.identity", "You sell meat and seafood.", "We sell chicken, mutton"),
                 ans("offerings.main", "Chicken, mutton, fish, crab and squid.",
                     "chicken, mutton, fish, crab and squid"),
                 ans("commerce.action", "People pick the meat, the kg, and order.",
                     "People select the meat and kg and order"),
                 ans("offerings.units", "Sold by weight — customers choose the kg.", "select the meat and kg")],
    "operating_patterns": [pat("product_led", "We sell chicken, mutton, fish, crab and squid"),
                           pat("order_led", "and order")],
    "catalogue": [
        {"group": "Chicken", "unknown": ["cuts"], "sold_by": "by weight (kg)"},
        {"group": "Mutton", "unknown": ["cuts"], "sold_by": "by weight (kg)"},
        {"group": "Fish & Seafood", "items": [{"name": "Fish"}, {"name": "Crab"}, {"name": "Squid"}],
         "unknown": ["varieties"]},
    ],
    "draft": {"hero_headline": "Chicken, mutton and seafood, by the kilo.",
              "hero_subheadline": "Pick your meat, choose the weight and order."},
    "acknowledgement": "Nice.",
    "next_target": "offerings.structure",
    "next_question": "For chicken and mutton, do people choose cuts too? And for fish, which "
                     "varieties do you normally sell?",
}
N2 = {
    "answered": [ans("offerings.structure", "Chicken and mutton come in cuts; fish in three varieties.",
                     "Chicken whole, curry cut and boneless")],
    "catalogue": [
        {"group": "Chicken", "items": [{"name": "Whole chicken"}, {"name": "Curry cut"}, {"name": "Boneless"}]},
        {"group": "Mutton", "items": [{"name": "Curry cut"}, {"name": "Chops"}]},
        {"group": "Fish & Seafood", "items": [{"name": "Seer fish"}, {"name": "Pomfret"}, {"name": "Sardine"},
                                              {"name": "Crab"}, {"name": "Squid"},
                                              {"name": "fish different varieties"}]},
    ],
    "acknowledgement": "That helps.",
    # A secondary question the model wants to ask too early.
    "next_target": "operations.hours",
    "next_question": "What are your opening hours?",
}
N3 = {"acknowledgement": "Sure.", "next_target": "brand.story",
      "next_question": "What should people remember about Ishant Proteins?"}
N5 = {"answered": [ans("fulfilment.mode", "You deliver and offer pickup.",
                       "We deliver ourselves around Nookampalayam and Perumbakkam, people can pick up too"),
                   ans("fulfilment.area", "Nookampalayam and Perumbakkam", "around Nookampalayam and Perumbakkam")],
      "operating_patterns": [pat("local_delivery", "We deliver ourselves"), pat("pickup", "people can pick up too")],
      "acknowledgement": "Delivery and pickup.", "next_target": "commerce.payment",
      "next_question": "How do customers pay — online, cash on delivery, or both?"}
N6 = {"answered": [ans("commerce.payment", "Online and cash on delivery.", "Both online and cash on delivery")],
      "acknowledgement": "Both work.", "next_target": "contact.location",
      "next_question": "Where is the shop?"}
N7 = {"facts": [fact("locations", "nookampalayam road")],
      "answered": [ans("contact.location", "Nookampalayam Road", "nookampalayam road")],
      "acknowledgement": "Noted.", "next_target": "contact.phone",
      "next_question": "Which number should customers call or WhatsApp?"}
N8 = {"facts": [fact("phone", "8754722026")],
      "answered": [ans("contact.phone", "8754722026", "8754722026")],
      "acknowledgement": "Saved.", "next_target": "offerings.pricing",
      "next_question": "Do you already have prices per kg, or should I leave those for later?"}
N9 = {"answered": [ans("offerings.pricing", "Chicken 240 and mutton 800 per kg.", "Chicken 240 per kg")],
      "catalogue": [{"group": "Chicken", "price": "₹240", "unit": "per kg"},
                    {"group": "Mutton", "price": "₹800", "unit": "per kg"},
                    {"group": "Fish & Seafood", "price": "₹999", "unit": "per kg"}],
      "acknowledgement": "Prices noted.", "next_target": "media.logo",
      "next_question": "Do you have a logo, or should I create a simple one?"}


@pytest.mark.asyncio
async def test_the_ishant_proteins_conversation():
    bp = blueprint()
    say_ = lambda b, t, a, **k: say(b, t, a, business_type="other", **k)  # noqa: E731

    # 1. The whole range in one line: understood as a structure, and the next
    # question is what the WEBSITE needs — cuts and varieties.
    bp = await say_(bp, "We sell chicken, mutton, fish, crab and squid. People select the meat and kg and order.", N1)
    groups = {g.name: g for g in bp.taxonomy.groups}
    assert list(groups) == ["Chicken", "Mutton", "Fish & Seafood"]
    assert groups["Fish & Seafood"].label_source == "ai_suggestion"
    assert [i.name for i in groups["Fish & Seafood"].items] == ["Fish", "Crab", "Squid"]
    assert "varieties" in groups["Fish & Seafood"].needs and "cuts" in groups["Chicken"].needs
    assert bp.last_asked_target == "offerings.structure"
    assert "cuts" in reply(bp) and "varieties" in reply(bp)

    # 2. Cuts and varieties — "fish different varieties" never becomes a product.
    bp = await say_(bp, "Chicken whole, curry cut and boneless. Mutton curry cut and chops. "
                        "Fish - seer, pomfret, sardine, fish different varieties.", N2)
    groups = {g.name: g for g in bp.taxonomy.groups}
    assert [i.name for i in groups["Chicken"].items] == ["Whole chicken", "Curry cut", "Boneless"]
    assert "Fish different varieties" not in [i.name for i in groups["Fish & Seafood"].items]
    assert "cuts" not in groups["Chicken"].needs
    # Hours can wait: the photos question shapes the website more.
    assert bp.last_asked_target == "media.photos"
    assert "draft visuals" in reply(bp)

    # 3. Draft visuals, with consent.
    bp = await say_(bp, "No photos yet, you can create them", N3)
    assert bp.visual_consent == "draft_visuals"
    assert "draft visuals" in reply(bp)
    assert bp.last_asked_target == "brand.story"

    bp = await say_(bp, STORY, T8)
    assert bp.last_asked_target == "fulfilment.mode"  # operations now, after the website shape
    bp = await say_(bp, "We deliver ourselves around Nookampalayam and Perumbakkam, people can pick up too", N5)
    bp = await say_(bp, "Both online and cash on delivery", N6)
    bp = await say_(bp, "In nookampalayam road", N7)
    bp = await say_(bp, "8754722026", N8)
    assert bp.last_asked_target == "offerings.pricing"

    # 4. Prices only as the owner said them — an invented one is dropped.
    bp = await say_(bp, "Chicken 240 per kg, mutton 800 per kg. Fish I'll fill later.", N9)
    groups = {g.name: g for g in bp.taxonomy.groups}
    assert (groups["Chicken"].price, groups["Chicken"].unit) == ("₹240", "per kg")
    assert groups["Fish & Seafood"].price == "" and "price" in groups["Fish & Seafood"].needs
    assert bp.last_asked_target == "media.logo"

    bp = await say_(bp, "Generate one", T10)
    assert bp.readiness.ready
    assert all(bp.readiness.website.values())
    assert bp.discovery["operations.hours"].asked == 0  # never needed for a first website
    asked = [t for t, s in bp.discovery.items() if s.asked]
    assert all(bp.discovery[t].asked <= 2 for t in asked)


@pytest.mark.asyncio
async def test_a_bad_model_proposal_cannot_re_ask_what_is_known():
    bp = blueprint()
    bad = {**T1, "next_target": "business.identity",
           "next_question": "Tell me a little about your business. What do people come to you for?"}
    bp = await say(bp, "We sell all types of meat", bad)
    assert GENERIC not in reply(bp).lower()
    assert bp.last_asked_target == "offerings.main"


@pytest.mark.asyncio
async def test_with_no_model_the_question_still_comes_from_what_is_known():
    bp = blueprint()
    bp = await say(bp, "We sell all types of meat", T1)
    bp = await Engine.turn(bp, "Select meat and then select kg and then order", provider=Down(),
                           business_type="retail")
    text = reply(bp)
    assert text.startswith("I've saved what you said")  # a system problem, said as one
    assert GENERIC not in text.lower()


@pytest.mark.asyncio
async def test_generate_one_without_image_generation_is_explained_specifically():
    bp = blueprint()
    bp.discovery["media.logo"] = TargetState(status="asked", asked=1)
    bp.last_asked_target = "media.logo"
    bp = await say(bp, "Generate one", T10, image=False)
    assert [(r.role, r.status) for r in bp.media_generation_requests] == [("logo", "unavailable")]
    assert "saved that you want a logo made" in reply(bp)
    assert "won't hold up your website" in reply(bp)


@pytest.mark.asyncio
async def test_owner_edits_to_the_draft_are_never_rewritten_by_later_turns():
    bp = blueprint()
    bp = await say(bp, "We sell all types of meat", T1)
    from platform_core.interview.models import DraftText
    bp.website_draft.hero_headline = DraftText(text="Fresh from our farm to your family.", provenance="owner_edited")
    bp = await say(bp, STORY, T8)
    assert bp.website_draft.hero_headline.text == "Fresh from our farm to your family."
    assert bp.website_draft.about.text.startswith("At Ishant Proteins")


# ------------------------------------------------------------------ planner


def test_the_same_mechanism_serves_every_kind_of_business():
    """No vertical branches: characteristics decide which questions exist."""
    salon = blueprint("Mirror & Muse")
    salon.known_facts["description"] = Fact(value="We run a salon", source="USER_STATEMENT")
    salon.known_facts["customer_actions"] = Fact(value="Clients book appointments", source="USER_STATEMENT")
    salon.discovery = {}
    Engine.project(salon, "salon")
    ids = {r.target.id for r in rank(salon, "salon")}
    assert "bookings.format" in ids and "fulfilment.mode" not in ids and "offerings.units" not in ids

    supplier = blueprint("Kaveri Industrial")
    supplier.known_facts["description"] = Fact(
        value="We supply bearings to factories around Hosur", source="USER_STATEMENT")
    supplier.known_facts["customer_actions"] = Fact(
        value="Purchase teams send us a quotation request", source="USER_STATEMENT")
    Engine.project(supplier, "other")
    ids = {r.target.id for r in rank(supplier, "other")}
    assert "b2b.customers" in ids or supplier.discovery["b2b.customers"].status == "answered"
    assert "commerce.payment" not in ids  # a quote-led supplier is not a checkout


def test_readiness_is_about_this_business_not_three_fields():
    shop = blueprint()
    for key, value in {"description": "We sell meat", "offerings": "Chicken, mutton and fish",
                       "customer_actions": "Customers select meat and order online",
                       "locations": "Chennai", "phone": "8754722026"}.items():
        shop.known_facts[key] = Fact(value=value, source="USER_STATEMENT")
    Engine.project(shop, "retail")
    # Orders are online, so how they are sold, delivered and paid for matter.
    assert {"offerings.units", "fulfilment.mode", "commerce.payment"} <= set(readiness(shop, "retail").missing)


def test_every_target_has_owner_facing_words():
    for target in TARGETS_BY_ID.values():
        assert target.label and target.learn and target.fallback.get("en")
        assert "module" not in target.fallback["en"].lower()


# --------------------------------------------------------------- website draft


def drafted() -> BusinessBlueprint:
    from platform_core.interview.models import DraftText, OfferingDraft

    bp = blueprint()
    wd = bp.website_draft
    wd.hero_headline = DraftText(text="Every kind of meat, in one place.", provenance="ai_suggestion")
    wd.about = DraftText(text="Ishant Proteins sells chicken, mutton and fish.", provenance="ai_suggestion")
    wd.offerings = [OfferingDraft(name="Chicken", description=DraftText(text="For curries.", provenance="ai_suggestion")),
                    OfferingDraft(name="Mutton")]
    return bp


def test_the_owner_can_edit_keep_and_remove_draft_wording():
    from platform_core.interview.models import DraftCommand
    from platform_core.services.business_interview import _apply_draft

    bp = drafted()
    _apply_draft(bp, DraftCommand(field="hero_headline", op="edit", text="  Fresh from our farm  "))
    assert (bp.website_draft.hero_headline.text, bp.website_draft.hero_headline.provenance) == (
        "Fresh from our farm", "owner_edited")
    _apply_draft(bp, DraftCommand(field="about", op="approve"))
    assert bp.website_draft.about.provenance == "owner_approved"
    _apply_draft(bp, DraftCommand(field="offering", op="edit", offering_name="mutton", text="Slow-cooked goat."))
    assert bp.website_draft.offerings[1].description.provenance == "owner_edited"
    _apply_draft(bp, DraftCommand(field="offering", op="dismiss", offering_name="Chicken"))
    assert [o.name for o in bp.website_draft.offerings] == ["Mutton"]
    _apply_draft(bp, DraftCommand(field="hero_subheadline", op="dismiss"))
    assert "hero_subheadline" in bp.website_draft.dismissed


@pytest.mark.asyncio
async def test_a_removed_line_is_not_quietly_put_back_and_kept_lines_are_not_rewritten():
    from platform_core.interview.models import DraftCommand
    from platform_core.services.business_interview import _apply_draft

    bp = drafted()
    _apply_draft(bp, DraftCommand(field="hero_subheadline", op="dismiss"))
    _apply_draft(bp, DraftCommand(field="about", op="approve"))
    rewrite = {"draft": {"hero_subheadline": "Pick the meat and order in a few taps.",
                         "about": "Ishant Proteins sells meat."},
               "acknowledgement": "Right."}
    bp = await say(bp, "We sell all types of meat", rewrite)
    assert bp.website_draft.hero_subheadline is None
    assert bp.website_draft.about.text == "Ishant Proteins sells chicken, mutton and fish."


@pytest.mark.asyncio
async def test_regenerate_rewrites_only_the_field_asked_for_and_still_refuses_claims():
    bp = drafted()
    bp.known_facts["offerings"] = Fact(value="chicken, mutton and fish", source="USER_STATEMENT")
    fresh = Model({"hero_headline": "Chicken, mutton and fish, the way you like it.",
                   "about": "Something else entirely."})
    bp = await Engine.regenerate_draft(bp, "hero_headline", provider=fresh, business_type="retail")
    assert bp.website_draft.hero_headline.text == "Chicken, mutton and fish, the way you like it."
    assert bp.website_draft.about.text == "Ishant Proteins sells chicken, mutton and fish."
    invented = Model({"hero_headline": "Organic, farm-fresh meat since 1990."})
    bp = await Engine.regenerate_draft(bp, "hero_headline", provider=invented, business_type="retail")
    assert bp.website_draft.hero_headline.text == "Chicken, mutton and fish, the way you like it."


def test_owner_wording_wins_over_personalisation_on_the_built_site():
    import json

    from platform_core.interview.models import DraftText
    from platform_core.interview.website import build_preview
    from platform_core.interview.website_copy import WebsiteCopy

    from test_business_interview import confirmed, plan

    bp = confirmed()
    bp.website_draft.hero_headline = DraftText(text="Sofas that last a lifetime.", provenance="owner_edited")
    copy = WebsiteCopy(headline="Comfort for every home", about_body="We make sofas and dining tables.")
    payload = json.dumps(build_preview(bp, plan(bp), copy=copy))
    assert "Sofas that last a lifetime." in payload
    assert "Comfort for every home" not in payload
    assert "We make sofas and dining tables." in payload  # the draft had no About, so copy fills it


def test_confirming_covers_every_detail_the_panel_shows():
    """Live: after "These details are correct", delivery and payment still said "Needs confirmation"."""
    bp = blueprint()
    bp.discovery["commerce.payment"] = TargetState(status="answered", summary="Online and cash on delivery.")
    assert understanding(bp, "retail")["items"][0]["status"] == "from_you"
    bp.completion_state.confirmed = True
    assert understanding(bp, "retail")["items"][0]["status"] == "confirmed"


def test_food_made_in_small_batches_is_not_a_class_to_book() -> None:
    """A pickle kitchen was asked "What do people usually book with you?"."""
    from platform_core.interview.discovery import characteristics

    bp = BusinessBlueprint(business_id=uuid4())
    bp.known_facts["description"] = Fact(
        value="We make homemade podis and pickles in small batches from our home kitchen.",
        source="USER_STATEMENT", confirmation="confirmed")
    assert "runs_classes" not in characteristics(bp, "other")
    assert "bookings.format" not in {r.target.id for r in rank(bp, "other")}
    bp.known_facts["description"] = Fact(value="Morning batch and evening batch for strength classes.",
                                         source="USER_STATEMENT", confirmation="confirmed")
    assert "runs_classes" in characteristics(bp, "other")
