"""Unit tests for type-aware image prompts. No live xAI network."""

from platform_core.website.image_generation import (
    family_for_business_type,
    hero_prompt,
    offering_prompt,
)


def test_restaurant_and_gym_hero_prompts_diverge() -> None:
    food = hero_prompt(
        display_name="Ragi House",
        business_type="restaurant",
        description="Millet kitchen",
    )
    gym = hero_prompt(
        display_name="Iron Hall",
        business_type="gym",
        description="Strength studio",
    )
    assert "restaurant" in food.lower() or "food" in food.lower() or "dining" in food.lower()
    assert "gym" in gym.lower() or "studio" in gym.lower() or "equipment" in gym.lower()
    assert food != gym
    assert "No text" in food


def test_offering_prompt_uses_the_item_title() -> None:
    prompt = offering_prompt(
        display_name="Ragi House",
        business_type="restaurant",
        title="Ragi dosa",
        description="Crisp, served with sambar",
    )
    assert "Ragi dosa" in prompt
    assert family_for_business_type("restaurant") == "food"
    assert family_for_business_type("hotel") == "stay"
