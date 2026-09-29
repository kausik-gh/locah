"""Collect what is due (P1-10D; Founder refinement — Payments).

Owner side, under `/v1/platform/businesses/{id}/collect`: what is due on a
transaction, payment links, confirming UPI that arrived, recording money taken,
and the overview of paid today / waiting / needs attention / owed / refunds.
Public side, under `/v1/public/websites/{slug}/pay/{token}`: the customer's
payment page. The customer's "I have paid" is a claim the business confirms;
it never marks anything paid by itself.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from platform_api.db import get_db_session
from platform_api.dependencies import BusinessActorContext, require_business_actor
from platform_core.models import Business, CustomerContact
from platform_core.exceptions import PermissionDenied
from platform_core.permissions import MESSAGING_REPLY, PAYMENTS_COLLECT, PAYMENTS_READ
from platform_core.services.payment_collect import PURPOSES, PaymentCollectService, share_text, wa_share
from platform_core.site_urls import business_site_url

router = APIRouter(prefix="/v1/platform/businesses", tags=["payments-collect"])
public_router = APIRouter(prefix="/v1/public/websites", tags=["payments-collect"])

SourceType = Literal["order", "booking", "membership", "invoice", "khata"]


def _meta(actor: BusinessActorContext) -> dict[str, Any]:
    return {"correlation_id": actor.request.correlation_id}


class RequestBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: SourceType
    source_id: UUID
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    purpose: Literal["full", "advance", "deposit", "balance", "dues"]
    note: str | None = Field(default=None, max_length=200)


class ConfirmBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    arrived: bool


class RecordBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: Literal["order", "booking", "membership"]
    source_id: UUID
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    method: Literal["cash", "upi", "card", "bank_transfer"]
    reference: str | None = Field(default=None, max_length=120)
    purpose: Literal["full", "advance", "deposit", "balance"] | None = None


class PaidBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # The UPI reference (UTR) from the customer's app, if they have it.
    reference: str | None = Field(default=None, max_length=120)


def _today() -> Any:
    return (datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)).date()


@router.get("/{business_id}/collect/overview")
async def overview(
    business_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(PAYMENTS_READ)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await PaymentCollectService.overview(session, business_id, today=_today())
    return {"data": data, "meta": _meta(actor)}


@router.get("/{business_id}/collect/due")
async def due(
    business_id: UUID, source_type: SourceType, source_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(PAYMENTS_READ)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    money = await PaymentCollectService.money(session, business_id, source_type, source_id)
    links = await PaymentCollectService.requests_for(session, business_id, source_type, source_id)
    return {"data": money | {"links": links}, "meta": _meta(actor)}


@router.post("/{business_id}/collect/requests")
async def create_request(
    business_id: UUID, body: RequestBody,
    actor: BusinessActorContext = Depends(require_business_actor(PAYMENTS_COLLECT)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    req, token = await PaymentCollectService.create_request(
        session, business_id, actor.request.identity_id, source_type=body.source_type, source_id=body.source_id,
        amount=body.amount, purpose=body.purpose, note=body.note, correlation_id=actor.request.correlation_id)
    business = await session.get(Business, business_id)
    assert business is not None
    contact = await session.get(CustomerContact, req.customer_contact_id) if req.customer_contact_id else None
    money = await PaymentCollectService.money(session, business_id, body.source_type, body.source_id)
    url = business_site_url(business.slug, f"/pay/{token}")
    what = f"{money['label']} ({PURPOSES[body.purpose].lower()})"
    message = share_text(business.display_name, what, Decimal(str(req.amount)), url)
    from platform_core.services.messaging import MessagingService

    channel = await MessagingService.channel(session, business_id)
    await session.commit()
    # The token is shown here once; only its hash is stored.
    return {"data": PaymentCollectService._request_row(req) | {
        "url": url, "path": f"/{business.slug}/pay/{token}", "message": message,
        "whatsapp": wa_share(contact.phone if contact else None, message),
        "customer_phone": contact.phone if contact else None,
        # the business's own number can send it (Payments §7), when connected
        "from_number": bool(channel is not None and channel.status == "connected" and contact and contact.phone
                            and MESSAGING_REPLY in actor.request.effective_permissions),
    }, "meta": _meta(actor)}


class SendBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # The link's token, which only the person who made it holds (its hash is stored).
    token: str = Field(min_length=16, max_length=64)


@router.post("/{business_id}/collect/requests/{request_id}/whatsapp")
async def send_request(
    business_id: UUID, request_id: UUID, body: SendBody,
    actor: BusinessActorContext = Depends(require_business_actor(PAYMENTS_COLLECT)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """The payment link to the customer from the business's WhatsApp number."""
    if MESSAGING_REPLY not in actor.request.effective_permissions:
        raise PermissionDenied(MESSAGING_REPLY)
    msg = await PaymentCollectService.send_on_whatsapp(session, business_id, actor.request.identity_id, request_id,
                                                       body.token)
    await session.commit()
    return {"data": {"status": msg.status, "body": msg.body}, "meta": _meta(actor)}


