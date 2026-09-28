"""Is a module actually ready to show customers? (Business OS Guide §4, Founder §50)

Enabled, configured, ready and permitted are four different things:

* **enabled** — the owner switched the module on (business_module_states).
* **configured / ready** — the setup steps in the module catalogue are true in
  the business's real data (a priced product exists, a plan is published...).
  Computed here, never stored, so it cannot go stale.
* **permitted** — a particular person may use it; that is the permission engine.

Surfaces (website, Marketplace, WhatsApp) expose a module's customer actions
only when it is enabled *and* ready. Nothing here guesses: a step whose check
does not exist yet is reported not done.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable, Iterable
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.catalog.modules import MODULES

OPERATIONAL_STATES = frozenset({"enabled", "ready", "active"})

Check = Callable[[AsyncSession, uuid.UUID], Awaitable[bool]]


async def _exists(session: AsyncSession, sql: str, business_id: uuid.UUID) -> bool:
    row = (await session.execute(text(f"SELECT EXISTS ({sql})"), {"b": str(business_id)})).scalar()
    return bool(row)


def _sql(sql: str) -> Check:
    async def run(session: AsyncSession, business_id: uuid.UUID) -> bool:
        return await _exists(session, sql, business_id)

    return run


async def _table_exists(session: AsyncSession, name: str) -> bool:
    return bool((await session.execute(text("SELECT to_regclass(:n) IS NOT NULL"), {"n": name})).scalar())


def _sql_if_table(table: str, sql: str) -> Check:
    """A check over a table a later packet creates; false until it exists."""

    async def run(session: AsyncSession, business_id: uuid.UUID) -> bool:
        if not await _table_exists(session, table):
            return False
        return await _exists(session, sql, business_id)

    return run


_LIVE_OFFERING = (
    "SELECT 1 FROM offerings_catalog_offerings WHERE business_id = CAST(:b AS uuid) "
    "AND deleted_at IS NULL AND status = 'active' AND visibility = 'public'"
)

CHECKS: dict[str, Check] = {
    "offering_live": _sql(_LIVE_OFFERING),
    "priced_product": _sql(
        _LIVE_OFFERING + " AND price_amount IS NOT NULL AND price_amount > 0 "
        "AND price_type IN ('fixed', 'starting_from')"
    ),
    # Cash / COD / pay-at-business is always available; online payment is an
    # activation on top (merchant connection) and not required for readiness.
    "payment_method": lambda s, b: _true(),
    "stock_recorded": _sql(
        "SELECT 1 FROM inventory_records WHERE business_id = CAST(:b AS uuid)"
    ),
    "fulfilment_mode": _sql(
        "SELECT 1 FROM fulfilment_settings WHERE business_id = CAST(:b AS uuid) "
        "AND (pickup_enabled OR delivery_enabled)"
    ),
    "bookable_offering": _sql(
        _LIVE_OFFERING + " AND offering_type IN ('service', 'accommodation', 'class_session', "
        "'rental', 'menu_item', 'room_type', 'rental_resource', 'class', 'course')"
    ),
    "plan_live": _sql(
        "SELECT 1 FROM memberships_plans WHERE business_id = CAST(:b AS uuid) "
        "AND deleted_at IS NULL AND status = 'active' AND visibility = 'public'"
    ),
    "provider_added": _sql(
        "SELECT 1 FROM workforce_members WHERE business_id = CAST(:b AS uuid) "
        "AND deleted_at IS NULL AND status = 'active'"
    ),
    # Billing is set up when the owner chose how they bill, told LOCAH their
    # registration (or that they are not registered) and has a register.
    "tax_profile": _sql_if_table(
        "invoicing_tax_profiles",
        "SELECT 1 FROM invoicing_tax_profiles p WHERE p.business_id = CAST(:b AS uuid) "
        "AND EXISTS (SELECT 1 FROM invoicing_registrations r WHERE r.business_id = p.business_id "
        "AND r.status = 'active') "
        "AND EXISTS (SELECT 1 FROM invoicing_registers g WHERE g.business_id = p.business_id "
        "AND g.status = 'active')",
    ),
    # A POS register is the invoicing register (one concept, §14.4).
    "register_created": _sql_if_table(
        "invoicing_registers",
        "SELECT 1 FROM invoicing_registers WHERE business_id = CAST(:b AS uuid) AND status = 'active'",
    ),
    "channel_connected": _sql_if_table(
        "messaging_channels",
        "SELECT 1 FROM messaging_channels WHERE business_id = CAST(:b AS uuid) "
        "AND status = 'connected'",
    ),
}


async def _true() -> bool:
    return True


async def module_states(session: AsyncSession, business_id: uuid.UUID) -> dict[str, str]:
    rows = await session.execute(
        text("SELECT module_id, activation_state FROM business_module_states "
             "WHERE business_id = CAST(:b AS uuid)"),
        {"b": str(business_id)},
    )
    return {r[0]: r[1] for r in rows}


async def readiness(
    session: AsyncSession, business_id: uuid.UUID, modules: Iterable[str] | None = None
) -> dict[str, dict[str, Any]]:
    """module -> {state, enabled, steps: [{key, label, done}], ready}."""
    states = await module_states(session, business_id)
    wanted = list(modules) if modules is not None else list(MODULES)
    cache: dict[str, bool] = {}
    out: dict[str, dict[str, Any]] = {}
    for key in wanted:
        info = MODULES.get(key)
        state = states.get(key, "not_enabled")
        enabled = state in OPERATIONAL_STATES
        steps = []
        for step in info.setup if info else ():
            if step.key not in cache:
                check = CHECKS.get(step.key)
                cache[step.key] = bool(await check(session, business_id)) if check else False
            steps.append({"key": step.key, "label": step.label, "done": cache[step.key]})
        built = bool(info and info.built and not info.future)
        out[key] = {
            "state": state,
            "enabled": enabled,
            "built": built,
            "steps": steps,
            "configured": all(s["done"] for s in steps),
            "ready": built and enabled and all(s["done"] for s in steps),
        }
    return out


async def ready_modules(session: AsyncSession, business_id: uuid.UUID) -> frozenset[str]:
    """Modules whose customer actions any surface may show right now."""
    r = await readiness(session, business_id)
    return frozenset(k for k, v in r.items() if v["ready"])
