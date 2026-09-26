"""Phase A regressions: every answer keeps its meaning, and Build never disappears.

The transcript below is the real "Wift" interview from staging (24 Sep 2026),
replayed turn by turn with the model unreachable — the condition it ran in.
Then its fallback filed each answer under a *different* question:

    "GYm equipment, available trainers, dumbells,contact section" -> customer actions
    "All india" (delivery areas)            -> opening hours
    "Freshness and energy" (the story)      -> phone number
    "fixed" (packs or weight?)              -> location

and after 25 turns it had never offered to build. No AI provider is called here.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from platform_core.catalog.taxonomy import search
from platform_core.interview.corrections import CorrectionError, apply_correction
from platform_core.interview.coverage import floor_met
from platform_core.interview.models import BusinessBlueprint, CategorySeed, Fact
from platform_core.interview.orchestrator import BusinessInterviewOrchestrator as Engine
from platform_core.interview.understanding import customer_actions, understanding


class Down:
    """The model cannot be reached — as on staging that day."""

    provider_name = "down"
    model_name = "down"
    last_usage = None

    async def generate_structured(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("provider unavailable")


class Model:
    provider_name = "fixture"
    model_name = "fixture"
    last_usage = {"prompt_tokens": 1, "completion_tokens": 1}

    def __init__(self, answer: dict[str, Any]) -> None:
        self.answer = answer

    async def generate_structured(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return self.answer


def blueprint(name: str = "Wift", category: CategorySeed | None = None) -> BusinessBlueprint:
    bp = BusinessBlueprint(
        business_id=uuid4(),
        identity={"display_name": Fact(value=name, source="PLATFORM", confirmation="confirmed")},
        category=category,
    )
    Engine.open(bp)
    return bp


WIFT = [
    "Wift is a gym app, which allows user to track their exercises by adding exercies to routines.\n"
    "See analytics of their workouts and track their weights and stuff.",
    "See the analytics about weight,streak and all.\nthen they mut be able to start workouts.\nAnd add exercies",
    "They must be able to order a equipment, book slots for trainsers, call",
    "GYm equipment, available trainers, dumbells,contact section",
    "fixed",
    "Freshness and energy",
    "only deliver",
    "All india",
    "No, just this much",
    "Build it",
]


@pytest.mark.asyncio
async def test_the_wift_answers_keep_their_meaning_with_the_model_down() -> None:
    bp = blueprint()
    for text in WIFT:
        bp = await Engine.turn(bp, text, provider=Down(), business_type="not_sure")
    facts = {**bp.known_facts, **bp.unconfirmed_facts}
    # A delivery area is never opening hours; a slogan is never a phone number;
    # an answer about packs is never a place.
    assert "opening_hours" not in facts
    assert "phone" not in facts
    assert "fixed" not in facts.get("locations", Fact(value="", source="PLATFORM")).value
    panel = understanding(bp, "not_sure")
    assert panel["contact"] == {"location": "", "phone": "", "hours": ""}
    # What customers can do is only ever what customers do.
    labels = " ".join(a["label"] for a in panel["actions"]).lower()
    for thing in ("equipment", "dumbbell", "dumbell", "trainer", "contact section"):
        assert thing not in labels
    assert set(customer_actions(bp)) <= {"order_online", "book_online", "call"}
    # "contact section" is a part of the website the owner wants.
    assert "Contact section" in bp.content_wishes
    # Enough for a first version long before 25 turns — and "Build it" opens the summary.
    assert bp.readiness.ready
    assert bp.checkpoint_turn is not None and bp.checkpoint_turn <= 7
    assert bp.confirm_requested
    # Never the same question twice in a row, never more than the budget.
    asks = [a.ask for a in bp.asks if a.ask not in {"opening", "free"}]
    assert all(a != b for a, b in zip(asks, asks[1:]))
    assert len(asks) <= 7


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "text"),
    [("opening_hours", "All india"), ("phone", "Freshness and energy"), ("locations", "fixed"),
     ("customer_actions", "GYm equipment, available trainers, dumbells,contact section")],
)
async def test_a_typed_correction_of_the_wrong_kind_is_refused(field: str, text: str) -> None:
    with pytest.raises(ValueError):
        await Engine.turn(blueprint(), text, field=field, provider=Down())  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_the_model_filing_the_wrong_kind_of_thing_is_dropped() -> None:
    wrong = Model({
        "facts": [{"field": "opening_hours", "quote": "All india"},
                  {"field": "phone", "quote": "Freshness and energy"},
                  {"field": "customer_actions", "quote": "GYm equipment, available trainers, dumbells,contact section"}],
        "answered": [{"target": "operations.hours", "summary": "All india", "quote": "All india"},
                     {"target": "commerce.action", "summary": "Gym equipment",
                      "quote": "GYm equipment, available trainers, dumbells,contact section"}],
    })
    text = "GYm equipment, available trainers, dumbells,contact section. All india. Freshness and energy"
    bp = await Engine.turn(blueprint(), text, provider=wrong)
    facts = {**bp.known_facts, **bp.unconfirmed_facts}
    assert not {"opening_hours", "phone", "customer_actions"} & set(facts)
    assert bp.discovery["operations.hours"].status != "answered"
    assert understanding(bp)["actions"] == []


@pytest.mark.asyncio
async def test_build_once_offered_is_never_taken_away() -> None:
    meat = CategorySeed(category_key="fresh_grocery", subcategory_key="meat_shop", label="Meat shop")
    bp = blueprint("Ishant Proteins", meat)
    for text in ["We sell chicken, mutton and fish. People order on WhatsApp.",
                 "Chicken - curry cut, boneless. Mutton - curry cut, chops. Fish - seer, pomfret.",
                 "We deliver around Perumbakkam, people can also pick up.",
                 "Nookampalayam Road, Chennai, 8754722026"]:
        bp = await Engine.turn(bp, text, provider=Down())
    assert bp.readiness.ready and bp.completion_state.ready_at is not None
    ready_at = bp.completion_state.ready_at
    # New ways of working after that used to add "essential" questions and hide Build.
    for text in ["We also take bulk orders from restaurants and hotels.",
                 "Some customers book a slot to collect in the evening."]:
        bp = await Engine.turn(bp, text, provider=Down())
        assert bp.readiness.ready and bp.completion_state.sufficient
        assert bp.completion_state.ready_at == ready_at
        assert "?" not in bp.messages[-1].text  # after the checkpoint, no more questions unasked for


@pytest.mark.asyncio
async def test_build_it_with_too_little_asks_one_thing_first() -> None:
    bp = await Engine.turn(blueprint("Nameless"), "Build it", provider=Down())
    assert not bp.confirm_requested and not floor_met(bp)
    assert bp.messages[-1].text.count("?") == 1
    bp = await Engine.turn(bp, "We sell handmade candles and soaps.", provider=Down())
    bp = await Engine.turn(bp, "Build it", provider=Down())
    assert floor_met(bp) and bp.confirm_requested


@pytest.mark.asyncio
async def test_keep_refining_asks_the_most_useful_optional_things_one_at_a_time() -> None:
    meat = CategorySeed(category_key="fresh_grocery", subcategory_key="meat_shop", label="Meat shop")
    bp = blueprint("Ishant Proteins", meat)
    for text in ["We sell chicken and mutton by the kg. People order on WhatsApp.",
                 "Chicken - curry cut, boneless. Mutton - curry cut.",
                 "We deliver around Perumbakkam.", "Perumbakkam, Chennai. 8754722026"]:
        bp = await Engine.turn(bp, text, provider=Down())
    assert bp.readiness.ready
    bp = Engine.refine(bp)
    first = bp.asks[-1].ask
    assert first in {"photos", "story", "pricing", "payment", "hours"}
    assert bp.messages[-1].text.count("?") >= 1
    bp = await Engine.turn(bp, "No", provider=Down())
    assert bp.asks[-1].ask != first  # declined, so the next one — never the same again


def test_structured_changes_are_checked_for_their_kind() -> None:
    bp = blueprint()
    with pytest.raises(CorrectionError):
        apply_correction(bp, "hours", [], "All india")
    with pytest.raises(CorrectionError):
        apply_correction(bp, "phone", [], "Freshness and energy")
    with pytest.raises(CorrectionError):
        apply_correction(bp, "location", [], "We deliver around Perumbakkam")
    with pytest.raises(CorrectionError):
        apply_correction(bp, "actions", ["dumbbells"])
    apply_correction(bp, "hours", [], "9 am to 8 pm, Monday to Saturday")
    apply_correction(bp, "phone", [], "+91 87547 22026")
    apply_correction(bp, "location", [], "Nookampalayam Road, Chennai")
    apply_correction(bp, "actions", ["order_whatsapp", "call"])
    apply_correction(bp, "offerings", ["Chicken", "Mutton", "Fish"])
    apply_correction(bp, "fulfilment", ["delivery", "pickup"])
    apply_correction(bp, "area", [], "Perumbakkam and Sholinganallur")
    panel = understanding(bp)
    assert panel["contact"] == {"location": "Nookampalayam Road, Chennai", "phone": "+91 87547 22026",
                                "hours": "9 am to 8 pm, Monday to Saturday"}
    assert [a["id"] for a in panel["actions"]] == ["order_whatsapp", "call"]
    assert [g["name"] for g in panel["offer"]["groups"]] == ["Chicken", "Mutton", "Fish"]
    assert {"kind": "delivery", "text": "Delivery around Perumbakkam and Sholinganallur"} in panel["buying"]
    # The owner's word wins over anything extracted later.
    assert bp.known_facts["phone"].source == "USER_STATEMENT"


@pytest.mark.parametrize(
    ("typed", "expected"),
    [("meat shop", "meat_shop"), ("dentel clinic", "dental"), ("tiffin", "tiffin"),
     ("kirana", "grocery"), ("mandapam", "banquet_hall"), ("PG", "co_living"),
     ("biriyani", "biryani_shop"), ("pump supplier", "industrial_supplier"),
     ("wedding photographer", "wedding_photographer"), ("florist", "florist"),
     ("tution", "tuition_centre"), ("car detailing", "detailing")],
)
def test_the_business_kind_is_found_the_way_owners_type_it(typed: str, expected: str) -> None:
    assert search(typed)[0]["subcategory_key"] == expected
