"""Offline sync (Capability Universe §24 #12, §2 rule 9, §14.2, §13.3).

A device (POS register, crew phone) keeps working without a connection: it
gives each change its own UUID and queues it. When the network returns it
replays the queue here. Replaying is idempotent on (business, client id): a
mutation already applied returns its original result, never a second effect.

Each module registers the mutation kinds it accepts. A handler validates
server-side exactly as the online endpoint would — prices, permissions and
stock are rechecked; the device is never trusted to have decided them.
Conflict rule: the server's current state wins; a mutation that can no longer
apply is rejected with a reason the device shows its user.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.exceptions import PlatformError


@dataclass(frozen=True)
class SyncContext:
    business_id: uuid.UUID
    actor_id: uuid.UUID
    device_id: str
    permissions: frozenset[str]
    correlation_id: str


class Rejected(Exception):
    """The mutation cannot apply any more; the reason is shown to the device's user."""


Handler = Callable[[AsyncSession, SyncContext, dict[str, Any]], Awaitable[dict[str, Any]]]
_HANDLERS: dict[str, tuple[Handler, str]] = {}


def mutation(kind: str, *, permission: str) -> Callable[[Handler], Handler]:
    def wrap(fn: Handler) -> Handler:
        _HANDLERS[kind] = (fn, permission)
        return fn

    return wrap


def registered_kinds() -> list[str]:
    return sorted(_HANDLERS)


class OfflineSyncService:
    @staticmethod
    async def apply_batch(
        session: AsyncSession, ctx: SyncContext, mutations: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Apply queued mutations in order; each in its own savepoint."""
        results: list[dict[str, Any]] = []
        for m in mutations:
            try:
                client_id = uuid.UUID(str(m.get("client_mutation_id")))
            except (TypeError, ValueError):
                results.append({"client_mutation_id": m.get("client_mutation_id"), "status": "rejected",
                                "reason": "Missing or malformed client id"})
                continue
            kind = str(m.get("kind") or "")
            prior = (await session.execute(
                text("SELECT status, result FROM offline_mutations WHERE business_id = :b AND client_mutation_id = :c"),
                {"b": str(ctx.business_id), "c": str(client_id)},
            )).first()
            if prior is not None:
                results.append({"client_mutation_id": str(client_id), "status": prior[0], "replayed": True,
                                **(dict(prior[1] or {}))})
                continue
            entry = _HANDLERS.get(kind)
            status, result = "rejected", {}
            if entry is None:
                result = {"reason": f"This device sent something LOCAH does not accept ({kind})"}
            elif entry[1] not in ctx.permissions:
                result = {"reason": "You are not allowed to do this any more"}
            else:
                try:
                    async with session.begin_nested():
                        result = await entry[0](session, ctx, dict(m.get("payload") or {}))
                    status = "applied"
                except Rejected as exc:
                    result = {"reason": str(exc)}
                except PlatformError as exc:
                    detail: dict[str, Any] = exc.detail if isinstance(exc.detail, dict) else {}
                    result = {"reason": str(detail.get("message") or exc.code)}
            created = m.get("client_created_at")
            await session.execute(
                text("""
                    INSERT INTO offline_mutations (business_id, client_mutation_id, device_id, kind, payload, status,
                                                   result, client_created_at, applied_by)
                    VALUES (:b, :c, :d, :k, CAST(:p AS jsonb), :s, CAST(:r AS jsonb), :t, :u)
                    ON CONFLICT (business_id, client_mutation_id) DO NOTHING
                """),
                {"b": str(ctx.business_id), "c": str(client_id), "d": ctx.device_id, "k": kind,
                 "p": json.dumps(m.get("payload") or {}), "s": status, "r": json.dumps(result, default=str),
                 "t": datetime.fromisoformat(created) if isinstance(created, str) else None,
                 "u": str(ctx.actor_id)},
            )
            results.append({"client_mutation_id": str(client_id), "status": status, "replayed": False, **result})
        return results
