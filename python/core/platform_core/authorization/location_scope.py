"""Location scope (Capability Universe §7.2; Business OS Guide §5 security model).

A member whose membership is limited to some locations sees and changes only
the operational records at those locations: orders, bookings, deliveries,
stock, quotes and projects. Records with no location (business-wide) stay
visible. The owner is never limited.

The server enforces it here, for every ORM read and write in the request's
session; `location_scope_allows()` RLS policies repeat the rule in the
database as defence in depth ("UI hiding is not the security boundary").
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from typing import Any

from sqlalchemy import event, or_
from sqlalchemy.orm import ORMExecuteState, Session, with_loader_criteria

_INFO_KEY = "locah_location_scope"


def _scoped_models() -> tuple[type[Any], ...]:
    from platform_core.models import (
        Booking,
        FulfilmentJob,
        InventoryMovement,
        InventoryRecord,
        Project,
        Quote,
        SalesOrder,
    )

    return (SalesOrder, Booking, FulfilmentJob, InventoryRecord, InventoryMovement, Quote, Project)


def scoped_locations(membership: Any) -> tuple[uuid.UUID, ...] | None:
    """The locations a membership is limited to, or None for no limit."""
    from platform_core.permissions import ROLE_PRIMARY_OWNER

    if membership is None or getattr(membership, "role", None) == ROLE_PRIMARY_OWNER:
        return None
    scope = getattr(membership, "location_scope", None)
    return tuple(uuid.UUID(str(x)) for x in scope) if scope else None


def bind(session: Any, locations: Iterable[uuid.UUID] | None) -> None:
    """Limit this session's ORM reads and writes to `locations` (None clears)."""
    info = session.info  # AsyncSession.info is the underlying Session's info
    if locations:
        info[_INFO_KEY] = frozenset(uuid.UUID(str(x)) for x in locations)
    else:
        info.pop(_INFO_KEY, None)


def current(session: Any) -> frozenset[uuid.UUID] | None:
    scope = session.info.get(_INFO_KEY)
    return scope if scope else None


@event.listens_for(Session, "do_orm_execute")
def _filter_reads(state: ORMExecuteState) -> None:
    scope = state.session.info.get(_INFO_KEY)
    if not scope or not state.is_select or state.execution_options.get("skip_location_scope"):
        return
    allowed = list(scope)
    for model in _scoped_models():
        state.statement = state.statement.options(
            with_loader_criteria(
                model,
                lambda cls: or_(cls.location_id.is_(None), cls.location_id.in_(allowed)),
                include_aliases=True,
                track_closure_variables=True,
            )
        )


@event.listens_for(Session, "before_flush")
def _guard_writes(session: Session, flush_context: Any, instances: Any) -> None:
    scope = session.info.get(_INFO_KEY)
    if not scope:
        return
    models = _scoped_models()
    for obj in list(session.new) + list(session.dirty):
        if isinstance(obj, models):
            loc = getattr(obj, "location_id", None)
            if loc is not None and uuid.UUID(str(loc)) not in scope:
                from platform_core.exceptions import OutsideLocationScope

                raise OutsideLocationScope()
