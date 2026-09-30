"""The one AI employee runtime (Capability Universe §8).

Every AI employee — receptionist, collections, procurement today — goes
through here:

* **Identity.** An employee is a row (business, kind, autonomy ceiling, tool
  allowlist, limits, enabled). Its records are created through the same
  services people use, attributed to the business owner as today's guest
  and automation paths are, and each is linked from an ``ai_actions`` row
  (actor = the AI employee).
* **Tiers, enforced here, not in a prompt.** T0 read · T1 draft · T2 act within
  owner limits · T3 owner approval always. A tool above the employee's
  autonomy becomes an approval request; a T3 tool always does.
* **Allowlist.** A tool runs only if it belongs to the employee's kind AND the
  owner left it switched on. Nothing an AI employee can call writes
  ``ai_employees``/``ai_employee_controls``: it cannot grant itself a tool,
  raise its tier or change its limits. Only a person with
  ``ai_employees.manage`` can (``update`` refuses anything else).
* **Kill switch.** Per employee (``enabled``) and per business (global pause);
  the module must be on. Paused → the flow falls back to buttons and people.
* **Audit.** Every decision — done, drafted, awaiting approval, refused,
  failed, escalated — is an ``ai_actions`` row with summaries (never secrets).
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.exceptions import ConflictError, PermissionDenied, ResourceNotFound, ValidationError
from platform_core.models import AIAction, AIEmployee, AIEmployeeControl

TIERS = ("T0", "T1", "T2", "T3")
MODULE = "ai-employees"


@dataclass(frozen=True)
class Tool:
    name: str
    tier: str
    label: str


TOOLS: dict[str, Tool] = {t.name: t for t in (
    # Receptionist / WhatsApp manager
    Tool("business_info", "T0", "Answer hours, address and contact from the business's records"),
    Tool("list_services", "T0", "List services and prices from the catalogue"),
    Tool("check_availability", "T0", "Look up free times (the booking engine's own answer)"),
    Tool("start_booking", "T2", "Start a booking on WhatsApp (the customer picks a free time)"),
    Tool("capture_lead", "T2", "Save the customer's question as an enquiry"),
    Tool("send_link", "T2", "Send the business's existing booking, menu or website link"),
    Tool("escalate", "T0", "Hand the chat to a person"),
    # Collections assistant
    Tool("find_outstanding", "T0", "Find bills past their due date"),
    Tool("send_payment_reminder", "T2", "Send the payment reminder with the bill's own payment link"),
    # Procurement assistant
    Tool("find_shortages", "T0", "Find items at or below their reorder point"),
    Tool("draft_requisition", "T1", "Draft a requisition on the Buying desk (never a purchase order)"),
    Tool("request_po_send", "T3", "Ask the owner to send an approved purchase order to the supplier"),
)}

KIND_TOOLS: dict[str, tuple[str, ...]] = {
    "receptionist": ("business_info", "list_services", "check_availability", "start_booking", "capture_lead",
                     "send_link", "escalate"),
    "collections": ("find_outstanding", "send_payment_reminder"),
    "procurement": ("find_shortages", "draft_requisition", "request_po_send"),
}

DEFAULTS: dict[str, dict[str, Any]] = {
    "receptionist": {"display_name": "Receptionist", "autonomy": "T2",
                     "limits": {"max_replies_per_chat_per_day": 20}},
    "collections": {"display_name": "Collections assistant", "autonomy": "T2",
                    "limits": {"min_days_overdue": 1, "min_days_between_reminders": 3, "max_reminders_per_run": 20}},
    "procurement": {"display_name": "Procurement assistant", "autonomy": "T1",
                    "limits": {"max_drafts_per_run": 10}},
}

# What an owner may set each limit to. A limit outside its range is refused.
LIMIT_BOUNDS: dict[str, dict[str, tuple[int, int]]] = {
    "receptionist": {"max_replies_per_chat_per_day": (1, 100)},
    "collections": {"min_days_overdue": (0, 90), "min_days_between_reminders": (1, 30),
                    "max_reminders_per_run": (1, 200)},
    "procurement": {"max_drafts_per_run": (1, 100)},
}

ROLE: dict[str, str] = {
    "receptionist": "Answers customers on WhatsApp from your records, starts bookings and takes enquiries",
    "collections": "Reminds customers about overdue bills with their own payment link; stops once paid",
    "procurement": "Finds items running low and drafts requisitions; asks you before any PO goes to a supplier",
}

# How an approved T3 action is carried out (the owner's approval is the actor).
Approver = Callable[[AsyncSession, AIAction, uuid.UUID], Awaitable[str]]
APPROVERS: dict[str, Approver] = {}


def _rank(tier: str) -> int:
    return TIERS.index(tier)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _clip(value: str, n: int = 400) -> str:
    value = " ".join(str(value or "").split())
    return value if len(value) <= n else value[: n - 1] + "…"


@dataclass
class Outcome:
    """What a tool reports back: in owner words, plus the record it touched."""

    summary: str
    status: str = "done"  # done | drafted | escalated | refused | failed
    related_type: str | None = None
    related_id: uuid.UUID | None = None
    value: Any = None


class AIRuntime:
    # ------------------------------------------------------------ the roster
    @staticmethod
    async def ensure(session: AsyncSession, business_id: uuid.UUID) -> list[AIEmployee]:
        """The business's AI employees, created switched off the first time."""
        rows = {e.kind: e for e in (await session.execute(
            select(AIEmployee).where(AIEmployee.business_id == business_id))).scalars()}
        for kind, spec in DEFAULTS.items():
            if kind not in rows:
                emp = AIEmployee(business_id=business_id, kind=kind, display_name=spec["display_name"],
                                 autonomy=spec["autonomy"], tools=list(KIND_TOOLS[kind]),
                                 limits=dict(spec["limits"]), enabled=False)
                session.add(emp)
                rows[kind] = emp
        await session.flush()
        return [rows[k] for k in DEFAULTS]

    @staticmethod
    async def module_on(session: AsyncSession, business_id: uuid.UUID) -> bool:
        row = (await session.execute(
            text("SELECT activation_state FROM business_module_states WHERE business_id = :b AND module_id = :m"),
            {"b": str(business_id), "m": MODULE})).first()
        return row is not None and row[0] in ("enabled", "ready", "active")

    @staticmethod
    async def paused(session: AsyncSession, business_id: uuid.UUID) -> bool:
        control = await session.get(AIEmployeeControl, business_id)
        return bool(control and control.paused)

    @staticmethod
    async def active(session: AsyncSession, business_id: uuid.UUID, kind: str) -> AIEmployee | None:
        """The employee if it may work right now: module on, not paused, switched on."""
        emp = (await session.execute(select(AIEmployee).where(
            AIEmployee.business_id == business_id, AIEmployee.kind == kind))).scalars().first()
        if emp is None or not emp.enabled:
            return None
        if await AIRuntime.paused(session, business_id) or not await AIRuntime.module_on(session, business_id):
            return None
        return emp

    # ------------------------------------------------------------ decisions
    @staticmethod
    def decide(emp: AIEmployee, tool_name: str) -> tuple[str, str]:
        """("run" | "approval" | "refused", why). The only place tiers are read."""
        tool = TOOLS.get(tool_name)
        if tool is None or tool_name not in KIND_TOOLS.get(emp.kind, ()):
            return "refused", f"{tool_name} is not one of this AI employee's tools"
        if tool_name not in (emp.tools or []):
            return "refused", f"The owner switched {tool.label.lower()} off"
        if not emp.enabled:
            return "refused", "This AI employee is switched off"
        if tool.tier == "T3":
            return "approval", "Always needs the owner's approval"
        if _rank(tool.tier) > _rank(emp.autonomy):
            return "approval", f"Above its autonomy ({emp.autonomy}) — needs the owner's approval"
        return "run", ""

    @staticmethod
    async def act(
        session: AsyncSession,
        emp: AIEmployee,
        tool_name: str,
        run: Callable[[], Awaitable[Outcome]],
        *,
        input_summary: str,
        source: str,
        conversation_id: uuid.UUID | None = None,
        pending_args: dict[str, Any] | None = None,
        related: tuple[str, uuid.UUID] | None = None,
        model: str | None = None,
        tokens: tuple[int | None, int | None] = (None, None),
    ) -> tuple[AIAction, Outcome | None]:
        """Decide, then run (or ask, or refuse), and record it — every time."""
        tool = TOOLS[tool_name] if tool_name in TOOLS else Tool(tool_name, "T3", tool_name)
        if await AIRuntime.paused(session, emp.business_id):
            decision, why = "refused", "All AI employees are paused"
        else:
            decision, why = AIRuntime.decide(emp, tool_name)
        action = AIAction(
            business_id=emp.business_id, ai_employee_id=emp.id, tool=tool_name, tier=tool.tier,
            input_summary=_clip(input_summary), source=_clip(source, 200), conversation_id=conversation_id,
            related_type=related[0] if related else None, related_id=related[1] if related else None,
            model=model, tokens_in=tokens[0], tokens_out=tokens[1], started_at=_now(),
        )
        outcome: Outcome | None = None
        if decision == "refused":
            action.status, action.reason, action.result_summary = "refused", why, why
        elif decision == "approval":
            action.status, action.approval_required, action.approval_status = "awaiting_approval", True, "pending"
            action.reason, action.pending_args = why, pending_args or {}
            action.result_summary = "Waiting for your approval"
        else:
            try:
                async with session.begin_nested():
                    outcome = await run()
            except (ValidationError, ConflictError, ResourceNotFound, PermissionDenied) as exc:
                outcome = Outcome(f"Could not: {exc}", status="failed")
            action.status = outcome.status
            action.result_summary = _clip(outcome.summary)
            if outcome.related_id is not None:
                action.related_type, action.related_id = outcome.related_type, outcome.related_id
        action.completed_at = _now() if action.status != "awaiting_approval" else None
        session.add(action)
        await session.flush()
        return action, outcome

    @staticmethod
    async def decide_approval(
        session: AsyncSession, business_id: uuid.UUID, action_id: uuid.UUID, *, approve: bool, actor_id: uuid.UUID,
    ) -> AIAction:
        """The owner approves or rejects a T3 request. Approving carries it out now, as the owner."""
        action = (await session.execute(select(AIAction).where(
            AIAction.id == action_id, AIAction.business_id == business_id).with_for_update())).scalars().first()
        if action is None:
            raise ResourceNotFound("AI action")
        if action.approval_status != "pending":
            raise ConflictError("This request was already decided")
        action.decided_by, action.decided_at = actor_id, _now()
        if not approve:
            action.approval_status, action.status = "rejected", "rejected"
            action.result_summary = "You said no"
        else:
            approver = APPROVERS.get(action.tool)
            if approver is None:
                raise ValidationError("Nothing to carry out for this request")
            async with session.begin_nested():
                done = await approver(session, action, actor_id)
            action.approval_status, action.status = "approved", "approved"
            action.result_summary = _clip(done)
        action.completed_at = _now()
        await session.flush()
        return action

    # ------------------------------------------------------------ the owner's controls
    @staticmethod
    async def update(
        session: AsyncSession, business_id: uuid.UUID, kind: str, patch: dict[str, Any], *, actor_id: uuid.UUID,
    ) -> AIEmployee:
        """Tools, tier, limits, on/off — a person's change only (the caller checks ai_employees.manage)."""
        if kind not in DEFAULTS:
            raise ResourceNotFound("AI employee")
        await AIRuntime.ensure(session, business_id)
        emp = (await session.execute(select(AIEmployee).where(
            AIEmployee.business_id == business_id, AIEmployee.kind == kind).with_for_update())).scalars().one()
        if "tools" in patch:
            tools = [str(t) for t in patch["tools"] or []]
            outside = sorted(set(tools) - set(KIND_TOOLS[kind]))
            if outside:
                raise ValidationError(f"Not a tool this AI employee can have: {', '.join(outside)}")
            emp.tools = [t for t in KIND_TOOLS[kind] if t in tools]
        if "autonomy" in patch:
            if patch["autonomy"] not in ("T0", "T1", "T2"):
                raise ValidationError("Autonomy is T0, T1 or T2 — approval-only actions always ask")
            emp.autonomy = str(patch["autonomy"])
        if "limits" in patch:
            limits = dict(emp.limits or {})
            for key, value in (patch["limits"] or {}).items():
                bounds = LIMIT_BOUNDS[kind].get(key)
                if bounds is None:
                    raise ValidationError(f"Unknown limit: {key}")
                if not isinstance(value, int) or not bounds[0] <= value <= bounds[1]:
                    raise ValidationError(f"{key} must be between {bounds[0]} and {bounds[1]}")
                limits[key] = value
            emp.limits = limits
        if "enabled" in patch:
            if patch["enabled"] and not await AIRuntime.module_on(session, business_id):
                raise ValidationError("Switch on AI staff in Modules first")
            emp.enabled = bool(patch["enabled"])
            if emp.enabled and kind in ("collections", "procurement"):
                from platform_core.ai_employees.sweep import ensure_scheduled

                await ensure_scheduled(session)
        emp.updated_by = actor_id
        await session.flush()
        return emp

    @staticmethod
    async def set_pause(session: AsyncSession, business_id: uuid.UUID, paused: bool, *, actor_id: uuid.UUID) -> bool:
        control = await session.get(AIEmployeeControl, business_id)
        if control is None:
            control = AIEmployeeControl(business_id=business_id)
            session.add(control)
        control.paused = paused
        control.paused_at, control.paused_by = (_now(), actor_id) if paused else (None, None)
        await session.flush()
        return paused

    # ------------------------------------------------------------ the Workspace page
    @staticmethod
    async def overview(session: AsyncSession, business_id: uuid.UUID) -> dict[str, Any]:
        employees = await AIRuntime.ensure(session, business_id)
        actions = (await session.execute(select(AIAction).where(AIAction.business_id == business_id)
                                         .order_by(AIAction.created_at.desc()).limit(50))).scalars().all()
        pending = (await session.execute(select(AIAction).where(
            AIAction.business_id == business_id, AIAction.approval_status == "pending")
            .order_by(AIAction.created_at.asc()))).scalars().all()
        names = {e.id: e.display_name for e in employees}
        return {
            "module_on": await AIRuntime.module_on(session, business_id),
            "paused": await AIRuntime.paused(session, business_id),
            "employees": [{
                "kind": e.kind, "name": e.display_name, "role": ROLE[e.kind], "enabled": e.enabled,
                "autonomy": e.autonomy, "limits": e.limits, "limit_bounds": LIMIT_BOUNDS[e.kind],
                "tools": [{"name": t, "tier": TOOLS[t].tier, "label": TOOLS[t].label, "on": t in (e.tools or [])}
                          for t in KIND_TOOLS[e.kind]],
            } for e in employees],
            "needs_approval": [_action(a, names) for a in pending],
            "recent": [_action(a, names) for a in actions],
        }


def _action(a: AIAction, names: dict[uuid.UUID, str]) -> dict[str, Any]:
    return {
        "id": str(a.id), "employee": names.get(a.ai_employee_id, ""), "tool": a.tool,
        "tool_label": TOOLS[a.tool].label if a.tool in TOOLS else a.tool, "tier": a.tier, "status": a.status,
        "approval_status": a.approval_status, "input": a.input_summary, "result": a.result_summary,
        "reason": a.reason, "source": a.source, "related_type": a.related_type,
        "related_id": str(a.related_id) if a.related_id else None, "model": a.model,
        "at": a.created_at.isoformat() if a.created_at else None,
    }
