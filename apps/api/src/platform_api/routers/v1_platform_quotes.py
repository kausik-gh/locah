"""Quotation APIs for the business side.

Permissions reuse the quotes module's own set rather than borrowing another
module's, because issuing a priced commitment is a distinct authority from
editing the catalogue it draws on.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from platform_api.db import get_db_session
from platform_api.dependencies import BusinessActorContext, require_business_actor
from platform_core.exceptions import ValidationError
from platform_core.permissions import (
    QUOTES_APPROVE,
    QUOTES_CREATE,
    QUOTES_ISSUE,
    QUOTES_READ,
    QUOTES_UPDATE,
)
from platform_core.services.quote import QuoteService

router = APIRouter(prefix="/v1/platform/businesses", tags=["quotes"])


class QuoteItemInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    offering_id: UUID | None = None
    title: str | None = None
    description: str | None = None
    unit_label: str | None = None
    quantity: float = Field(default=1, gt=0)
    unit_price: float | None = Field(default=None, ge=0)
    tax_rate: float = Field(default=0, ge=0, le=100)
    discount_type: str | None = None
    discount_value: float | None = Field(default=None, ge=0)
    line_kind: str | None = None
    moq: float | None = Field(default=None, gt=0)
    lead_time_days: int | None = Field(default=None, ge=0)
    quantity_breaks: list[dict[str, Any]] | None = None
    boq_section: str | None = None
    size_matrix: list[dict[str, Any]] | None = None
    metadata: dict[str, Any] | None = None


class PaymentPlanInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    amount_type: str = "amount"
    amount_value: float = Field(ge=0)
    due_rule: str = "on_acceptance"
    due_days: int | None = Field(default=None, ge=0)


class QuoteChargeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    amount: float = Field(ge=0)
    taxable: bool = False
    tax_rate: float = Field(default=0, ge=0, le=100)


class CreateQuoteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_contact_id: UUID | None = None
    location_id: UUID | None = None
    title: str | None = None
    terms: str | None = None
    notes: str | None = None
    internal_notes: str | None = None
    currency: str = "INR"
    discount_type: str | None = None
    discount_value: float | None = Field(default=None, ge=0)
    deposit_type: str | None = None
    deposit_value: float | None = Field(default=None, ge=0)
    valid_until: str | None = None
    items: list[QuoteItemInput] = Field(default_factory=list, max_length=200)
    charges: list[QuoteChargeInput] = Field(default_factory=list, max_length=50)
    payment_plan: list[PaymentPlanInput] = Field(default_factory=list, max_length=24)
    idempotency_key: str | None = None


class UpdateQuoteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int | None = Field(default=None, ge=1)
    customer_contact_id: UUID | None = None
    title: str | None = None
    terms: str | None = None
    notes: str | None = None
    internal_notes: str | None = None
    discount_type: str | None = None
    discount_value: float | None = Field(default=None, ge=0)
    deposit_type: str | None = None
    deposit_value: float | None = Field(default=None, ge=0)
    valid_until: str | None = None
    items: list[QuoteItemInput] | None = Field(default=None, max_length=200)
    charges: list[QuoteChargeInput] | None = Field(default=None, max_length=50)
    payment_plan: list[PaymentPlanInput] | None = Field(default=None, max_length=24)


class IssueQuoteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    valid_days: int | None = Field(default=None, ge=1, le=365)


class DecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: str
    reason: str | None = None
    decided_by_name: str | None = None


class CancelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str | None = None


def _meta(actor: BusinessActorContext, **extra: Any) -> dict[str, Any]:
    return {"correlation_id": actor.request.correlation_id, **extra}


@router.get("/{business_id}/quotes")
async def list_quotes(
    business_id: UUID,
    status: str | None = Query(default=None),
    customer_contact_id: UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    actor: BusinessActorContext = Depends(require_business_actor(QUOTES_READ, "quotes")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    quotes = await QuoteService.list_quotes(
        session,
        business_id=business_id,
        status=status,
        customer_contact_id=customer_contact_id,
        limit=limit,
        offset=offset,
    )
    return {"data": {"quotes": quotes}, "meta": _meta(actor, count=len(quotes))}


@router.post("/{business_id}/quotes")
async def create_quote(
    business_id: UUID,
    body: CreateQuoteRequest,
    actor: BusinessActorContext = Depends(require_business_actor(QUOTES_CREATE, "quotes")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    quote = await QuoteService.create(
        session,
        business_id=business_id,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
        payload=body.model_dump(mode="json"),
    )
    await session.commit()
    detail = await QuoteService.get_detail(
        session, business_id=business_id, quote_id=quote.id
    )
    return {"data": detail, "meta": _meta(actor)}


@router.get("/{business_id}/quotes/{quote_id}")
async def get_quote(
    business_id: UUID,
    quote_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(QUOTES_READ, "quotes")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    detail = await QuoteService.get_detail(
        session, business_id=business_id, quote_id=quote_id
    )
    return {"data": detail, "meta": _meta(actor)}


@router.patch("/{business_id}/quotes/{quote_id}")
async def update_quote(
    business_id: UUID,
    quote_id: UUID,
    body: UpdateQuoteRequest,
    actor: BusinessActorContext = Depends(require_business_actor(QUOTES_UPDATE, "quotes")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    payload = body.model_dump(mode="json", exclude_unset=True)
    expected_version = payload.pop("version", None)
    await QuoteService.update_draft(
        session,
        business_id=business_id,
        quote_id=quote_id,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
        payload=payload,
        expected_version=expected_version,
    )
    await session.commit()
    detail = await QuoteService.get_detail(
        session, business_id=business_id, quote_id=quote_id
    )
    return {"data": detail, "meta": _meta(actor)}


@router.post("/{business_id}/quotes/{quote_id}/issue")
async def issue_quote(
    business_id: UUID,
    quote_id: UUID,
    body: IssueQuoteRequest,
    actor: BusinessActorContext = Depends(require_business_actor(QUOTES_ISSUE, "quotes")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    try:
        quote = await QuoteService.issue(
            session,
            business_id=business_id,
            quote_id=quote_id,
            actor_id=actor.request.identity_id,
            correlation_id=actor.request.correlation_id,
            valid_days=body.valid_days,
            permissions=frozenset(actor.request.effective_permissions),
        )
    except ValidationError as exc:
        # The refusal is the outcome: the quote stays a draft, but it is now
        # waiting on the owner. That mark has to survive the error response.
        details = exc.detail.get("details") if isinstance(exc.detail, dict) else {}
        if (details or {}).get("code") == "discount_approval_required":
            await session.commit()
        raise
    await session.commit()
    detail = await QuoteService.get_detail(
        session, business_id=business_id, quote_id=quote_id
    )
    # The share credential is returned once, to the staff member who issued it,
    # so they can send it on. It is not part of the normal quote payload.
    detail["share_token"] = quote.access_token
    return {"data": detail, "meta": _meta(actor)}


@router.post("/{business_id}/quotes/{quote_id}/decision")
async def record_decision(
    business_id: UUID,
    quote_id: UUID,
    body: DecisionRequest,
    actor: BusinessActorContext = Depends(require_business_actor(QUOTES_ISSUE, "quotes")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Record a decision the customer gave offline — on a call, or in person."""
    await QuoteService.decide(
        session,
        business_id=business_id,
        quote_id=quote_id,
        decision=body.decision,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
        reason=body.reason,
        decided_by_name=body.decided_by_name,
    )
    await session.commit()
    detail = await QuoteService.get_detail(
        session, business_id=business_id, quote_id=quote_id
    )
    return {"data": detail, "meta": _meta(actor)}


