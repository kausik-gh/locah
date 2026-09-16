"""Canonical capability gates (Document 12 §8.9).

Each failed gate raises a distinct PlatformError code so Entitlement, module
state, Location, permission, and resource state remain independently enforceable.
"""

from __future__ import annotations

from collections.abc import Collection

from platform_core.exceptions import ResourceStateDenied

# Business lifecycle states that still permit ordinary mutations (Stage 1).
BUSINESS_MUTABLE_STATES: frozenset[str] = frozenset(
    {"draft", "onboarding", "active", "dormant"}
)

# Switching into a Business uses the same operable lifecycle set (not closed).
BUSINESS_SWITCHABLE_STATES: frozenset[str] = BUSINESS_MUTABLE_STATES


def assert_resource_allows(
    *,
    resource: str,
    current_state: str,
    allowed_states: Collection[str],
    action: str | None = None,
) -> None:
    """Gate [9]: resource/workflow state must permit the requested action."""
    allowed = frozenset(allowed_states)
    if current_state not in allowed:
        raise ResourceStateDenied(
            resource,
            current_state,
            action=action,
            allowed_states=sorted(allowed),
        )


def assert_business_mutable(state: str, *, action: str = "update") -> None:
    """Stage 1 resource gate over the Business lifecycle resource."""
    assert_resource_allows(
        resource="business",
        current_state=state,
        allowed_states=BUSINESS_MUTABLE_STATES,
        action=action,
    )


def assert_business_switchable(state: str) -> None:
    """Resource gate for entering/switching Business context."""
    assert_resource_allows(
        resource="business",
        current_state=state,
        allowed_states=BUSINESS_SWITCHABLE_STATES,
        action="switch",
    )


# Platform standing that blocks new commercial intake (Doc 04 §6.1).
# `under_review` is deliberately NOT here: Doc 04 §6.1 says a Business under
# review "may still operate but is flagged". Only `suspended` blocks.
COMMERCIAL_INTAKE_BLOCKING_STATUSES: frozenset[str] = frozenset({"suspended"})


def assert_business_accepts_commerce(status: str, *, action: str = "create") -> None:
    """Doc 04 §6.1: a suspended Business "cannot receive orders".

    Applies to *intake* only — creating orders, bookings, and payment attempts.
    Deliberately NOT applied to lifecycle transitions on work that already
    exists: a suspended Business must still be able to complete, cancel, and
    refund what its customers already paid for, or suspension would strand
    those customers rather than the Business.

    This is the standing axis (`status`), independent of the lifecycle axis
    (`state`) checked by `assert_business_mutable` — both can apply.
    """
    from platform_core.exceptions import BusinessSuspended

    if status in COMMERCIAL_INTAKE_BLOCKING_STATUSES:
        raise BusinessSuspended(action=action)
