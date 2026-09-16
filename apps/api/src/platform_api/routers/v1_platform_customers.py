"""Platform customer APIs (Stage 4)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from platform_api.db import get_db_session
from platform_api.dependencies import BusinessActorContext, require_business_actor
from platform_core.exceptions import ResourceNotFound
from platform_core.permissions import (
    CUSTOMERS_EXPORT,
    CUSTOMERS_MANAGE_NOTES,
    CUSTOMERS_READ,
    CUSTOMERS_UPDATE,
)
from platform_core.resolvers.customer_resolver import CustomerResolver
from platform_core.services.customer import CustomerService
from platform_core.services.customer_note import CustomerNoteService
from platform_core.services.customer_timeline import CustomerTimelineService

router = APIRouter(prefix="/v1/platform/businesses", tags=["customers"])


class VersionedBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int | None = Field(default=None, ge=1)


class CreateCustomerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str
    phone: str | None = None
    email: str | None = None
    status: str = "active"
    tags: list[str] = Field(default_factory=list)
    identity_id: UUID | None = None
    preferred_location_id: UUID | None = None


class PatchCustomerRequest(VersionedBody):
    display_name: str | None = None
    phone: str | None = None
    email: str | None = None
    status: str | None = None
    tags: list[str] | None = None
    identity_id: UUID | None = None
    preferred_location_id: UUID | None = None


class CreateNoteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body: str


def _patch_payload(body: BaseModel) -> dict[str, Any]:
    return body.model_dump(exclude_unset=True)


@router.get("/{business_id}/customers")
async def list_customers(
    business_id: UUID,
    status: str | None = Query(default=None),
    search: str | None = Query(default=None, min_length=1, max_length=120),
    location_id: UUID | None = Query(default=None),
    actor: BusinessActorContext = Depends(require_business_actor(CUSTOMERS_READ, "customer-relationships")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    customers = await CustomerService.list_for_business(
        session,
        business_id,
        status=status,
        search=search,
        location_id=location_id,
    )
    return {
        "data": [CustomerResolver.serialize_contact(c) for c in customers],
        "meta": {"correlation_id": actor.request.correlation_id, "count": len(customers)},
    }


@router.get("/{business_id}/customers/export")
async def export_customers(
    business_id: UUID,
    status: str | None = Query(default=None),
    actor: BusinessActorContext = Depends(require_business_actor(CUSTOMERS_EXPORT, "customer-relationships")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await CustomerService.export_customers(session, business_id, status=status)
    return {
        "data": data,
        "meta": {"correlation_id": actor.request.correlation_id, "count": len(data)},
    }


@router.post("/{business_id}/customers")
async def create_customer(
    business_id: UUID,
    body: CreateCustomerRequest,
    actor: BusinessActorContext = Depends(require_business_actor(CUSTOMERS_UPDATE, "customer-relationships")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    contact = await CustomerService.create_customer(
        session,
        business_id=business_id,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
        payload=body.model_dump(),
    )
    await session.commit()
    return {
        "data": CustomerResolver.serialize_contact(contact),
        "meta": {"correlation_id": actor.request.correlation_id},
    }


@router.get("/{business_id}/customers/{customer_id}")
async def get_customer(
    business_id: UUID,
    customer_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(CUSTOMERS_READ, "customer-relationships")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await CustomerService.get_by_id(session, business_id, customer_id)
    if data is None:
        raise ResourceNotFound("Customer")
    return {
        "data": data,
        "meta": {"correlation_id": actor.request.correlation_id},
    }


@router.patch("/{business_id}/customers/{customer_id}")
async def patch_customer(
    business_id: UUID,
    customer_id: UUID,
    body: PatchCustomerRequest,
    actor: BusinessActorContext = Depends(require_business_actor(CUSTOMERS_UPDATE, "customer-relationships")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    payload = _patch_payload(body)
    version = payload.pop("version", None)
    contact = await CustomerService.update_customer(
        session,
        business_id=business_id,
        contact_id=customer_id,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
        payload=payload,
        expected_version=version,
    )
    await session.commit()
    return {
        "data": CustomerResolver.serialize_contact(contact),
        "meta": {"correlation_id": actor.request.correlation_id},
    }


@router.post("/{business_id}/customers/{customer_id}/block")
async def block_customer(
    business_id: UUID,
    customer_id: UUID,
    body: VersionedBody,
    actor: BusinessActorContext = Depends(require_business_actor(CUSTOMERS_UPDATE, "customer-relationships")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    contact = await CustomerService.block_customer(
        session,
        business_id=business_id,
        contact_id=customer_id,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
        expected_version=body.version,
    )
    await session.commit()
    return {
        "data": CustomerResolver.serialize_contact(contact),
        "meta": {"correlation_id": actor.request.correlation_id},
    }


@router.post("/{business_id}/customers/{customer_id}/archive")
async def archive_customer(
    business_id: UUID,
    customer_id: UUID,
    body: VersionedBody,
    actor: BusinessActorContext = Depends(require_business_actor(CUSTOMERS_UPDATE, "customer-relationships")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    contact = await CustomerService.archive_customer(
        session,
        business_id=business_id,
        contact_id=customer_id,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
        expected_version=body.version,
    )
    await session.commit()
    return {
        "data": CustomerResolver.serialize_contact(contact),
        "meta": {"correlation_id": actor.request.correlation_id},
    }


@router.post("/{business_id}/customers/{customer_id}/restore")
async def restore_customer(
    business_id: UUID,
    customer_id: UUID,
    body: VersionedBody,
    actor: BusinessActorContext = Depends(require_business_actor(CUSTOMERS_UPDATE, "customer-relationships")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    contact = await CustomerService.restore_customer(
        session,
        business_id=business_id,
        contact_id=customer_id,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
        expected_version=body.version,
    )
    await session.commit()
    return {
        "data": CustomerResolver.serialize_contact(contact),
        "meta": {"correlation_id": actor.request.correlation_id},
    }


@router.get("/{business_id}/customers/{customer_id}/timeline")
async def list_customer_timeline(
    business_id: UUID,
    customer_id: UUID,
    limit: int = Query(default=50, ge=1, le=100),
    actor: BusinessActorContext = Depends(require_business_actor(CUSTOMERS_READ, "customer-relationships")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    entries = await CustomerTimelineService.list_for_contact(
        session,
        business_id=business_id,
        contact_id=customer_id,
        limit=limit,
    )
    return {
        "data": [CustomerResolver.serialize_timeline_entry(e) for e in entries],
        "meta": {"correlation_id": actor.request.correlation_id, "count": len(entries)},
    }


@router.get("/{business_id}/customers/{customer_id}/notes")
async def list_customer_notes(
    business_id: UUID,
    customer_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(CUSTOMERS_READ, "customer-relationships")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    notes = await CustomerNoteService.list_for_contact(
        session, business_id=business_id, contact_id=customer_id
    )
    return {
        "data": [CustomerResolver.serialize_note(n) for n in notes],
        "meta": {"correlation_id": actor.request.correlation_id, "count": len(notes)},
    }


@router.post("/{business_id}/customers/{customer_id}/notes")
async def create_customer_note(
    business_id: UUID,
    customer_id: UUID,
    body: CreateNoteRequest,
    actor: BusinessActorContext = Depends(require_business_actor(CUSTOMERS_MANAGE_NOTES, "customer-relationships")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    note = await CustomerNoteService.create_note(
        session,
        business_id=business_id,
        contact_id=customer_id,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
        body=body.body,
    )
    await session.commit()
    return {
        "data": CustomerResolver.serialize_note(note),
        "meta": {"correlation_id": actor.request.correlation_id},
    }