@router.post("/{business_id}/collect/requests/{request_id}/cancel")
async def cancel_request(
    business_id: UUID, request_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(PAYMENTS_COLLECT)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    req = await PaymentCollectService.cancel_request(session, business_id, actor.request.identity_id, request_id)
    await session.commit()
    return {"data": PaymentCollectService._request_row(req), "meta": _meta(actor)}


@router.post("/{business_id}/collect/payments/{payment_id}/confirm")
async def confirm(
    business_id: UUID, payment_id: UUID, body: ConfirmBody,
    actor: BusinessActorContext = Depends(require_business_actor(PAYMENTS_COLLECT)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    attempt = await PaymentCollectService.confirm(session, business_id, actor.request.identity_id, payment_id,
                                                  arrived=body.arrived, correlation_id=actor.request.correlation_id)
    money = await PaymentCollectService.money(session, business_id, attempt.source_type, attempt.source_id)
    await session.commit()
    return {"data": {"payment": PaymentCollectService._attempt_row(attempt), "due": money}, "meta": _meta(actor)}


@router.post("/{business_id}/collect/record")
async def record(
    business_id: UUID, body: RecordBody,
    actor: BusinessActorContext = Depends(require_business_actor(PAYMENTS_COLLECT)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    attempt = await PaymentCollectService.record(
        session, business_id, actor.request.identity_id, source_type=body.source_type, source_id=body.source_id,
        amount=body.amount, method=body.method, reference=body.reference, purpose=body.purpose,
        correlation_id=actor.request.correlation_id)
    money = await PaymentCollectService.money(session, business_id, body.source_type, body.source_id)
    await session.commit()
    return {"data": {"payment": PaymentCollectService._attempt_row(attempt), "due": money}, "meta": _meta(actor)}


# ---------------------------------------------------------------- the customer's payment page
@public_router.get("/{slug}/pay/{token}")
async def pay_view(slug: str, token: str, session: AsyncSession = Depends(get_db_session)) -> dict[str, Any]:
    return {"data": await PaymentCollectService.public_view(session, slug, token)}


@public_router.post("/{slug}/pay/{token}/paid")
async def pay_claimed(slug: str, token: str, body: PaidBody,
                      session: AsyncSession = Depends(get_db_session)) -> dict[str, Any]:
    import uuid

    data = await PaymentCollectService.customer_paid(session, slug, token, reference=body.reference,
                                                     correlation_id=str(uuid.uuid4()))
    await session.commit()
    return {"data": data}


@public_router.post("/{slug}/pay/{token}/not-paid")
async def pay_withdrawn(slug: str, token: str, session: AsyncSession = Depends(get_db_session)) -> dict[str, Any]:
    data = await PaymentCollectService.customer_not_paid(session, slug, token)
    await session.commit()
    return {"data": data}


@public_router.get("/{slug}/pay/{token}/upi-qr.svg")
async def pay_qr(slug: str, token: str, session: AsyncSession = Depends(get_db_session)) -> Any:
    """The link's UPI payment as a QR, for a customer who opened it on a computer."""
    from fastapi import Response

    from platform_core.exceptions import ResourceNotFound
    from platform_core.services.pos import PosService

    view = await PaymentCollectService.public_view(session, slug, token)
    upi = next((m for m in view["methods"] if m["method"] == "upi_direct"), None)
    if upi is None:
        raise ResourceNotFound("UPI QR")
    return Response(content=PosService.qr_svg(str(upi["upi_link"])), media_type="image/svg+xml",
                    headers={"Cache-Control": "private, no-store"})
