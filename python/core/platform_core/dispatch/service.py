"""Dispatch execution (Capability Universe §13).

A dispatch job moves or hands over something after the order exists. It does
not change the order, the fulfilment choice, or a payment. Status names match
packages/contracts/src/dispatch.ts.

Live coordinates are not invented. public_tracking always reports
location_mode "status_only" and live_location null until a device posts a
real fix — this service has no path that fabricates one.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.dispatch.models import DispatchEvent, DispatchJob
from platform_core.exceptions import ConflictError, ResourceNotFound, ValidationError
from platform_core.models import (
    BusinessLocation,
    CustomerContact,
    FulfilmentJob,
    SalesOrder,
    WorkforceMember,
)
from platform_core.services.audit import AuditService
from platform_core.services.outbox import OutboxService

# Keep in step with packages/contracts/src/dispatch.ts
STATUSES = (
    "unassigned",
    "assigned",
    "picked_up",
    "out_for_delivery",
    "delivered",
    "failed",
)
KINDS = ("delivery", "pickup")
# Crew may call the customer only while the job is still in their hands.
ACTIVE = frozenset({"assigned", "picked_up", "out_for_delivery"})
# Customer stepper. "placed" is the order itself; dispatch starts at preparing.
REACHED = {
    "unassigned": "preparing",
    "assigned": "preparing",
    "picked_up": "picked_up",
    "out_for_delivery": "on_the_way",
    "delivered": "delivered",
}
COLUMNS = (
    ("unassigned", "Unassigned", ("unassigned",)),
    ("assigned", "Assigned", ("assigned",)),
    ("out_now", "Out now", ("picked_up", "out_for_delivery")),
    ("delivered", "Delivered", ("delivered",)),
    ("attention", "Failed / attention", ("failed",)),
)

# From-status → allowed next statuses. Pickup never enters out_for_delivery;
# a delivery cannot skip it. Checked again in _assert_transition.
_NEXT: dict[str, frozenset[str]] = {
    "unassigned": frozenset({"assigned"}),
    "assigned": frozenset({"picked_up", "failed"}),
    "picked_up": frozenset({"out_for_delivery", "delivered", "failed"}),
    "out_for_delivery": frozenset({"delivered", "failed"}),
    "failed": frozenset({"assigned"}),
    "delivered": frozenset(),
}


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _when(raw: Any) -> datetime | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, datetime):
        parsed = raw
    else:
        parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _note(raw: Any, field: str) -> str | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    if len(text) > 500:
        raise ValidationError("Keep the note under 500 characters", details={"field": field})
    return text


def _place_text(address: dict[str, Any] | None) -> str:
    if not address:
        return ""
    parts = [address.get("line"), address.get("area"), address.get("city"), address.get("postal_code")]
    return ", ".join(str(part) for part in parts if part)


def maps_search(address: dict[str, Any] | None) -> str | None:
    """A Maps link for an address the business already has. Not a live fix."""
    if not address:
        return None
    lat, lng = address.get("lat"), address.get("lng")
    if lat is not None and lng is not None:
        query = f"{lat},{lng}"
    else:
        query = _place_text(address)
    if not query:
        return None
    return "https://www.google.com/maps/search/?api=1&query=" + quote(query)


def _dropoff(raw: Any) -> dict[str, Any] | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValidationError("Drop-off must be an address", details={"field": "dropoff"})
    allowed = ("line", "area", "city", "postal_code", "lat", "lng")
    extra = set(raw) - set(allowed)
    if extra:
        raise ValidationError("Unknown drop-off field", details={"field": "dropoff", "unknown": sorted(extra)})
    out: dict[str, Any] = {}
    for key in ("line", "area", "city", "postal_code"):
        if raw.get(key):
            out[key] = str(raw[key]).strip()
    for key in ("lat", "lng"):
        if raw.get(key) is not None:
            out[key] = float(raw[key])
    return out or None


def _dropoff_from_fulfilment(address: dict[str, Any]) -> dict[str, Any] | None:
    """The customer's checkout address, read into a drop-off. It is the
    customer's own shape (line1/line2, pincode, latitude…), so it is mapped
    rather than refused; unknown keys are simply not carried."""
    def first(*keys: str) -> Any:
        return next((address[k] for k in keys if address.get(k) not in (None, "")), None)

    line = ", ".join(str(address[k]).strip() for k in ("line", "line1", "line2", "address_line", "landmark")
                     if address.get(k))
    mapped: dict[str, Any] = {"line": line or None, "area": first("area", "locality"), "city": first("city"),
                              "postal_code": first("postal_code", "pincode", "postal")}
    lat, lng = first("lat", "latitude"), first("lng", "longitude")
    if lat is not None and lng is not None:
        mapped.update(lat=lat, lng=lng)
    return _dropoff(mapped)


def reached_step(job: DispatchJob) -> str:
    """How far the customer stepper has got, including after a failure."""
    if job.delivered_at or job.status == "delivered":
        return "delivered"
    if job.out_for_delivery_at or job.status == "out_for_delivery":
        return "on_the_way"
    if job.picked_up_at or job.status == "picked_up":
        return "picked_up"
    return "preparing"


def _first_name(display_name: str | None) -> str | None:
    if not display_name:
        return None
    token = display_name.strip().split()[0]
    return token or None


class DispatchService:
    @staticmethod
    def _assert_transition(job: DispatchJob, nxt: str) -> None:
        if nxt not in STATUSES:
            raise ValidationError("Unknown status", details={"field": "status", "status": nxt})
        allowed = _NEXT[job.status]
        if nxt not in allowed:
            raise ValidationError(
                "That status move is not allowed",
                details={"from": job.status, "to": nxt},
            )
        if job.kind == "pickup" and nxt == "out_for_delivery":
            raise ValidationError("Pickup jobs do not go out for delivery")
        if job.kind == "delivery" and job.status == "picked_up" and nxt == "delivered":
            raise ValidationError(
                "Delivery jobs go out for delivery before they are delivered",
                details={"from": "picked_up", "to": "delivered"},
            )

    @staticmethod
    async def _order(session: AsyncSession, business_id: uuid.UUID, order_id: uuid.UUID) -> SalesOrder:
        order = (
            await session.execute(
                select(SalesOrder).where(
                    SalesOrder.id == order_id,
                    SalesOrder.business_id == business_id,
                    SalesOrder.deleted_at.is_(None),
                )
            )
        ).scalars().first()
        if order is None:
            raise ResourceNotFound("Order")
        if order.status in {"cancelled", "rejected"}:
            raise ValidationError("A cancelled order is not dispatched")
        return order

    @staticmethod
    async def _location(session: AsyncSession, business_id: uuid.UUID, location_id: uuid.UUID) -> BusinessLocation:
        location = (
            await session.execute(
                select(BusinessLocation).where(
                    BusinessLocation.id == location_id,
                    BusinessLocation.business_id == business_id,
                    BusinessLocation.deleted_at.is_(None),
                )
            )
        ).scalars().first()
        if location is None:
            raise ResourceNotFound("Location")
        return location

    @staticmethod
    async def _member(session: AsyncSession, business_id: uuid.UUID, member_id: uuid.UUID) -> WorkforceMember:
        member = (
            await session.execute(
                select(WorkforceMember).where(
                    WorkforceMember.id == member_id,
                    WorkforceMember.business_id == business_id,
                    WorkforceMember.deleted_at.is_(None),
                )
            )
        ).scalars().first()
        if member is None or member.status != "active":
            raise ValidationError("Choose an active staff member", details={"field": "member_id"})
        return member

    @staticmethod
    async def _by_order(
        session: AsyncSession, business_id: uuid.UUID, order_id: uuid.UUID
    ) -> DispatchJob | None:
        return (
            await session.execute(
                select(DispatchJob).where(
                    DispatchJob.business_id == business_id,
                    DispatchJob.order_id == order_id,
                )
            )
        ).scalars().first()

    @staticmethod
    async def _by_key(
        session: AsyncSession, business_id: uuid.UUID, key: str
    ) -> DispatchJob | None:
        return (
            await session.execute(
                select(DispatchJob).where(
                    DispatchJob.business_id == business_id,
                    DispatchJob.idempotency_key == key,
                )
            )
        ).scalars().first()

    @staticmethod
    async def _event_by_key(
        session: AsyncSession, business_id: uuid.UUID, key: str
    ) -> DispatchEvent | None:
        return (
            await session.execute(
                select(DispatchEvent).where(
                    DispatchEvent.business_id == business_id,
                    DispatchEvent.idempotency_key == key,
                )
            )
        ).scalars().first()

    @staticmethod
    async def get_job(
        session: AsyncSession, *, business_id: uuid.UUID, job_id: uuid.UUID
    ) -> DispatchJob:
        job = (
            await session.execute(
                select(DispatchJob).where(
                    DispatchJob.id == job_id,
                    DispatchJob.business_id == business_id,
                )
            )
        ).scalars().first()
        if job is None:
            raise ResourceNotFound("Dispatch job")
        return job

    @staticmethod
    async def create_job(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        actor_id: uuid.UUID,
        correlation_id: str,
        payload: dict[str, Any],
    ) -> DispatchJob:
        order_id = uuid.UUID(str(payload["order_id"]))
        key = _note(payload.get("idempotency_key"), "idempotency_key")
        if key:
            existing = await DispatchService._by_key(session, business_id, key)
            if existing is not None:
                return existing
        # One execution record per order. A second create is the first job.
        existing = await DispatchService._by_order(session, business_id, order_id)
        if existing is not None:
            return existing

        order = await DispatchService._order(session, business_id, order_id)
        fulfilment = (
            await session.execute(
                select(FulfilmentJob).where(
                    FulfilmentJob.business_id == business_id,
                    FulfilmentJob.order_id == order_id,
                )
            )
        ).scalars().first()
        kind = payload.get("kind") or (fulfilment.mode if fulfilment else None)
        if kind not in KINDS:
            raise ValidationError("Choose delivery or pickup", details={"field": "kind"})
        if fulfilment is not None and fulfilment.mode in KINDS and kind != fulfilment.mode:
            raise ValidationError(
                "Dispatch follows the fulfilment choice",
                details={"field": "kind", "fulfilment": fulfilment.mode},
            )
        location_id = uuid.UUID(str(payload.get("location_id") or order.location_id))
        location = await DispatchService._location(session, business_id, location_id)
        dropoff = _dropoff(payload.get("dropoff"))
        if dropoff is None and fulfilment is not None and isinstance(fulfilment.delivery_address, dict):
            dropoff = _dropoff_from_fulfilment(fulfilment.delivery_address)
        if kind == "delivery" and not _place_text(dropoff):
            raise ValidationError("A delivery needs a drop-off address", details={"field": "dropoff"})

        now = datetime.now(timezone.utc)
        job = DispatchJob(
            business_id=business_id,
            order_id=order.id,
            fulfilment_job_id=fulfilment.id if fulfilment else None,
            location_id=location.id,
            kind=kind,
            status="unassigned",
            customer_contact_id=order.customer_contact_id,
            order_number=order.order_number,
            pickup_label=location.name,
            pickup_address=location.address if isinstance(location.address, dict) else None,
            dropoff=dropoff,
            planned_at=_when(payload.get("planned_at")),
            idempotency_key=key,
            created_by=actor_id,
            updated_by=actor_id,
            created_at=now,
            updated_at=now,
        )
        session.add(job)
        try:
            async with session.begin_nested():
                await session.flush()
        except IntegrityError:
            again = await DispatchService._by_order(session, business_id, order_id)
            if again is not None:
                return again
            raise
        # History row plus dispatch.job_created. No customer message on create.
        await DispatchService._record(
            session,
            job=job,
            actor_id=actor_id,
            correlation_id=correlation_id,
            from_status=None,
            to_status="unassigned",
            note=None,
            key=f"create:{job.id}",
        )
        return job

    @staticmethod
    async def transition(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        job_id: uuid.UUID,
        actor_id: uuid.UUID,
        correlation_id: str,
        payload: dict[str, Any],
    ) -> DispatchJob:
        job = await DispatchService.get_job(session, business_id=business_id, job_id=job_id)
        nxt = str(payload.get("status") or "")
        if nxt not in STATUSES:
            raise ValidationError("Unknown status", details={"field": "status", "status": nxt})
        # A repeated submit of the same key is the move that already happened,
        # even when the job has since left the status that move started from.
        key = _note(payload.get("idempotency_key"), "idempotency_key") or f"{job.id}:{nxt}:{job.version}"
        prior = await DispatchService._event_by_key(session, business_id, key)
        if prior is not None:
            if prior.job_id != job.id or prior.to_status != nxt:
                raise ConflictError(
                    "This idempotency key was already used for a different move",
                    details={"idempotency_key": key},
                )
            return job
        DispatchService._assert_transition(job, nxt)
        member_id = payload.get("member_id")
        member: WorkforceMember | None = None
        if nxt == "assigned":
            if not member_id:
                raise ValidationError("Choose who is taking this job", details={"field": "member_id"})
            member = await DispatchService._member(session, business_id, uuid.UUID(str(member_id)))
        proof = _note(payload.get("proof_note"), "proof_note")
        reason = _note(payload.get("reason"), "reason")
        if nxt == "delivered" and not proof:
            raise ValidationError("Add a proof note for the delivery", details={"field": "proof_note"})
        if nxt == "failed" and not reason:
            raise ValidationError("Say why it failed", details={"field": "reason"})

        before = job.status
        now = datetime.now(timezone.utc)
        job.status = nxt
        job.updated_by = actor_id
        job.updated_at = now
        job.version += 1
        if nxt == "assigned" and member is not None:
            job.assigned_member_id = member.id
            job.assigned_at = now
            planned = _when(payload.get("planned_at"))
            if planned is not None:
                job.planned_at = planned
        elif nxt == "picked_up":
            job.picked_up_at = now
        elif nxt == "out_for_delivery":
            job.out_for_delivery_at = now
        elif nxt == "delivered":
            job.delivered_at = now
            job.proof_note = proof
        elif nxt == "failed":
            job.failed_at = now
            job.failure_reason = reason

        note = proof or reason
        try:
            await DispatchService._record(
                session,
                job=job,
                actor_id=actor_id,
                correlation_id=correlation_id,
                from_status=before,
                to_status=nxt,
                note=note,
                key=key,
            )
        except IntegrityError:
            # The savepoint undid this attempt. The winner already committed
            # the same key. Do not roll the request transaction back — that
            # would clear the tenant GUC the re-read still needs.
            session.expire_all()
            winner = await DispatchService._event_by_key(session, business_id, key)
            if winner is not None and winner.job_id == job_id and winner.to_status == nxt:
                return await DispatchService.get_job(session, business_id=business_id, job_id=job_id)
            raise ConflictError("This move was already recorded", details={"idempotency_key": key})
        return job

    @staticmethod
    async def _record(
        session: AsyncSession,
        *,
        job: DispatchJob,
        actor_id: uuid.UUID,
        correlation_id: str,
        from_status: str | None,
        to_status: str,
        note: str | None,
        key: str,
    ) -> None:
        """Append the history row and publish the dispatch event."""
        event = DispatchEvent(
            business_id=job.business_id,
            job_id=job.id,
            location_id=job.location_id,
            assigned_member_id=job.assigned_member_id,
            idempotency_key=key,
            from_status=from_status,
            to_status=to_status,
            note=note,
            actor_identity_id=actor_id,
        )
        async with session.begin_nested():
            session.add(event)
            await session.flush()
        await AuditService.record(
            session,
            event_type=f"dispatch.{to_status}",
            actor_identity_id=actor_id,
            actor_context="business",
            business_id=job.business_id,
            resource_type="dispatch_job",
            resource_id=job.id,
            action=to_status,
            before_state={"status": from_status} if from_status else None,
            after_state={"status": to_status, "kind": job.kind},
            reason=note,
        )
        await OutboxService.publish(
            session,
            event_type=f"dispatch.{to_status}" if to_status != "unassigned" else "dispatch.job_created",
            payload=_event_payload(job, from_status, to_status, note),
            business_id=job.business_id,
            correlation_id=correlation_id,
        )
        # The customer's record and messages follow from these dispatch events:
        # Fulfilment subscribes and moves its own record (fulfilment_follows_dispatch),
        # so dispatch never publishes another module's events for it.

    @staticmethod
    async def list_jobs(
        session: AsyncSession, business_id: uuid.UUID, *, status: str | None = None
    ) -> list[DispatchJob]:
        query = select(DispatchJob).where(DispatchJob.business_id == business_id)
        if status:
            query = query.where(DispatchJob.status == status)
        query = query.order_by(DispatchJob.planned_at.asc().nulls_last(), DispatchJob.created_at)
        return list((await session.execute(query)).scalars())

    @staticmethod
    async def board(session: AsyncSession, business_id: uuid.UUID) -> list[dict[str, Any]]:
        jobs = await DispatchService.list_jobs(session, business_id)
        rows = await DispatchService.serialize_many(session, jobs, privileged=True)
        by_status: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            by_status.setdefault(str(row["status"]), []).append(row)
        return [
            {"key": key, "label": label, "jobs": [job for status in statuses for job in by_status.get(status, [])]}
            for key, label, statuses in COLUMNS
        ]

    @staticmethod
    async def mine(session: AsyncSession, business_id: uuid.UUID) -> dict[str, Any]:
        """The signed-in crew member's jobs. Assignment scope already narrowed the query."""
        jobs = await DispatchService.list_jobs(session, business_id)
        open_jobs = [job for job in jobs if job.status in ACTIVE or job.status == "assigned"]
        # list_jobs is planned-time order. The next stop is the first still open.
        rows = await DispatchService.serialize_many(session, jobs, privileged=False)
        by_id = {row["id"]: row for row in rows}
        ordered = [by_id[str(job.id)] for job in jobs if str(job.id) in by_id]
        nxt = next((by_id[str(job.id)] for job in open_jobs if str(job.id) in by_id), None)
        return {"next": nxt, "jobs": ordered}

    @staticmethod
    async def serialize_many(
        session: AsyncSession, jobs: list[DispatchJob], *, privileged: bool
    ) -> list[dict[str, Any]]:
        if not jobs:
            return []
        contact_ids = {job.customer_contact_id for job in jobs if job.customer_contact_id}
        member_ids = {job.assigned_member_id for job in jobs if job.assigned_member_id}
        # The contact is the one already on a job this person can see. Skip the
        # customer-book arm of assignment scope so the phone for this job loads
        # without opening the rest of the book.
        contacts: dict[Any, CustomerContact] = {}
        if contact_ids:
            found = (
                await session.execute(
                    select(CustomerContact).where(CustomerContact.id.in_(contact_ids)),
                    execution_options={"skip_assignment_scope": True},
                )
            ).scalars()
            contacts = {row.id: row for row in found}
        members: dict[Any, WorkforceMember] = {}
        if member_ids:
            found_members = (
                await session.execute(select(WorkforceMember).where(WorkforceMember.id.in_(member_ids)))
            ).scalars()
            members = {row.id: row for row in found_members}
        return [
            _serialize(job, contacts.get(job.customer_contact_id), members.get(job.assigned_member_id), privileged)
            for job in jobs
        ]

    @staticmethod
    async def serialize_one(
        session: AsyncSession, job: DispatchJob, *, privileged: bool
    ) -> dict[str, Any]:
        rows = await DispatchService.serialize_many(session, [job], privileged=privileged)
        return rows[0]

    @staticmethod
    async def public_tracking(session: AsyncSession, *, order_id: uuid.UUID) -> dict[str, Any] | None:
        """Status and times for the customer page. Never a made-up coordinate."""
        job = (
            await session.execute(select(DispatchJob).where(DispatchJob.order_id == order_id))
        ).scalars().first()
        if job is None:
            return None
        partner: str | None = None
        if job.status in ACTIVE and job.assigned_member_id is not None:
            member = await session.get(WorkforceMember, job.assigned_member_id)
            partner = _first_name(member.display_name if member else None)
        return {
            "status": job.status,
            "reached_step": reached_step(job),
            "failed": job.status == "failed",
            "timestamps": _timestamps(job),
            "live_location": None,
            "location_mode": "status_only",
            "partner_first_name": partner,
        }


