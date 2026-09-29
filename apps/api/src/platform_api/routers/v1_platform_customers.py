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
    CUSTOMERS_ERASE,
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
    tag: str | None = Query(default=None, min_length=1, max_length=64),
    actor: BusinessActorContext = Depends(require_business_actor(CUSTOMERS_READ, "customer-relationships")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    customers = await CustomerService.list_for_business(
        session,
        business_id,
        status=status,
        search=search,
        location_id=location_id,
        tag=tag,
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


# ---------------------------------------------------------------- tags and segments (P1-10E2; CR-03, CR-04)
class SegmentBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80)
    rules: list[dict[str, Any]]


class SegmentPatch(VersionedBody):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    rules: list[dict[str, Any]] | None = None


class PreviewBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rules: list[dict[str, Any]]


async def _live(session: AsyncSession, business_id: UUID) -> set[str]:
    from platform_core.services.module_readiness import module_states

    return {k for k, v in (await module_states(session, business_id)).items() if v in ("enabled", "ready", "active")}


@router.get("/{business_id}/customers/tags")
async def customer_tags(
    business_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(CUSTOMERS_READ, "customer-relationships")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    from platform_core.customers.segments import SegmentService

    return {"data": await SegmentService.tags(session, business_id),
            "meta": {"correlation_id": actor.request.correlation_id}}


@router.get("/{business_id}/customers/segments")
async def list_segments(
    business_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(CUSTOMERS_READ, "customer-relationships")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    from platform_core.customers.segments import SegmentService, available

    return {"data": await SegmentService.all(session, business_id),
            "meta": {"correlation_id": actor.request.correlation_id, "rules": available(await _live(session, business_id))}}


@router.post("/{business_id}/customers/segments/preview")
async def preview_segment(
    business_id: UUID,
    body: PreviewBody,
    actor: BusinessActorContext = Depends(require_business_actor(CUSTOMERS_READ, "customer-relationships")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    from platform_core.customers.segments import clean_rules, evaluate, titles, words

    rules = clean_rules(body.rules, await _live(session, business_id))
    found = await evaluate(session, business_id, rules, limit=20)
    names = await titles(session, business_id, rules)
    return {"data": {**found, "rule_words": [words(r, names) for r in rules]},
            "meta": {"correlation_id": actor.request.correlation_id}}


@router.post("/{business_id}/customers/segments")
async def create_segment(
    business_id: UUID,
    body: SegmentBody,
    actor: BusinessActorContext = Depends(require_business_actor(CUSTOMERS_UPDATE, "customer-relationships")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    from platform_core.customers.segments import SegmentService

    seg = await SegmentService.create(session, business_id, actor.request.identity_id, name=body.name,
                                      rules=body.rules, live=await _live(session, business_id))
    data = await SegmentService.serialize(session, business_id, seg)
    await session.commit()
    return {"data": data, "meta": {"correlation_id": actor.request.correlation_id}}


@router.get("/{business_id}/customers/segments/{segment_id}")
async def get_segment(
    business_id: UUID,
    segment_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(CUSTOMERS_READ, "customer-relationships")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    from platform_core.customers.segments import SegmentService, available

    seg = await SegmentService._get(session, business_id, segment_id)
    return {"data": await SegmentService.serialize(session, business_id, seg, members=True, limit=500),
            "meta": {"correlation_id": actor.request.correlation_id, "rules": available(await _live(session, business_id))}}


@router.patch("/{business_id}/customers/segments/{segment_id}")
async def update_segment(
    business_id: UUID,
    segment_id: UUID,
    body: SegmentPatch,
    actor: BusinessActorContext = Depends(require_business_actor(CUSTOMERS_UPDATE, "customer-relationships")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    from platform_core.customers.segments import SegmentService

    seg = await SegmentService.update(session, business_id, actor.request.identity_id, segment_id,
                                      name=body.name, rules=body.rules, version=body.version,
                                      live=await _live(session, business_id))
    data = await SegmentService.serialize(session, business_id, seg)
    await session.commit()
    return {"data": data, "meta": {"correlation_id": actor.request.correlation_id}}


@router.post("/{business_id}/customers/segments/{segment_id}/archive")
async def archive_segment(
    business_id: UUID,
    segment_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(CUSTOMERS_UPDATE, "customer-relationships")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    from platform_core.customers.segments import SegmentService

    await SegmentService.update(session, business_id, actor.request.identity_id, segment_id, archive=True,
                                live=await _live(session, business_id))
    await session.commit()
    return {"data": {"archived": True}, "meta": {"correlation_id": actor.request.correlation_id}}


# ---------------------------------------------------------------- DPDP export and erasure (P1-10E3; CR-08, CO-01)
class EraseBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirm: str = Field(min_length=1, max_length=160)
    reason: str | None = Field(default=None, max_length=300)


class DeclineBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=500)


def _whole_business(actor: BusinessActorContext) -> None:
    """Export and erasure cover every location's records, so they are for people who see every location."""
    from platform_core.authorization.location_scope import scoped_locations
    from platform_core.exceptions import PermissionDenied

    if scoped_locations(actor.actor_membership) is not None:
        raise PermissionDenied(CUSTOMERS_EXPORT)


@router.get("/{business_id}/customers/privacy-requests")
async def open_privacy_requests(
    business_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(CUSTOMERS_READ, "customer-relationships")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    from platform_core.customers.privacy import PrivacyRequests

    return {"data": await PrivacyRequests.open_for(session, business_id),
            "meta": {"correlation_id": actor.request.correlation_id}}


@router.post("/{business_id}/customers/privacy-requests/{request_id}/decline")
async def decline_privacy_request(
    business_id: UUID,
    request_id: UUID,
    body: DeclineBody,
    actor: BusinessActorContext = Depends(require_business_actor(CUSTOMERS_ERASE, "customer-relationships")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    from platform_core.customers.privacy import PrivacyRequests

    await PrivacyRequests.decline(session, business_id, request_id, actor.request.identity_id, body.reason)
    await session.commit()
    return {"data": {"declined": True}, "meta": {"correlation_id": actor.request.correlation_id}}


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


@router.get("/{business_id}/customers/{customer_id}/privacy")
async def customer_privacy(
    business_id: UUID,
    customer_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(CUSTOMERS_READ, "customer-relationships")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """What erasing this customer would wait for, what would be kept, and their requests."""
    from platform_core.customers.privacy import KEPT, PrivacyRequests, _contact, blockers

    contact = await _contact(session, business_id, customer_id)
    return {"data": {"erased_at": contact["erased_at"], "open": await blockers(session, business_id, customer_id),
                     "kept": KEPT, "requests": await PrivacyRequests.for_contact(session, business_id, customer_id)},
            "meta": {"correlation_id": actor.request.correlation_id}}


@router.get("/{business_id}/customers/{customer_id}/export")
async def export_customer(
    business_id: UUID,
    customer_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(CUSTOMERS_EXPORT, "customer-relationships")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Everything held about one customer, in one file (DPDP access, MD §25.1)."""
    from platform_core.customers.privacy import PrivacyRequests, _contact, export
    from platform_core.services.audit import AuditService

    _whole_business(actor)
    await _contact(session, business_id, customer_id)
    data = await export(session, business_id, [customer_id], business_name=actor.business.display_name)
    await PrivacyRequests.record(session, business_id, customer_id, kind="access", source="staff",
                                 identity_id=actor.request.identity_id, note="Downloaded by the business",
                                 status="done")
    await AuditService.record(session, event_type="customer.exported", actor_identity_id=actor.request.identity_id,
                              actor_context="business", action="export", business_id=business_id,
                              resource_type="customer", resource_id=customer_id, after_state={"sections": len(data)})
    await session.commit()
    return {"data": data, "meta": {"correlation_id": actor.request.correlation_id}}


@router.post("/{business_id}/customers/{customer_id}/erase")
async def erase_customer(
    business_id: UUID,
    customer_id: UUID,
    body: EraseBody,
    actor: BusinessActorContext = Depends(require_business_actor(CUSTOMERS_ERASE, "customer-relationships")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Remove a customer's personal details for good, keeping what the law requires (DPDP erasure)."""
    from platform_core.customers.privacy import erase

    _whole_business(actor)
    result = await erase(session, business_id, customer_id, actor.request.identity_id, reason=body.reason,
                         confirm=body.confirm)
    await session.commit()
    return {"data": result, "meta": {"correlation_id": actor.request.correlation_id}}
