"""Business-type module recommendations must be actionable, not just present.

The onboarding flow shows `module_seeds` for the chosen business type and lets
the owner claim them with `POST /v1/b/{id}/modules/{module_id}/enable`. That
only works if every seeded `module_id` is a real module in `ModuleRegistry`.

Before this guard, all 14 profiles referenced ids that did not exist —
`catalog-orders`, `booking-calendar`, `appointments`, `delivery`, `crm` — so
3 of the 5 retail recommendations returned 403 ENTITLEMENT_REQUIRED when
claimed. The data looked right and was unusable. These tests are pure
in-process registry checks (no DB, no network) so the drift can never come
back silently.
"""

from __future__ import annotations

from platform_core.business_type_profiles import BusinessTypeProfileRegistry
from platform_core.business_types import SUPPORTED_BUSINESS_TYPES
from platform_core.entitlements.module_registry import _MODULES

_REAL_MODULE_IDS = set(_MODULES)


def test_every_seeded_module_id_exists_in_the_registry() -> None:
    broken: dict[str, list[str]] = {}
    for type_id in sorted(SUPPORTED_BUSINESS_TYPES):
        profile = BusinessTypeProfileRegistry.get_or_default(type_id)
        missing = [
            seed.module_id
            for seed in profile.module_seeds
            if seed.module_id not in _REAL_MODULE_IDS
        ]
        if missing:
            broken[type_id] = missing
    assert not broken, f"business types recommending non-existent modules: {broken}"


def test_navigation_emphasis_modules_exist_too() -> None:
    broken: dict[str, list[str]] = {}
    for type_id in sorted(SUPPORTED_BUSINESS_TYPES):
        profile = BusinessTypeProfileRegistry.get_or_default(type_id)
        for group in profile.navigation.groups:
            missing = [
                mid
                for mid in group.get("emphasis_modules", [])
                if mid not in _REAL_MODULE_IDS
            ]
            if missing:
                broken[f"{type_id}/{group.get('id')}"] = missing
    assert not broken, f"navigation groups emphasising non-existent modules: {broken}"


def test_seed_ranks_are_contiguous_and_ids_unique() -> None:
    """Ranks drive the display order of recommendations; gaps or duplicate
    module ids would render a confusing or repeated list."""
    for type_id in sorted(SUPPORTED_BUSINESS_TYPES):
        profile = BusinessTypeProfileRegistry.get_or_default(type_id)
        ids = [seed.module_id for seed in profile.module_seeds]
        ranks = sorted(seed.rank for seed in profile.module_seeds)
        assert len(set(ids)) == len(ids), f"{type_id}: duplicate module ids {ids}"
        assert ranks == list(range(1, len(ids) + 1)), f"{type_id}: non-contiguous ranks {ranks}"


def test_every_business_type_recommends_at_least_one_optional_module() -> None:
    """A recommendation list of only always-on core modules gives the owner
    nothing to claim — onboarding's claim step would be empty."""
    for type_id in sorted(SUPPORTED_BUSINESS_TYPES):
        profile = BusinessTypeProfileRegistry.get_or_default(type_id)
        optional = [
            seed.module_id
            for seed in profile.module_seeds
            if _MODULES[seed.module_id].module_class == "optional"
        ]
        assert optional, f"{type_id}: recommends no optional (claimable) modules"
