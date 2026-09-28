"""Business-supplied licence and filing dates, never statutory advice."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal, cast
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_api.db import get_db_session
from platform_api.dependencies import BusinessActorContext, require_business_actor
from platform_core.context_resolver import bind_public_context
from platform_core.exceptions import ResourceNotFound
from platform_core.models import BusinessModuleState
from platform_core.permissions import COMPLIANCE_MANAGE, COMPLIANCE_READ
from platform_core.services.business import BusinessService
from platform_core.services.compliance import ComplianceService

router = APIRouter(prefix="/v1/platform/businesses", tags=["compliance"])
public_router = APIRouter(prefix="/v1/public/websites", tags=["compliance-public"])
MODULE = "compliance"
IST = ZoneInfo("Asia/Kolkata")


class CreateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location_id: UUID | None = None
    item_type: Literal["licence", "filing"]
    kind: str = Field(min_length=1, max_length=60)
    title: str = Field(min_length=1, max_length=120)
    licence_number: str | None = Field(default=None, max_length=60)
    authority: str | None = Field(default=None, max_length=120)
    issued_on: date | None = None
    due_on: date
    recurrence: Literal["none", "monthly", "quarterly", "yearly"] = "none"
    document_url: str | None = Field(default=None, max_length=500)
    show_on_site: bool = False
    notes: str | None = Field(default=None, max_length=1000)


class UpdateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location_id: UUID | None = None
    kind: str | None = Field(default=None, min_length=1, max_length=60)
    title: str | None = Field(default=None, min_length=1, max_length=120)
    licence_number: str | None = Field(default=None, max_length=60)
    authority: str | None = Field(default=None, max_length=120)
    issued_on: date | None = None
    due_on: date | None = None
    recurrence: Literal["none", "monthly", "quarterly", "yearly"] | None = None
    document_url: str | None = Field(default=None, max_length=500)
    show_on_site: bool | None = None
    notes: str | None = Field(default=None, max_length=1000)


class RenewBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    new_due_on: date
    completed_on: date | None = None
    note: str | None = Field(default=None, max_length=500)


class FiledBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    completed_on: date | None = None
    note: str | None = Field(default=None, max_length=500)


class ArchiveBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    archived: bool


def _meta(actor: BusinessActorContext) -> dict[str, str]:
    return {"correlation_id": actor.request.correlation_id}


def _scope(actor: BusinessActorContext) -> list[UUID] | None:
    return cast(list[UUID] | None, actor.actor_membership.location_scope)


@router.get("/{business_id}/compliance/items")
async def list_items(
    business_id: UUID, archived: bool = Query(default=False),
    actor: BusinessActorContext = Depends(require_business_actor(COMPLIANCE_READ, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await ComplianceService.list_items(session, business_id, _scope(actor), archived=archived)
    return {"data": data, "meta": _meta(actor)}


@router.post("/{business_id}/compliance/items")
async def create_item(
    business_id: UUID, body: CreateBody,
    actor: BusinessActorContext = Depends(require_business_actor(COMPLIANCE_MANAGE, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    item = await ComplianceService.create(session, business_id, actor.request.identity_id,
                                          body.model_dump(), _scope(actor))
    data = ComplianceService.serialize(item)
    await session.commit()
    return {"data": data, "meta": _meta(actor)}


@router.get("/{business_id}/compliance/items/{item_id}")
async def get_item(
    business_id: UUID, item_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(COMPLIANCE_READ, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    item = await ComplianceService.get(session, business_id, item_id, _scope(actor))
    return {"data": ComplianceService.serialize(item), "meta": _meta(actor)}


@router.get("/{business_id}/compliance/items/{item_id}/history")
async def history(
    business_id: UUID, item_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(COMPLIANCE_READ, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await ComplianceService.history(session, business_id, item_id, _scope(actor))
    return {"data": data, "meta": _meta(actor)}


@router.patch("/{business_id}/compliance/items/{item_id}")
async def update_item(
    business_id: UUID, item_id: UUID, body: UpdateBody,
    actor: BusinessActorContext = Depends(require_business_actor(COMPLIANCE_MANAGE, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    item = await ComplianceService.update(session, business_id, item_id, actor.request.identity_id,
                                          body.model_dump(exclude_unset=True), _scope(actor))
    data = ComplianceService.serialize(item)
    await session.commit()
    return {"data": data, "meta": _meta(actor)}


@router.post("/{business_id}/compliance/items/{item_id}/renew")
async def renew_item(
    business_id: UUID, item_id: UUID, body: RenewBody,
    actor: BusinessActorContext = Depends(require_business_actor(COMPLIANCE_MANAGE, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    item = await ComplianceService.renew(session, business_id, item_id, actor.request.identity_id,
                                         body.new_due_on, body.completed_on or datetime.now(IST).date(),
                                         body.note, _scope(actor))
    data = ComplianceService.serialize(item)
    await session.commit()
    return {"data": data, "meta": _meta(actor)}


@router.post("/{business_id}/compliance/items/{item_id}/filed")
async def file_item(
    business_id: UUID, item_id: UUID, body: FiledBody,
    actor: BusinessActorContext = Depends(require_business_actor(COMPLIANCE_MANAGE, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    item = await ComplianceService.file(session, business_id, item_id, actor.request.identity_id,
                                        body.completed_on or datetime.now(IST).date(),
                                        body.note, _scope(actor))
    data = ComplianceService.serialize(item)
    await session.commit()
    return {"data": data, "meta": _meta(actor)}


@router.post("/{business_id}/compliance/items/{item_id}/archive")
async def archive_item(
    business_id: UUID, item_id: UUID, body: ArchiveBody,
    actor: BusinessActorContext = Depends(require_business_actor(COMPLIANCE_MANAGE, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    item = await ComplianceService.set_archived(session, business_id, item_id, actor.request.identity_id,
                                                body.archived, _scope(actor))
    data = ComplianceService.serialize(item)
    await session.commit()
    return {"data": data, "meta": _meta(actor)}


@public_router.get("/{slug}/licences")
async def public_licences(slug: str, session: AsyncSession = Depends(get_db_session)) -> dict[str, Any]:
    business = await BusinessService.get_by_slug(session, slug)
    if business is None or business.deleted_at is not None or business.visibility == "private":
        raise ResourceNotFound("Licences")
    await bind_public_context(session, business.id)
    state = (await session.execute(select(BusinessModuleState).where(
        BusinessModuleState.business_id == business.id, BusinessModuleState.module_id == MODULE,
    ))).scalars().first()
    if state is None or state.activation_state not in {"ready", "active"}:
        raise ResourceNotFound("Licences")
    return {"data": await ComplianceService.public_licences(session, business.id), "meta": {}}
