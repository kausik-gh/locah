"""Platform membership plan + enrolment APIs (Stage 6 — Doc 11 §9.5)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from platform_api.db import get_db_session
from platform_api.dependencies import BusinessActorContext, require_business_actor
from platform_core.permissions import (
    MEMBERSHIPS_CANCEL_ENROLMENT,
    MEMBERSHIPS_CREATE_PLAN,
    MEMBERSHIPS_MANAGE_ENROLMENT,
    MEMBERSHIPS_READ,
    MEMBERSHIPS_UPDATE_PLAN,
)
from platform_core.resolvers.membership_resolver import MembershipResolver
from platform_core.services.membership_enrolment import MembershipEnrolmentService
from platform_core.services.membership_plan import MembershipPlanService

router = APIRouter(prefix="/v1/platform/businesses", tags=["memberships"])

_MODULE = "memberships"


class VersionedBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int | None = Field(default=None, ge=1)


class CreatePlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str | None = None
    offering_id: UUID | None = None
    price_amount: float = 0
    currency: str = "INR"
    billing_model: str = "fixed_duration"
    duration_days: int
    status: str = "draft"
    visibility: str = "private"
    offering_access: list[UUID] = Field(default_factory=list)


class PatchPlanRequest(VersionedBody):
    name: str | None = None
    description: str | None = None
    offering_id: UUID | None = None
    price_amount: float | None = None
    currency: str | None = None
    duration_days: int | None = None
    status: str | None = None
    visibility: str | None = None
    offering_access: list[UUID] | None = None


class EnrolRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_id: UUID
    customer_contact_id: UUID
    starts_at: str | None = None
    payment_method: str = "cod"
    auto_renew: bool = False
    idempotency_key: str | None = None


class EnrolmentTransitionRequest(VersionedBody):
    reason: str | None = None


# ---------------------------------------------------------------------------
# Plans
# ---------------------------------------------------------------------------
@router.get("/{business_id}/membership-plans")
async def list_plans(
    business_id: UUID,
    status: str | None = Query(default=None),
    visibility: str | None = Query(default=None),
    actor: BusinessActorContext = Depends(require_business_actor(MEMBERSHIPS_READ, _MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    plans = await MembershipPlanService.list_plans(
        session, business_id=business_id, status=status, visibility=visibility
    )
    out = []
    for plan in plans:
        access = await MembershipResolver.load_plan_offering_access(
            session, business_id=business_id, plan_id=plan.id
        )
        out.append(
            MembershipResolver.serialize_plan(
                plan, offering_access=[a.offering_id for a in access]
            )
        )
    return {
        "data": out,
        "meta": {"correlation_id": actor.request.correlation_id, "count": len(out)},
    }


@router.post("/{business_id}/membership-plans")
async def create_plan(
    business_id: UUID,
    body: CreatePlanRequest,
    actor: BusinessActorContext = Depends(require_business_actor(MEMBERSHIPS_CREATE_PLAN, _MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    plan = await MembershipPlanService.create_plan(
        session,
        business_id=business_id,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
        payload=body.model_dump(mode="json"),
    )
    access = await MembershipResolver.load_plan_offering_access(
        session, business_id=business_id, plan_id=plan.id
    )
    await session.commit()
    return {
        "data": MembershipResolver.serialize_plan(
            plan, offering_access=[a.offering_id for a in access]
        ),
        "meta": {"correlation_id": actor.request.correlation_id},
    }


@router.get("/{business_id}/membership-plans/{plan_id}")
async def get_plan(
    business_id: UUID,
    plan_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(MEMBERSHIPS_READ, _MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    plan = await MembershipResolver.resolve_plan(
        session, business_id=business_id, plan_id=plan_id
    )
    access = await MembershipResolver.load_plan_offering_access(
        session, business_id=business_id, plan_id=plan_id
    )
    return {
        "data": MembershipResolver.serialize_plan(
            plan, offering_access=[a.offering_id for a in access]
        ),
        "meta": {"correlation_id": actor.request.correlation_id},
    }


@router.patch("/{business_id}/membership-plans/{plan_id}")
async def patch_plan(
    business_id: UUID,
    plan_id: UUID,
    body: PatchPlanRequest,
    actor: BusinessActorContext = Depends(require_business_actor(MEMBERSHIPS_UPDATE_PLAN, _MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    payload = body.model_dump(mode="json", exclude_unset=True)
    version = payload.pop("version", None)
    plan = await MembershipPlanService.patch_plan(
        session,
        business_id=business_id,
        plan_id=plan_id,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
        payload=payload,
        expected_version=version,
    )
    access = await MembershipResolver.load_plan_offering_access(
        session, business_id=business_id, plan_id=plan_id
    )
    await session.commit()
    return {
        "data": MembershipResolver.serialize_plan(
            plan, offering_access=[a.offering_id for a in access]
        ),
        "meta": {"correlation_id": actor.request.correlation_id},
    }


@router.post("/{business_id}/membership-plans/{plan_id}/archive")
async def archive_plan(
    business_id: UUID,
    plan_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(MEMBERSHIPS_UPDATE_PLAN, _MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    plan = await MembershipPlanService.archive_plan(
        session,
        business_id=business_id,
        plan_id=plan_id,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
    )
    await session.commit()
    return {
        "data": MembershipResolver.serialize_plan(plan),
        "meta": {"correlation_id": actor.request.correlation_id},
    }


# ---------------------------------------------------------------------------
# Enrolments
# ---------------------------------------------------------------------------
@router.get("/{business_id}/membership-enrolments")
async def list_enrolments(
    business_id: UUID,
    plan_id: UUID | None = Query(default=None),
    customer_contact_id: UUID | None = Query(default=None),
    status: str | None = Query(default=None),
    actor: BusinessActorContext = Depends(require_business_actor(MEMBERSHIPS_READ, _MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    enrolments = await MembershipEnrolmentService.list_enrolments(
        session,
        business_id=business_id,
        plan_id=plan_id,
        customer_contact_id=customer_contact_id,
        status=status,
    )
    return {
        "data": [MembershipResolver.serialize_enrolment(e) for e in enrolments],
        "meta": {"correlation_id": actor.request.correlation_id, "count": len(enrolments)},
    }


@router.post("/{business_id}/membership-enrolments")
async def enrol(
    business_id: UUID,
    body: EnrolRequest,
    actor: BusinessActorContext = Depends(
        require_business_actor(MEMBERSHIPS_MANAGE_ENROLMENT, _MODULE)
    ),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    enrolment = await MembershipEnrolmentService.enrol(
        session,
        business_id=business_id,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
        payload=body.model_dump(mode="json", exclude_none=True),
    )
    await session.commit()
    return {
        "data": MembershipResolver.serialize_enrolment(enrolment),
        "meta": {"correlation_id": actor.request.correlation_id},
    }


@router.get("/{business_id}/membership-enrolments/{enrolment_id}")
async def get_enrolment(
    business_id: UUID,
    enrolment_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(MEMBERSHIPS_READ, _MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    enrolment = await MembershipResolver.resolve_enrolment(
        session, business_id=business_id, enrolment_id=enrolment_id
    )
    history = await MembershipResolver.load_enrolment_status_history(
        session, enrolment_id=enrolment_id
    )
    return {
        "data": {
            **MembershipResolver.serialize_enrolment(enrolment),
            "status_history": [
                MembershipResolver.serialize_status_event(e) for e in history
            ],
        },
        "meta": {"correlation_id": actor.request.correlation_id},
    }


def _transition_route(target: str, permission: str) -> Any:
    async def handler(
        business_id: UUID,
        enrolment_id: UUID,
        body: EnrolmentTransitionRequest,
        actor: BusinessActorContext = Depends(require_business_actor(permission, _MODULE)),
        session: AsyncSession = Depends(get_db_session),
    ) -> dict[str, Any]:
        enrolment = await MembershipEnrolmentService.transition(
            session,
            business_id=business_id,
            enrolment_id=enrolment_id,
            target_status=target,
            actor_id=actor.request.identity_id,
            correlation_id=actor.request.correlation_id,
            reason=body.reason,
            expected_version=body.version,
        )
        await session.commit()
        return {
            "data": MembershipResolver.serialize_enrolment(enrolment),
            "meta": {"correlation_id": actor.request.correlation_id},
        }

    return handler


router.add_api_route(
    "/{business_id}/membership-enrolments/{enrolment_id}/pause",
    _transition_route("paused", MEMBERSHIPS_MANAGE_ENROLMENT),
    methods=["POST"],
)
router.add_api_route(
    "/{business_id}/membership-enrolments/{enrolment_id}/resume",
    _transition_route("active", MEMBERSHIPS_MANAGE_ENROLMENT),
    methods=["POST"],
)
router.add_api_route(
    "/{business_id}/membership-enrolments/{enrolment_id}/cancel",
    _transition_route("cancelled", MEMBERSHIPS_CANCEL_ENROLMENT),
    methods=["POST"],
)
