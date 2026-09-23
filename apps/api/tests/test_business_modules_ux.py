"""Available versus recommended: two different claims, kept apart.

Available comes from the canonical module registry and entitlement. Recommended
needs evidence from what the owner said, and says so in their words. Neither
is active, and neither is mandatory.
"""

from __future__ import annotations

from uuid import uuid4

from platform_core.entitlements.models import FeatureState, ModuleState, ResolvedEntitlement
from platform_core.entitlements.module_registry import ModuleRegistry
from platform_core.interview.capabilities import (
    INTENTS,
    available_modules,
    because,
    resolve_recommendations,
)
from platform_core.interview.models import BusinessBlueprint, CapabilityIntent, Fact


def entitled(active: bool = False) -> ResolvedEntitlement:
    modules = {row["module_id"] for row in ModuleRegistry.list_modules()}
    features = {
        fid: FeatureState(fid, mid, True, True, "test")
        for mid in modules
        for fid in ModuleRegistry.get(mid).features
    }
    state = "active" if active else "inactive"
    return ResolvedEntitlement(
        str(uuid4()), "test", "1", "1", "other", frozenset(modules), frozenset(features),
        {mid: ModuleState(mid, True, state, True, True, "test") for mid in modules},
        features, {}, {}, 1,
    )


def owner_said(**facts: str) -> BusinessBlueprint:
    bp = BusinessBlueprint(business_id=uuid4(), identity={
        "display_name": Fact(value="Apex Industrial Supplies", source="PLATFORM", confirmation="confirmed"),
    })
    bp.known_facts = {k: Fact(value=v, source="USER_STATEMENT", confirmation="confirmed") for k, v in facts.items()}
    return bp


def test_every_intent_names_a_real_registry_module():
    for intent, (module, _label, _pattern) in INTENTS.items():
        assert ModuleRegistry.get(module) is not None, intent


def test_a_b2b_supplier_asking_for_quotes_is_recommended_quotations():
    bp = owner_said(
        description="We supply industrial pumps and valves to factories.",
        customer_actions="Factories should be able to request a quote for bulk orders.",
    )
    resolve_recommendations(bp, entitled())
    recommended = {item.module_id: item for item in bp.recommended_modules}
    assert "quotes" in recommended
    assert recommended["quotes"].reason.startswith("Because you said “Factories should be able to request a quote")


def test_the_reason_is_the_owners_words_not_a_restated_label():
    bp = owner_said(description="Hospital", customer_actions="Patients should book appointments online.")
    bp.requested_capabilities = [
        CapabilityIntent(intent="bookings", original_request="Patients should book appointments online.")
    ]
    resolve_recommendations(bp, entitled())
    booking = next(item for item in bp.recommended_modules if item.module_id == "bookings")
    assert booking.reason.startswith("Because you said “Patients should book appointments online”.")
    assert booking.strength == "strong"
    assert booking.evidence[0].kind == "owner_said"


def test_available_comes_from_the_registry_and_excludes_what_is_recommended():
    bp = owner_said(description="Furniture", customer_actions="Send us an enquiry.")
    resolve_recommendations(bp, entitled())
    available = available_modules(bp, entitled())
    ids = [item.module_id for item in available]
    optional = {row["module_id"] for row in ModuleRegistry.list_modules() if row["module_class"] == "optional"}
    recommended = {item.module_id for item in bp.recommended_modules}
    assert set(ids) == optional - recommended
    # Nothing core, nothing already recommended, nothing listed twice.
    assert not any(module.startswith("core-") for module in ids)
    assert len(ids) == len(set(ids))
    # Customer-facing tools come before back-office ones.
    groups = [item.group for item in available]
    assert groups == sorted(groups, key=lambda g: g != "customer")
    assert {"quotes", "projects"} <= set(ids)


def test_available_is_never_active_and_choice_starts_pending():
    bp = owner_said(description="Salon")
    for item in available_modules(bp, entitled(active=False)):
        assert item.status != "SUPPORTED"
        assert item.choice == "pending"


def test_long_quotes_are_trimmed_on_a_word_boundary():
    reason = because("word " * 60)
    assert reason.endswith("…”.") and len(reason) < 140
