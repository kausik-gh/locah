"""Website edits, read from what the owner says — deterministic, no model."""

from __future__ import annotations

from uuid import uuid4

import pytest

from platform_core.interview import website_edits as we
from platform_core.interview.models import BusinessBlueprint, CatalogueGroup, CatalogueItem, Fact


@pytest.mark.parametrize("text, field, value", [
    ("Make the website warmer", "feel", "warmer"),
    ("Can it be a bit darker?", "feel", "darker"),
    ("make it more premium", "feel", "premium"),
    ("Don't show prices", "prices", "hidden"),
    ("please hide the prices", "prices", "hidden"),
    ("say price on request", "prices", "on_request"),
    ("Show our prices", "prices", "show"),
    ("Put delivery higher", "lead", "fulfilment_strip"),
    ("move our story to the top", "lead", "about"),
    ("That isn't our story", "story_reset", True),
    ("Use this photo first", "photo_first", True),
    ("Change the headline to Fresh cuts, every morning", "headline", "Fresh cuts, every morning"),
])
def test_what_the_owner_asks_is_read_as_one_typed_edit(text, field, value) -> None:
    assert getattr(we.read(text), field) == value


def test_plain_business_talk_is_not_a_website_edit() -> None:
    for text in ("We deliver around Adyar", "9876543210", "Our hours are 9 to 9", "Thanks!"):
        assert not we.read(text).any(), text


def test_a_new_item_goes_where_it_belongs() -> None:
    bp = BusinessBlueprint(business_id=uuid4(),
                           identity={"display_name": Fact(value="X", source="PLATFORM", confirmation="confirmed")})
    bp.taxonomy.groups = [CatalogueGroup(name="Chicken"),
                          CatalogueGroup(name="Fish & Seafood", items=[CatalogueItem(name="Crab")])]
    done = we.apply(bp, we.read("We also sell prawns and country chicken"))
    seafood = next(g for g in bp.taxonomy.groups if g.name == "Fish & Seafood")
    assert "Prawns" in [i.name for i in seafood.items]
    assert any(d.startswith("add:Prawns:Fish & Seafood") for d in done)
    assert we.reply(done, bp).startswith("Done — added Prawns to Fish & Seafood")


def test_the_story_is_asked_for_and_then_taken() -> None:
    bp = BusinessBlueprint(business_id=uuid4())
    done = we.apply(bp, we.read("That's not our story"))
    assert bp.website_prefs.awaiting_story and "story:reset" in done
    assert "What would you like people to know" in we.reply(done, bp)
    assert not we.take_story(bp, "ok")  # too short to be a story
    assert we.take_story(bp, "We have cut meat fresh every morning for eight years.")
    assert bp.website_draft.about and bp.website_draft.about.provenance == "owner_edited"
