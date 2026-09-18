"""The domain event catalogue — every event type the platform may publish.

This list used to live in the worker as `KNOWN_HANDLERS`, where it did two
unrelated jobs badly: it was named for handlers but contained no handlers, and
it was consulted hours after publication, so a typo'd event type surfaced as a
dead letter attributed to the worker rather than to the code that emitted it.

It is now checked at publish time, in the emitting transaction, where the
mistake is attributable. Membership here says only "this is a real event type"
— not that anything consumes it. Who consumes what lives in
`platform_core.events.registry`, and most of these have no subscriber at all.

Adding an event type is deliberately a one-line edit here. That is the only
central edit a new capability needs; it does not touch the worker.
"""

from __future__ import annotations

# Grouped by the capability that owns the event. An owner may publish only the
# events in its own group.
_CATALOGUE: dict[str, frozenset[str]] = {
    "business": frozenset(
        {
            "business.created",
            "business.initialized",
            "business.settings.updated",
            "business.profile.updated",
            "business.branding.updated",
            "business.preferences.updated",
            "business.visibility.changed",
            "business.suspended",
            "business.context_switched",
            "business.override.updated",
            "business_type.changed",
        }
    ),
    "membership": frozenset(
        {
            "membership.created",
            "membership.updated",
            "membership.suspended",
            "membership.reactivated",
            "membership.removed",
            "ownership.transferred",
            "role.changed",
        }
    ),
    "invitation": frozenset(
        {
            "invitation.created",
            "invitation.resent",
            "invitation.accepted",
            "invitation.declined",
            "invitation.revoked",
            "invitation.expired",
        }
    ),
    "configuration": frozenset(
        {
            "configuration.resolved",
            "configuration.profile.updated",
            "entitlement.updated",
            "module.enabled",
            "module.disabled",
            "module.deactivated",
            "feature.enabled",
            "feature.disabled",
        }
    ),
    "authorization": frozenset(
        {
            "permission.granted",
            "permission.override.created",
            "permission.override.removed",
            "authorization.snapshot.updated",
        }
    ),
    "location": frozenset(
        {
            "location.created",
            "location.updated",
            "location.archived",
        }
    ),
    "employee": frozenset(
        {
            "employee.created",
            "employee.updated",
            "employee.deactivated",
            "employee.assigned",
            "employee.unassigned",
            "employee.transferred",
        }
    ),
    "customer": frozenset(
        {
            "customer.created",
            "customer.updated",
            "customer.blocked",
            "customer.archived",
            "customer.restored",
            "customer.tagged",
            "customer.note.created",
        }
    ),
    "catalogue": frozenset(
        {
            "product_category.created",
            "product_category.updated",
            "product_category.archived",
            "offering.created",
            "offering.updated",
            "offering.archived",
            "offering.restored",
            "offering.variant.created",
        }
    ),
    "inventory": frozenset(
        {
            "inventory.stock.updated",
            "inventory.stock.low",
            "inventory.stock.zero",
            "inventory.stock.replenished",
            "inventory.adjusted",
            "inventory.opening_stock.set",
        }
    ),
    "order": frozenset(
        {
            "order.created",
            "order.updated",
            "order.accepted",
            "order.preparing",
            "order.ready",
            "order.completed",
            "order.cancelled",
            "order.rejected",
            "order.note.created",
        }
    ),
    "booking": frozenset(
        {
            "booking.created",
            "booking.updated",
            "booking.confirmed",
            "booking.rejected",
            "booking.checked_in",
            "booking.completed",
            "booking.cancelled",
            "booking.rescheduled",
            "booking.no_show",
            "booking.note.created",
            "booking.deposit_collected",
            "booking.policy_updated",
            "bookings.resource.created",
            "bookings.resource.updated",
            "bookings.resource.archived",
        }
    ),
    "workforce": frozenset(
        {
            "workforce.member_created",
            "workforce.member_updated",
            "workforce.location_assigned",
            "workforce.location_unassigned",
            "workforce.service_associated",
            "workforce.availability_updated",
        }
    ),
    "payment": frozenset(
        {
            "payment.initiated",
            "payment.completed",
            "payment.failed",
            "payment.refunded",
            "payment.updated",
            "payment.webhook_processed",
            "payment.merchant.updated",
        }
    ),
    "website": frozenset(
        {
            "website.draft_generated",
            "website.published",
            "website.generation_failed",
        }
    ),
    "marketplace": frozenset(
        {
            "marketplace.indexed",
            "marketplace.index_failed",
            "marketplace.deindexed",
            "marketplace.reindex_triggered",
        }
    ),
    "fulfilment": frozenset(
        {
            "fulfilment.job_created",
            "fulfilment.status_changed",
            "fulfilment.failed",
            "fulfilment.delivered",
            "fulfilment.zone_configured",
            "fulfilment.settings_updated",
        }
    ),
    "lead": frozenset(
        {
            "lead.created",
            "lead.updated",
            "lead.assigned",
            "lead.deleted",
            "lead.stage_changed",
            "lead.contacted",
            "lead.qualified",
            "lead.won",
            "lead.lost",
            "lead.note.created",
        }
    ),
    "quote": frozenset(
        {
            "quote.created",
            "quote.updated",
            "quote.issued",
            "quote.accepted",
            "quote.rejected",
            "quote.expired",
            "quote.cancelled",
            "quote.revised",
            "quote.converted",
        }
    ),
    "membership_plan": frozenset(
        {
            "membership.plan.created",
            "membership.plan.updated",
            "membership.plan.archived",
            "membership.enrolled",
            "membership.enrolment.updated",
            "membership.enrolment.activated",
            "membership.enrolment.paused",
            "membership.enrolment.expired",
            "membership.enrolment.cancelled",
            "membership.enrolment.completed",
        }
    ),
}

KNOWN_EVENT_TYPES: frozenset[str] = frozenset().union(*_CATALOGUE.values())

EVENT_OWNERS: dict[str, str] = {
    event_type: owner for owner, events in _CATALOGUE.items() for event_type in events
}


class UnknownEventType(ValueError):
    """An event type that is not in the catalogue — almost always a typo."""


def is_known_event_type(event_type: str) -> bool:
    return event_type in KNOWN_EVENT_TYPES


def assert_known_event_type(event_type: str) -> None:
    if event_type not in KNOWN_EVENT_TYPES:
        raise UnknownEventType(
            f"Unknown domain event type {event_type!r}. Add it to "
            "platform_core.events.catalogue before publishing it."
        )


def owner_of(event_type: str) -> str | None:
    return EVENT_OWNERS.get(event_type)
