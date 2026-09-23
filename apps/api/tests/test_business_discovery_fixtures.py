"""Evaluation fixtures: one discovery system, many kinds of business.

Each fixture is a short conversation with scripted model output of the kind
Gemini returns — sometimes a good proposal, sometimes a bad one (a question
that does not apply, jargon, a re-ask). What is checked is what Locah keeps,
what it asks, what it recommends and when it says it has enough.

Nothing here branches on a business type; if a fixture needed an `if` for its
vertical, the planner would be wrong.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from uuid import uuid4

import pytest

from platform_core.interview.capabilities import resolve_recommendations
from platform_core.interview.conversation import govern_question
from platform_core.interview.discovery import TARGETS, characteristics, fallback_question, rank
from platform_core.interview.models import BusinessBlueprint, Fact
from platform_core.interview.orchestrator import BusinessInterviewOrchestrator as Engine

from test_business_interview import entitlements


class Model:
    provider_name = "fixture"
    model_name = "fixture"
    last_usage = {"prompt_tokens": 1, "completion_tokens": 1}

    def __init__(self, answer: dict) -> None:
        self.answer = answer

    async def generate_structured(self, prompt, schema, model_config, timeout_seconds):
        return self.answer


@dataclass
class Fixture:
    name: str
    business_type: str
    turns: list[tuple[str, dict]]
    strong: set[str]
    useful: set[str] = field(default_factory=set)
    never: set[str] = field(default_factory=set)  # must not be recommended at all
    never_asked: set[str] = field(default_factory=set)
    asked: set[str] = field(default_factory=set)  # asked at some point
    only_as_dependency: set[str] = field(default_factory=set)  # present only because another needs it


def fact(name: str, quote: str) -> dict:
    return {"field": name, "quote": quote}


def ans(target: str, summary: str, quote: str, status: str = "answered") -> dict:
    return {"target": target, "summary": summary, "quote": quote, "status": status}


def pat(pattern: str, quote: str) -> dict:
    return {"pattern": pattern, "quote": quote}


MEAT = Fixture(
    "Ishant Proteins", "retail",
    [
        ("We sell chicken, mutton and fish. Customers pick the item, choose the kg and order online.", {
            "facts": [fact("offerings", "chicken, mutton and fish"),
                      fact("customer_actions", "Customers pick the item, choose the kg and order online")],
            "answered": [ans("business.identity", "A meat shop.", "We sell chicken, mutton and fish"),
                         ans("offerings.main", "Chicken, mutton and fish.", "chicken, mutton and fish"),
                         ans("commerce.action", "Pick, choose the kg, order online.", "order online"),
                         ans("offerings.units", "By weight.", "choose the kg")],
            "operating_patterns": [pat("product_led", "We sell chicken, mutton and fish"),
                                   pat("order_led", "order online")],
            "acknowledgement": "Got it — sold by the kilo.",
            "next_target": "fulfilment.mode",
            "next_question": "Do you deliver the orders, or do customers pick them up?"}),
        ("We deliver in Perumbakkam. Payment online or cash on delivery.", {
            "answered": [ans("fulfilment.mode", "Delivery.", "We deliver in Perumbakkam"),
                         ans("fulfilment.area", "Perumbakkam", "in Perumbakkam"),
                         ans("commerce.payment", "Online or cash on delivery.",
                             "Payment online or cash on delivery")],
            "operating_patterns": [pat("local_delivery", "We deliver in Perumbakkam")],
            "acknowledgement": "Perfect.",
            # A bad proposal: "which meats?" is already answered.
            "next_target": "offerings.main",
            "next_question": "Which meats do you sell?"}),
    ],
    strong={"offerings-catalog", "orders", "payments", "inventory", "fulfilment"},
    never={"bookings", "workforce", "quotes", "memberships", "projects"},
    never_asked={"bookings.format", "b2b.customers", "memberships.plans", "offerings.main",
                 "operations.hours", "fulfilment.mode"},
    # Website-shaping first: pictures before delivery, even though the model proposed delivery.
    asked={"media.photos"},
)

FURNITURE = Fixture(
    "Teakwood Furniture Co", "other",
    [
        ("We make custom wooden furniture — wardrobes, beds and dining tables, made to order in our "
         "Coimbatore workshop.", {
             "facts": [fact("description", "We make custom wooden furniture"),
                       fact("offerings", "wardrobes, beds and dining tables"),
                       fact("locations", "Coimbatore")],
             "answered": [ans("business.identity", "A custom furniture maker.", "We make custom wooden furniture"),
                          ans("offerings.main", "Wardrobes, beds and dining tables.",
                              "wardrobes, beds and dining tables"),
                          ans("contact.location", "Coimbatore", "Coimbatore")],
             "operating_patterns": [pat("made_to_order", "made to order"),
                                    pat("product_led", "We make custom wooden furniture")],
             "acknowledgement": "Lovely — made to order.",
             # Jargon: must be replaced by the planner's own question.
             "next_target": "offerings.customisation",
             "next_question": "Which offerings should go into your catalogue?"}),
        ("Customers visit the showroom or WhatsApp us their measurements, then we send a quote.", {
            "facts": [fact("customer_actions",
                           "Customers visit the showroom or WhatsApp us their measurements, then we send a quote")],
            "answered": [ans("commerce.action", "Showroom visit or WhatsApp, then a quote.",
                             "visit the showroom or WhatsApp us their measurements")],
            "operating_patterns": [pat("quote_led", "then we send a quote"),
                                   pat("walk_in", "visit the showroom")],
            "intents": [{"intent": "quotes", "original_request": "then we send a quote"}],
            "acknowledgement": "Makes sense.",
            "next_target": "fulfilment.mode",
            "next_question": "Once it's ready, do you deliver and fit it, or do customers collect it?"}),
        ("We deliver and install everything ourselves within Coimbatore.", {
            "answered": [ans("fulfilment.mode", "Delivered and installed.", "We deliver and install everything"),
                         ans("fulfilment.area", "Coimbatore", "within Coimbatore")],
            "operating_patterns": [pat("local_delivery", "We deliver and install everything ourselves")],
            "acknowledgement": "Great.",
            "next_target": "contact.phone",
            "next_question": "What number should customers call or WhatsApp?"}),
    ],
    strong={"offerings-catalog", "quotes", "leads"},
    useful={"projects"},
    never={"orders", "payments", "inventory", "bookings", "workforce"},
    never_asked={"bookings.format", "commerce.payment", "memberships.plans"},
    asked={"offerings.customisation"},
)

RESTAURANT = Fixture(
    "Amma's Kitchen", "restaurant",
    [
        ("We're a South Indian restaurant in Anna Nagar — idli, dosa and full meals.", {
            "facts": [fact("description", "We're a South Indian restaurant in Anna Nagar"),
                      fact("offerings", "idli, dosa and full meals"), fact("locations", "Anna Nagar")],
            "answered": [ans("business.identity", "A South Indian restaurant.", "South Indian restaurant"),
                         ans("offerings.main", "Idli, dosa and full meals.", "idli, dosa and full meals"),
                         ans("contact.location", "Anna Nagar", "Anna Nagar")],
            "acknowledgement": "Lovely.",
            "next_target": "commerce.action",
            "next_question": "When people find you online, should they book a table, order takeaway, or just call?"}),
        ("People book tables for weekend dinners and order takeaway on the phone.", {
            "facts": [fact("customer_actions",
                           "People book tables for weekend dinners and order takeaway on the phone")],
            "answered": [ans("commerce.action", "Table bookings and takeaway orders.",
                             "book tables for weekend dinners and order takeaway")],
            "operating_patterns": [pat("appointment_led", "book tables"), pat("order_led", "order takeaway"),
                                   pat("pickup", "takeaway")],
            "acknowledgement": "Got it.",
            "next_target": "bookings.format",
            "next_question": "Roughly how many people can you seat, and is it only weekends?"}),
        ("Only weekends, about 40 seats. Customers pay cash or UPI at the counter.", {
            "answered": [ans("bookings.format", "Weekend table bookings, 40 seats.", "Only weekends, about 40 seats"),
                         ans("commerce.payment", "Cash or UPI at the counter.", "cash or UPI at the counter")],
            "acknowledgement": "Noted.",
            "next_target": "operations.hours",
            "next_question": "What are your usual opening hours?"}),
    ],
    strong={"offerings-catalog", "bookings", "orders", "payments", "fulfilment"},
    # Food is sold, but nobody said stock — inventory only as what pickup needs.
    never={"workforce", "quotes", "memberships"},
    never_asked={"b2b.customers", "memberships.plans", "offerings.customisation"},
    asked={"bookings.format"},
)

CLINIC = Fixture(
    "Smile Dental Care", "clinic",
    [
        ("Dental clinic in T Nagar. Two dentists — cleaning, braces and root canal treatment.", {
            "facts": [fact("description", "Dental clinic in T Nagar"),
                      fact("offerings", "cleaning, braces and root canal treatment"),
                      fact("locations", "T Nagar")],
            "answered": [ans("business.identity", "A dental clinic.", "Dental clinic"),
                         ans("offerings.main", "Cleaning, braces and root canal.",
                             "cleaning, braces and root canal treatment"),
                         ans("contact.location", "T Nagar", "T Nagar")],
            "operating_patterns": [pat("service_led", "cleaning, braces and root canal treatment"),
                                   pat("provider_based", "Two dentists")],
            "acknowledgement": "Understood.",
            # Does not apply to a clinic: the planner must not ask it.
            "next_target": "fulfilment.mode",
            "next_question": "Do you deliver, or do patients pick up?"}),
        ("Patients should book an appointment online, or call us.", {
            "facts": [fact("customer_actions", "Patients should book an appointment online, or call us")],
            "answered": [ans("commerce.action", "Book online or call.", "book an appointment online")],
            "operating_patterns": [pat("appointment_led", "book an appointment online")],
            "intents": [{"intent": "bookings", "original_request": "book an appointment online"}],
            "acknowledgement": "Right.",
            "next_target": "bookings.format",
            "next_question": "How long is a usual visit, and can patients choose their dentist?"}),
    ],
    strong={"bookings"},
    useful={"offerings-catalog", "workforce"},
    never={"orders", "payments", "inventory", "fulfilment", "leads", "quotes"},
    never_asked={"fulfilment.mode", "offerings.units", "commerce.payment", "operations.stock"},
    asked={"bookings.format"},
)

GYM = Fixture(
    "Iron Temple Fitness", "gym",
    [
        ("A gym in Velachery with monthly and yearly memberships, plus zumba and yoga classes.", {
            "facts": [fact("description", "A gym in Velachery"),
                      fact("offerings", "monthly and yearly memberships, plus zumba and yoga classes"),
                      fact("locations", "Velachery")],
            "answered": [ans("business.identity", "A gym.", "A gym in Velachery"),
                         ans("offerings.main", "Memberships and classes.",
                             "monthly and yearly memberships, plus zumba and yoga classes"),
                         ans("memberships.plans", "Monthly and yearly.", "monthly and yearly memberships"),
                         ans("contact.location", "Velachery", "Velachery")],
            "operating_patterns": [pat("membership_led", "monthly and yearly memberships"),
                                   pat("runs_classes", "zumba and yoga classes")],
            "acknowledgement": "Nice.",
            "next_target": "commerce.action",
            "next_question": "What should people be able to do online — join, book a class, or ask a question?"}),
        ("People should join online and book their class slot. Our trainers also do personal training.", {
            "facts": [fact("customer_actions", "People should join online and book their class slot")],
            "answered": [ans("commerce.action", "Join online and book class slots.",
                             "join online and book their class slot")],
            "operating_patterns": [pat("appointment_led", "book their class slot"),
                                   pat("has_team", "Our trainers also do personal training")],
            "acknowledgement": "Great.",
            "next_target": "commerce.payment",
            "next_question": "How do members pay — online, at the desk, or both?"}),
    ],
    strong={"memberships", "bookings", "payments"},
    useful={"workforce"},
    never={"inventory", "fulfilment", "quotes"},
    never_asked={"fulfilment.mode", "offerings.units", "operations.stock", "b2b.customers"},
    asked={"bookings.format"},
)

SUPPLIER = Fixture(
    "Kaveri Industrial Supplies", "other",
    [
        ("We supply bearings, seals and V-belts to factories around Hosur.", {
            "facts": [fact("description", "We supply bearings, seals and V-belts to factories around Hosur"),
                      fact("offerings", "bearings, seals and V-belts"), fact("locations", "Hosur")],
            "answered": [ans("business.identity", "An industrial supplier.", "We supply bearings"),
                         ans("offerings.main", "Bearings, seals and V-belts.", "bearings, seals and V-belts"),
                         ans("b2b.customers", "Factories around Hosur.", "factories around Hosur"),
                         ans("contact.location", "Hosur", "Hosur")],
            "operating_patterns": [pat("b2b", "to factories around Hosur"),
                                   pat("product_led", "We supply bearings, seals and V-belts")],
            "acknowledgement": "Understood.",
            "next_target": "b2b.process",
            "next_question": "How does a factory usually order — do they ask for a quotation first?"}),
        ("Purchase teams send us their requirement, we send a quotation and then they raise a PO. "
         "We deliver by our own truck and raise GST invoices.", {
             "facts": [fact("customer_actions", "Purchase teams send us their requirement, we send a quotation")],
             "answered": [ans("b2b.process", "Requirement, quotation, then a PO.",
                              "send us their requirement, we send a quotation and then they raise a PO"),
                          ans("commerce.action", "Send a requirement for a quotation.",
                              "send us their requirement"),
                          ans("fulfilment.mode", "Own truck.", "We deliver by our own truck")],
             "operating_patterns": [pat("quote_led", "we send a quotation"),
                                    pat("local_delivery", "We deliver by our own truck")],
             "intents": [{"intent": "quotes", "original_request": "we send a quotation"},
                         {"intent": "invoicing", "original_request": "raise GST invoices"}],
             "acknowledgement": "Clear.",
             # A consumer checkout question for a quote-led supplier: refused.
             "next_target": "commerce.payment",
             "next_question": "How would you like customers to pay — online or cash on delivery?"}),
    ],
    strong={"offerings-catalog", "quotes", "leads"},
    useful={"invoicing", "orders"},  # a PO after an accepted quote — not a checkout
    never={"payments", "bookings", "memberships"},
    only_as_dependency={"inventory"},
    never_asked={"commerce.payment", "bookings.format", "operations.stock"},
    # What a buyer does comes before how the quote process runs.
    asked={"commerce.action"},
)

FIXTURES = [MEAT, FURNITURE, RESTAURANT, CLINIC, GYM, SUPPLIER]


def blueprint(name: str) -> BusinessBlueprint:
    bp = BusinessBlueprint(
        business_id=uuid4(),
        identity={"display_name": Fact(value=name, source="PLATFORM", confirmation="confirmed")},
    )
    bp.messages = []
    return bp


async def run(fx: Fixture) -> tuple[BusinessBlueprint, list[str], list[str | None]]:
    bp = blueprint(fx.name)
    replies: list[str] = []
    targets: list[str | None] = []
    for text, answer in fx.turns:
        bp = await Engine.turn(bp, text, provider=Model(answer), business_type=fx.business_type,
                               image_available=False)
        resolve_recommendations(bp, entitlements(), fx.business_type)
        replies.append(bp.messages[-1].text)
        targets.append(bp.last_asked_target)
    return bp, replies, targets


def by_strength(bp: BusinessBlueprint) -> dict[str, str]:
    return {r.module_id: r.strength for r in bp.recommended_modules}


# ------------------------------------------------------------ recommendations


@pytest.mark.asyncio
@pytest.mark.parametrize("fx", FIXTURES, ids=lambda f: f.name)
async def test_recommendations_follow_the_evidence(fx: Fixture):
    bp, _, _ = await run(fx)
    got = by_strength(bp)
    strong = {m for m, s in got.items() if s == "strong"}
    assert fx.strong <= strong, f"missing strong: {fx.strong - strong}; got {got}"
    for module in fx.useful:
        assert got.get(module) == "useful", f"{module}: {got.get(module)}"
    assert not fx.never & set(got), f"over-recommended: {fx.never & set(got)}"
    for module in fx.only_as_dependency:
        assert got.get(module) in (None, "dependency"), f"{module}: {got.get(module)}"
    for rec in bp.recommended_modules:
        # Every recommendation says why, with evidence the owner can recognise.
        assert rec.reason and rec.evidence, rec.module_id
        assert not re.search(r"\b(module|offerings-catalog|fulfilment)\b", rec.reason), rec.reason
        if rec.strength == "dependency":
            assert rec.needed_by, rec.module_id


@pytest.mark.asyncio
async def test_a_restaurant_gets_stock_only_as_what_pickup_needs():
    bp, _, _ = await run(RESTAURANT)
    got = by_strength(bp)
    assert got.get("inventory") == "dependency"
    inventory = next(r for r in bp.recommended_modules if r.module_id == "inventory")
    assert inventory.needed_by == ["Delivery & pickup"]


@pytest.mark.asyncio
async def test_the_journey_order_is_how_an_owner_thinks():
    bp, _, _ = await run(MEAT)
    strong = [r.module_id for r in bp.recommended_modules if r.strength == "strong"]
    assert strong == ["offerings-catalog", "orders", "payments", "inventory", "fulfilment"]


def test_a_salon_gets_staff_scheduling_only_when_the_owner_mentions_a_team():
    salon = blueprint("Mirror & Muse")
    salon.known_facts["description"] = Fact(value="A salon for haircuts and facials", source="USER_STATEMENT")
    salon.known_facts["customer_actions"] = Fact(value="Clients book appointments", source="USER_STATEMENT")
    Engine.project(salon, "salon")
    resolve_recommendations(salon, entitlements(), "salon")
    got = by_strength(salon)
    assert got.get("bookings") == "strong"
    assert "workforce" not in got  # the profile says salons have teams; this owner did not

    salon.known_facts["operational_characteristics"] = Fact(
        value="Our three stylists work different days", source="USER_STATEMENT")
    resolve_recommendations(salon, entitlements(), "salon")
    assert by_strength(salon).get("workforce") == "useful"


def test_a_local_service_that_takes_enquiries_gets_no_shop_tools():
    ac = blueprint("CoolFix AC Service")
    ac.known_facts["description"] = Fact(value="We repair and service ACs at homes in Tambaram",
                                         source="USER_STATEMENT")
    ac.known_facts["customer_actions"] = Fact(value="Customers WhatsApp us the problem and we come and check",
                                              source="USER_STATEMENT")
    ac.operating_patterns = []
    Engine.project(ac, "other")
    resolve_recommendations(ac, entitlements(), "other")
    got = by_strength(ac)
    assert got.get("leads") == "strong"
    assert not {"orders", "payments", "inventory", "fulfilment"} & set(got)


def test_unsupported_live_tracking_becomes_a_gap_not_a_promise():
    shop = blueprint("Ishant Proteins")
    shop.known_facts["customer_actions"] = Fact(
        value="Customers order online and see live tracking of the delivery boy on a map",
        source="USER_STATEMENT")
    Engine.project(shop, "retail")
    resolve_recommendations(shop, entitlements(), "retail")
    gap = next(g for g in shop.unsupported_requests if g.normalized_intent == "live_courier_tracking")
    assert gap.closest_supported_capabilities == ["use_fulfilment"]


# ------------------------------------------------------------ question quality


@pytest.mark.asyncio
@pytest.mark.parametrize("fx", FIXTURES, ids=lambda f: f.name)
async def test_questions_fit_the_business_and_never_repeat(fx: Fixture):
    bp, replies, targets = await run(fx)
    asked = {t for t in targets if t}
    assert fx.asked <= asked, f"never asked {fx.asked - asked}; asked {targets}"
    assert not fx.never_asked & asked, f"asked what does not apply: {fx.never_asked & asked}"
    for before, after in zip(targets, targets[1:]):
        assert before is None or before != after or bp.discovery[after].status == "partial"
    for reply in replies:
        assert reply.count("?") <= 2, reply
        assert not re.search(r"\b(module|catalogue|offerings|fulfilment|inventory|cta)\b", reply, re.I), reply
        assert "what do people come to you for" not in reply.lower()
    acks = [r.split(".")[0] for r in replies]
    assert all(a != b for a, b in zip(acks, acks[1:])), acks


def test_every_fallback_question_is_plain_and_single():
    bp = blueprint("Ishant Proteins")
    bp.known_facts["offerings"] = Fact(value="chicken, mutton and fish", source="USER_STATEMENT")
    for target in TARGETS:
        for style in ("en", "ta_en", "ta"):
            question = fallback_question(target.id, bp, style)
            assert 1 <= question.count("?") <= 2, (target.id, style, question)
            assert "{" not in question, question
            assert not re.search(r"\b(module|catalogue|fulfilment|inventory)\b", question, re.I), question


@pytest.mark.parametrize("question", [
    "Tell me a little about your business. What do people come to you for?",
    "Which offerings should go into your catalogue?",
    "Great answer! What else?",
    "Do you deliver? Do you ship? Do you offer pickup?",
])
def test_the_governor_refuses_bad_questions(question):
    bp = blueprint("Ishant Proteins")
    bp.discovery.clear()
    Engine.project(bp, "retail")
    bp.discovery["business.identity"].status = "answered"
    assert govern_question(question, "We sell all types of meat", bp) is None


def test_characteristics_do_not_come_from_the_word_customers():
    bp = blueprint("Ishant Proteins")
    bp.known_facts["customer_actions"] = Fact(value="Customers select meat and order", source="USER_STATEMENT")
    assert "made_to_order" not in characteristics(bp, "retail")
    assert "offerings.customisation" not in {r.target.id for r in rank(bp, "retail")}
    bp.known_facts["description"] = Fact(value="We also do custom cuts on request", source="USER_STATEMENT")
    assert characteristics(bp, "retail")["made_to_order"] == "observed"


# ----------------------------------------------- found on the live Railway run


@pytest.mark.asyncio
async def test_evidence_is_a_sentence_the_owner_said_not_one_word():
    """Live: the catalogue said `You said: "sell"` — the model's one-word quote."""
    bp = blueprint("Ishant Proteins")
    one_word = {"facts": [fact("offerings", "all types of meat")],
                "answered": [ans("offerings.main", "All kinds of meat.", "all types of meat", "partial")],
                "operating_patterns": [pat("product_led", "sell")],
                "acknowledgement": "Understood.", "next_target": "offerings.main",
                "next_question": "Which meats should customers see first?"}
    bp = await Engine.turn(bp, "We sell all types of meat", provider=Model(one_word), business_type="other")
    resolve_recommendations(bp, entitlements(), "other")
    catalogue = next(r for r in bp.recommended_modules if r.module_id == "offerings-catalog")
    assert catalogue.evidence[0].text == "We sell all types of meat"


