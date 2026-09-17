"""Domain event subscription registry.

A capability subscribes to the events it cares about by registering an
`EventSubscriber` here. It never imports the emitting service, and the emitting
service never learns who is listening — which is the whole point. The previous
arrangement had the worker importing `FulfilmentService` and
`MarketplaceIndexingService` directly and branching on event type inline, so
every new consumer meant editing the worker: exactly the cross-module coupling
the architecture is supposed to prevent.

Subscribers are registered at import time by `platform_core.events.subscribers`.
Nothing else should call `register()`.

Failure semantics are per subscriber:

  * returning normally      — that delivery completes;
  * raising                 — that delivery retries on its own backoff, up to
                              its own `max_attempts`, then dead-letters;
  * raising `PermanentEventError` — dead-letters immediately, because a payload
                              the handler can never accept does not get better
                              on the fifth attempt.

A subscriber that raises does not affect the other subscribers of the same
event, and does not cause them to be re-run.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

class PermanentEventError(Exception):
    """The handler can never accept this payload — do not retry.

    Use for a malformed or unresolvable payload, not for a provider being down.
    """


@dataclass(frozen=True)
class EventContext:
    """What a handler receives. Deliberately narrow.

    A handler gets the event's identity and payload and nothing else — no
    access to the delivery row, the lease, or the other subscribers. It cannot
    mark itself complete or reschedule its siblings; the consumer owns that.
    """

    event_id: uuid.UUID
    event_type: str
    payload: dict[str, Any]
    business_id: uuid.UUID | None
    correlation_id: str | None
    attempt: int

    def require_business_id(self) -> uuid.UUID:
        """Business-scoped handlers fail permanently without a tenant.

        An event that should carry a business and does not is a publisher bug;
        retrying it five times just delays noticing.
        """
        business_id = self.business_id or _uuid_or_none(self.payload.get("business_id"))
        if business_id is None:
            raise PermanentEventError(
                f"{self.event_type} carries no business_id; cannot resolve tenant context"
            )
        return business_id

    def require_uuid(self, key: str) -> uuid.UUID:
        value = _uuid_or_none(self.payload.get(key))
        if value is None:
            raise PermanentEventError(f"{self.event_type} payload is missing {key!r}")
        return value


def _uuid_or_none(value: Any) -> uuid.UUID | None:
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return None


# Declared after EventContext, not before it: as a forward reference the alias
# resolves to Any under mypy, which then reports every @subscribe-decorated
# handler as untyped.
EventHandler = Callable[[AsyncSession, EventContext], Awaitable[None]]


@dataclass(frozen=True)
class EventSubscriber:
    """One capability's interest in a set of event types.

    `subscriber_id` is a stable identifier stored on every delivery row, so it
    is part of the data model: renaming one strands the in-flight deliveries of
    the old name. Use `capability.purpose` — `marketplace.index`, not `index`.
    """

    subscriber_id: str
    event_types: frozenset[str]
    handler: EventHandler
    description: str = ""
    max_attempts: int = 5


_SUBSCRIBERS: dict[str, EventSubscriber] = {}
_BY_EVENT_TYPE: dict[str, list[EventSubscriber]] = {}


def register(subscriber: EventSubscriber) -> EventSubscriber:
    """Register a subscriber. Idempotent for the identical object, fatal otherwise.

    Two different subscribers sharing an id would silently share delivery rows
    and each see the other's attempt counts, so this refuses rather than
    last-one-wins.
    """
    existing = _SUBSCRIBERS.get(subscriber.subscriber_id)
    if existing is not None:
        if existing is subscriber:
            return subscriber
        raise ValueError(
            f"Duplicate event subscriber id {subscriber.subscriber_id!r}; "
            "subscriber ids are stored on delivery rows and must be unique"
        )

    from platform_core.events.catalogue import assert_known_event_type

    for event_type in subscriber.event_types:
        # Catch a typo'd subscription at import time. Otherwise the subscriber
        # is simply never invoked and nothing anywhere reports it.
        assert_known_event_type(event_type)

    _SUBSCRIBERS[subscriber.subscriber_id] = subscriber
    for event_type in subscriber.event_types:
        _BY_EVENT_TYPE.setdefault(event_type, []).append(subscriber)
    return subscriber


def subscribe(
    subscriber_id: str,
    *event_types: str,
    description: str = "",
    max_attempts: int = 5,
) -> Callable[[EventHandler], EventHandler]:
    """Decorator form of `register`, for the common single-handler case."""

    def decorator(handler: EventHandler) -> EventHandler:
        register(
            EventSubscriber(
                subscriber_id=subscriber_id,
                event_types=frozenset(event_types),
                handler=handler,
                description=description or (handler.__doc__ or "").strip().split("\n")[0],
                max_attempts=max_attempts,
            )
        )
        return handler

    return decorator


def subscribers_for(event_type: str) -> tuple[EventSubscriber, ...]:
    """Every subscriber registered for `event_type`, in registration order.

    An empty tuple is a normal answer, not an error: most events exist to be
    available, and are consumed later or only by analytics.
    """
    load_subscribers()
    return tuple(_BY_EVENT_TYPE.get(event_type, ()))


def get_subscriber(subscriber_id: str) -> EventSubscriber | None:
    load_subscribers()
    return _SUBSCRIBERS.get(subscriber_id)


def all_subscribers() -> tuple[EventSubscriber, ...]:
    load_subscribers()
    return tuple(_SUBSCRIBERS.values())


_import_done = False


def load_subscribers() -> None:
    """Import the subscriber package once, so registration has happened.

    Called from every read path rather than relying on the caller to import
    the right module first — a consumer that reads an empty registry would
    silently complete every event without doing the work.
    """
    global _import_done
    if _import_done:
        return
    _import_done = True
    import platform_core.events.subscribers  # noqa: F401  (registration side effect)


def reset_for_tests() -> None:
    """Drop all registrations. Test-support only."""
    global _import_done
    _SUBSCRIBERS.clear()
    _BY_EVENT_TYPE.clear()
    _import_done = False
