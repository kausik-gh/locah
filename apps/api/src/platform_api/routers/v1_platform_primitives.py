"""Shared primitives exposed to owners and devices (Capability Universe §24):
automations (visible, switchable off), consent, usage meters, rendered
documents and offline sync.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from platform_api.db import get_db_session
from platform_api.dependencies import (
    BusinessActorContext,
    require_business_actor,
    require_business_member,
)
from platform_core.automation import LADDERS, AutomationEngine, is_wired
from platform_core.catalog.modules import MODULES
from platform_core.exceptions import PermissionDenied, ResourceNotFound, ValidationError
from platform_core.permissions import (
    CUSTOMERS_READ,
    CUSTOMERS_UPDATE,
    SETTINGS_READ,
    SETTINGS_UPDATE,
)
from platform_core.services.consent import PURPOSE_LABELS, ConsentService
from platform_core.services.documents_store import DocumentStore
from platform_core.services.module_readiness import module_states
from platform_core.services.offline_sync import OfflineSyncService, SyncContext
from platform_core.services.usage_meter import UsageMeterService

router = APIRouter(prefix="/v1/platform/businesses", tags=["primitives"])

# Who may open a rendered document of each type. A module adds its type here
# when it starts rendering documents.
DOCUMENT_PERMISSIONS: dict[str, str] = {
    "quote": "quotes.read",
    **{kind: "invoices.read" for kind in ("tax_invoice", "bill_of_supply", "bill", "credit_note", "debit_note")},
}


def _meta(actor: BusinessActorContext, **extra: Any) -> dict[str, Any]:
    return {"correlation_id": actor.request.correlation_id, **extra}


# ------------------------------------------------------------------ automations
class AutomationPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool | None = None
    config: dict[str, Any] | None = None


def _ladder_view(key: str, rule: dict[str, Any]) -> dict[str, Any]:
    lad = LADDERS[key]
    info = MODULES.get(lad.module)
    offsets = rule["config"].get("offset_hours", {})
    off = set(rule["config"].get("disabled_steps", []))
    return {
        "key": key, "label": lad.label, "module": lad.module, "module_label": info.label if info else lad.module,
        "anchor": lad.anchor, "stops_when": lad.stops_when, "enabled": rule["enabled"],
        "quiet_hours": rule["config"].get("quiet_hours", lad.quiet_hours),
        "steps": [
            {"key": s.key, "when": s.when, "does": s.does, "marketing": s.marketing, "on": s.key not in off,
             "offset_hours": offsets.get(s.key, int(s.offset.total_seconds() // 3600))}
            for s in lad.steps
        ],
    }


@router.get("/{business_id}/automations")
async def list_automations(
    business_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(SETTINGS_READ)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Automations the owner can see: only those whose module is built and on,
    and whose steps have code behind them."""
    states = await module_states(session, business_id)
    live = {k for k, v in states.items() if v in ("enabled", "ready", "active")}
    items = []
    for key, lad in LADDERS.items():
        info = MODULES.get(lad.module)
        if not info or not info.built or lad.module not in live or not is_wired(key):
            continue
        items.append(_ladder_view(key, await AutomationEngine.rule(session, business_id, key)))
    activity = await AutomationEngine.activity(session, business_id, limit=30)
    return {"data": {"automations": items, "activity": activity}, "meta": _meta(actor)}