def test_delivery_reason_never_splices_a_summary_into_a_sentence():
    """Live: "You offer delivery to Delivery covers Nookampalayam and Perumbakkam"."""
    from platform_core.interview.models import TargetState

    bp = blueprint("Ishant Proteins")
    bp.known_facts["customer_actions"] = Fact(value="Select meat, select kg and order", source="USER_STATEMENT")
    bp.discovery["fulfilment.mode"] = TargetState(
        status="answered", summary="You offer both home delivery and store pickup",
        quote="We deliver ourselves around Nookampalayam and Perumbakkam, people can pick up too")
    bp.discovery["fulfilment.area"] = TargetState(
        status="answered", summary="Delivery covers Nookampalayam and Perumbakkam",
        quote="around Nookampalayam and Perumbakkam")
    Engine.project(bp, "other")
    resolve_recommendations(bp, entitlements(), "other")
    fulfilment = next(r for r in bp.recommended_modules if r.module_id == "fulfilment")
    assert fulfilment.reason == "You offer delivery and pickup — manage it order by order."
    assert "Delivery covers Nookampalayam and Perumbakkam" in [e.text for e in fulfilment.evidence]


@pytest.mark.asyncio
async def test_a_delivery_area_never_becomes_the_address():
    """Live: the site's address read "In nookampalayam road; Nookampalayam and Perumbakkam"."""
    bp = blueprint("Ishant Proteins")
    bp.unconfirmed_facts["locations"] = Fact(value="In nookampalayam road", source="USER_STATEMENT")
    text = "We deliver ourselves around Nookampalayam and Perumbakkam, people can pick up too"
    answer = {"facts": [{"field": "locations", "quote": "Nookampalayam and Perumbakkam", "mode": "add"}],
              "answered": [ans("fulfilment.area", "Delivery covers Nookampalayam and Perumbakkam",
                               "around Nookampalayam and Perumbakkam")],
              "acknowledgement": "Both covered.", "next_target": "commerce.payment",
              "next_question": "How do customers pay?"}
    bp = await Engine.turn(bp, text, provider=Model(answer), business_type="other")
    assert bp.unconfirmed_facts["locations"].value == "In nookampalayam road"
