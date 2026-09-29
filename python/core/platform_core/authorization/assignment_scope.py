"""Assignment scope (Capability Universe §7.2–§7.3, §24 #11; P2-01).

"Assignment is the new security primitive." A member whose role's scope is
`assignment` (a provider, a sales executive, later a delivery partner,
technician or housekeeper) sees and changes only the records assigned to them:

  * bookings where they are the provider (`provider_id` → their workforce
    record),
  * enquiries (leads) assigned to them (`assignee_identity_id`),
  * quotes they wrote, or for the customer of an enquiry assigned to them,
  * project tasks assigned to them (`assignee_member_id` → their workforce
    record),
  * and, of the customer book, only the customers on those bookings and
    enquiries (server-side only: matching a new enquiry to an existing customer
    by phone still looks at the whole book, with `skip_assignment_scope`).

Dispatch jobs and job cards join as they ship. Tasks and the walk-in queue are in this scope. A record with
nobody assigned is not theirs. The owner is never limited, and neither is a
member whose scope is business or location.

The server enforces it here, for every ORM read and write in the request's
session, alongside location scope; `assignment_scope_allows_identity()` /
`assignment_scope_allows_member()` RLS policies repeat the rule in the
database as defence in depth.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import event, or_, select
from sqlalchemy.orm import ORMExecuteState, Session, with_loader_criteria

_INFO_KEY = "locah_assignment_scope"

# What a member limited to their assignments may be given: only permissions over
# records this scope actually narrows (plus reading the business itself). A
# permission over records nobody is assigned to — orders, stock, money — would
# show the whole book, so it cannot sit on an assignment-scoped role.
ASSIGNMENT_PERMISSIONS = frozenset({
    "business.read", "locations.read", "notifications.read",
    "bookings.read", "bookings.update",
    "leads.read", "leads.create", "leads.update_status",
    "quotes.read", "quotes.create", "quotes.update", "quotes.issue",
    "customers.read",
    # Job cards and teaching are assignment-scoped work. They do not open the
    # customer book, exports, stock, or the right to create jobs and enrol
    # students. Recording a part calls Inventory; it does not grant inventory.read,
    # which would show the whole stock book.
    "jobs.read", "jobs.complete", "jobs.use_parts",
    "academics.read", "academics.teach",
    # Queue tokens for their provider lane, and tasks assigned to them.
    "queue.read", "queue.operate",
    "tasks.read", "tasks.complete",
})


def assigned_identity(membership: Any) -> uuid.UUID | None:
    """The identity whose assignments bound this membership, or None for no assignment limit."""
    from platform_core.permissions import ROLE_PRIMARY_OWNER

    if membership is None or getattr(membership, "role", None) == ROLE_PRIMARY_OWNER:
        return None
    if getattr(membership, "access_scope", None) != "assignment":
        return None
    identity = getattr(membership, "identity_id", None)
    return uuid.UUID(str(identity)) if identity else None


def bind(session: Any, identity: uuid.UUID | None) -> None:
    """Limit this session's ORM reads and writes to `identity`'s assignments (None clears)."""
    info = session.info
    if identity:
        info[_INFO_KEY] = uuid.UUID(str(identity))
    else:
        info.pop(_INFO_KEY, None)


def current(session: Any) -> uuid.UUID | None:
    value = session.info.get(_INFO_KEY)
    return value if value else None


def _member_ids(identity: uuid.UUID) -> Any:
    from platform_core.models import WorkforceMember

    return select(WorkforceMember.id).where(WorkforceMember.identity_id == identity)


@event.listens_for(Session, "do_orm_execute")
def _filter_reads(state: ORMExecuteState) -> None:
    identity = state.session.info.get(_INFO_KEY)
    if not identity or not state.is_select or state.execution_options.get("skip_assignment_scope"):
        return
    from platform_core.models import Booking, CustomerContact, Lead, ProjectTask, QueueEntry, QueueLane, Quote, WorkTask

    mine = _member_ids(identity)
    # Their customers are the ones on their bookings and enquiries — not the whole book.
    theirs = select(Booking.customer_contact_id).where(Booking.provider_id.in_(_member_ids(identity))).union(
        select(Lead.customer_contact_id).where(Lead.assignee_identity_id == identity))
    state.statement = state.statement.options(
        with_loader_criteria(CustomerContact, lambda cls: cls.id.in_(theirs), include_aliases=True,
                             track_closure_variables=True),
        with_loader_criteria(Booking, lambda cls: cls.provider_id.in_(mine), include_aliases=True,
                             track_closure_variables=True),
        with_loader_criteria(Lead, lambda cls: cls.assignee_identity_id == identity, include_aliases=True,
                             track_closure_variables=True),
        with_loader_criteria(ProjectTask, lambda cls: cls.assignee_member_id.in_(mine), include_aliases=True,
                             track_closure_variables=True),
        with_loader_criteria(Quote, lambda cls: or_(cls.created_by == identity, cls.customer_contact_id.in_(
            select(Lead.customer_contact_id).where(Lead.assignee_identity_id == identity))),
            include_aliases=True, track_closure_variables=True),
        with_loader_criteria(WorkTask, lambda cls: cls.assignee_member_id.in_(mine), include_aliases=True,
                             track_closure_variables=True),
        with_loader_criteria(QueueLane, lambda cls: cls.provider_id.in_(mine), include_aliases=True,
                             track_closure_variables=True),
        with_loader_criteria(QueueEntry, lambda cls: cls.provider_id.in_(mine), include_aliases=True,
                             track_closure_variables=True),
    )


@event.listens_for(Session, "before_flush")
def _guard_writes(session: Session, flush_context: Any, instances: Any) -> None:
    """A member limited to their assignments cannot create or hand a record to someone else."""
    identity = session.info.get(_INFO_KEY)
    if not identity:
        return
    from platform_core.models import Booking, Lead, ProjectTask, QueueEntry, QueueLane, Quote, WorkTask, WorkforceMember

    for quote in [o for o in session.new if isinstance(o, Quote)]:
        if quote.created_by is None or uuid.UUID(str(quote.created_by)) != identity:
            from platform_core.exceptions import OutsideAssignmentScope

            raise OutsideAssignmentScope()
    objects = [o for o in list(session.new) + list(session.dirty) if isinstance(o, (Booking, Lead, ProjectTask, WorkTask, QueueLane, QueueEntry))]
    if not objects:
        return
    with session.no_autoflush:
        mine = set(session.execute(
            select(WorkforceMember.id).where(WorkforceMember.identity_id == identity)).scalars())
    for obj in objects:
        if isinstance(obj, Lead):
            ok = obj.assignee_identity_id is not None and uuid.UUID(str(obj.assignee_identity_id)) == identity
        elif isinstance(obj, (Booking, QueueLane, QueueEntry)):
            ok = obj.provider_id is not None and uuid.UUID(str(obj.provider_id)) in mine
        else:
            ok = obj.assignee_member_id is not None and uuid.UUID(str(obj.assignee_member_id)) in mine
        if not ok:
            from platform_core.exceptions import OutsideAssignmentScope

            raise OutsideAssignmentScope()
