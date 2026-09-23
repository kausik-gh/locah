"""The conversation layer: natural, governed, and one Blueprint across turns.

No network and no paid model: every provider here is a fixture that returns
what a model plausibly would, including the ways a model misbehaves.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from platform_core.interview.conversation import (
    TEMPLATES,
    ask_order,
    govern_acknowledgement,
    govern_question,
    next_ask,
)
from platform_core.interview.models import BusinessBlueprint, Fact
from platform_core.interview.orchestrator import QUESTIONS
from platform_core.interview.orchestrator import BusinessInterviewOrchestrator as Engine


class Fixture:
    provider_name = "fixture"
    model_name = "fixture"
    last_usage = {"prompt_tokens": 1, "completion_tokens": 1}

    def __init__(self, *results):
        self.results = list(results)
        self.payloads: list[str] = []

    async def generate_structured(self, prompt, schema, model_config, timeout_seconds):
        self.payloads.append(prompt)
        return self.results.pop(0) if self.results else {}


def blueprint(name: str = "Teakwood Studio") -> BusinessBlueprint:
    return BusinessBlueprint(
        business_id=uuid4(),
        identity={"display_name": Fact(value=name, source="PLATFORM", confirmation="confirmed")},
        remaining_questions=list(QUESTIONS),
    )


# ----------------------------------------------------------- rich first answer

RICH = (
    "We run a small furniture store in Coimbatore. Mostly custom wardrobes and sofas. "
    "People usually WhatsApp us and come to the showroom. We can deliver around the city."
)


@pytest.mark.asyncio
async def test_one_rich_answer_fills_everything_and_asks_nothing_already_known():
    model = Fixture({
        "language": "en",
        "facts": [
            {"field": "description", "quote": "We run a small furniture store in Coimbatore."},
            {"field": "offerings", "quote": "Mostly custom wardrobes and sofas."},
            {"field": "customer_actions", "quote": "People usually WhatsApp us and come to the showroom."},
            {"field": "locations", "quote": "Coimbatore"},
            {"field": "operational_characteristics", "quote": "We can deliver around the city."},
        ],
        "operating_patterns": [
            {"pattern": "made_to_order", "quote": "custom wardrobes"},
            {"pattern": "walk_in", "quote": "come to the showroom"},
            {"pattern": "delivery", "quote": "We can deliver around the city."},
        ],
        "acknowledgement": "Okay — custom wardrobes and sofas.",
        "next_question_field": "phone",
        "next_question": "Which number should customers WhatsApp?",
    })
    bp = await Engine.turn(blueprint(), RICH, provider=model)

    assert bp.completion_state.sufficient
    assert {"description", "offerings", "customer_actions", "locations"} <= set(bp.unconfirmed_facts)
    assert {p.pattern for p in bp.operating_patterns} == {"made_to_order", "walk_in", "delivery"}
    reply = bp.messages[-1].text
    # It moves straight on to the optional contact number, not "what do you sell?".
    assert reply == "Okay — custom wardrobes and sofas. Which number should customers WhatsApp?"
    assert "phone" in bp.asked_optional
    for known in ("What do you mainly sell", "Where are you based", "what should they be able to do"):
        assert known not in reply


@pytest.mark.asyncio
async def test_the_model_sees_compact_state_and_what_is_still_worth_asking():
    model = Fixture({})
    bp = blueprint()
    bp.unconfirmed_facts["description"] = Fact(value="A bakery", source="USER_STATEMENT")
    await Engine.turn(bp, "We sell cakes", provider=model)
    payload = model.payloads[0]
    assert '"ask_order": ["offerings", "customer_actions", "locations", "phone", "logo"]' in payload
    assert "A bakery" in payload


# ------------------------------------------------------------- Tamil + English

TANGLISH = "Naan Chennai-la furniture business run panren. Mainly custom wardrobes, sofas and dining tables."


@pytest.mark.asyncio
async def test_a_tanglish_owner_is_answered_in_tanglish_even_without_model_phrasing():
    model = Fixture({
        "language": "ta_en",
        "facts": [
            {"field": "description", "quote": "Naan Chennai-la furniture business run panren."},
            {"field": "offerings", "quote": "Mainly custom wardrobes, sofas and dining tables."},
        ],
        "acknowledgement": "Seri, custom wardrobes dhaan main.",
        # A phrasing for the wrong field is discarded; the template is used.
        "next_question_field": "locations",
        "next_question": "Enga irukeenga?",
    })
    bp = await Engine.turn(blueprint(), TANGLISH, provider=model)
    assert bp.language_style == "ta_en"
    reply = bp.messages[-1].text
    assert reply.startswith("Seri, custom wardrobes dhaan main.")
    assert reply.endswith(TEMPLATES["customer_actions"]["ta_en"])


@pytest.mark.asyncio
async def test_switching_back_to_english_is_followed():
    model = Fixture(
        {"language": "ta_en", "facts": [{"field": "description", "quote": "Furniture kadai"}]},
        {"language": "en", "facts": [{"field": "offerings", "quote": "sofas and beds"}]},
    )
    bp = await Engine.turn(blueprint(), "Furniture kadai", provider=model)
    bp = await Engine.turn(bp, "We sell sofas and beds", provider=model)
    assert bp.language_style == "en"
    assert bp.messages[-1].text.endswith(TEMPLATES["customer_actions"]["en"])


# ------------------------------------------------------ gradual understanding


@pytest.mark.asyncio
async def test_a_business_explained_over_five_turns_builds_one_blueprint():
    model = Fixture(
        {"facts": [{"field": "description", "quote": "I run a food business."}]},
        {"facts": [{"field": "offerings", "quote": "Mostly homemade Tamil meals."}]},
        {"facts": [{"field": "operating_model", "quote": "Customers order one day before."}],
         "intents": [{"intent": "orders", "original_request": "Customers order one day before."}]},
        {"facts": [{"field": "operational_characteristics", "quote": "Delivery around Anna Nagar."}]},
        {"facts": [{"field": "offerings", "quote": "weekly lunch subscriptions for offices", "mode": "add"}],
         "operating_patterns": [{"pattern": "b2b", "quote": "for offices"},
                                {"pattern": "subscription_like", "quote": "weekly lunch subscriptions"}],
         "intents": [{"intent": "memberships", "original_request": "weekly lunch subscriptions for offices"}]},
    )
    bp = blueprint("Amma's Kitchen")
    for said in (
        "I run a food business.",
        "Mostly homemade Tamil meals.",
        "Customers order one day before.",
        "Delivery around Anna Nagar.",
        "Actually we also do weekly lunch subscriptions for offices.",
    ):
        bp = await Engine.turn(bp, said, provider=model)

    offerings = bp.unconfirmed_facts["offerings"].value
    # The fifth turn added to the menu; it did not erase the Tamil meals.
    assert "homemade Tamil meals" in offerings and "weekly lunch subscriptions" in offerings
    assert bp.unconfirmed_facts["operational_characteristics"].value == "Delivery around Anna Nagar."
    assert {p.pattern for p in bp.operating_patterns} == {"b2b", "subscription_like"}
    assert {i.intent for i in bp.requested_capabilities} == {"orders", "memberships"}


@pytest.mark.asyncio
async def test_a_correction_replaces_instead_of_accumulating():
    model = Fixture(
        {"facts": [{"field": "offerings", "quote": "sofas and beds"}]},
        {"facts": [{"field": "offerings", "quote": "custom wardrobes are our main product", "mode": "replace"}]},
    )
    bp = await Engine.turn(blueprint(), "We sell sofas and beds", provider=model)
    bp = await Engine.turn(bp, "Actually custom wardrobes are our main product", provider=model)
    assert bp.unconfirmed_facts["offerings"].value == "custom wardrobes are our main product"


# ---------------------------------------------------------------- highlights


@pytest.mark.asyncio
async def test_only_numbers_the_owner_said_become_highlights():
    said = "We are a 200-bed hospital with around 25 doctors and a 24-hour emergency department."
    model = Fixture({"highlights": [
        {"value": "200-bed", "label": "bed hospital", "quote": "a 200-bed hospital"},
        {"value": "25", "label": "doctors", "quote": "around 25 doctors"},
        {"value": "24-hour", "label": "emergency", "quote": "a 24-hour emergency department"},
        # Invented: nobody said 5000 patients.
        {"value": "5000", "label": "patients", "quote": "5000 happy patients"},
        # Mislabelled: the number is real, the label is not from the sentence.
        {"value": "25", "label": "awards", "quote": "around 25 doctors"},
        # A price is never a highlight.
        {"value": "500", "label": "consultation", "quote": "consultation Rs 500"},
    ]})
    bp = await Engine.turn(blueprint("Meridian Hospital"), said, provider=model)
    assert [(h.value, h.label) for h in bp.highlights] == [
        ("200-bed", "bed hospital"), ("25", "doctors"), ("24-hour", "emergency"),
    ]


# ------------------------------------------------------------ reply governance


@pytest.mark.parametrize("ack", [
    "Wonderful! That's amazing.",
    "Great, I'll set up delivery tracking for you.",
    "We can enable bookings.",
    "Got it — 500 happy customers.",
    "Nice. Which module do you want?",
])
def test_flattery_promises_invented_numbers_and_jargon_are_rejected(ack):
    assert govern_acknowledgement(ack, "We make sofas in Chennai") is None


def test_a_plain_acknowledgement_in_the_owners_words_is_kept():
    assert govern_acknowledgement("Seri, got it.", "x") == "Seri, got it."
    assert govern_acknowledgement("Okay — 3 branches in Chennai.", "we have 3 branches") is not None


@pytest.mark.parametrize("question", [
    "What offerings do you have?",  # jargon
    "Where are you? And your number?",  # two questions
    "We'll set up bookings — which days?",  # promise
])
def test_bad_question_phrasings_fall_back_to_the_template(question):
    assert govern_question(question, "x") is None


@pytest.mark.asyncio
async def test_off_topic_is_redirected_without_answering_or_recording_anything():
    model = Fixture({"off_topic": True, "acknowledgement": "India won by 5 wickets."})
    bp = await Engine.turn(blueprint(), "Who won yesterday's cricket match?", provider=model)
    reply = bp.messages[-1].text
    assert "wickets" not in reply and "India" not in reply
    assert reply.startswith("Let's stay with setting up your business.")
    assert not bp.unconfirmed_facts


# -------------------------------------------------------------- optional asks


def test_optional_questions_are_asked_once_and_only_after_the_essentials():
    bp = blueprint()
    assert next_ask(bp) == "description"
    bp.unconfirmed_facts.update({
        k: Fact(value=k, source="USER_STATEMENT")
        for k in ("description", "offerings", "customer_actions")
    })
    assert ask_order(bp) == ["locations", "phone", "logo"]
    bp.asked_optional = ["locations", "phone"]
    assert next_ask(bp) == "logo"
    bp.asked_optional.append("logo")
    assert next_ask(bp) == "none"


@pytest.mark.asyncio
async def test_saying_yes_to_a_logo_queues_one_request_and_nothing_runs_now():
    model = Fixture({"asset_request": "generate_logo", "acknowledgement": "Seri."})
    bp = await Engine.turn(blueprint(), "Illa, logo illa. Neenga create pannunga.", provider=model)
    assert [(r.role, r.status) for r in bp.media_generation_requests] == [("logo", "requested")]
    assert bp.logo_state == "generation_requested"
    bp = await Engine.turn(bp, "Yes make a logo", provider=Fixture({"asset_request": "generate_logo"}))
    assert len(bp.media_generation_requests) == 1


def test_product_speak_questions_fall_back_to_plain_ones():
    from platform_core.interview.conversation import govern_question

    live = "What actions should visitors be able to take on your website?"
    assert govern_question(live, heard="We make furniture.") is None
    plain = "Do people mostly call you, WhatsApp you, or come to the shop?"
    assert govern_question(plain, heard="We make furniture.") == plain
