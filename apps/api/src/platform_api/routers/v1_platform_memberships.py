"""Platform membership plan + enrolment APIs (Stage 6 — Doc 11 §9.5)."""

from __future__ import annotations

from datetime import date
from typing import Any, Literal
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


class PlanRules(BaseModel):
    """What a kind of plan carries (P2-02)."""

    plan_kind: str | None = None
    billing_timing: str | None = None
    grace_days: int | None = None
    grace_allows_entry: bool | None = None
    freeze_allowed: bool | None = None
    max_freeze_days: int | None = None
    sessions_included: int | None = None
    consume_on: str | None = None
    no_show_consumes: bool | None = None
    delivery: dict[str, Any] | None = None
    instalment_template: list[dict[str, Any]] | None = None
    visits_included: int | None = None
    visit_every_days: int | None = None


class CreatePlanRequest(PlanRules):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str | None = None
    offering_id: UUID | None = None
    price_amount: float = 0
    currency: str = "INR"
    billing_model: str = "fixed_duration"
    duration_days: int | None = None
    status: str = "draft"
    visibility: str = "private"
    offering_access: list[UUID] = Field(default_factory=list)


class PatchPlanRequest(VersionedBody, PlanRules):
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
    location_id: UUID | None = None
    payer_contact_id: UUID | None = None
    source_ref_type: str | None = None
    source_ref_id: UUID | None = None
    delivery: dict[str, Any] | None = None
    instalments: list[dict[str, Any]] | None = None
    channel: str | None = None


class EnrolmentTransitionRequest(VersionedBody):
    reason: str | None = None
    days: int | None = Field(default=None, ge=1, le=366)
    starts_on: date | None = None


class FreezeBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    starts_on: date
    days: int = Field(ge=1, le=366)
    reason: str | None = Field(default=None, max_length=200)


class SessionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: str = Field(min_length=6, max_length=120)
    note: str | None = Field(default=None, max_length=200)


class CheckinBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=6, max_length=64)


class DeliveryDayBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    on_date: date
    kind: Literal["skip", "quantity", "restore"]
    quantity: int | None = Field(default=None, ge=1, le=1000)


class DeliveryFutureBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quantity: int | None = Field(default=None, ge=1, le=1000)
    days: list[int] | None = None


class BillBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    month: date


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
    from platform_core.memberships.service import MembershipCore

    return {
        "data": {
            **MembershipResolver.serialize_enrolment(enrolment),
            "status_history": [
                MembershipResolver.serialize_status_event(e) for e in history
            ],
            # P2-02: periods, freezes, sessions, instalments, visits and the answers.
            "detail": await MembershipCore.detail(session, enrolment),
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
            days=body.days,
            starts_on=body.starts_on,
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


# ---------------------------------------------------------------------------
# P2-02: the relationship engine — board, renew, freezes, sessions, check-in,
# subscriptions. Every change goes through platform_core.memberships.
# ---------------------------------------------------------------------------
def _meta(actor: BusinessActorContext) -> dict[str, Any]:
    return {"correlation_id": actor.request.correlation_id}


@router.get("/{business_id}/membership-board")
async def membership_board(
    business_id: UUID,
    kind: str | None = Query(default=None),
    actor: BusinessActorContext = Depends(require_business_actor(MEMBERSHIPS_READ, _MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    from platform_core.memberships.board import board

    return {"data": await board(session, business_id, kind=kind), "meta": _meta(actor)}


@router.post("/{business_id}/membership-enrolments/{enrolment_id}/renew")
async def renew(
    business_id: UUID, enrolment_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(MEMBERSHIPS_MANAGE_ENROLMENT, _MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """The next period after the last (early renewal keeps every day already
    paid). Collect it like any money due: a payment link or money recorded."""
    from platform_core.memberships.service import MembershipCore

    enrolment = await MembershipCore.get(session, business_id, enrolment_id, lock=True)
    period = await MembershipCore.renew(session, enrolment, actor_id=actor.request.identity_id)
    detail = await MembershipCore.detail(session, enrolment)
    await session.commit()
    return {"data": {"period": MembershipCore.serialize_period(period), "membership": detail}, "meta": _meta(actor)}


@router.post("/{business_id}/membership-enrolments/{enrolment_id}/freezes")
async def add_freeze(
    business_id: UUID, enrolment_id: UUID, body: FreezeBody,
    actor: BusinessActorContext = Depends(require_business_actor(MEMBERSHIPS_MANAGE_ENROLMENT, _MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    from platform_core.memberships.service import MembershipCore

    enrolment = await MembershipCore.get(session, business_id, enrolment_id, lock=True)
    await MembershipCore.freeze(session, enrolment, starts_on=body.starts_on, days=body.days, reason=body.reason,
                                actor_id=actor.request.identity_id)
    detail = await MembershipCore.detail(session, enrolment)
    await session.commit()
    return {"data": detail, "meta": _meta(actor)}


@router.post("/{business_id}/membership-enrolments/{enrolment_id}/freezes/{freeze_id}/cancel")
async def cancel_freeze(
    business_id: UUID, enrolment_id: UUID, freeze_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(MEMBERSHIPS_MANAGE_ENROLMENT, _MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    from platform_core.memberships.service import MembershipCore

    enrolment = await MembershipCore.get(session, business_id, enrolment_id, lock=True)
    await MembershipCore.cancel_freeze(session, enrolment, freeze_id, actor_id=actor.request.identity_id)
    detail = await MembershipCore.detail(session, enrolment)
    await session.commit()
    return {"data": detail, "meta": _meta(actor)}


@router.post("/{business_id}/membership-enrolments/{enrolment_id}/sessions")
async def use_session(
    business_id: UUID, enrolment_id: UUID, body: SessionBody,
    actor: BusinessActorContext = Depends(require_business_actor(MEMBERSHIPS_MANAGE_ENROLMENT, _MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """A session used outside a booking (a walk-in PT session). Same key, same use."""
    from platform_core.memberships.service import MembershipCore

    enrolment = await MembershipCore.get(session, business_id, enrolment_id)
    await MembershipCore.consume_session(session, enrolment, source_type="manual", source_id=None,
                                         idempotency_key=f"manual:{body.idempotency_key}",
                                         actor_id=actor.request.identity_id)
    detail = await MembershipCore.detail(session, enrolment)
    await session.commit()
    return {"data": detail, "meta": _meta(actor)}


@router.post("/{business_id}/membership-checkin")
async def checkin_decision(
    business_id: UUID, body: CheckinBody,
    actor: BusinessActorContext = Depends(require_business_actor(MEMBERSHIPS_READ, _MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Front desk: scan or type the member's code → green, amber or red (§6).
    Recording the visit itself is Attendance's job."""
    from platform_core.memberships.service import MembershipCore

    enrolment = await MembershipCore.resolve_code(session, business_id, body.code)
    decision = await MembershipCore.checkin_decision(session, business_id, enrolment.id)
    await session.commit()
    return {"data": decision, "meta": _meta(actor)}


@router.get("/{business_id}/subscriptions/day")
async def subscription_day(
    business_id: UUID, on_date: date,
    actor: BusinessActorContext = Depends(require_business_actor(MEMBERSHIPS_READ, _MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    from platform_core.memberships.subscriptions import SubscriptionService

    return {"data": await SubscriptionService.board(session, business_id, on_date), "meta": _meta(actor)}


@router.post("/{business_id}/subscriptions/day/{on_date}/generate")
async def subscription_generate(
    business_id: UUID, on_date: date,
    actor: BusinessActorContext = Depends(require_business_actor(MEMBERSHIPS_MANAGE_ENROLMENT, _MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Finalise a day now (the sweep does it at the cutoff by itself). Once only."""
    from platform_core.memberships.subscriptions import SubscriptionService

    data = await SubscriptionService.generate_day(session, business_id, on_date, actor_id=actor.request.identity_id,
                                                  correlation_id=actor.request.correlation_id)
    await session.commit()
    return {"data": data, "meta": _meta(actor)}


@router.post("/{business_id}/membership-enrolments/{enrolment_id}/delivery-day")
async def delivery_day(
    business_id: UUID, enrolment_id: UUID, body: DeliveryDayBody,
    actor: BusinessActorContext = Depends(require_business_actor(MEMBERSHIPS_MANAGE_ENROLMENT, _MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    from platform_core.memberships.service import MembershipCore
    from platform_core.memberships.subscriptions import SubscriptionService

    enrolment = await MembershipCore.get(session, business_id, enrolment_id, lock=True)
    await SubscriptionService.change_day(session, enrolment, on_date=body.on_date, kind=body.kind,
                                         quantity=body.quantity, actor_id=actor.request.identity_id,
                                         channel="workspace")
    await session.commit()
    return {"data": await SubscriptionService.board(session, business_id, body.on_date), "meta": _meta(actor)}


@router.patch("/{business_id}/membership-enrolments/{enrolment_id}/delivery")
async def delivery_future(
    business_id: UUID, enrolment_id: UUID, body: DeliveryFutureBody,
    actor: BusinessActorContext = Depends(require_business_actor(MEMBERSHIPS_MANAGE_ENROLMENT, _MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    from platform_core.memberships.service import MembershipCore
    from platform_core.memberships.subscriptions import SubscriptionService

    enrolment = await MembershipCore.get(session, business_id, enrolment_id, lock=True)
    new = await SubscriptionService.change_future(session, enrolment, quantity=body.quantity, days=body.days,
                                                  actor_id=actor.request.identity_id)
    await session.commit()
    return {"data": new, "meta": _meta(actor)}


@router.post("/{business_id}/subscriptions/bill")
async def subscription_bill(
    business_id: UUID, body: BillBody,
    actor: BusinessActorContext = Depends(require_business_actor(MEMBERSHIPS_MANAGE_ENROLMENT, _MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Postpaid month-end bill onto the khata now (the sweep does it on the 1st). Once per month."""
    from platform_core.memberships.subscriptions import SubscriptionService

    data = await SubscriptionService.bill_postpaid(session, business_id, body.month,
                                                   actor_id=actor.request.identity_id)
    await session.commit()
    return {"data": data, "meta": _meta(actor)}


@router.get("/{business_id}/membership-enrolments/{enrolment_id}/qr")
async def member_qr(
    business_id: UUID, enrolment_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(MEMBERSHIPS_READ, _MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """The member's front-desk code as a QR (the same code can be typed)."""
    from platform_core.memberships.service import MembershipCore
    from platform_core.services.pos import PosService

    enrolment = await MembershipCore.get(session, business_id, enrolment_id)
    code = enrolment.checkin_code or str(enrolment.id)
    return {"data": {"code": code, "svg": PosService.qr_svg(code)}, "meta": _meta(actor)}
