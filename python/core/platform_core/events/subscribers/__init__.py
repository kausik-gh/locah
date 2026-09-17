"""Registered event subscribers.

Importing this package registers every subscriber. `registry.load_subscribers()`
does that import once; nothing else needs to.

To add a subscriber: create a module here, decorate the handler with
`@subscribe(...)`, and import the module below. That is the whole wiring — no
change to the publisher, the outbox, or the worker.
"""

from __future__ import annotations

from platform_core.events.subscribers import (  # noqa: F401  (registration side effects)
    fulfilment_cancellation,
    marketplace_index,
)

__all__ = ["fulfilment_cancellation", "marketplace_index"]
