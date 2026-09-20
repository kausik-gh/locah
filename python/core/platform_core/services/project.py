"""Projects and work orders — committed work, steered to completion.

The whole point of this module is that it is not a vertical. A kitchen refit, a
treatment plan, a photo shoot and a boiler repair differ in how long they run and
what the stages are called, not in what the software has to do: hold a scope for
a customer, order the stages, allocate the tasks, and know how far along it is.
So the vocabulary and the starting stages come from the Business-Type Profile
and nothing in this file branches on a business type.

It also owns very little. Customers, workforce, quotations, audit, events and
notifications already exist; a project references them. The one number it keeps
is `agreed_value`, copied once from the quote it was converted from so reporting
does not have to join back — and the quote remains the commercial truth.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.business_type_profiles.registry import BusinessTypeProfileRegistry
from platform_core.exceptions import ConflictError, ResourceNotFound, ValidationError
from platform_core.gates import assert_business_mutable
from platform_core.models import Project, ProjectPhase, ProjectTask, Quote, WorkforceMember
from platform_core.resolvers.customer_resolver import CustomerResolver
from platform_core.services.audit import AuditService
from platform_core.services.business import BusinessService
from platform_core.services.outbox import OutboxService

TITLE_MAX = 200
SUMMARY_MAX = 4000

STATUSES = ("draft", "active", "on_hold", "completed", "cancelled")
OPEN_STATUSES = frozenset({"draft", "active", "on_hold"})
TERMINAL_STATUSES = frozenset({"completed", "cancelled"})

# Which lifecycle moves are legal. Written out rather than inferred so the rule
# is readable: work can be paused and resumed, and anything still open can be
# abandoned, but nothing comes back from completed or cancelled. A project that
# restarts is a new project — the old one is a record of what happened.
ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "draft": frozenset({"active", "cancelled"}),
    "active": frozenset({"on_hold", "completed", "cancelled"}),
    "on_hold": frozenset({"active", "cancelled"}),
    "completed": frozenset(),
    "cancelled": frozenset(),
}

TASK_STATUSES = ("todo", "in_progress", "blocked", "done", "cancelled")
PHASE_STATUSES = ("pending", "in_progress", "done", "skipped")
PRIORITIES = ("low", "normal", "high", "urgent")


def _money(value: Any) -> str | None:
    if value is None:
        return None
    return str(Decimal(str(value)).quantize(Decimal("0.01")))


def _date(value: Any) -> date | None:
    """Accept `YYYY-MM-DD` or a full ISO timestamp; store a plain date."""
    if value in (None, ""):
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    text = str(value).strip()
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        pass
    try:
        return date.fromisoformat(text[:10])
    except ValueError as exc:
        raise ValidationError("Invalid date", details={"value": text}) from exc


def _text(value: Any, *, limit: int, field: str) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    if not cleaned:
        return None
    if len(cleaned) > limit:
        raise ValidationError(f"{field} is too long", details={"field": field, "max": limit})
    return cleaned


class ProjectService:
    # ------------------------------------------------------------- reading

    @staticmethod
    def serialize(
        project: Project,
        phases: list[ProjectPhase] | None = None,
        tasks: list[ProjectTask] | None = None,
    ) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": str(project.id),
            "reference": project.reference,
            "title": project.title,
            "summary": project.summary,
            "status": project.status,
            "priority": project.priority,
            "customer_contact_id": (
                str(project.customer_contact_id) if project.customer_contact_id else None
            ),
            "location_id": str(project.location_id) if project.location_id else None,
            "lead_member_id": str(project.lead_member_id) if project.lead_member_id else None,
            "starts_on": project.starts_on.isoformat() if project.starts_on else None,
            "due_on": project.due_on.isoformat() if project.due_on else None,
            "completed_at": project.completed_at.isoformat() if project.completed_at else None,
            "cancelled_at": project.cancelled_at.isoformat() if project.cancelled_at else None,
            "on_hold_reason": project.on_hold_reason,
            "cancellation_reason": project.cancellation_reason,
            "source_quote_id": str(project.source_quote_id) if project.source_quote_id else None,
            "agreed_value": _money(project.agreed_value),
            "currency": project.currency,
            "is_open": project.status in OPEN_STATUSES,
            "version": project.version,
            "created_at": project.created_at.isoformat() if project.created_at else None,
        }
        if tasks is not None:
            done = sum(1 for t in tasks if t.status == "done")
            counted = [t for t in tasks if t.status != "cancelled"]
            data["task_count"] = len(counted)
            data["tasks_done"] = done
            # Progress is a count of finished work, not an estimate. A project
            # with no tasks reports no progress rather than 100%, because "no
            # work recorded" and "all work finished" are not the same thing.
            data["progress_percent"] = (
                round(done * 100 / len(counted)) if counted else None
            )
            data["tasks"] = [ProjectService.serialize_task(t) for t in tasks]
        if phases is not None:
            data["phases"] = [ProjectService.serialize_phase(p) for p in phases]
        return data

    @staticmethod
    def serialize_phase(phase: ProjectPhase) -> dict[str, Any]:
        return {
            "id": str(phase.id),
            "name": phase.name,
            "status": phase.status,
            "is_milestone": phase.is_milestone,
            "due_on": phase.due_on.isoformat() if phase.due_on else None,
            "completed_at": phase.completed_at.isoformat() if phase.completed_at else None,
            "sort_order": phase.sort_order,
        }

    @staticmethod
    def serialize_task(task: ProjectTask) -> dict[str, Any]:
        return {
            "id": str(task.id),
            "phase_id": str(task.phase_id) if task.phase_id else None,
            "title": task.title,
            "description": task.description,
            "status": task.status,
            "assignee_member_id": (
                str(task.assignee_member_id) if task.assignee_member_id else None
            ),
            "due_on": task.due_on.isoformat() if task.due_on else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            "blocked_reason": task.blocked_reason,
            "sort_order": task.sort_order,
            "version": task.version,
        }

    @staticmethod
    async def resolve(
        session: AsyncSession, *, business_id: uuid.UUID, project_id: uuid.UUID
    ) -> Project:
        project = (
            (
                await session.execute(
                    select(Project).where(
                        Project.id == project_id,
                        Project.business_id == business_id,
                        Project.deleted_at.is_(None),
                    )
                )
            )
            .scalars()
            .first()
        )
        if project is None:
            raise ResourceNotFound("Project")
        return project

    @staticmethod
    async def load_children(
        session: AsyncSession, *, project_id: uuid.UUID
    ) -> tuple[list[ProjectPhase], list[ProjectTask]]:
        phases = list(
            (
                await session.execute(
                    select(ProjectPhase)
                    .where(ProjectPhase.project_id == project_id)
                    .order_by(ProjectPhase.sort_order.asc())
                )
            )
            .scalars()
            .all()
        )
        tasks = list(
            (
                await session.execute(
                    select(ProjectTask)
                    .where(ProjectTask.project_id == project_id)
                    .order_by(ProjectTask.sort_order.asc())
                )
            )
            .scalars()
            .all()
        )
        return phases, tasks

    @staticmethod
    async def get_detail(
        session: AsyncSession, *, business_id: uuid.UUID, project_id: uuid.UUID
    ) -> dict[str, Any]:
        project = await ProjectService.resolve(
            session, business_id=business_id, project_id=project_id
        )
        phases, tasks = await ProjectService.load_children(session, project_id=project.id)
        return ProjectService.serialize(project, phases, tasks)

    @staticmethod
    async def list_projects(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        status: str | None = None,
        customer_contact_id: uuid.UUID | None = None,
        assignee_member_id: uuid.UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """The list view, with progress but without every task.

        Task counts are aggregated in one grouped query rather than by loading
        each project's tasks — a list of fifty projects should not cost fifty
        round trips, and progress is the column people scan.
        """
        query = select(Project).where(
            Project.business_id == business_id, Project.deleted_at.is_(None)
        )
        if status:
            query = query.where(Project.status == status)
        if customer_contact_id:
            query = query.where(Project.customer_contact_id == customer_contact_id)
        if assignee_member_id:
            query = query.where(
                Project.id.in_(
                    select(ProjectTask.project_id).where(
                        ProjectTask.business_id == business_id,
                        ProjectTask.assignee_member_id == assignee_member_id,
                    )
                )
            )
        query = query.order_by(Project.created_at.desc()).limit(min(limit, 200)).offset(offset)
        projects = list((await session.execute(query)).scalars().all())
        if not projects:
            return []

        ids = [p.id for p in projects]
        counts = (
            await session.execute(
                select(
                    ProjectTask.project_id,
                    func.count().filter(ProjectTask.status != "cancelled"),
                    func.count().filter(ProjectTask.status == "done"),
                )
                .where(ProjectTask.project_id.in_(ids))
                .group_by(ProjectTask.project_id)
            )
        ).all()
        by_project = {row[0]: (row[1] or 0, row[2] or 0) for row in counts}

        out: list[dict[str, Any]] = []
        for project in projects:
            total, done = by_project.get(project.id, (0, 0))
            data = ProjectService.serialize(project)
            data["task_count"] = total
            data["tasks_done"] = done
            data["progress_percent"] = round(done * 100 / total) if total else None
            out.append(data)
        return out

    # ------------------------------------------------------------ numbering

    @staticmethod
    async def _next_reference(session: AsyncSession, business_id: uuid.UUID) -> str:
        """Per-business, readable, and starting at one for every business.

        Derived from the highest existing reference rather than a shared
        sequence, so one business's numbering never reveals another's volume.
        The unique index is what actually prevents a collision; `create` retries.
        """
        year = datetime.now(timezone.utc).year
        prefix = f"P-{year}-"
        highest = await session.scalar(
            select(func.max(Project.reference)).where(
                Project.business_id == business_id,
                Project.reference.like(f"{prefix}%"),
            )
        )
        nxt = 1
        if highest:
            try:
                nxt = int(str(highest).rsplit("-", 1)[-1]) + 1
            except ValueError:
                nxt = 1
        return f"{prefix}{nxt:04d}"

    # -------------------------------------------------------------- writing

    @staticmethod
    async def _seed_phases(
        session: AsyncSession,
        *,
        project: Project,
        names: tuple[str, ...] | list[str],
    ) -> list[ProjectPhase]:
        phases: list[ProjectPhase] = []
        for index, name in enumerate(names):
            cleaned = _text(name, limit=120, field="phase name")
            if not cleaned:
                continue
            phase = ProjectPhase(
                business_id=project.business_id,
                project_id=project.id,
                name=cleaned,
                sort_order=index,
            )
            session.add(phase)
            phases.append(phase)
        if phases:
            await session.flush()
        return phases

    @staticmethod
    async def _validate_member(
        session: AsyncSession, *, business_id: uuid.UUID, member_id: Any
    ) -> uuid.UUID | None:
        """A person assigned to work must belong to this business.

        RLS would already refuse a member from another tenant, but failing here
        gives a clear 404 rather than a foreign key error the caller cannot read.
        """
        if not member_id:
            return None
        parsed = uuid.UUID(str(member_id))
        member = (
            (
                await session.execute(
                    select(WorkforceMember).where(
                        WorkforceMember.id == parsed,
                        WorkforceMember.business_id == business_id,
                        WorkforceMember.deleted_at.is_(None),
                    )
                )
            )
            .scalars()
            .first()
        )
        if member is None:
            raise ResourceNotFound("Workforce member")
        return uuid.UUID(str(member.id))

    @staticmethod
    async def create(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        actor_id: uuid.UUID,
        correlation_id: str,
        payload: dict[str, Any],
    ) -> Project:
        business = await BusinessService.get_by_id(session, business_id)
        assert_business_mutable(business.state, action="create project")

        title = _text(payload.get("title"), limit=TITLE_MAX, field="title")
        if not title:
            raise ValidationError("A project needs a title", details={"field": "title"})

        customer_contact_id = payload.get("customer_contact_id")
        if customer_contact_id:
            contact = await CustomerResolver.resolve(
                session,
                business_id=business_id,
                contact_id=uuid.UUID(str(customer_contact_id)),
            )
            customer_contact_id = contact.id

        lead_member_id = await ProjectService._validate_member(
            session, business_id=business_id, member_id=payload.get("lead_member_id")
        )

        priority = str(payload.get("priority") or "normal")
        if priority not in PRIORITIES:
            raise ValidationError("Unknown priority", details={"field": "priority"})

        # The stages a new project starts with come from the Business-Type
        # Profile, so a clinic opens at Assessment and a studio at Brief. An
        # explicit list overrides it; an explicitly empty list means "no stages".
        requested_phases = payload.get("phases")
        if requested_phases is None:
            profile = BusinessTypeProfileRegistry.get_or_default(business.business_type)
            phase_names: list[str] = list(profile.project_semantics.default_phases)
        else:
            phase_names = [str(p) for p in requested_phases]

        # No retry loop here. A rollback would discard the caller's whole
        # transaction, and a savepoint does not survive a failed flush in this
        # codebase — so a collision surfaces as a conflict the caller can retry,
        # which for two projects created in the same instant is the honest
        # answer rather than a silently different number.
        reference = await ProjectService._next_reference(session, business_id)
        project = Project(
            business_id=business_id,
            customer_contact_id=customer_contact_id,
            location_id=(
                uuid.UUID(str(payload["location_id"])) if payload.get("location_id") else None
            ),
            reference=reference,
            title=title,
            summary=_text(payload.get("summary"), limit=SUMMARY_MAX, field="summary"),
            internal_notes=_text(
                payload.get("internal_notes"), limit=SUMMARY_MAX, field="internal_notes"
            ),
            priority=priority,
            starts_on=_date(payload.get("starts_on")),
            due_on=_date(payload.get("due_on")),
            source_quote_id=(
                uuid.UUID(str(payload["source_quote_id"]))
                if payload.get("source_quote_id")
                else None
            ),
            agreed_value=payload.get("agreed_value"),
            currency=str(payload.get("currency") or "INR"),
            lead_member_id=lead_member_id,
            created_by=actor_id,
        )
        session.add(project)
        try:
            await session.flush()
        except IntegrityError as exc:
            raise ConflictError(
                "Another project was created at the same moment — try again",
                details={"code": "reference_collision"},
            ) from exc

        await ProjectService._seed_phases(session, project=project, names=phase_names)

        await ProjectService._record(
            session,
            project=project,
            event_type="project.created",
            action="create",
            actor_id=actor_id,
            correlation_id=correlation_id,
            after_state={"status": project.status, "title": project.title},
        )
        return project

    @staticmethod
    async def create_from_quote(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        quote_id: uuid.UUID,
        actor_id: uuid.UUID,
        correlation_id: str,
        payload: dict[str, Any] | None = None,
    ) -> Project:
        """Turn an accepted quote into the work it describes.

        Only an accepted quote converts: a draft is not agreed and an expired or
        declined one is not work anybody asked for. The conversion is idempotent
        through the unique index on `source_quote_id` — clicking twice returns
        the project that already exists rather than creating a second one.
        """
        quote = (
            (
                await session.execute(
                    select(Quote).where(
                        Quote.id == quote_id,
                        Quote.business_id == business_id,
                        Quote.deleted_at.is_(None),
                    )
                )
            )
            .scalars()
            .first()
        )
        if quote is None:
            raise ResourceNotFound("Quote")

        existing = (
            (
                await session.execute(
                    select(Project).where(
                        Project.source_quote_id == quote.id,
                        Project.deleted_at.is_(None),
                    )
                )
            )
            .scalars()
            .first()
        )
        if existing is not None:
            return existing

        if quote.status != "accepted":
            raise ValidationError(
                "Only an accepted quote becomes a project",
                details={"code": "quote_not_accepted", "status": quote.status},
            )

        base: dict[str, Any] = {
            "title": quote.title or f"Work for {quote.quote_number}",
            "customer_contact_id": (
                str(quote.customer_contact_id) if quote.customer_contact_id else None
            ),
            "location_id": str(quote.location_id) if quote.location_id else None,
            "source_quote_id": str(quote.id),
            # Snapshot, for reporting. The quote stays the commercial record.
            "agreed_value": quote.total,
            "currency": quote.currency,
        }
        base.update(payload or {})
        project = await ProjectService.create(
            session,
            business_id=business_id,
            actor_id=actor_id,
            correlation_id=correlation_id,
            payload=base,
        )

        # Close the loop the other way so the quote knows what became of it.
        quote.converted_to_type = "project"
        quote.converted_to_id = project.id
        await session.flush()

        await OutboxService.publish(
            session,
            event_type="quote.converted",
            payload={
                "quote_id": str(quote.id),
                "project_id": str(project.id),
                "converted_to_type": "project",
            },
            business_id=business_id,
            correlation_id=correlation_id,
        )
        return project

    @staticmethod
    async def update(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        project_id: uuid.UUID,
        actor_id: uuid.UUID,
        correlation_id: str,
        payload: dict[str, Any],
        expected_version: int | None = None,
    ) -> Project:
        project = await ProjectService.resolve(
            session, business_id=business_id, project_id=project_id
        )
        if project.status in TERMINAL_STATUSES:
            raise ValidationError(
                "A completed or cancelled project cannot be edited",
                details={"code": "project_closed", "status": project.status},
            )
        if expected_version is not None and project.version != expected_version:
            raise ConflictError(
                "Stale project version",
                details={"expected_version": expected_version, "current_version": project.version},
            )

        before = {"title": project.title, "due_on": str(project.due_on), "priority": project.priority}

        if "title" in payload:
            title = _text(payload.get("title"), limit=TITLE_MAX, field="title")
            if not title:
                raise ValidationError("A project needs a title", details={"field": "title"})
            project.title = title
        if "summary" in payload:
            project.summary = _text(payload.get("summary"), limit=SUMMARY_MAX, field="summary")
        if "internal_notes" in payload:
            project.internal_notes = _text(
                payload.get("internal_notes"), limit=SUMMARY_MAX, field="internal_notes"
            )
        if "priority" in payload:
            priority = str(payload.get("priority") or "normal")
            if priority not in PRIORITIES:
                raise ValidationError("Unknown priority", details={"field": "priority"})
            project.priority = priority
        if "starts_on" in payload:
            project.starts_on = _date(payload.get("starts_on"))
        if "due_on" in payload:
            project.due_on = _date(payload.get("due_on"))
        if "customer_contact_id" in payload:
            value = payload.get("customer_contact_id")
            if value:
                contact = await CustomerResolver.resolve(
                    session, business_id=business_id, contact_id=uuid.UUID(str(value))
                )
                project.customer_contact_id = contact.id
            else:
                project.customer_contact_id = None
        if "lead_member_id" in payload:
            project.lead_member_id = await ProjectService._validate_member(
                session, business_id=business_id, member_id=payload.get("lead_member_id")
            )

        project.version += 1
        project.updated_at = datetime.now(timezone.utc)
        await session.flush()

        await ProjectService._record(
            session,
            project=project,
            event_type="project.updated",
            action="update",
            actor_id=actor_id,
            correlation_id=correlation_id,
            before_state=before,
            after_state={
                "title": project.title,
                "due_on": str(project.due_on),
                "priority": project.priority,
            },
        )
        return project

    @staticmethod
    async def change_status(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        project_id: uuid.UUID,
        status: str,
        actor_id: uuid.UUID,
        correlation_id: str,
        reason: str | None = None,
    ) -> Project:
        project = await ProjectService.resolve(
            session, business_id=business_id, project_id=project_id
        )
        if status not in STATUSES:
            raise ValidationError("Unknown status", details={"field": "status"})
        if status == project.status:
            return project
        if status not in ALLOWED_TRANSITIONS[project.status]:
            raise ValidationError(
                f"A {project.status} project cannot become {status}",
                details={
                    "code": "invalid_transition",
                    "from": project.status,
                    "to": status,
                    "allowed": sorted(ALLOWED_TRANSITIONS[project.status]),
                },
            )

        previous = project.status
        now = datetime.now(timezone.utc)
        project.status = status
        project.on_hold_reason = reason if status == "on_hold" else None
        if status == "completed":
            project.completed_at = now
        if status == "cancelled":
            project.cancelled_at = now
            project.cancellation_reason = reason
        project.version += 1
        project.updated_at = now
        await session.flush()

        await ProjectService._record(
            session,
            project=project,
            event_type="project.status.changed",
            action="change_status",
            actor_id=actor_id,
            correlation_id=correlation_id,
            before_state={"status": previous},
            after_state={"status": status},
            reason=reason,
            extra={"from": previous, "to": status},
        )
        # A completion is what anything downstream actually waits for, so it is
        # its own event rather than something a subscriber has to infer.
        if status in ("completed", "cancelled"):
            await OutboxService.publish(
                session,
                event_type=f"project.{status}",
                payload={
                    "project_id": str(project.id),
                    "reference": project.reference,
                    "customer_contact_id": (
                        str(project.customer_contact_id) if project.customer_contact_id else None
                    ),
                    "source_quote_id": (
                        str(project.source_quote_id) if project.source_quote_id else None
                    ),
                },
                business_id=business_id,
                correlation_id=correlation_id,
            )
        return project

    # --------------------------------------------------------------- phases

    @staticmethod
    async def add_phase(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        project_id: uuid.UUID,
        actor_id: uuid.UUID,
        correlation_id: str,
        payload: dict[str, Any],
    ) -> ProjectPhase:
        project = await ProjectService._open_project(session, business_id, project_id)
        name = _text(payload.get("name"), limit=120, field="name")
        if not name:
            raise ValidationError("A phase needs a name", details={"field": "name"})
        highest = await session.scalar(
            select(func.max(ProjectPhase.sort_order)).where(ProjectPhase.project_id == project.id)
        )
        phase = ProjectPhase(
            business_id=business_id,
            project_id=project.id,
            name=name,
            is_milestone=bool(payload.get("is_milestone")),
            due_on=_date(payload.get("due_on")),
            sort_order=(highest or 0) + 1,
        )
        session.add(phase)
        await session.flush()
        await ProjectService._record(
            session,
            project=project,
            event_type="project.updated",
            action="add_phase",
            actor_id=actor_id,
            correlation_id=correlation_id,
            after_state={"phase": name},
        )
        return phase

    @staticmethod
    async def update_phase(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        project_id: uuid.UUID,
        phase_id: uuid.UUID,
        actor_id: uuid.UUID,
        correlation_id: str,
        payload: dict[str, Any],
    ) -> ProjectPhase:
        project = await ProjectService._open_project(session, business_id, project_id)
        phase = (
            (
                await session.execute(
                    select(ProjectPhase).where(
                        ProjectPhase.id == phase_id,
                        ProjectPhase.project_id == project.id,
                        ProjectPhase.business_id == business_id,
                    )
                )
            )
            .scalars()
            .first()
        )
        if phase is None:
            raise ResourceNotFound("Phase")

        previous = phase.status
        if "name" in payload:
            name = _text(payload.get("name"), limit=120, field="name")
            if not name:
                raise ValidationError("A phase needs a name", details={"field": "name"})
            phase.name = name
        if "due_on" in payload:
            phase.due_on = _date(payload.get("due_on"))
        if "is_milestone" in payload:
            phase.is_milestone = bool(payload.get("is_milestone"))
        if "status" in payload:
            status = str(payload.get("status"))
            if status not in PHASE_STATUSES:
                raise ValidationError("Unknown phase status", details={"field": "status"})
            phase.status = status
            phase.completed_at = datetime.now(timezone.utc) if status == "done" else None
        phase.updated_at = datetime.now(timezone.utc)
        await session.flush()

        if phase.status == "done" and previous != "done":
            await OutboxService.publish(
                session,
                event_type="project.phase.completed",
                payload={
                    "project_id": str(project.id),
                    "phase_id": str(phase.id),
                    "name": phase.name,
                    "is_milestone": phase.is_milestone,
                },
                business_id=business_id,
                correlation_id=correlation_id,
            )
        await ProjectService._record(
            session,
            project=project,
            event_type="project.updated",
            action="update_phase",
            actor_id=actor_id,
            correlation_id=correlation_id,
            before_state={"status": previous},
            after_state={"status": phase.status, "name": phase.name},
        )
        return phase

    # ---------------------------------------------------------------- tasks

    @staticmethod
    async def add_task(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        project_id: uuid.UUID,
        actor_id: uuid.UUID,
        correlation_id: str,
        payload: dict[str, Any],
    ) -> ProjectTask:
        project = await ProjectService._open_project(session, business_id, project_id)
        title = _text(payload.get("title"), limit=TITLE_MAX, field="title")
        if not title:
            raise ValidationError("A task needs a title", details={"field": "title"})

        phase_id = payload.get("phase_id")
        if phase_id:
            exists = await session.scalar(
                select(func.count())
                .select_from(ProjectPhase)
                .where(
                    ProjectPhase.id == uuid.UUID(str(phase_id)),
                    ProjectPhase.project_id == project.id,
                )
            )
            if not exists:
                raise ResourceNotFound("Phase")

        assignee = await ProjectService._validate_member(
            session, business_id=business_id, member_id=payload.get("assignee_member_id")
        )
        highest = await session.scalar(
            select(func.max(ProjectTask.sort_order)).where(ProjectTask.project_id == project.id)
        )
        task = ProjectTask(
            business_id=business_id,
            project_id=project.id,
            phase_id=uuid.UUID(str(phase_id)) if phase_id else None,
            title=title,
            description=_text(payload.get("description"), limit=SUMMARY_MAX, field="description"),
            assignee_member_id=assignee,
            due_on=_date(payload.get("due_on")),
            sort_order=(highest or 0) + 1,
        )
        session.add(task)
        await session.flush()

        if assignee:
            await ProjectService._publish_assignment(
                session, project=project, task=task, correlation_id=correlation_id
            )
        await ProjectService._record(
            session,
            project=project,
            event_type="project.updated",
            action="add_task",
            actor_id=actor_id,
            correlation_id=correlation_id,
            after_state={"task": title},
        )
        return task

    @staticmethod
    async def update_task(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        project_id: uuid.UUID,
        task_id: uuid.UUID,
        actor_id: uuid.UUID,
        correlation_id: str,
        payload: dict[str, Any],
        expected_version: int | None = None,
    ) -> ProjectTask:
        project = await ProjectService._open_project(session, business_id, project_id)
        task = (
            (
                await session.execute(
                    select(ProjectTask).where(
                        ProjectTask.id == task_id,
                        ProjectTask.project_id == project.id,
                        ProjectTask.business_id == business_id,
                    )
                )
            )
            .scalars()
            .first()
        )
        if task is None:
            raise ResourceNotFound("Task")
        if expected_version is not None and task.version != expected_version:
            raise ConflictError(
                "Stale task version",
                details={"expected_version": expected_version, "current_version": task.version},
            )

        previous_status = task.status
        previous_assignee = task.assignee_member_id

        if "title" in payload:
            title = _text(payload.get("title"), limit=TITLE_MAX, field="title")
            if not title:
                raise ValidationError("A task needs a title", details={"field": "title"})
            task.title = title
        if "description" in payload:
            task.description = _text(
                payload.get("description"), limit=SUMMARY_MAX, field="description"
            )
        if "due_on" in payload:
            task.due_on = _date(payload.get("due_on"))
        if "phase_id" in payload:
            value = payload.get("phase_id")
            task.phase_id = uuid.UUID(str(value)) if value else None
        if "assignee_member_id" in payload:
            task.assignee_member_id = await ProjectService._validate_member(
                session, business_id=business_id, member_id=payload.get("assignee_member_id")
            )
        if "status" in payload:
            status = str(payload.get("status"))
            if status not in TASK_STATUSES:
                raise ValidationError("Unknown task status", details={"field": "status"})
            task.status = status
            task.completed_at = datetime.now(timezone.utc) if status == "done" else None
            task.blocked_reason = (
                _text(payload.get("blocked_reason"), limit=500, field="blocked_reason")
                if status == "blocked"
                else None
            )

        task.version += 1
        task.updated_at = datetime.now(timezone.utc)
        await session.flush()

        if task.assignee_member_id and task.assignee_member_id != previous_assignee:
            await ProjectService._publish_assignment(
                session, project=project, task=task, correlation_id=correlation_id
            )
        if task.status == "done" and previous_status != "done":
            await OutboxService.publish(
                session,
                event_type="project.task.completed",
                payload={
                    "project_id": str(project.id),
                    "task_id": str(task.id),
                    "title": task.title,
                    "assignee_member_id": (
                        str(task.assignee_member_id) if task.assignee_member_id else None
                    ),
                },
                business_id=business_id,
                correlation_id=correlation_id,
            )
        await ProjectService._record(
            session,
            project=project,
            event_type="project.updated",
            action="update_task",
            actor_id=actor_id,
            correlation_id=correlation_id,
            before_state={"status": previous_status},
            after_state={"status": task.status, "title": task.title},
        )
        return task

    # ------------------------------------------------------------- internals

    @staticmethod
    async def _open_project(
        session: AsyncSession, business_id: uuid.UUID, project_id: uuid.UUID
    ) -> Project:
        """Resolve a project that can still be worked on.

        Phases and tasks are the shape of live work. Editing them on a completed
        or cancelled project would change the record of what happened, so it is
        refused here rather than in each caller.
        """
        project = await ProjectService.resolve(
            session, business_id=business_id, project_id=project_id
        )
        if project.status in TERMINAL_STATUSES:
            raise ValidationError(
                "A completed or cancelled project cannot be changed",
                details={"code": "project_closed", "status": project.status},
            )
        return project

    @staticmethod
    async def _publish_assignment(
        session: AsyncSession,
        *,
        project: Project,
        task: ProjectTask,
        correlation_id: str,
    ) -> None:
        await OutboxService.publish(
            session,
            event_type="project.task.assigned",
            payload={
                "project_id": str(project.id),
                "task_id": str(task.id),
                "title": task.title,
                "assignee_member_id": str(task.assignee_member_id),
                "due_on": task.due_on.isoformat() if task.due_on else None,
            },
            business_id=project.business_id,
            correlation_id=correlation_id,
        )

    @staticmethod
    async def _record(
        session: AsyncSession,
        *,
        project: Project,
        event_type: str,
        action: str,
        actor_id: uuid.UUID,
        correlation_id: str,
        before_state: dict[str, Any] | None = None,
        after_state: dict[str, Any] | None = None,
        reason: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """Every write leaves both a domain event and an audit row.

        The event is for other capabilities; the audit row is evidence of who did
        it. They are not interchangeable, so both are always written.
        """
        await OutboxService.publish(
            session,
            event_type=event_type,
            payload={
                "project_id": str(project.id),
                "reference": project.reference,
                "status": project.status,
                **(extra or {}),
            },
            business_id=project.business_id,
            correlation_id=correlation_id,
        )
        await AuditService.record(
            session,
            event_type=event_type,
            actor_identity_id=actor_id,
            actor_context="business",
            business_id=project.business_id,
            resource_type="project",
            resource_id=project.id,
            action=action,
            before_state=before_state,
            after_state=after_state,
            reason=reason,
        )
