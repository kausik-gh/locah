"""Platform lead pipeline APIs (Stage 6 — Doc 11 §10.2)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from platform_api.db import get_db_session
from platform_api.dependencies import BusinessActorContext, require_business_actor
from platform_core.permissions import (
    LEADS_ASSIGN,
    LEADS_CREATE,
    LEADS_DELETE,
    LEADS_READ,
    LEADS_UPDATE_STATUS,
)
from platform_core.resolvers.lead_resolver import LeadResolver
from platform_core.services.lead import LeadService
from platform_core.services.lead_note import LeadNoteService

router = APIRouter(prefix="/v1/platform/businesses", tags=["leads"])

_MODULE = "leads"


class VersionedBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int | None = Field(default=None, ge=1)


class CreateLeadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str
    email: str | None = None
    phone: str | None = None
    message: str | None = None
    source: str | None = None
    origin_context: dict[str, Any] | None = None
    offering_id: UUID | None = None
    assignee_identity_id: UUID | None = None
    next_follow_up_at: str | None = None


class PatchLeadRequest(VersionedBody):
    display_name: str | None = None
    email: str | None = None
    phone: str | None = None
    message: str | None = None
    offering_id: UUID | None = None
    next_follow_up_at: str | None = None


class MoveStageRequest(VersionedBody):
    status: str
    reason: str | None = None


class AssignLeadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assignee_identity_id: UUID | None = None


class LeadNoteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body: str


@router.get("/{business_id}/leads")
async def list_leads(
    business_id: UUID,
    status: str | None = Query(default=None),
    assignee_identity_id: UUID | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=200),
    actor: BusinessActorContext = Depends(require_business_actor(LEADS_READ, _MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    leads = await LeadService.list_leads(
        session,
        business_id=business_id,
        status=status,
        assignee_identity_id=assignee_identity_id,
        limit=limit,
    )
    counts = await LeadService.pipeline_counts(session, business_id=business_id)
    return {
        "data": [LeadResolver.serialize_lead(lead) for lead in leads],
        "meta": {
            "correlation_id": actor.request.correlation_id,
            "count": len(leads),
            "pipeline": counts,
        },
    }


@router.post("/{business_id}/leads")
async def create_lead(
    business_id: UUID,
    body: CreateLeadRequest,
    actor: BusinessActorContext = Depends(require_business_actor(LEADS_CREATE, _MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    lead = await LeadService.create_lead(
        session,
        business_id=business_id,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
        payload=body.model_dump(mode="json", exclude_none=True),
    )
    await session.commit()
    return {
        "data": LeadResolver.serialize_lead(lead),
        "meta": {"correlation_id": actor.request.correlation_id},
    }


@router.get("/{business_id}/leads/{lead_id}")
async def get_lead(
    business_id: UUID,
    lead_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(LEADS_READ, _MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    lead = await LeadResolver.resolve(session, business_id=business_id, lead_id=lead_id)
    history = await LeadResolver.load_status_history(session, lead_id=lead_id)
    notes = await LeadResolver.load_notes(session, lead_id=lead_id)
    return {
        "data": {
            **LeadResolver.serialize_lead(lead),
            "status_history": [LeadResolver.serialize_status_event(e) for e in history],
            "notes": [LeadResolver.serialize_note(n) for n in notes],
        },
        "meta": {"correlation_id": actor.request.correlation_id},
    }


@router.patch("/{business_id}/leads/{lead_id}")
async def patch_lead(
    business_id: UUID,
    lead_id: UUID,
    body: PatchLeadRequest,
    actor: BusinessActorContext = Depends(require_business_actor(LEADS_UPDATE_STATUS, _MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    payload = body.model_dump(mode="json", exclude_unset=True)
    version = payload.pop("version", None)
    lead = await LeadService.patch_lead(
        session,
        business_id=business_id,
        lead_id=lead_id,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
        payload=payload,
        expected_version=version,
    )
    await session.commit()
    return {
        "data": LeadResolver.serialize_lead(lead),
        "meta": {"correlation_id": actor.request.correlation_id},
    }


@router.post("/{business_id}/leads/{lead_id}/move-stage")
async def move_stage(
    business_id: UUID,
    lead_id: UUID,
    body: MoveStageRequest,
    actor: BusinessActorContext = Depends(require_business_actor(LEADS_UPDATE_STATUS, _MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    payload = body.model_dump(mode="json", exclude_none=True)
    version = payload.pop("version", None)
    lead = await LeadService.move_stage(
        session,
        business_id=business_id,
        lead_id=lead_id,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
        payload=payload,
        expected_version=version,
    )
    await session.commit()
    return {
        "data": LeadResolver.serialize_lead(lead),
        "meta": {"correlation_id": actor.request.correlation_id},
    }


@router.post("/{business_id}/leads/{lead_id}/assign")
async def assign_lead(
    business_id: UUID,
    lead_id: UUID,
    body: AssignLeadRequest,
    actor: BusinessActorContext = Depends(require_business_actor(LEADS_ASSIGN, _MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    lead = await LeadService.assign_lead(
        session,
        business_id=business_id,
        lead_id=lead_id,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
        payload=body.model_dump(mode="json"),
    )
    await session.commit()
    return {
        "data": LeadResolver.serialize_lead(lead),
        "meta": {"correlation_id": actor.request.correlation_id},
    }


@router.post("/{business_id}/leads/{lead_id}/notes")
async def add_lead_note(
    business_id: UUID,
    lead_id: UUID,
    body: LeadNoteRequest,
    actor: BusinessActorContext = Depends(require_business_actor(LEADS_UPDATE_STATUS, _MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    note = await LeadNoteService.create_note(
        session,
        business_id=business_id,
        lead_id=lead_id,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
        body=body.body,
    )
    await session.commit()
    return {
        "data": LeadNoteService.serialize(note),
        "meta": {"correlation_id": actor.request.correlation_id},
    }


@router.delete("/{business_id}/leads/{lead_id}")
async def delete_lead(
    business_id: UUID,
    lead_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(LEADS_DELETE, _MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    await LeadService.delete_lead(
        session,
        business_id=business_id,
        lead_id=lead_id,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
    )
    await session.commit()
    return {"data": {"deleted": True}, "meta": {"correlation_id": actor.request.correlation_id}}