@router.patch("/{business_id}/automations/{ladder_key}")
async def patch_automation(
    business_id: UUID,
    ladder_key: str,
    body: AutomationPatch,
    actor: BusinessActorContext = Depends(require_business_actor(SETTINGS_UPDATE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    if ladder_key not in LADDERS:
        raise ResourceNotFound("Automation")
    rule = await AutomationEngine.set_rule(
        session, business_id, ladder_key, enabled=body.enabled, config=body.config,
        actor_id=actor.request.identity_id,
    )
    await session.commit()
    return {"data": _ladder_view(ladder_key, rule), "meta": _meta(actor)}


@router.get("/{business_id}/automations/activity")
async def automation_activity(
    business_id: UUID,
    ladder_key: str | None = Query(default=None),
    entity_id: UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    actor: BusinessActorContext = Depends(require_business_actor(SETTINGS_READ)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    rows = await AutomationEngine.activity(session, business_id, ladder_key=ladder_key, entity_id=entity_id,
                                           limit=limit)
    return {"data": rows, "meta": _meta(actor)}


# ------------------------------------------------------------------ consent
class ConsentChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    purpose: str
    channel: str = "whatsapp"
    granted: bool
    source: str = Field(default="staff_recorded", max_length=60)
    note: str | None = Field(default=None, max_length=300)


@router.get("/{business_id}/customers/{contact_id}/consents")
async def list_consents(
    business_id: UUID,
    contact_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(CUSTOMERS_READ, "customer-relationships")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    history = await ConsentService.history(session, business_id, contact_id)
    return {"data": {"history": history, "purposes": PURPOSE_LABELS}, "meta": _meta(actor)}


@router.post("/{business_id}/customers/{contact_id}/consents")
async def change_consent(
    business_id: UUID,
    contact_id: UUID,
    body: ConsentChange,
    actor: BusinessActorContext = Depends(require_business_actor(CUSTOMERS_UPDATE, "customer-relationships")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    if body.granted:
        changed = await ConsentService.grant(
            session, business_id, contact_id, purpose=body.purpose, channel=body.channel, source=body.source,
            evidence={"note": body.note} if body.note else {}, recorded_by=actor.request.identity_id,
        )
    else:
        changed = await ConsentService.withdraw(
            session, business_id, contact_id, purpose=body.purpose, channel=body.channel, source=body.source,
        )
    await session.commit()
    history = await ConsentService.history(session, business_id, contact_id)
    return {"data": {"changed": changed, "history": history}, "meta": _meta(actor)}


# ------------------------------------------------------------------ usage meters
class CapRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cap: int | None = Field(default=None, ge=0, le=10**12)


@router.get("/{business_id}/usage")
async def usage(
    business_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(SETTINGS_READ)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    return {"data": await UsageMeterService.summary(session, business_id), "meta": _meta(actor)}


@router.put("/{business_id}/usage/{resource}/cap")
async def set_cap(
    business_id: UUID,
    resource: str,
    body: CapRequest,
    actor: BusinessActorContext = Depends(require_business_actor(SETTINGS_UPDATE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    await UsageMeterService.set_cap(session, business_id, resource, body.cap)
    await session.commit()
    return {"data": await UsageMeterService.summary(session, business_id), "meta": _meta(actor)}


# ------------------------------------------------------------------ documents
@router.get("/{business_id}/documents/{document_id}")
async def get_document(
    business_id: UUID,
    document_id: UUID,
    actor: BusinessActorContext = Depends(require_business_member()),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    content, meta = await DocumentStore.fetch(session, business_id, document_id)
    needed = DOCUMENT_PERMISSIONS.get(meta["doc_type"], SETTINGS_READ)
    from platform_core.authorization.resolver import AuthorizationService

    decision = await AuthorizationService.authorize(
        session, business_id=business_id, identity_id=actor.request.identity_id, permission=needed
    )
    if not decision.allowed:
        raise PermissionDenied(needed)
    return Response(
        content=content, media_type=meta["media_type"],
        headers={"Content-Disposition": f'inline; filename="{meta["doc_type"]}-{document_id}.pdf"',
                 "X-Content-SHA256": meta["sha256"], "Cache-Control": "private, no-store"},
    )


# ------------------------------------------------------------------ offline sync
class SyncRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device_id: str = Field(min_length=3, max_length=80)
    mutations: list[dict[str, Any]] = Field(max_length=200)


@router.post("/{business_id}/sync")
async def sync(
    business_id: UUID,
    body: SyncRequest,
    actor: BusinessActorContext = Depends(require_business_member()),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Replay a device's offline queue. Each mutation is checked against the
    caller's permissions by its own handler, exactly as online."""
    if not body.mutations:
        raise ValidationError("Nothing to sync", details={"field": "mutations"})
    from platform_core.authorization.resolver import AuthorizationService

    perms = await AuthorizationService.effective_permissions(
        session, business_id=business_id, identity_id=actor.request.identity_id
    )
    ctx = SyncContext(business_id=business_id, actor_id=actor.request.identity_id, device_id=body.device_id,
                      permissions=frozenset(perms), correlation_id=actor.request.correlation_id)
    results = await OfflineSyncService.apply_batch(session, ctx, body.mutations)
    await session.commit()
    return {"data": {"results": results}, "meta": _meta(actor)}
