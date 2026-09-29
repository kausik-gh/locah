"""One executable job card, distinct from bookings, projects, tasks and orders."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.authorization.assignment_scope import current as assigned_identity
from platform_core.authorization.location_scope import current as allowed_locations
from platform_core.exceptions import ConflictError, OutsideAssignmentScope, OutsideLocationScope, ResourceNotFound, ValidationError
from platform_core.jobs.models import JobCard, JobPart
from platform_core.models import BusinessLocation, CustomerContact, InventoryMovement, Quote, WorkforceMember
from platform_core.resolvers.customer_resolver import CustomerResolver
from platform_core.services.audit import AuditService
from platform_core.services.business import BusinessService
from platform_core.services.outbox import OutboxService
from platform_core.services.project import ProjectService
from platform_core.gates import assert_business_mutable
from platform_core.stock.service import StockService
from platform_core.stock import ledger as stock_ledger

SOURCE_TYPES = frozenset({"manual", "project", "quote"})
PRIORITIES = frozenset({"low", "normal", "high", "urgent"})
TRANSITIONS = {
    "new": frozenset({"assigned", "inspecting", "cancelled"}),
    "assigned": frozenset({"inspecting", "in_progress", "cancelled"}),
    "inspecting": frozenset({"awaiting_approval", "in_progress", "cancelled"}),
    "awaiting_approval": frozenset({"approved", "cancelled"}),
    "approved": frozenset({"in_progress", "cancelled"}),
    "in_progress": frozenset({"waiting_parts", "quality_check", "cancelled"}),
    "waiting_parts": frozenset({"in_progress", "cancelled"}),
    "quality_check": frozenset({"in_progress", "completed", "cancelled"}),
    "completed": frozenset(),
    "cancelled": frozenset(),
}


def _short(value: Any, *, field: str, limit: int) -> str | None:
    if value is None:
        return None
    word = str(value).strip()
    if len(word) > limit:
        raise ValidationError(f"{field} is too long")
    return word or None


def _when(value: Any) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValidationError("Invalid scheduled time") from exc
    if parsed.tzinfo is None:
        raise ValidationError("Scheduled time needs a timezone")
    return parsed


class JobService:
    @staticmethod
    def serialize(job: JobCard, parts: list[JobPart] | None = None) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": str(job.id), "reference": job.reference, "title": job.title,
            "customer_contact_id": str(job.customer_contact_id),
            "location_id": str(job.location_id) if job.location_id else None,
            "project_id": str(job.project_id) if job.project_id else None,
            "source_quote_id": str(job.source_quote_id) if job.source_quote_id else None,
            "source_type": job.source_type, "source_id": str(job.source_id) if job.source_id else None,
            "problem": job.problem, "asset_description": job.asset_description,
            "asset_serial": job.asset_serial, "priority": job.priority,
            "status": job.status, "stage": job.stage,
            "scheduled_at": job.scheduled_at.isoformat() if job.scheduled_at else None,
            "assigned_member_id": str(job.assigned_member_id) if job.assigned_member_id else None,
            "work_performed": job.work_performed, "completion_note": job.completion_note,
            "approval_note": job.approval_note,
            "approval_recorded_at": job.approval_recorded_at.isoformat() if job.approval_recorded_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "invoice_id": str(job.invoice_id) if job.invoice_id else None,
            "version": job.version, "created_at": job.created_at.isoformat() if job.created_at else None,
        }
        if parts is not None:
            data["parts"] = [{"id": str(part.id), "offering_id": str(part.offering_id),
                              "quantity": part.quantity, "serials": part.serials,
                              "inventory_movement_id": str(part.inventory_movement_id)}
                             for part in parts]
        return data

    @staticmethod
    async def _member(session: AsyncSession, business_id: uuid.UUID, member_id: uuid.UUID | None) -> WorkforceMember | None:
        if member_id is None:
            return None
        member = (await session.execute(select(WorkforceMember).where(
            WorkforceMember.id == member_id, WorkforceMember.business_id == business_id,
            WorkforceMember.deleted_at.is_(None), WorkforceMember.status == "active"))).scalar_one_or_none()
        if member is None:
            raise ResourceNotFound("Workforce member")
        return member

    @staticmethod
    async def _scope(session: AsyncSession, job: JobCard) -> None:
        locations = allowed_locations(session)
        if locations is not None and job.location_id is not None and job.location_id not in locations:
            raise OutsideLocationScope()
        identity = assigned_identity(session)
        if identity is not None:
            member = await JobService._member(session, job.business_id, job.assigned_member_id)
            if member is None or member.identity_id != identity:
                raise OutsideAssignmentScope()

    @staticmethod
    async def resolve(session: AsyncSession, business_id: uuid.UUID, job_id: uuid.UUID, *, lock: bool = False) -> JobCard:
        query = select(JobCard).where(JobCard.id == job_id, JobCard.business_id == business_id)
        if lock:
            query = query.with_for_update()
        job = (await session.execute(query)).scalar_one_or_none()
        if job is None:
            raise ResourceNotFound("Job card")
        await JobService._scope(session, job)
        return job

    @staticmethod
    async def detail(session: AsyncSession, business_id: uuid.UUID, job_id: uuid.UUID) -> dict[str, Any]:
        job = await JobService.resolve(session, business_id, job_id)
        parts = list((await session.execute(select(JobPart).where(
            JobPart.business_id == business_id, JobPart.job_id == job.id).order_by(JobPart.created_at))).scalars())
        data = JobService.serialize(job, parts)
        # This single contact is authorized by the already-scoped job card.
        # P2-01's broad customer book remains closed to assignment-scoped staff.
        customer = (await session.execute(select(CustomerContact.display_name, CustomerContact.phone).where(
            CustomerContact.id == job.customer_contact_id,
            CustomerContact.business_id == business_id,
            CustomerContact.deleted_at.is_(None),
        ).execution_options(skip_assignment_scope=True))).first()
        data["customer_name"] = customer[0] if customer else None
        data["customer_phone"] = customer[1] if customer else None
        return data

    @staticmethod
    async def list_jobs(session: AsyncSession, business_id: uuid.UUID, *, status: str | None = None,
                   customer_contact_id: uuid.UUID | None = None, project_id: uuid.UUID | None = None) -> list[dict[str, Any]]:
        query = select(JobCard).where(JobCard.business_id == business_id)
        if status:
            query = query.where(JobCard.status == status)
        if customer_contact_id:
            query = query.where(JobCard.customer_contact_id == customer_contact_id)
        if project_id:
            query = query.where(JobCard.project_id == project_id)
        identity = assigned_identity(session)
        if identity:
            query = query.where(JobCard.assigned_member_id.in_(select(WorkforceMember.id).where(
                WorkforceMember.business_id == business_id, WorkforceMember.identity_id == identity)))
        locations = allowed_locations(session)
        if locations:
            query = query.where((JobCard.location_id.is_(None)) | (JobCard.location_id.in_(locations)))
        rows = (await session.execute(query.order_by(JobCard.created_at.desc()).limit(100))).scalars().all()
        contacts = (await session.execute(select(CustomerContact.id, CustomerContact.display_name).where(
            CustomerContact.business_id == business_id,
            CustomerContact.id.in_([row.customer_contact_id for row in rows]),
            CustomerContact.deleted_at.is_(None),
        ).execution_options(skip_assignment_scope=True))).all() if rows else []
        names: dict[uuid.UUID, str] = {contact_id: display_name for contact_id, display_name in contacts}
        result = [JobService.serialize(row) for row in rows]
        for data, row in zip(result, rows, strict=True):
            data["customer_name"] = names.get(row.customer_contact_id)
        return result

    @staticmethod
    async def _record(session: AsyncSession, job: JobCard, actor_id: uuid.UUID, correlation_id: str,
                      event: str, action: str, before: dict[str, Any] | None = None) -> None:
        await OutboxService.publish(session, event_type=event, business_id=job.business_id,
                                    correlation_id=correlation_id,
                                    payload={"job_id": str(job.id), "status": job.status, "reference": job.reference})
        await AuditService.record(session, event_type=event, actor_identity_id=actor_id,
                                  actor_context="business", business_id=job.business_id,
                                  resource_type="job_card", resource_id=job.id, action=action,
                                  before_state=before, after_state={"status": job.status, "version": job.version})

    @staticmethod
    async def create(session: AsyncSession, business_id: uuid.UUID, actor_id: uuid.UUID,
                     correlation_id: str, payload: dict[str, Any]) -> JobCard:
        business = await BusinessService.get_by_id(session, business_id)
        if business is None:
            raise ResourceNotFound("Business")
        assert_business_mutable(business.state, action="create job")
        if assigned_identity(session):
            raise OutsideAssignmentScope()
        title = _short(payload.get("title"), field="title", limit=200)
        if not title:
            raise ValidationError("A job needs a title")
        customer = await CustomerResolver.resolve(session, business_id=business_id,
                                                  contact_id=uuid.UUID(str(payload["customer_contact_id"])))
        location_id = payload.get("location_id")
        if location_id:
            location = (await session.execute(select(BusinessLocation).where(
                BusinessLocation.id == location_id, BusinessLocation.business_id == business_id,
                BusinessLocation.deleted_at.is_(None)))).scalar_one_or_none()
            if location is None:
                raise ResourceNotFound("Location")
            permitted = allowed_locations(session)
            if permitted is not None and location_id not in permitted:
                raise OutsideLocationScope()
        project_id = payload.get("project_id")
        if project_id:
            project = await ProjectService.resolve(session, business_id=business_id, project_id=project_id)
            if project.customer_contact_id and project.customer_contact_id != customer.id:
                raise ValidationError("Project belongs to another customer")
        quote_id = payload.get("source_quote_id")
        if quote_id:
            quote = (await session.execute(select(Quote).where(Quote.id == quote_id,
                Quote.business_id == business_id))).scalar_one_or_none()
            if quote is None:
                raise ResourceNotFound("Quote")
            if quote.customer_contact_id and quote.customer_contact_id != customer.id:
                raise ValidationError("Quote belongs to another customer")
            if quote.status != "accepted":
                raise ValidationError("Only an accepted quote can start a job")
        source_type = str(payload.get("source_type") or "manual")
        if source_type not in SOURCE_TYPES:
            raise ValidationError("This job source is not connected yet")
        source_id = payload.get("source_id")
        if source_type == "project" and source_id != project_id:
            raise ValidationError("Project source must match the project")
        if source_type == "quote" and source_id != quote_id:
            raise ValidationError("Quote source must match the quote")
        if source_type == "manual" and source_id is not None:
            raise ValidationError("Manual jobs have no source ID")
        member_id = payload.get("assigned_member_id")
        await JobService._member(session, business_id, member_id)
        priority = str(payload.get("priority") or "normal")
        if priority not in PRIORITIES:
            raise ValidationError("Unknown priority")
        # A business-local sequence under an advisory lock prevents concurrent duplicate references.
        await session.execute(select(func.pg_advisory_xact_lock(func.hashtext(str(business_id)), 5100)))
        count = await session.scalar(select(func.count()).select_from(JobCard).where(JobCard.business_id == business_id))
        job = JobCard(business_id=business_id, location_id=location_id, customer_contact_id=customer.id,
                      project_id=project_id, source_quote_id=quote_id, source_type=source_type, source_id=source_id,
                      reference=f"J-{datetime.now(timezone.utc).year}-{(count or 0) + 1:05d}", title=title,
                      problem=_short(payload.get("problem"), field="problem", limit=4000),
                      asset_description=_short(payload.get("asset_description"), field="asset", limit=300),
                      asset_serial=_short(payload.get("asset_serial"), field="serial", limit=100),
                      priority=priority, scheduled_at=_when(payload.get("scheduled_at")),
                      assigned_member_id=member_id, status="assigned" if member_id else "new", created_by=actor_id)
        session.add(job)
        await session.flush()
        await JobService._record(session, job, actor_id, correlation_id, "job.created", "create")
        return job

    @staticmethod
    async def assign(session: AsyncSession, business_id: uuid.UUID, job_id: uuid.UUID,
                     member_id: uuid.UUID, actor_id: uuid.UUID, correlation_id: str) -> JobCard:
        job = await JobService.resolve(session, business_id, job_id, lock=True)
        if assigned_identity(session):
            raise OutsideAssignmentScope()
        if job.status in {"completed", "cancelled"}:
            raise ConflictError("Closed jobs cannot be assigned")
        await JobService._member(session, business_id, member_id)
        if job.assigned_member_id == member_id:
            return job
        before = {"assigned_member_id": str(job.assigned_member_id) if job.assigned_member_id else None}
        job.assigned_member_id = member_id
        if job.status == "new":
            job.status = "assigned"
        job.version += 1
        job.updated_at = datetime.now(timezone.utc)
        await JobService._record(session, job, actor_id, correlation_id, "job.assigned", "assign", before)
        return job

    @staticmethod
    async def transition(session: AsyncSession, business_id: uuid.UUID, job_id: uuid.UUID,
                         status: str, work_performed: str | None, completion_note: str | None,
                         approval_note: str | None,
                         expected_version: int, actor_id: uuid.UUID, correlation_id: str) -> JobCard:
        job = await JobService.resolve(session, business_id, job_id, lock=True)
        if job.version != expected_version:
            raise ConflictError("The job changed. Reload before updating")
        if status not in TRANSITIONS[job.status]:
            raise ValidationError("That job status change is not allowed")
        if status != "cancelled" and job.assigned_member_id is None:
            raise ValidationError("Assign the job before work begins")
        performed = _short(work_performed, field="work performed", limit=6000)
        if performed:
            job.work_performed = performed
        if status == "completed" and not job.work_performed:
            raise ValidationError("Record the work performed before completing")
        if status == "approved":
            proof = _short(approval_note, field="approval note", limit=2000)
            if not proof and not job.source_quote_id:
                raise ValidationError("Record how the customer approved this work")
            job.approval_note = proof or f"Accepted quote {job.source_quote_id}"
            job.approval_recorded_at = datetime.now(timezone.utc)
        before = {"status": job.status, "version": job.version}
        job.status = status
        if status == "completed":
            job.completed_at = datetime.now(timezone.utc)
            job.completion_note = _short(completion_note, field="completion note", limit=2000)
        job.version += 1
        job.updated_at = datetime.now(timezone.utc)
        event = "job.completed" if status == "completed" else "job.status.changed"
        await JobService._record(session, job, actor_id, correlation_id, event, "transition", before)
        return job

    @staticmethod
    async def consume_part(session: AsyncSession, business_id: uuid.UUID, job_id: uuid.UUID,
                           record_id: uuid.UUID, quantity: int, serials: list[str],
                           idempotency_key: str, actor_id: uuid.UUID,
                           correlation_id: str) -> JobPart:
        job = await JobService.resolve(session, business_id, job_id, lock=True)
        if job.status not in {"in_progress", "waiting_parts", "quality_check"}:
            raise ValidationError("Start the job before using parts")
        if not idempotency_key or len(idempotency_key) > 100:
            raise ValidationError("A short idempotency key is required")
        cleaned_serials = stock_ledger.clean_serials(serials)
        existing = (await session.execute(select(JobPart).where(
            JobPart.business_id == business_id, JobPart.job_id == job_id,
            JobPart.idempotency_key == idempotency_key))).scalar_one_or_none()
        if existing:
            movement = (await session.execute(select(InventoryMovement).where(
                InventoryMovement.id == existing.inventory_movement_id,
                InventoryMovement.business_id == business_id))).scalar_one_or_none()
            if (movement is None or movement.inventory_record_id != record_id
                    or existing.quantity != quantity or existing.serials != cleaned_serials):
                raise ConflictError("That part request key was already used for a different item or quantity")
            return existing
        permitted = allowed_locations(session)
        movement = await StockService.consume_for_job(
            session, business_id=business_id, job_id=job_id,
            record_id=record_id, quantity=quantity, serials=cleaned_serials,
            customer_contact_id=job.customer_contact_id, actor_id=actor_id,
            allowed=list(permitted) if permitted is not None else None)
        part = JobPart(business_id=business_id, job_id=job_id,
                       inventory_movement_id=movement.id, offering_id=movement.offering_id,
                       quantity=quantity, serials=cleaned_serials, idempotency_key=idempotency_key)
        session.add(part)
        await session.flush()
        await JobService._record(session, job, actor_id, correlation_id, "job.part.consumed", "consume_part")
        return part
