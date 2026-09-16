"""Doc 12 §12.7 — website generation questionnaire (pure, no DB)."""

from __future__ import annotations

import pytest
from platform_core.exceptions import ValidationError
from platform_core.website.questionnaire import (
    UNIVERSAL_QUESTIONS,
    build_intake_brief,
    get_questionnaire,
    validate_intake,
)


def test_every_universal_question_is_optional_with_an_example() -> None:
    for q in UNIVERSAL_QUESTIONS:
        assert q["optional"] is True, q["id"]
        assert q.get("example"), q["id"]


def test_get_questionnaire_is_business_type_aware() -> None:
    salon = get_questionnaire("salon")
    assert [s["id"] for s in salon["sections"]] == ["universal", "type_specific"]
    assert salon["sections"][1]["questions"][0]["id"] == "services"

    unknown = get_questionnaire("wat")
    assert unknown["business_type"] == "not_sure"
    assert [s["id"] for s in unknown["sections"]] == ["universal"]  # no type block


def test_validate_intake_clamps_and_drops_empties() -> None:
    out = validate_intake(
        "restaurant",
        {
            "lead_with": "offerings",
            "words_prefer": "  hand-rolled  ",
            "skip_me": "",
            "menu_items": [
                {"name": "Dosa", "description": "crisp"},
                {"name": "", "description": ""},  # fully empty row dropped
            ],
            "tone": {"warm_minimal": 20, "playful_serious": 80},
        },
    )
    assert out["words_prefer"] == "hand-rolled"
    assert "skip_me" not in out
    assert out["menu_items"] == [{"name": "Dosa", "description": "crisp"}]
    assert out["tone"] == {"warm_minimal": 20, "playful_serious": 80}


def test_validate_intake_rejects_unsafe_content() -> None:
    with pytest.raises(ValidationError):
        validate_intake("cafe", {"words_prefer": "<script>alert(1)</script>"})
    with pytest.raises(ValidationError):
        validate_intake("cafe", {"hours": "visit https://evil.example"})


def test_validate_intake_caps_repeatable_rows() -> None:
    out = validate_intake(
        "retail",
        {"products": [{"name": f"P{i}"} for i in range(100)]},
    )
    assert len(out["products"]) == 30


def test_build_intake_brief_only_mentions_answered_fields() -> None:
    assert build_intake_brief({}, None) == ""
    assert build_intake_brief({}, {}) == ""

    brief = build_intake_brief(
        {},
        {
            "lead_with": "story",
            "palette": "sage",
            "words_avoid": "cheap",
            "menu_items": [{"name": "Ragi dosa", "description": "stone-ground"}],
        },
    )
    assert "Lead the home page with: story" in brief
    assert "Sage & brass" in brief
    assert "Do NOT use these words: cheap" in brief
    assert "Ragi dosa" in brief
    assert "Services" not in brief  # not answered
