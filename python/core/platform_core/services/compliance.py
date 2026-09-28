"""Owner-entered licence and filing calendar (P1-09).

This records dates supplied by the business or its accountant. It does not
calculate legal deadlines or offer tax/legal advice.
"""

from __future__ import annotations

import calendar
import uuid
from datetime import date, datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.exceptions import ConflictError, OutsideLocationScope, ResourceNotFound, ValidationError
from platform_core.models import BusinessLocation, ComplianceHistory, ComplianceItem
from platform_core.services.audit import AuditService
from platform_core.services.outbox import OutboxService

IST = ZoneInfo("Asia/Kolkata")
KINDS = frozenset({
    "fssai", "trade_licence", "shop_establishment", "drug_licence", "fire_noc", "bar_licence",
    "pollution", "gst_registration", "gst_filing", "income_tax", "tds", "professional_tax",
    "rera", "accreditation", "other",
})
RECURRENCES = frozenset({"none", "monthly", "quarterly", "yearly"})


def _today() -> date:
    return datetime.now(IST).date()


def _advance(day: date, recurrence: str) -> date:
    months = {"monthly": 1, "quarterly": 3, "yearly": 12}.get(recurrence)
    if months is None:
        raise ValidationError("Choose a recurring schedule to calculate the next due date")
    year, month = divmod(day.year * 12 + day.month - 1 + months, 12)
    month += 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


