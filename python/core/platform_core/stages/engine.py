"""The stage engine (P2-01; Capability Universe §24 #10 "configurable stage sets
with guarded transitions shared by orders, jobs, leads, projects").

Each module keeps its statuses and the rules between them — the only place a
cancelled order releases its stock, a won enquiry becomes a customer, a
completed project closes. A business adds its own *steps inside a status*
(an order's "Picking" and "Packed" inside Preparing; an enquiry's "Site visit
booked" inside Contacted), renames any stage, and marks a step as needing a
note. The engine:

  * lists the stages of an entity in flow order (core stage first, then its
    steps), with the moves open from each,
  * moves a record: a step within the same status is recorded here; a move to
    another status goes through the module's own service (so its side effects
    and its own history run) and then lands on the chosen step,
  * guards every move: only to a stage of the same status or of a status the
    module allows next, a note where the stage asks for one (and where the
    module does — a cancelled order, a lost enquiry), the right permission,
  * keeps a history row per move, an audit record and a `stage.changed` event.

A record's `stage` is only trusted while it belongs to the record's current
status: a status changed by any other path (the Accept button, a customer
cancelling on WhatsApp) simply shows that status's own stage.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.exceptions import ResourceNotFound, ValidationError

ENTITIES = ("orders", "leads", "projects")

# Each module's statuses in flow order with the words a business reads, and the
# statuses a business may add steps inside (open work, not endings).
_CORE: dict[str, list[tuple[str, str]]] = {
    "orders": [("pending", "New"), ("accepted", "Accepted"), ("preparing", "Preparing"), ("ready", "Ready"),
               ("completed", "Completed"), ("cancelled", "Cancelled"), ("rejected", "Declined")],
    "leads": [("new", "New"), ("contacted", "Contacted"), ("qualified", "Qualified"), ("won", "Won"),
              ("lost", "Lost")],
    "projects": [("draft", "Draft"), ("active", "In progress"), ("on_hold", "On hold"), ("completed", "Completed"),
                 ("cancelled", "Cancelled")],
}
OPEN: dict[str, frozenset[str]] = {
    "orders": frozenset({"pending", "accepted", "preparing", "ready"}),
    "leads": frozenset({"new", "contacted", "qualified"}),
    "projects": frozenset({"draft", "active", "on_hold"}),
}
MODULE = {"orders": "orders", "leads": "leads", "projects": "projects"}
MAX_STEPS = 20


def _transitions(entity: str) -> dict[str, frozenset[str]]:
    from platform_core.services import project
    from platform_core.validation import lead, order

    found: dict[str, frozenset[str]] = {"orders": order.ALLOWED_TRANSITIONS, "leads": lead.ALLOWED_TRANSITIONS,
                                        "projects": project.ALLOWED_TRANSITIONS}[entity]
    return found


def permission_for(entity: str, to_status: str) -> str:
    """What a person needs to make this move (the same gates as the module's own buttons)."""
    import platform_core.permissions as p

    needed: str
    if entity == "orders":
        needed = p.ORDERS_CANCEL if to_status in ("cancelled", "rejected") else p.ORDERS_UPDATE_STATUS
    elif entity == "leads":
        needed = p.LEADS_UPDATE_STATUS
    else:
        needed = p.PROJECTS_MANAGE_LIFECYCLE
    return needed


@dataclass(frozen=True)
class Stage:
    key: str
    label: str
    status: str
    custom: bool
    needs_note: bool

    def view(self) -> dict[str, Any]:
        return {"key": self.key, "label": self.label, "status": self.status, "custom": self.custom,
                "needs_note": self.needs_note}


class StageSetView:
    def __init__(self, entity: str, stages: list[Stage], version: int) -> None:
        self.entity, self.stages, self.version = entity, stages, version
        self.by_key = {s.key: s for s in stages}

    def effective(self, stage: str | None, status: str) -> Stage:
        """The stage a record is at: its step while that step belongs to its status, else the status itself."""
        found = self.by_key.get(stage or "")
        if found is not None and found.status == status:
            return found
        return self.by_key.get(status) or Stage(status, status.replace("_", " ").capitalize(), status, False, False)

    def moves_from(self, current: Stage) -> list[Stage]:
        allowed = _transitions(self.entity).get(current.status, frozenset())
        return [s for s in self.stages if s.key != current.key and (s.status == current.status or s.status in allowed)]

    def view(self) -> dict[str, Any]:
        return {"entity": self.entity, "version": self.version, "stages": [s.view() for s in self.stages],
                "moves": {s.key: [m.key for m in self.moves_from(s)] for s in self.stages},
                "open": [k for k, _ in _CORE[self.entity] if k in OPEN[self.entity]]}


def _default(entity: str) -> list[Stage]:
    return [Stage(key, label, key, False, False) for key, label in _CORE[entity]]


def _slug(label: str) -> str:
    return "s_" + (re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")[:30] or "step")


def clean(entity: str, raw: Any) -> list[Stage]:
    """Validate a business's stage set; returns it in flow order (each status, then its steps)."""
    if entity not in ENTITIES:
        raise ValidationError("Unknown stage set", details={"field": "entity"})
    if not isinstance(raw, list):
        raise ValidationError("Send the stages as a list", details={"field": "stages"})
    core = dict(_CORE[entity])
    labels: dict[str, str] = {}
    notes: dict[str, bool] = {}
    steps: dict[str, list[Stage]] = {k: [] for k in core}
    seen: set[str] = set()
    for i, row in enumerate(raw):
        if not isinstance(row, dict):
            raise ValidationError("Each stage needs a name and a status", details={"field": f"stages[{i}]"})
        label = " ".join(str(row.get("label") or "").split())
        if not 1 <= len(label) <= 40:
            raise ValidationError("Give each stage a name of up to 40 letters", details={"field": f"stages[{i}].label"})
        status = str(row.get("status") or "")
        if status not in core:
            raise ValidationError("A stage belongs to one of the module's statuses",
                                  details={"field": f"stages[{i}].status"})
        key = str(row.get("key") or "")
        needs_note = bool(row.get("needs_note"))
        if key == status:
            labels[status], notes[status] = label, needs_note
            seen.add(key)
            continue
        if status not in OPEN[entity]:
            raise ValidationError(f"Steps can be added only inside open stages, not inside “{core[status]}”",
                                  details={"field": f"stages[{i}].status"})
        key = key if re.fullmatch(r"s_[a-z0-9_]{1,30}", key) else _slug(label)
        base, n = key, 2
        while key in seen or key in core:
            key, n = f"{base}_{n}", n + 1
        seen.add(key)
        steps[status].append(Stage(key, label, status, True, needs_note))
    if sum(len(v) for v in steps.values()) > MAX_STEPS:
        raise ValidationError(f"Up to {MAX_STEPS} steps of your own", details={"field": "stages"})
    missing = [core[s] for s in core if s not in labels]
    if missing:
        raise ValidationError("The module's own stages can be renamed but not removed: " + ", ".join(missing),
                              details={"field": "stages"})
    out: list[Stage] = []
    for status in core:
        out.append(Stage(status, labels[status], status, False, notes.get(status, False)))
        out.extend(steps[status])
    return out


class StageEngine:
    @staticmethod
    async def get(session: AsyncSession, business_id: uuid.UUID, entity: str) -> StageSetView:
        from platform_core.models import StageSet

        if entity not in ENTITIES:
            raise ResourceNotFound("Stage set")
        row = (await session.execute(select(StageSet).where(
            StageSet.business_id == business_id, StageSet.entity == entity))).scalars().first()
        if row is None:
            return StageSetView(entity, _default(entity), 0)
        return StageSetView(entity, [Stage(**s) for s in row.stages], row.version)

    @staticmethod
    async def save(session: AsyncSession, business_id: uuid.UUID, entity: str, raw: Any, *, actor_id: uuid.UUID,
                   correlation_id: str | None = None) -> StageSetView:
        from datetime import datetime, timezone

        from platform_core.models import StageSet
        from platform_core.services.audit import AuditService
        from platform_core.services.outbox import OutboxService

        stages = clean(entity, raw)
        await StageEngine._mutable(session, business_id, "change stages")
        before = await StageEngine.get(session, business_id, entity)
        row = (await session.execute(select(StageSet).where(
            StageSet.business_id == business_id, StageSet.entity == entity).with_for_update())).scalars().first()
        data = [s.view() for s in stages]
        if row is None:
            row = StageSet(business_id=business_id, entity=entity, stages=data, version=1, updated_by=actor_id)
            session.add(row)
        else:
            row.stages, row.version = data, row.version + 1
            row.updated_by, row.updated_at = actor_id, datetime.now(timezone.utc)
        await session.flush()
        await AuditService.record(session, event_type="stage_set.changed", actor_identity_id=actor_id,
                                  actor_context="business", business_id=business_id, resource_type="stage_set",
                                  resource_id=row.id, action="update",
                                  before_state={"stages": [s.view() for s in before.stages]},
                                  after_state={"stages": data})
        await OutboxService.publish(session, event_type="stage_set.changed",
                                    payload={"business_id": str(business_id), "entity": entity,
                                             "version": row.version},
                                    business_id=business_id, correlation_id=correlation_id)
        return StageSetView(entity, stages, row.version)

    @staticmethod
    async def _mutable(session: AsyncSession, business_id: uuid.UUID, action: str) -> None:
        from platform_core.gates import assert_business_mutable
        from platform_core.services.business import BusinessService

        business = await BusinessService.get_by_id(session, business_id)
        if business is None:
            raise ResourceNotFound("Business")
        assert_business_mutable(business.state, action=action)

    @staticmethod
    async def _record(session: AsyncSession, business_id: uuid.UUID, entity: str, record_id: uuid.UUID) -> Any:
        """The record, through the ORM — so location and assignment scope apply."""
        from platform_core.models import Lead, Project, SalesOrder

        model: Any = {"orders": SalesOrder, "leads": Lead, "projects": Project}[entity]
        row = (await session.execute(select(model).where(
            model.business_id == business_id, model.id == record_id))).scalars().first()
        if row is None or getattr(row, "deleted_at", None) is not None:
            raise ResourceNotFound({"orders": "Order", "leads": "Enquiry", "projects": "Project"}[entity])
        return row

    @staticmethod
    async def where(session: AsyncSession, business_id: uuid.UUID, entity: str, record_id: uuid.UUID) -> dict[str, Any]:
        """The record's stage and the moves open from it."""
        sset = await StageEngine.get(session, business_id, entity)
        record = await StageEngine._record(session, business_id, entity, record_id)
        current = sset.effective(record.stage, record.status)
        return {"stage": current.view(), "moves": [m.view() for m in sset.moves_from(current)],
                "path": [s.view() for s in sset.stages if s.status == current.status],
                "has_steps": any(s.custom for s in sset.stages), "version": int(record.version)}

    @staticmethod
    async def move(session: AsyncSession, *, business_id: uuid.UUID, entity: str, record_id: uuid.UUID, to: str,
                   note: str | None, actor_id: uuid.UUID, permissions: frozenset[str], correlation_id: str,
                   version: int | None = None) -> dict[str, Any]:
        from platform_core.exceptions import PermissionDenied
        from platform_core.models import StageEvent
        from platform_core.services.audit import AuditService
        from platform_core.services.outbox import OutboxService

        await StageEngine._mutable(session, business_id, "move a stage")
        sset = await StageEngine.get(session, business_id, entity)
        record = await StageEngine._record(session, business_id, entity, record_id)
        current = sset.effective(record.stage, record.status)
        target = sset.by_key.get(to)
        if target is None:
            raise ValidationError("That stage is not in this business's stages", details={"field": "to"})
        if target.key == current.key:
            raise ValidationError(f"It is already at “{current.label}”", details={"field": "to"})
        if target not in sset.moves_from(current):
            nexts = ", ".join(f"“{m.label}”" for m in sset.moves_from(current)) or "nowhere"
            raise ValidationError(f"From “{current.label}” it can move to {nexts}", details={"field": "to"})
        needed = permission_for(entity, target.status)
        if needed not in permissions:
            raise PermissionDenied(needed)
        note = " ".join((note or "").split())[:500] or None
        if target.needs_note and not note:
            raise ValidationError(f"Add a note to move it to “{target.label}”", details={"field": "note"})
        if version is not None and int(record.version) != int(version):
            from platform_core.exceptions import ConflictError

            raise ConflictError("Someone changed this a moment ago — refresh and try again")
        from_status = record.status
        if target.status != record.status:
            await StageEngine._change_status(session, entity, business_id, record, target.status, note, actor_id,
                                             correlation_id)
        record.stage = target.key
        await session.flush()
        session.add(StageEvent(business_id=business_id, entity=entity, record_id=record.id, from_stage=current.key,
                               to_stage=target.key, from_status=from_status, to_status=target.status, note=note,
                               actor_identity_id=actor_id))
        await AuditService.record(session, event_type="stage.changed", actor_identity_id=actor_id,
                                  actor_context="business", business_id=business_id, resource_type=entity[:-1],
                                  resource_id=record.id, action="move_stage",
                                  before_state={"stage": current.key, "status": from_status},
                                  after_state={"stage": target.key, "status": target.status, "note": note})
        await OutboxService.publish(session, event_type="stage.changed",
                                    payload={"business_id": str(business_id), "entity": entity,
                                             "record_id": str(record.id), "from": current.key, "to": target.key,
                                             "status": target.status},
                                    business_id=business_id, correlation_id=correlation_id)
        await session.flush()
        return {"stage": target.view(), "status": target.status,
                "moves": [m.view() for m in sset.moves_from(target)]}

    @staticmethod
    async def _change_status(session: AsyncSession, entity: str, business_id: uuid.UUID, record: Any, status: str,
                             note: str | None, actor_id: uuid.UUID, correlation_id: str) -> None:
        """A move to another status runs the module's own service — its rules, side effects and history."""
        if entity == "orders":
            from platform_core.services.order_lifecycle import OrderLifecycleService

            await OrderLifecycleService.transition_status(
                session, business_id=business_id, order_id=record.id, actor_id=actor_id,
                correlation_id=correlation_id, payload={"status": status, "reason": note})
        elif entity == "leads":
            from platform_core.services.lead import LeadService

            await LeadService.move_stage(session, business_id=business_id, lead_id=record.id, actor_id=actor_id,
                                         correlation_id=correlation_id, payload={"status": status, "reason": note})
        else:
            from platform_core.services.project import ProjectService

            await ProjectService.change_status(session, business_id=business_id, project_id=record.id, status=status,
                                               actor_id=actor_id, correlation_id=correlation_id, reason=note)

    @staticmethod
    async def history(session: AsyncSession, business_id: uuid.UUID, entity: str,
                      record_id: uuid.UUID) -> list[dict[str, Any]]:
        from platform_core.models import StageEvent

        await StageEngine._record(session, business_id, entity, record_id)  # scope check
        sset = await StageEngine.get(session, business_id, entity)
        rows = (await session.execute(select(StageEvent).where(
            StageEvent.business_id == business_id, StageEvent.entity == entity, StageEvent.record_id == record_id,
        ).order_by(StageEvent.created_at))).scalars()

        def label(key: str | None) -> str | None:
            return sset.by_key[key].label if key and key in sset.by_key else key

        return [{"from": label(r.from_stage), "to": label(r.to_stage), "note": r.note,
                 "at": r.created_at.isoformat() if r.created_at else None} for r in rows]
