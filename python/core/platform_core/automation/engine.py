"""The automation engine: schedule, cancel and run ladder steps.

Rules it keeps (Capability Universe §2 rule 11, §10.4; Guide §6):

* **Idempotent.** A step's key is ladder + entity + period + step. Scheduling
  twice, or a replayed webhook, never creates a second step.
* **Visible.** Every step row is the owner's activity log: when it was due,
  what happened, in words.
* **Switchable off.** An owner can switch a ladder (or one step) off; pending
  steps are then cancelled with the reason, never silently dropped.
* **Quiet hours.** Customer-facing steps due between 9 pm and 8 am
  (Asia/Kolkata by default) wait until 8 am.
* **No secret money movement.** Handlers may send messages, change statuses
  and create payment *links*; any irreversible money action is a T3 approval
  elsewhere, never a ladder step.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.automation.ladders import LADDERS, Ladder
from platform_core.exceptions import ValidationError

DEFAULT_TZ = "Asia/Kolkata"
QUIET_START = time(21, 0)
QUIET_END = time(8, 0)
MAX_ATTEMPTS = 3


@dataclass
class StepOutcome:
    status: str  # done | skipped | failed
    outcome: str  # owner words
    result: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DueStep:
    id: uuid.UUID
    business_id: uuid.UUID
    ladder_key: str
    step_key: str
    entity_type: str
    entity_id: uuid.UUID
    period_key: str
    due_at: datetime
    attempts: int
    context: dict[str, Any]


Handler = Callable[[AsyncSession, DueStep], Awaitable[StepOutcome]]
_HANDLERS: dict[tuple[str, str], Handler] = {}


def step_handler(ladder_key: str, *step_keys: str) -> Callable[[Handler], Handler]:
    """Register the code that performs a ladder step (one handler may serve several)."""
    if ladder_key not in LADDERS:
        raise ValueError(f"unknown ladder {ladder_key}")

    def wrap(fn: Handler) -> Handler:
        keys = step_keys or tuple(s.key for s in LADDERS[ladder_key].steps)
        for k in keys:
            _HANDLERS[(ladder_key, k)] = fn
        return fn

    return wrap


def is_wired(ladder_key: str) -> bool:
    """True once every step of the ladder has code behind it. A ladder is only
    shown to owners when it is wired — never a switch that does nothing."""
    from platform_core.events.registry import load_subscribers

    load_subscribers()
    lad = LADDERS.get(ladder_key)
    return lad is not None and all((ladder_key, s.key) in _HANDLERS for s in lad.steps)


def in_quiet_hours(moment: datetime, tz: str = DEFAULT_TZ) -> datetime | None:
    """The moment quiet hours end, if `moment` falls inside them; else None."""
    local = moment.astimezone(ZoneInfo(tz))
    t = local.timetz().replace(tzinfo=None)
    if t >= QUIET_START:
        end = datetime.combine(local.date() + timedelta(days=1), QUIET_END, ZoneInfo(tz))
    elif t < QUIET_END:
        end = datetime.combine(local.date(), QUIET_END, ZoneInfo(tz))
    else:
        return None
    return end.astimezone(timezone.utc)


class AutomationEngine:
    # ------------------------------------------------------------- rules
    @staticmethod
    async def rule(session: AsyncSession, business_id: uuid.UUID, ladder_key: str) -> dict[str, Any]:
        row = (await session.execute(
            text("SELECT enabled, config FROM automation_rules WHERE business_id = :b AND ladder_key = :k"),
            {"b": str(business_id), "k": ladder_key},
        )).first()
        return {"enabled": True, "config": {}} if row is None else {"enabled": bool(row[0]), "config": dict(row[1] or {})}

    @staticmethod
    async def set_rule(
        session: AsyncSession,
        business_id: uuid.UUID,
        ladder_key: str,
        *,
        enabled: bool | None,
        config: dict[str, Any] | None,
        actor_id: uuid.UUID,
    ) -> dict[str, Any]:
        ladder = LADDERS.get(ladder_key)
        if ladder is None:
            raise ValidationError("Unknown automation", details={"field": "ladder_key"})
        current = await AutomationEngine.rule(session, business_id, ladder_key)
        # A change names only what it changes: switching a step keeps the other options.
        new_config = current["config"] if config is None else AutomationEngine._validate_config(
            ladder, {**current["config"], **config})
        new_enabled = current["enabled"] if enabled is None else bool(enabled)
        await session.execute(
            text("""
                INSERT INTO automation_rules (business_id, ladder_key, enabled, config, updated_by, updated_at)
                VALUES (:b, :k, :e, CAST(:c AS jsonb), :u, now())
                ON CONFLICT (business_id, ladder_key)
                DO UPDATE SET enabled = EXCLUDED.enabled, config = EXCLUDED.config,
                              updated_by = EXCLUDED.updated_by, updated_at = now()
            """),
            {"b": str(business_id), "k": ladder_key, "e": new_enabled, "c": _json(new_config), "u": str(actor_id)},
        )
        if not new_enabled:
            await AutomationEngine.cancel(session, business_id, ladder_key=ladder_key,
                                          reason="Switched off by the owner")
        else:
            off = set(new_config.get("disabled_steps", []))
            if off:
                await session.execute(
                    text("""
                        UPDATE automation_steps SET status = 'cancelled', outcome = 'Step switched off by the owner',
                               executed_at = now()
                        WHERE business_id = :b AND ladder_key = :k AND status = 'pending'
                          AND step_key = ANY(CAST(:s AS text[]))
                    """),
                    {"b": str(business_id), "k": ladder_key, "s": sorted(off)},
                )
        return {"enabled": new_enabled, "config": new_config}

    @staticmethod
    def _validate_config(ladder: Ladder, config: dict[str, Any]) -> dict[str, Any]:
        keys = {s.key for s in ladder.steps}
        out: dict[str, Any] = {}
        disabled = config.get("disabled_steps") or []
        if not isinstance(disabled, list) or not set(disabled) <= keys:
            raise ValidationError("Unknown step", details={"field": "disabled_steps"})
        out["disabled_steps"] = sorted(set(disabled))
        offsets = config.get("offset_hours") or {}
        if not isinstance(offsets, dict) or not set(offsets) <= keys:
            raise ValidationError("Unknown step", details={"field": "offset_hours"})
        clean: dict[str, int] = {}
        for k, v in offsets.items():
            if not isinstance(v, int) or not -24 * 90 <= v <= 24 * 90:
                raise ValidationError("Offsets must be whole hours within 90 days", details={"field": k})
            clean[k] = v
        out["offset_hours"] = clean
        if "quiet_hours" in config:
            out["quiet_hours"] = bool(config["quiet_hours"])
        # Low stock may also draft a requisition - only when the owner turns it
        # on, and never more than a draft (no purchase order goes to anyone).
        if "draft_requisition" in config:
            if ladder.key != "stock.low":
                raise ValidationError("Only low-stock alerts can draft a requisition",
                                      details={"field": "draft_requisition"})
            out["draft_requisition"] = bool(config["draft_requisition"])
        return out

    # ------------------------------------------------------------- schedule / cancel
    @staticmethod
    async def schedule(
        session: AsyncSession,
        business_id: uuid.UUID,
        *,
        ladder_key: str,
        entity_id: uuid.UUID,
        anchor: datetime,
        period_key: str = "",
        context: dict[str, Any] | None = None,
        due_overrides: dict[str, datetime] | None = None,
        now: datetime | None = None,
    ) -> int:
        """Create the ladder's steps for one entity occurrence. Idempotent.

        Steps whose time has already passed are not created (a member who joins
        two days before the end date gets no T−7 reminder). Returns the number
        of steps newly created.
        """
        ladder = LADDERS[ladder_key]
        rule = await AutomationEngine.rule(session, business_id, ladder_key)
        if not rule["enabled"]:
            return 0
        off = set(rule["config"].get("disabled_steps", []))
        offsets = rule["config"].get("offset_hours", {})
        moment = now or datetime.now(timezone.utc)
        created = 0
        for step in ladder.steps:
            if step.key in off:
                continue
            due = (due_overrides or {}).get(step.key)
            if due is None:
                delta = timedelta(hours=offsets[step.key]) if step.key in offsets else step.offset
                due = anchor + delta
            if due < moment - timedelta(minutes=5):
                continue
            key = f"{ladder_key}:{entity_id}:{period_key}:{step.key}"
            res = await session.execute(
                text("""
                    INSERT INTO automation_steps (business_id, ladder_key, step_key, entity_type, entity_id,
                                                  period_key, idempotency_key, due_at, context)
                    VALUES (:b, :l, :s, :t, :e, :p, :k, :d, CAST(:c AS jsonb))
                    ON CONFLICT (business_id, idempotency_key) DO NOTHING
                    RETURNING id
                """),
                {"b": str(business_id), "l": ladder_key, "s": step.key, "t": ladder.entity_type,
                 "e": str(entity_id), "p": period_key, "k": key, "d": due, "c": _json(context or {})},
            )
            created += len(res.all())
        return created

    @staticmethod
    async def cancel(
        session: AsyncSession,
        business_id: uuid.UUID,
        *,
        ladder_key: str,
        entity_id: uuid.UUID | None = None,
        period_key: str | None = None,
        reason: str,
    ) -> int:
        """Cancel pending steps (all of a ladder, one entity's, or one occurrence's)."""
        clauses = ["business_id = :b", "ladder_key = :l", "status = 'pending'"]
        params: dict[str, Any] = {"b": str(business_id), "l": ladder_key, "r": reason}
        if entity_id is not None:
            clauses.append("entity_id = :e")
            params["e"] = str(entity_id)
        if period_key is not None:
            clauses.append("period_key = :p")
            params["p"] = period_key
        res = await session.execute(
            text(f"""
                UPDATE automation_steps SET status = 'cancelled', outcome = :r, executed_at = now()
                WHERE {' AND '.join(clauses)} RETURNING id
            """),
            params,
        )
        return len(res.all())

    # ------------------------------------------------------------- run (worker lane)
    @staticmethod
    async def run_due(
        session: AsyncSession,
        worker_id: str,
        *,
        limit: int = 25,
        now: datetime | None = None,
        business_id: uuid.UUID | None = None,
    ) -> int:
        """Claim and perform due steps. The worker calls this every tick.

        `business_id` isolates a test's own steps (like `job_type` in the job lane).
        """
        from platform_core.events.registry import load_subscribers

        load_subscribers()  # step handlers register alongside the event subscribers
        moment = now or datetime.now(timezone.utc)
        scope = "AND business_id = :only" if business_id else ""
        params: dict[str, Any] = {"now": moment, "limit": limit, "w": worker_id}
        if business_id:
            params["only"] = str(business_id)
        rows = (await session.execute(
            text(f"""
                UPDATE automation_steps SET status = 'processing', leased_by = :w,
                       leased_until = :now + interval '5 minutes', attempts = attempts + 1
                WHERE id IN (
                    SELECT id FROM automation_steps
                    WHERE (status = 'pending' OR (status = 'processing' AND leased_until < :now))
                      AND due_at <= :now {scope}
                    ORDER BY due_at
                    FOR UPDATE SKIP LOCKED
                    LIMIT :limit
                )
                RETURNING id, business_id, ladder_key, step_key, entity_type, entity_id, period_key,
                          due_at, attempts, context
            """),
            params,
        )).all()
        await session.commit()
        done = 0
        for r in rows:
            step = DueStep(r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8], dict(r[9] or {}))
            outcome = await AutomationEngine._perform(session, step, moment)
            if outcome is None:
                continue
            await session.execute(
                text("""
                    UPDATE automation_steps
                    SET status = :s, outcome = :o, result = CAST(:r AS jsonb), executed_at = :now,
                        leased_by = NULL, leased_until = NULL,
                        due_at = CASE WHEN :s = 'pending' THEN due_at + interval '10 minutes' ELSE due_at END
                    WHERE id = :id
                """),
                {"s": outcome.status, "o": outcome.outcome, "r": _json(outcome.result), "now": moment,
                 "id": str(step.id)},
            )
            await session.commit()
            done += 1
        return done

    @staticmethod
    async def _perform(session: AsyncSession, step: DueStep, moment: datetime) -> StepOutcome | None:
        ladder = LADDERS.get(step.ladder_key)
        rule = await AutomationEngine.rule(session, step.business_id, step.ladder_key)
        if ladder is None:
            return StepOutcome("failed", "This automation no longer exists")
        if not rule["enabled"]:
            return StepOutcome("cancelled", "Switched off by the owner")
        quiet = rule["config"].get("quiet_hours", ladder.quiet_hours)
        if quiet:
            zone = (await session.execute(text(
                "SELECT timezone FROM business_locations WHERE business_id = :b ORDER BY is_primary DESC LIMIT 1"),
                {"b": str(step.business_id)})).scalar()
            try:
                until = in_quiet_hours(moment, str(zone or DEFAULT_TZ))
            except Exception:  # noqa: BLE001 — a bad stored zone falls back to India
                until = in_quiet_hours(moment)
            if until is not None:
                await session.execute(
                    text("""UPDATE automation_steps SET status = 'pending', due_at = :d, leased_by = NULL,
                            leased_until = NULL, attempts = attempts - 1,
                            outcome = 'Waiting for 8 am (quiet hours)' WHERE id = :id"""),
                    {"d": until, "id": str(step.id)},
                )
                await session.commit()
                return None
        handler = _HANDLERS.get((step.ladder_key, step.step_key))
        if handler is None:
            return StepOutcome("skipped", "Nothing to do yet: this step is not available on LOCAH")
        try:
            async with session.begin_nested():
                result = await handler(session, step)
            return result
        except Exception as exc:  # a handler bug must not stall the lane
            await session.rollback()
            if step.attempts >= MAX_ATTEMPTS:
                return StepOutcome("failed", f"Could not complete after {step.attempts} tries",
                                   {"error": str(exc)[:300]})
            return StepOutcome("pending", "Will retry shortly", {"error": str(exc)[:300]})

    # ------------------------------------------------------------- read (owner)
    @staticmethod
    async def runs(session: AsyncSession, business_id: uuid.UUID) -> dict[str, dict[str, Any]]:
        """Per automation: when a step last ran, when the next is due, and what
        the last 30 days' steps came to."""
        rows = (await session.execute(text("""
            SELECT ladder_key,
                   max(executed_at) FILTER (WHERE status IN ('done', 'skipped', 'failed')),
                   min(due_at) FILTER (WHERE status = 'pending'),
                   count(*) FILTER (WHERE status = 'done' AND executed_at > now() - interval '30 days'),
                   count(*) FILTER (WHERE status = 'skipped' AND executed_at > now() - interval '30 days'),
                   count(*) FILTER (WHERE status = 'failed' AND executed_at > now() - interval '30 days')
            FROM automation_steps WHERE business_id = :b GROUP BY ladder_key
        """), {"b": str(business_id)})).all()
        return {r[0]: {"last_run_at": r[1].isoformat() if r[1] else None,
                       "next_run_at": r[2].isoformat() if r[2] else None,
                       "counts": {"done": r[3], "skipped": r[4], "failed": r[5]}} for r in rows}

    @staticmethod
    async def activity(
        session: AsyncSession, business_id: uuid.UUID, *, ladder_key: str | None = None,
        entity_id: uuid.UUID | None = None, limit: int = 50,
    ) -> list[dict[str, Any]]:
        clauses = ["business_id = :b"]
        params: dict[str, Any] = {"b": str(business_id), "limit": limit}
        if ladder_key:
            clauses.append("ladder_key = :l")
            params["l"] = ladder_key
        if entity_id:
            clauses.append("entity_id = :e")
            params["e"] = str(entity_id)
        rows = (await session.execute(
            text(f"""
                SELECT id, ladder_key, step_key, entity_type, entity_id, period_key, due_at, status, outcome,
                       executed_at, created_at
                FROM automation_steps WHERE {' AND '.join(clauses)}
                ORDER BY COALESCE(executed_at, due_at) DESC LIMIT :limit
            """),
            params,
        )).all()
        out = []
        for r in rows:
            ladder = LADDERS.get(r[1])
            step = next((s for s in ladder.steps if s.key == r[2]), None) if ladder else None
            out.append({
                "id": str(r[0]), "ladder_key": r[1], "ladder_label": ladder.label if ladder else r[1],
                "step_key": r[2], "step_when": step.when if step else r[2], "step_does": step.does if step else "",
                "entity_type": r[3], "entity_id": str(r[4]), "period_key": r[5],
                "due_at": r[6].isoformat(), "status": r[7], "outcome": r[8],
                "executed_at": r[9].isoformat() if r[9] else None,
            })
        return out


def _json(value: Any) -> str:
    import json

    return json.dumps(value, default=str)
