"""Registered event subscribers.

Importing this package registers every subscriber. `registry.load_subscribers()`
does that import once; nothing else needs to.

To add a subscriber: create a module here, decorate the handler with
`@subscribe(...)`, and import the module below. That is the whole wiring — no
change to the publisher, the outbox, or the worker.
"""

from __future__ import annotations

from platform_core.events.subscribers import (  # noqa: F401  (registration side effects)
    automation_triggers,
    compliance_due,
    customer_activity,
    fulfilment_cancellation,
    inventory_expiry,
    invoicing_auto,
    marketplace_index,
    memberships_engine,
    messaging_notify,
    queue_turn,
    reviews_invite,
    task_events,
)

__all__ = ["automation_triggers", "compliance_due", "customer_activity", "fulfilment_cancellation", "inventory_expiry", "invoicing_auto",
           "marketplace_index", "memberships_engine", "messaging_notify", "queue_turn", "reviews_invite",
           "task_events"]
