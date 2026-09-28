"""Khata / credit book (Capability Universe §6.2 `ledger`, §14.5).

Who owes the business and whom it owes: one account per customer or supplier,
append-only entries, limits, ageing, statements. Credit is given by billing on
the customer's account (a Workspace bill or the counter's khata tender);
these routes are the book itself.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_api.db import get_db_session
from platform_api.dependencies import BusinessActorContext, require_business_actor
from platform_core.exceptions import PermissionDenied, ValidationError
from platform_core.models import Business, InvoicingRegistration
from platform_core.permissions import LEDGER_MANAGE, LEDGER_READ, LEDGER_RECORD
from platform_core.services.invoicing_setup import local_today
from platform_core.services.ledger import KIND_LABEL, METHODS, LedgerService

router = APIRouter(prefix="/v1/platform/businesses", tags=["ledger"])
public_router = APIRouter(prefix="/v1/public", tags=["ledger"])
MODULE = "ledger"


def _meta(actor: BusinessActorContext, **extra: Any) -> dict[str, Any]:
    return {"correlation_id": actor.request.correlation_id, **extra}


def _past(d: date | None, field: str) -> date | None:
    if d is not None and d > local_today():
        raise ValidationError("The date cannot be in the future",
                              details={"errors": [{"field": field, "message": "The date cannot be in the future"}]})
    return d


class OpenBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    party_type: Literal["customer", "supplier"]
    customer_contact_id: UUID | None = None
    display_name: str | None = Field(default=None, max_length=160)
    phone: str | None = Field(default=None, max_length=20)
    gstin: str | None = Field(default=None, max_length=15)
    credit_limit: float | None = Field(default=None, ge=0)
    credit_days: int | None = Field(default=None, ge=0, le=365)
    opening_balance: float | None = None
    notes: str | None = Field(default=None, max_length=500)


class UpdateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    credit_limit: float | None = Field(default=None, ge=0)
    credit_days: int | None = Field(default=None, ge=0, le=365)
    notes: str | None = Field(default=None, max_length=500)
    gstin: str | None = Field(default=None, max_length=15)
    status: Literal["active", "closed"] | None = None


class PaymentBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: float = Field(gt=0)
    method: Literal["cash", "upi", "card", "bank_transfer", "cheque", "other"]
    reference: str | None = Field(default=None, max_length=120)
    entry_date: date | None = None
    idempotency_key: str | None = Field(default=None, max_length=120)


class EntryBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["purchase", "adjustment", "opening_balance"]
    amount: float
    entry_date: date | None = None
    due_date: date | None = None
    reference: str | None = Field(default=None, max_length=120)
    note: str | None = Field(default=None, max_length=300)
    idempotency_key: str | None = Field(default=None, max_length=120)


@router.get("/{business_id}/ledger/accounts")
async def list_accounts(
    business_id: UUID,
    party: Literal["customer", "supplier"] | None = Query(default=None),
    q: str | None = Query(default=None, max_length=100),
    due: bool = Query(default=False),
    actor: BusinessActorContext = Depends(require_business_actor(LEDGER_READ, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await LedgerService.list_accounts(session, business_id, party_type=party, q=q, due_only=due)
    return {"data": data, "meta": _meta(actor, methods=METHODS)}


@router.post("/{business_id}/ledger/accounts")
async def open_account(
    business_id: UUID, body: OpenBody,
    actor: BusinessActorContext = Depends(require_business_actor(LEDGER_MANAGE, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    acct = await LedgerService.open(session, business_id, actor.request.identity_id,
                                    body.model_dump(mode="json", exclude_unset=True))
    await session.commit()
    return {"data": await LedgerService.detail(session, business_id, acct.id), "meta": _meta(actor)}


@router.get("/{business_id}/ledger/lookup")
async def lookup(
    business_id: UUID,
    phone: str | None = Query(default=None, max_length=20),
    contact_id: UUID | None = Query(default=None),
    actor: BusinessActorContext = Depends(require_business_actor(LEDGER_READ, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """The counter checks a customer's khata before giving credit."""
    if contact_id is not None:
        acct = await LedgerService.for_customer(session, business_id, contact_id, actor.request.identity_id,
                                                create=False)
        return {"data": {"customer_contact_id": str(contact_id),
                         "account": LedgerService.serialize(acct) if acct else None}, "meta": _meta(actor)}
    return {"data": await LedgerService.lookup(session, business_id, phone or ""), "meta": _meta(actor)}