@router.post("/{business_id}/quotes/{quote_id}/cancel")
async def cancel_quote(
    business_id: UUID,
    quote_id: UUID,
    body: CancelRequest,
    actor: BusinessActorContext = Depends(require_business_actor(QUOTES_ISSUE, "quotes")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    await QuoteService.cancel(
        session,
        business_id=business_id,
        quote_id=quote_id,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
        reason=body.reason,
    )
    await session.commit()
    detail = await QuoteService.get_detail(
        session, business_id=business_id, quote_id=quote_id
    )
    return {"data": detail, "meta": _meta(actor)}


@router.post("/{business_id}/quotes/{quote_id}/revise")
async def revise_quote(
    business_id: UUID,
    quote_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(QUOTES_UPDATE, "quotes")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    revision = await QuoteService.revise(
        session,
        business_id=business_id,
        quote_id=quote_id,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
    )
    await session.commit()
    detail = await QuoteService.get_detail(
        session, business_id=business_id, quote_id=revision.id
    )
    return {"data": detail, "meta": _meta(actor)}


@router.get("/{business_id}/quotes/{quote_id}/share-link")
async def get_share_link(
    business_id: UUID,
    quote_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(QUOTES_ISSUE, "quotes")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Recover the share credential for a quote that is already issued.

    `issue` returns the token once, which is right for a credential but wrong as
    the only time it can ever be seen: an owner who closed the tab, or who is
    sending the quote again a week later, had no way back to the link their
    customer needs. It stays out of the ordinary quote payload — every list and
    detail read would otherwise carry a live credential — and is fetched
    deliberately, by someone holding the same authority that issued it.
    """
    quote = await QuoteService.resolve(session, business_id=business_id, quote_id=quote_id)
    return {
        "data": {
            "token": quote.access_token,
            "expires_at": (
                quote.access_token_expires_at.isoformat()
                if quote.access_token_expires_at
                else None
            ),
            "status": QuoteService.effective_status(quote),
        },
        "meta": _meta(actor),
    }


class RfqCustomer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    phone: str | None = None
    email: str | None = None


class RfqIntakeRequest(BaseModel):
    """WhatsApp (or a replay of the website form) asks for a draft quote.

    `idempotency_key` is the message id or the lead id. Sending it twice
    returns the same draft.
    """

    model_config = ConfigDict(extra="forbid")

    channel: str
    idempotency_key: str
    customer: RfqCustomer
    brief: str | None = None
    lines: list[QuoteItemInput] = Field(default_factory=list, max_length=200)
    source_ref: str | None = None


class DiscountDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: str


class DiscountLimitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    executive_discount_limit_percent: float = Field(ge=0, le=100)


class ConversionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target: str


@router.post("/{business_id}/quotes/intake")
async def intake_rfq(
    business_id: UUID,
    body: RfqIntakeRequest,
    actor: BusinessActorContext = Depends(require_business_actor(QUOTES_CREATE, "quotes")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """The WhatsApp contract, and a staff replay of a website request.

    Messaging calls this with the inbound message id. It does not place an
    order and it does not price the lines.
    """
    quote = await QuoteService.intake_rfq(
        session,
        business_id=business_id,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
        channel=body.channel,
        idempotency_key=body.idempotency_key,
        customer_name=body.customer.name,
        phone=body.customer.phone,
        email=body.customer.email,
        brief=body.brief,
        lines=[line.model_dump(mode="json") for line in body.lines],
        source_ref=body.source_ref,
    )
    await session.commit()
    detail = await QuoteService.get_detail(session, business_id=business_id, quote_id=quote.id)
    return {"data": detail, "meta": _meta(actor)}


@router.post("/{business_id}/quotes/{quote_id}/discount-approval")
async def decide_discount(
    business_id: UUID,
    quote_id: UUID,
    body: DiscountDecisionRequest,
    actor: BusinessActorContext = Depends(require_business_actor(QUOTES_APPROVE, "quotes")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    await QuoteService.decide_discount(
        session,
        business_id=business_id,
        quote_id=quote_id,
        decision=body.decision,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
    )
    await session.commit()
    detail = await QuoteService.get_detail(session, business_id=business_id, quote_id=quote_id)
    return {"data": detail, "meta": _meta(actor)}


@router.put("/{business_id}/quotes/settings")
async def set_discount_limit(
    business_id: UUID,
    body: DiscountLimitRequest,
    actor: BusinessActorContext = Depends(require_business_actor(QUOTES_APPROVE, "quotes")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    from decimal import Decimal

    percent = await QuoteService.set_discount_limit(
        session,
        business_id=business_id,
        percent=Decimal(str(body.executive_discount_limit_percent)),
    )
    await session.commit()
    return {
        "data": {"executive_discount_limit_percent": str(percent)},
        "meta": _meta(actor),
    }


@router.post("/{business_id}/quotes/{quote_id}/conversion")
async def request_conversion(
    business_id: UUID,
    quote_id: UUID,
    body: ConversionRequest,
    actor: BusinessActorContext = Depends(require_business_actor(QUOTES_ISSUE, "quotes")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Hand the locked quote to Orders, Projects or Invoicing.

    The response is the contract. No order, project or invoice is created.
    """
    contract = await QuoteService.request_conversion(
        session,
        business_id=business_id,
        quote_id=quote_id,
        target=body.target,
        actor_id=actor.request.identity_id,
        correlation_id=actor.request.correlation_id,
    )
    await session.commit()
    return {"data": contract, "meta": _meta(actor)}
