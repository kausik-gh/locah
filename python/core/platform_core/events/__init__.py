"""Domain events: the catalogue of what can be published and who consumes it.

Capabilities communicate by publishing events through
`platform_core.services.outbox.OutboxService.publish` and by registering
subscribers here — never by importing each other's services.
"""

from platform_core.events.catalogue import (
    KNOWN_EVENT_TYPES,
    UnknownEventType,
    assert_known_event_type,
    is_known_event_type,
    owner_of,
)
from platform_core.events.registry import (
    EventContext,
    EventSubscriber,
    PermanentEventError,
    all_subscribers,
    get_subscriber,
    register,
    subscribe,
    subscribers_for,
)

__all__ = [
    "KNOWN_EVENT_TYPES",
    "EventContext",
    "EventSubscriber",
    "PermanentEventError",
    "UnknownEventType",
    "all_subscribers",
    "assert_known_event_type",
    "get_subscriber",
    "is_known_event_type",
    "owner_of",
    "register",
    "subscribe",
    "subscribers_for",
]
