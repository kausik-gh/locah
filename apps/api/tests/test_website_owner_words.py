"""What the real owner-flow run (tools/acceptance/stack/owner_flow_v4.py) caught.

Each case is a sentence a real owner typed that the website once got wrong.
Everything shown must come from the owner's own words — nothing invented.
"""

from __future__ import annotations

import uuid

from platform_core.interview import reader as rd
from platform_core.interview.models import BusinessBlueprint, Message, TargetState
from platform_core.interview.site_composer import (
    _area,
    _pickup_line,
    plans_from_answer,
    project_status,
    served_list,
)
from platform_core.interview.taxonomy import taxonomy_from_listing


def _bp(*said: str) -> BusinessBlueprint:
    bp = BusinessBlueprint(business_id=uuid.uuid4())
    bp.messages = [Message(role="user", text=t) for t in said]
    return bp


def test_cut_to_order_is_not_ordering_online() -> None:
    text = "We sell chicken, mutton and fish by the kg, cut fresh to order, and people order on WhatsApp."
    assert rd.read(text).actions == ["order_whatsapp"]
    assert "order_online" in rd.read("Order online or call us.").actions


def test_the_plain_listing_keeps_only_things_sold() -> None:
    names = lambda t: [g.name for g in taxonomy_from_listing(t)]  # noqa: E731
    assert names("We sell chicken, mutton and fish by the kg, cut fresh to order, and people order on "
                 "WhatsApp. We deliver around Nookampalayam and Perumbakkam") == ["Chicken", "Mutton", "Fish"]
    assert names("Our projects: Aranya Meadows, 3 and 4 BHK villas; Aranya Heights, 2 BHK flats.") == [
        "Aranya Meadows", "Aranya Heights"]
    assert names("I cook Tamil home-style food — idli, dosa batter, meals, and podi and pickles in jars.") == [
        "Idli", "Dosa batter", "Meals", "Podi", "Pickles"]


def test_a_delivery_radius_is_not_a_place() -> None:
    assert _area("Veetla vandhu pickup pannalaam, 3 km kulla naan deliver pannuven.") == "within 3 km"
    assert _area("within 5 km of Adyar") == "within 5 km of Adyar"
    assert _area("around Nookampalayam and Perumbakkam") == "Nookampalayam and Perumbakkam"


def test_a_home_kitchen_is_collected_from_home() -> None:
    bp = _bp("Naan veetla irundhu home food pannuren.")
    assert "our home" in _pickup_line(bp)


def test_plans_are_the_owners_own_numbers() -> None:
    bp = _bp()
    bp.discovery["memberships.plans"] = TargetState(
        status="answered", quote="Monthly 2500, quarterly 6500, and PT packs of 12 sessions")
    assert plans_from_answer(bp) == [{"name": "Monthly", "price": "₹2500"}, {"name": "Quarterly", "price": "₹6500"},
                                     {"name": "PT packs", "description": "12 sessions"}]
    bp.discovery["memberships.plans"] = TargetState(status="answered", quote="We have a few plans")
    assert plans_from_answer(bp) == []


def test_a_project_status_is_said_not_guessed() -> None:
    bp = _bp("Aranya Greens is ready to move, Heights is under construction, Meadows is upcoming.")
    assert [project_status(bp, n) for n in ("Aranya Greens", "Aranya Heights", "Aranya Meadows", "Aranya Vista")] \
        == ["Ready to move", "Under construction", "Upcoming", ""]


def test_who_is_served_is_not_where() -> None:
    bp = _bp()
    bp.discovery["b2b.customers"] = TargetState(
        status="answered", quote="factories and apartment builders around Chennai and Hosur")
    assert served_list(bp) == ["Factories", "Apartment builders"]


def test_a_calm_developer_still_gets_a_property_site() -> None:
    # "calm, green villa communities": the evidence of a property developer who
    # said calm — without trade priors, property must still outscore the clinic family.
    from platform_core.interview.design_system import FAMILIES

    said = {"offering=property", "journey=visit", "personality=calm", "trust=high", "energy=low"}

    def score(key: str) -> float:
        total: float = sum(w for d, w in FAMILIES[key].affinity.items() if d in said)
        return total + (2.5 if "personality=calm" in FAMILIES[key].affinity else 0)

    assert score("airy_property") > score("calm_professional")


def test_the_editor_is_offered_a_drawn_picture_only_where_one_is_honest() -> None:
    from platform_core.interview.media_director import image_policy

    def theme(arche: str) -> dict[str, object]:
        return {"creative_direction": {"archetype": arche}}

    menu, folio, homes = theme("menu_commerce"), theme("project_portfolio"), theme("real_estate_projects")
    assert image_policy(menu, "hero", "editorial_overlay") == {"self": "draw"}
    assert image_policy(menu, "about", "story_split") == {"self": "draw"}
    assert image_policy(menu, "cta_band", "image_banner") == {"self": "draw"}
    assert image_policy(menu, "category_showcase", "image_cards") == {"items": "draw"}
    assert image_policy(menu, "gallery", "masonry") == {"self": "real_photo"}  # a gallery is their own
    # Evidence: a photographer's work, a developer's named projects.
    assert image_policy(folio, "product_showcase", "service_cards") == {"items": "real_photo"}
    assert image_policy(homes, "product_showcase", "project_cards") == {"items": "real_photo"}
    assert image_policy(menu, "product_showcase", "project_cards") == {"items": "real_photo"}
    # Nothing to picture on plan cards or a contact block.
    assert image_policy(theme("membership_fitness"), "product_showcase", "plan_cards") == {}
    assert image_policy(menu, "contact", "full") == {}