def _timestamps(job: DispatchJob) -> dict[str, str | None]:
    return {
        "planned_at": _iso(job.planned_at),
        "assigned_at": _iso(job.assigned_at),
        "picked_up_at": _iso(job.picked_up_at),
        "out_for_delivery_at": _iso(job.out_for_delivery_at),
        "delivered_at": _iso(job.delivered_at),
        "failed_at": _iso(job.failed_at),
    }


def _event_payload(job: DispatchJob, from_status: str | None, to_status: str, note: str | None) -> dict[str, Any]:
    # job_id is the fulfilment job when this execution is tied to one, so the
    # existing out-for-delivery ladder keeps the key it already uses.
    fulfilment_or_dispatch = job.fulfilment_job_id or job.id
    return {
        "business_id": str(job.business_id),
        "job_id": str(fulfilment_or_dispatch),
        "dispatch_job_id": str(job.id),
        "order_id": str(job.order_id),
        "from": from_status,
        "to": to_status,
        "reason": note,
        "source": "dispatch",
    }


def _serialize(
    job: DispatchJob,
    contact: CustomerContact | None,
    member: WorkforceMember | None,
    privileged: bool,
) -> dict[str, Any]:
    show_phone = privileged or job.status in ACTIVE
    phone = contact.phone if contact and show_phone else None
    return {
        "id": str(job.id),
        "business_id": str(job.business_id),
        "order_id": str(job.order_id),
        "order_number": job.order_number,
        "fulfilment_job_id": str(job.fulfilment_job_id) if job.fulfilment_job_id else None,
        "kind": job.kind,
        "status": job.status,
        "reached_step": reached_step(job),
        "location_id": str(job.location_id),
        "assigned_member_id": str(job.assigned_member_id) if job.assigned_member_id else None,
        "assignee_name": member.display_name if member else None,
        "pickup": {
            "location_id": str(job.location_id),
            "label": job.pickup_label,
            "address": job.pickup_address,
            "maps_url": maps_search(job.pickup_address if isinstance(job.pickup_address, dict) else None),
        },
        "dropoff": job.dropoff,
        "dropoff_maps_url": maps_search(job.dropoff if isinstance(job.dropoff, dict) else None),
        "customer": {
            "name": contact.display_name if contact else None,
            "phone": phone,
        },
        "timestamps": _timestamps(job),
        "proof_note": job.proof_note,
        "failure_reason": job.failure_reason,
        "version": job.version,
        # Honest: no device has posted a coordinate.
        "live_location": None,
        "location_mode": "status_only",
    }