@router.get("/{business_id}/ledger/accounts/{account_id}")
async def get_account(
    business_id: UUID, account_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(LEDGER_READ, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    return {"data": await LedgerService.detail(session, business_id, account_id), "meta": _meta(actor)}


@router.patch("/{business_id}/ledger/accounts/{account_id}")
async def update_account(
    business_id: UUID, account_id: UUID, body: UpdateBody,
    actor: BusinessActorContext = Depends(require_business_actor(LEDGER_MANAGE, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    await LedgerService.update(session, business_id, actor.request.identity_id, account_id,
                               body.model_dump(mode="json", exclude_unset=True))
    await session.commit()
    return {"data": await LedgerService.detail(session, business_id, account_id), "meta": _meta(actor)}


@router.post("/{business_id}/ledger/accounts/{account_id}/payments")
async def record_payment(
    business_id: UUID, account_id: UUID, body: PaymentBody,
    actor: BusinessActorContext = Depends(require_business_actor(LEDGER_RECORD, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Money received from a customer (applied to their oldest bills) or paid to a supplier."""
    entry, applied = await LedgerService.receive(
        session, business_id, account_id, actor.request.identity_id, amount=body.amount, method=body.method,
        reference=body.reference, entry_date=_past(body.entry_date, "entry_date"),
        idempotency_key=body.idempotency_key)
    await session.commit()
    return {"data": await LedgerService.detail(session, business_id, account_id),
            "meta": _meta(actor, entry_id=str(entry.id), applied=applied)}


@router.post("/{business_id}/ledger/accounts/{account_id}/entries")
async def post_entry(
    business_id: UUID, account_id: UUID, body: EntryBody,
    actor: BusinessActorContext = Depends(require_business_actor(LEDGER_RECORD, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """A supplier's bill on credit; corrections and opening balances need ledger.manage."""
    if body.kind != "purchase" and LEDGER_MANAGE not in actor.request.effective_permissions:
        raise PermissionDenied(LEDGER_MANAGE)
    if body.kind in ("adjustment", "opening_balance") and not (body.note or "").strip():
        raise ValidationError("Say what this correction is for",
                              details={"errors": [{"field": "note", "message": "Say what this is for"}]})
    await LedgerService.post(
        session, business_id, account_id, kind=body.kind, amount=body.amount, actor_id=actor.request.identity_id,
        entry_date=_past(body.entry_date, "entry_date"), due_date=body.due_date, reference=body.reference,
        note=body.note, idempotency_key=body.idempotency_key)
    await session.commit()
    return {"data": await LedgerService.detail(session, business_id, account_id), "meta": _meta(actor)}


async def _statement(session: AsyncSession, business_id: UUID, account_id: UUID, start: date | None,
                     end: date | None) -> dict[str, Any]:
    if start and end and start > end:
        raise ValidationError("The start date is after the end date",
                              details={"errors": [{"field": "from", "message": "Pick a start before the end"}]})
    data: dict[str, Any] = await LedgerService.statement(session, business_id, account_id, start, end)
    return data


@router.get("/{business_id}/ledger/accounts/{account_id}/statement")
async def statement(
    business_id: UUID, account_id: UUID,
    date_from: date | None = Query(default=None, alias="from"),
    date_to: date | None = Query(default=None, alias="to"),
    actor: BusinessActorContext = Depends(require_business_actor(LEDGER_READ, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await _statement(session, business_id, account_id, date_from, date_to)
    return {"data": data, "meta": _meta(actor, kinds=KIND_LABEL)}


@router.get("/{business_id}/ledger/accounts/{account_id}/statement.pdf")
async def statement_pdf(
    business_id: UUID, account_id: UUID,
    date_from: date | None = Query(default=None, alias="from"),
    date_to: date | None = Query(default=None, alias="to"),
    actor: BusinessActorContext = Depends(require_business_actor(LEDGER_READ, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    from platform_core.documents.renderer import render_pdf

    data = await _statement(session, business_id, account_id, date_from, date_to)
    business = await session.get(Business, business_id)
    gstin = (await session.execute(select(InvoicingRegistration.gstin).where(
        InvoicingRegistration.business_id == business_id, InvoicingRegistration.gstin.is_not(None))
        .limit(1))).scalar()
    content = render_pdf(LedgerService.statement_spec(
        data, {"name": business.display_name if business else "", "gstin": gstin}), "a4")
    name = f"statement-{data['account']['display_name']}-{data['to']}".replace("/", "-").replace(" ", "_")
    return Response(content=content, media_type="application/pdf", headers={
        "Content-Disposition": f'inline; filename="{name}.pdf"', "Cache-Control": "private, no-store"})


@router.post("/{business_id}/ledger/accounts/{account_id}/share")
async def share(
    business_id: UUID, account_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(LEDGER_RECORD, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await LedgerService.share(session, business_id, account_id)
    await session.commit()
    return {"data": data, "meta": _meta(actor)}


@public_router.get("/websites/{slug}/khata/{token}")
async def public_statement(slug: str, token: str, session: AsyncSession = Depends(get_db_session)) -> dict[str, Any]:
    """The customer's own khata: what they owe, the last entries, a UPI link to pay."""
    return {"data": await LedgerService.public_statement(session, slug, token)}


@public_router.get("/websites/{slug}/khata/{token}/upi-qr.svg")
async def public_statement_qr(slug: str, token: str, session: AsyncSession = Depends(get_db_session)) -> Response:
    """The same UPI link as a QR, for a customer who opened the statement on a computer."""
    from platform_core.exceptions import ResourceNotFound
    from platform_core.services.pos import PosService

    data = await LedgerService.public_statement(session, slug, token)
    if not data.get("upi_uri"):
        raise ResourceNotFound("UPI QR")
    return Response(content=PosService.qr_svg(str(data["upi_uri"])), media_type="image/svg+xml",
                    headers={"Cache-Control": "private, no-store"})