class ComplianceService:
    @staticmethod
    def serialize(item: ComplianceItem) -> dict[str, Any]:
        today = _today()
        due = item.due_on
        attention = ("archived" if item.status == "archived" else "overdue" if due < today else
                     "due_soon" if due <= date.fromordinal(today.toordinal() + 7) else "upcoming")
        return {
            "id": str(item.id), "business_id": str(item.business_id),
            "location_id": str(item.location_id) if item.location_id else None,
            "item_type": item.item_type, "kind": item.kind, "title": item.title,
            "licence_number": item.licence_number, "authority": item.authority,
            "issued_on": item.issued_on.isoformat() if item.issued_on else None,
            "due_on": due.isoformat(), "recurrence": item.recurrence,
            "document_url": item.document_url, "show_on_site": item.show_on_site,
            "notes": item.notes, "status": item.status, "attention": attention,
            "last_done_on": item.last_done_on.isoformat() if item.last_done_on else None,
            "version": item.version,
        }

    @staticmethod
    async def _location(session: AsyncSession, business_id: uuid.UUID, location_id: uuid.UUID | None,
                        allowed_locations: list[uuid.UUID] | None) -> None:
        if allowed_locations is not None and (location_id is None or location_id not in allowed_locations):
            raise OutsideLocationScope()
        if location_id is not None:
            location = await session.get(BusinessLocation, location_id)
            if location is None or location.business_id != business_id or location.deleted_at is not None:
                raise ResourceNotFound("Location")

    @staticmethod
    def _validate(data: dict[str, Any]) -> None:
        if data.get("item_type") not in ("licence", "filing"):
            raise ValidationError("Choose licence or filing")
        if data.get("kind") not in KINDS:
            raise ValidationError("Choose a listed licence or filing kind")
        title = str(data.get("title") or "").strip()
        if not 1 <= len(title) <= 120:
            raise ValidationError("Give this licence or filing a title")
        data["title"] = title
        if data.get("recurrence") not in RECURRENCES:
            raise ValidationError("Choose a reminder recurrence")
        if not isinstance(data.get("due_on"), date):
            raise ValidationError("Enter the due or expiry date supplied by your team")
        if not isinstance(data.get("show_on_site"), bool):
            raise ValidationError("Choose whether this licence appears on your website")
        if data.get("show_on_site") and (data.get("item_type") != "licence" or not data.get("licence_number")):
            raise ValidationError("Only a licence with a number can appear on the website")
        document = data.get("document_url")
        if document and not str(document).startswith("https://"):
            raise ValidationError("Document links must use HTTPS")
        issued = data.get("issued_on")
        due = data.get("due_on")
        if issued is not None and due is not None and issued > due:
            raise ValidationError("The issue date cannot be after the due or expiry date")

    @staticmethod
    async def _change(session: AsyncSession, item: ComplianceItem, actor_id: uuid.UUID, action: str,
                      from_due: date | None, note: str | None = None) -> None:
        session.add(ComplianceHistory(business_id=item.business_id, item_id=item.id, action=action,
                                      from_due=from_due, to_due=item.due_on, note=note,
                                      actor_identity_id=actor_id))
        await session.flush()
        event = f"compliance.item.{action if action in {'created', 'updated', 'renewed', 'filed', 'archived'} else 'updated'}"
        await OutboxService.publish(session, event_type=event, business_id=item.business_id,
                                    payload={"business_id": str(item.business_id), "item_id": str(item.id),
                                             "due_on": item.due_on.isoformat(), "status": item.status})
        await AuditService.record(session, event_type=event, actor_identity_id=actor_id,
                                  actor_context="business", action=action, business_id=item.business_id,
                                  resource_type="compliance_item", resource_id=item.id,
                                  after_state={"due_on": item.due_on.isoformat(), "status": item.status})

    @staticmethod
    async def create(session: AsyncSession, business_id: uuid.UUID, actor_id: uuid.UUID,
                     data: dict[str, Any], allowed_locations: list[uuid.UUID] | None) -> ComplianceItem:
        ComplianceService._validate(data)
        await ComplianceService._location(session, business_id, data.get("location_id"), allowed_locations)
        item = ComplianceItem(business_id=business_id, created_by=actor_id, updated_by=actor_id, **data)
        session.add(item)
        await session.flush()
        await ComplianceService._change(session, item, actor_id, "created", None)
        return item

    @staticmethod
    async def get(session: AsyncSession, business_id: uuid.UUID, item_id: uuid.UUID,
                  allowed_locations: list[uuid.UUID] | None, *, lock: bool = False) -> ComplianceItem:
        q = select(ComplianceItem).where(ComplianceItem.business_id == business_id, ComplianceItem.id == item_id)
        if lock:
            q = q.with_for_update()
        item = (await session.execute(q)).scalars().first()
        if item is None:
            raise ResourceNotFound("Licence or filing")
        if allowed_locations is not None and item.location_id not in allowed_locations:
            raise OutsideLocationScope()
        return item

    @staticmethod
    async def list_items(session: AsyncSession, business_id: uuid.UUID,
                         allowed_locations: list[uuid.UUID] | None, *, archived: bool = False) -> dict[str, Any]:
        q = select(ComplianceItem).where(ComplianceItem.business_id == business_id)
        if not archived:
            q = q.where(ComplianceItem.status == "active")
        if allowed_locations is not None:
            q = q.where(ComplianceItem.location_id.in_(allowed_locations))
        rows = list((await session.execute(q.order_by(ComplianceItem.due_on, ComplianceItem.title))).scalars())
        return {"items": [ComplianceService.serialize(row) for row in rows],
                "counts": {"overdue": sum(row.due_on < _today() and row.status == "active" for row in rows),
                           "due_soon": sum(_today() <= row.due_on <= date.fromordinal(_today().toordinal() + 7)
                                           and row.status == "active" for row in rows)}}

    @staticmethod
    async def history(session: AsyncSession, business_id: uuid.UUID, item_id: uuid.UUID,
                      allowed_locations: list[uuid.UUID] | None) -> list[dict[str, Any]]:
        await ComplianceService.get(session, business_id, item_id, allowed_locations)
        rows = (await session.execute(select(ComplianceHistory).where(
            ComplianceHistory.business_id == business_id, ComplianceHistory.item_id == item_id,
        ).order_by(ComplianceHistory.created_at.desc()))).scalars()
        return [{"action": row.action, "from_due": row.from_due.isoformat() if row.from_due else None,
                 "to_due": row.to_due.isoformat() if row.to_due else None, "note": row.note,
                 "at": row.created_at.isoformat()} for row in rows]

    @staticmethod
    async def update(session: AsyncSession, business_id: uuid.UUID, item_id: uuid.UUID, actor_id: uuid.UUID,
                     changes: dict[str, Any], allowed_locations: list[uuid.UUID] | None) -> ComplianceItem:
        item = await ComplianceService.get(session, business_id, item_id, allowed_locations, lock=True)
        if item.status == "archived":
            raise ConflictError("Restore this item before changing it")
        merged = {k: getattr(item, k) for k in ("item_type", "kind", "title", "licence_number", "authority",
                  "issued_on", "due_on", "recurrence", "document_url", "show_on_site", "notes", "location_id")}
        merged.update(changes)
        ComplianceService._validate(merged)
        await ComplianceService._location(session, business_id, merged["location_id"], allowed_locations)
        before = item.due_on
        for key in merged:
            setattr(item, key, merged[key])
        item.updated_by, item.updated_at, item.version = actor_id, datetime.now(timezone.utc), item.version + 1
        await session.flush()
        await ComplianceService._change(session, item, actor_id, "updated", before)
        return item

    @staticmethod
    async def renew(session: AsyncSession, business_id: uuid.UUID, item_id: uuid.UUID, actor_id: uuid.UUID,
                    new_due_on: date, completed_on: date, note: str | None,
                    allowed_locations: list[uuid.UUID] | None) -> ComplianceItem:
        item = await ComplianceService.get(session, business_id, item_id, allowed_locations, lock=True)
        if item.item_type != "licence" or item.status != "active":
            raise ConflictError("Only an active licence can be renewed")
        if new_due_on <= item.due_on:
            raise ValidationError("Enter the new expiry date supplied by the issuing authority")
        before = item.due_on
        item.due_on, item.last_done_on, item.updated_by = new_due_on, completed_on, actor_id
        item.updated_at, item.version = datetime.now(timezone.utc), item.version + 1
        await session.flush()
        await ComplianceService._change(session, item, actor_id, "renewed", before, note)
        return item

    @staticmethod
    async def file(session: AsyncSession, business_id: uuid.UUID, item_id: uuid.UUID, actor_id: uuid.UUID,
                   completed_on: date, note: str | None,
                   allowed_locations: list[uuid.UUID] | None) -> ComplianceItem:
        item = await ComplianceService.get(session, business_id, item_id, allowed_locations, lock=True)
        if item.item_type != "filing" or item.status != "active":
            raise ConflictError("Only an active filing can be marked filed")
        before = item.due_on
        item.last_done_on = completed_on
        if item.recurrence == "none":
            item.status = "archived"
        else:
            item.due_on = _advance(item.due_on, item.recurrence)
        item.updated_by, item.updated_at, item.version = actor_id, datetime.now(timezone.utc), item.version + 1
        await session.flush()
        await ComplianceService._change(session, item, actor_id, "filed", before, note)
        return item

    @staticmethod
    async def set_archived(session: AsyncSession, business_id: uuid.UUID, item_id: uuid.UUID,
                           actor_id: uuid.UUID, archived: bool,
                           allowed_locations: list[uuid.UUID] | None) -> ComplianceItem:
        item = await ComplianceService.get(session, business_id, item_id, allowed_locations, lock=True)
        want = "archived" if archived else "active"
        if item.status == want:
            return item
        item.status, item.updated_by = want, actor_id
        item.updated_at, item.version = datetime.now(timezone.utc), item.version + 1
        await session.flush()
        await ComplianceService._change(session, item, actor_id, "archived" if archived else "restored", item.due_on)
        return item

    @staticmethod
    async def public_licences(session: AsyncSession, business_id: uuid.UUID) -> list[dict[str, str]]:
        rows = (await session.execute(select(ComplianceItem).where(
            ComplianceItem.business_id == business_id, ComplianceItem.item_type == "licence",
            ComplianceItem.status == "active", ComplianceItem.show_on_site.is_(True),
        ).order_by(ComplianceItem.title))).scalars()
        return [{"title": row.title, "licence_number": str(row.licence_number),
                 "authority": row.authority or ""} for row in rows]
