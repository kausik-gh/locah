"""Invoices & GST (Capability Universe §14): setup, rates, bills, notes,
money received, PDFs, the customer's bill link and the CA's reports.

Issuing a numbered tax document, cancelling one, recording money against it,
exporting for the CA and setting up tax are separate permissions; every route
also needs the invoicing module switched on.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from platform_api.db import get_db_session
from platform_api.dependencies import BusinessActorContext, assert_module_operational, require_business_actor
from platform_core.exceptions import PermissionDenied, ResourceNotFound, ValidationError
from platform_core.invoicing.states import STATES
from platform_core.permissions import (
    INVOICES_CANCEL,
    INVOICES_CONFIGURE,
    INVOICES_EXPORT,
    INVOICES_ISSUE,
    INVOICES_READ,
    INVOICES_RECORD_PAYMENT,
    LEDGER_MANAGE,
    LEDGER_RECORD,
)
from platform_core.services import invoicing_reports as reports
from platform_core.services.invoicing import (
    KIND_LABEL,
    NOTE_REASONS,
    PAYMENT_METHODS,
    InvoiceService,
    build_spec,
    public_bill,
)
from platform_core.services.invoicing_setup import (
    InvoicingSetupService,
    TaxRateService,
    local_today,
    serialize_profile,
    serialize_register,
    serialize_registration,
    serialize_rate,
)

router = APIRouter(prefix="/v1/platform/businesses", tags=["invoicing"])
public_router = APIRouter(prefix="/v1/public", tags=["invoicing"])
MODULE = "invoicing"


def _meta(actor: BusinessActorContext, **extra: Any) -> dict[str, Any]:
    return {"correlation_id": actor.request.correlation_id, **extra}


# ------------------------------------------------------------------ setup
class ProfileBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prices_include_tax: bool
    round_off: bool
    issue_on: Literal["order_accepted", "order_completed", "manual"]
    advances_treatment: Literal["receipt_voucher", "on_bill"] | None = None
    default_due_days: int | None = Field(default=None, ge=0, le=365)
    terms: str | None = Field(default=None, max_length=2000)
    bank_details: str | None = Field(default=None, max_length=1000)
    ca_confirmed: bool | None = None


class RegistrationBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scheme: Literal["regular", "composition", "unregistered"]
    gstin: str | None = Field(default=None, max_length=20)
    legal_name: str = Field(max_length=200)
    trade_name: str | None = Field(default=None, max_length=200)
    state_code: str | None = Field(default=None, max_length=2)
    address: str | None = Field(default=None, max_length=500)
    composition_declaration: str | None = Field(default=None, max_length=300)


class RegisterBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location_id: UUID
    registration_id: UUID
    code: str = Field(max_length=8)
    name: str | None = Field(default=None, max_length=80)
    pad: int = Field(default=5, ge=3, le=8)
    status: Literal["active", "inactive"] | None = None


class RateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hsn_sac: str | None = Field(default=None, max_length=8)
    offering_id: UUID | None = None
    rate: float = Field(ge=0, le=100)
    effective_from: date
    note: str | None = Field(default=None, max_length=300)


@router.get("/{business_id}/invoicing/setup")
async def get_setup(
    business_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(INVOICES_READ, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await InvoicingSetupService.overview(session, business_id)
    return {"data": data, "meta": _meta(actor)}


@router.put("/{business_id}/invoicing/profile")
async def put_profile(
    business_id: UUID, body: ProfileBody,
    actor: BusinessActorContext = Depends(require_business_actor(INVOICES_CONFIGURE, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    profile = await InvoicingSetupService.save_profile(session, business_id, actor.request.identity_id,
                                                       body.model_dump())
    await session.commit()
    return {"data": serialize_profile(profile), "meta": _meta(actor)}


@router.post("/{business_id}/invoicing/registrations")
async def add_registration(
    business_id: UUID, body: RegistrationBody,
    actor: BusinessActorContext = Depends(require_business_actor(INVOICES_CONFIGURE, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    reg = await InvoicingSetupService.save_registration(session, business_id, actor.request.identity_id,
                                                        body.model_dump())
    await session.commit()
    return {"data": serialize_registration(reg), "meta": _meta(actor)}


@router.patch("/{business_id}/invoicing/registrations/{registration_id}")
async def update_registration(
    business_id: UUID, registration_id: UUID, body: RegistrationBody,
    actor: BusinessActorContext = Depends(require_business_actor(INVOICES_CONFIGURE, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    reg = await InvoicingSetupService.save_registration(session, business_id, actor.request.identity_id,
                                                        body.model_dump(), registration_id)
    await session.commit()
    return {"data": serialize_registration(reg), "meta": _meta(actor)}


@router.post("/{business_id}/invoicing/registers")
async def add_register(
    business_id: UUID, body: RegisterBody,
    actor: BusinessActorContext = Depends(require_business_actor(INVOICES_CONFIGURE, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    reg = await InvoicingSetupService.save_register(session, business_id, actor.request.identity_id,
                                                    body.model_dump(mode="json"))
    await session.commit()
    return {"data": serialize_register(reg), "meta": _meta(actor)}


@router.patch("/{business_id}/invoicing/registers/{register_id}")
async def update_register(
    business_id: UUID, register_id: UUID, body: RegisterBody,
    actor: BusinessActorContext = Depends(require_business_actor(INVOICES_CONFIGURE, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    reg = await InvoicingSetupService.save_register(session, business_id, actor.request.identity_id,
                                                    body.model_dump(mode="json"), register_id)
    await session.commit()
    return {"data": serialize_register(reg), "meta": _meta(actor)}


@router.get("/{business_id}/invoicing/tax-rates")
async def list_rates(
    business_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(INVOICES_READ, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    from sqlalchemy import select

    from platform_core.models import Offering

    rates = await TaxRateService.list_rates(session, business_id)
    today = local_today()
    offerings = list((await session.execute(select(Offering).where(
        Offering.business_id == business_id, Offering.deleted_at.is_(None), Offering.status != "archived",
    ).order_by(Offering.title))).scalars())
    resolved = await TaxRateService.resolve(session, business_id,
                                            [(o.id, o.hsn_sac, o.tax_rate) for o in offerings], today)
    items = [{"id": str(o.id), "title": o.title, "hsn_sac": o.hsn_sac, "status": o.status,
              "typed_rate": float(o.tax_rate) if o.tax_rate is not None else None,
              "rate_today": float(r) if r is not None else None} for o, r in zip(offerings, resolved)]
    return {"data": {"rates": rates, "items": items, "today": today.isoformat()}, "meta": _meta(actor)}


@router.post("/{business_id}/invoicing/tax-rates")
async def add_rate(
    business_id: UUID, body: RateBody,
    actor: BusinessActorContext = Depends(require_business_actor(INVOICES_CONFIGURE, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    row = await TaxRateService.add(session, business_id, actor.request.identity_id, body.model_dump(mode="json"))
    await session.commit()
    return {"data": serialize_rate(row), "meta": _meta(actor)}


@router.delete("/{business_id}/invoicing/tax-rates/{rate_id}")
async def remove_rate(
    business_id: UUID, rate_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(INVOICES_CONFIGURE, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    await TaxRateService.remove(session, business_id, actor.request.identity_id, rate_id)
    await session.commit()
    return {"data": {"removed": True}, "meta": _meta(actor)}


# ------------------------------------------------------------------ bills
class LineBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    offering_id: UUID | None = None
    variant_id: UUID | None = None
    title: str | None = Field(default=None, max_length=300)
    hsn_sac: str | None = Field(default=None, max_length=8)
    unit_label: str | None = Field(default=None, max_length=20)
    quantity: float = Field(default=1, gt=0, le=1_000_000)
    unit_price: float | None = Field(default=None, ge=0)
    discount: float | None = Field(default=None, ge=0)
    rate: float | None = Field(default=None, ge=0, le=100)
    # §15.1: one serial or IMEI per unit for items that keep serial numbers.
    serials: list[str] | None = Field(default=None, max_length=300)


class BuyerBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, max_length=200)
    gstin: str | None = Field(default=None, max_length=20)
    address: str | None = Field(default=None, max_length=500)
    state_code: str | None = Field(default=None, max_length=2)
    phone: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=254)


class BillBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    register_id: UUID | None = None
    customer_contact_id: UUID | None = None
    buyer: BuyerBody | None = None
    place_of_supply: str | None = Field(default=None, max_length=2)
    reverse_charge: bool = False
    due_date: date | None = None
    notes: str | None = Field(default=None, max_length=2000)
    bill_discount: float | None = Field(default=None, ge=0)
    lines: list[LineBody] = Field(min_length=1, max_length=300)
    issue: bool = True
    idempotency_key: str | None = Field(default=None, max_length=120)
    # On the customer's khata (§14.5); above their limit only with ledger.manage.
    on_account: bool = False
    allow_over_limit: bool = False


class FromOrderBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    register_id: UUID | None = None
    place_of_supply: str | None = Field(default=None, max_length=2)
    buyer: BuyerBody | None = None
    reverse_charge: bool = False


class CancelBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=500)


class NoteLine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    original_line_id: UUID
    quantity: float | None = Field(default=None, gt=0)
    amount: float | None = Field(default=None, gt=0)
    serials: list[str] | None = Field(default=None, max_length=300)  # which units came back


class NoteBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["credit_note", "debit_note"]
    reason: str
    restock: bool = False
    notes: str | None = Field(default=None, max_length=2000)
    lines: list[NoteLine] = Field(min_length=1, max_length=300)


class PaymentBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: float = Field(gt=0)
    method: str
    reference: str | None = Field(default=None, max_length=120)
    received_on: date | None = None


def _body(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(mode="json", exclude_none=True, exclude={"allow_over_limit"})


def _khata(actor: BusinessActorContext, body: BillBody) -> dict[str, Any]:
    """Who may put a bill on a customer's khata, and allow it over the limit."""
    if not body.on_account:
        return {}
    perms = actor.request.effective_permissions
    if LEDGER_RECORD not in perms:
        raise PermissionDenied(LEDGER_RECORD)
    assert_module_operational(actor.request, "ledger")
    over = body.allow_over_limit and LEDGER_MANAGE in perms
    return {"credit_approved_by": actor.request.identity_id if over else None}


@router.get("/{business_id}/invoices")
async def list_invoices(
    business_id: UUID,
    kind: str | None = Query(default=None),
    status: str | None = Query(default=None),
    payment: Literal["unpaid", "overdue"] | None = Query(default=None),
    q: str | None = Query(default=None, max_length=100),
    order_id: UUID | None = Query(default=None),
    customer_contact_id: UUID | None = Query(default=None),
    date_from: date | None = Query(default=None, alias="from"),
    date_to: date | None = Query(default=None, alias="to"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    actor: BusinessActorContext = Depends(require_business_actor(INVOICES_READ, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    rows = await InvoiceService.list_documents(session, business_id, kind=kind, status=status, payment=payment, q=q,
                                     order_id=order_id, customer_contact_id=customer_contact_id,
                                     date_from=date_from, date_to=date_to, limit=limit, offset=offset)
    return {"data": rows, "meta": _meta(actor, count=len(rows), kinds=KIND_LABEL)}


@router.post("/{business_id}/invoices")
async def create_invoice(
    business_id: UUID, body: BillBody,
    actor: BusinessActorContext = Depends(require_business_actor(INVOICES_ISSUE, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    doc = await InvoiceService.create(session, business_id, actor.request.identity_id, _body(body) | {
        "issue": body.issue, "reverse_charge": body.reverse_charge} | _khata(actor, body))
    await session.commit()
    return {"data": await InvoiceService.detail(session, business_id, doc.id), "meta": _meta(actor)}


@router.post("/{business_id}/invoices/from-order/{order_id}")
async def invoice_order(
    business_id: UUID, order_id: UUID, body: FromOrderBody,
    actor: BusinessActorContext = Depends(require_business_actor(INVOICES_ISSUE, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    doc = await InvoiceService.from_order(
        session, business_id, order_id, actor.request.identity_id, register_id=body.register_id,
        place_of_supply=body.place_of_supply, buyer=_body(body.buyer) if body.buyer else None,
        reverse_charge=body.reverse_charge)
    await session.commit()
    return {"data": await InvoiceService.detail(session, business_id, doc.id), "meta": _meta(actor)}


@router.get("/{business_id}/invoices/{document_id}")
async def get_invoice(
    business_id: UUID, document_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(INVOICES_READ, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await InvoiceService.detail(session, business_id, document_id)
    return {"data": data, "meta": _meta(actor, note_reasons=NOTE_REASONS, payment_methods=PAYMENT_METHODS)}


@router.patch("/{business_id}/invoices/{document_id}")
async def update_invoice(
    business_id: UUID, document_id: UUID, body: BillBody,
    actor: BusinessActorContext = Depends(require_business_actor(INVOICES_ISSUE, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    khata = _khata(actor, body)
    doc = await InvoiceService.update_draft(session, business_id, document_id, actor.request.identity_id,
                                            _body(body) | {"reverse_charge": body.reverse_charge,
                                                           "on_account": body.on_account})
    if body.issue:
        await InvoiceService.issue(session, business_id, doc.id, actor.request.identity_id,
                                   credit_approved_by=khata.get("credit_approved_by"))
    await session.commit()
    return {"data": await InvoiceService.detail(session, business_id, doc.id), "meta": _meta(actor)}


@router.delete("/{business_id}/invoices/{document_id}")
async def delete_draft(
    business_id: UUID, document_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(INVOICES_ISSUE, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    await InvoiceService.delete_draft(session, business_id, document_id)
    await session.commit()
    return {"data": {"deleted": True}, "meta": _meta(actor)}


@router.post("/{business_id}/invoices/{document_id}/issue")
async def issue_invoice(
    business_id: UUID, document_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(INVOICES_ISSUE, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    await InvoiceService.issue(session, business_id, document_id, actor.request.identity_id)
    await session.commit()
    return {"data": await InvoiceService.detail(session, business_id, document_id), "meta": _meta(actor)}


@router.post("/{business_id}/invoices/{document_id}/cancel")
async def cancel_invoice(
    business_id: UUID, document_id: UUID, body: CancelBody,
    actor: BusinessActorContext = Depends(require_business_actor(INVOICES_CANCEL, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    await InvoiceService.cancel(session, business_id, document_id, actor.request.identity_id, body.reason)
    await session.commit()
    return {"data": await InvoiceService.detail(session, business_id, document_id), "meta": _meta(actor)}


@router.post("/{business_id}/invoices/{document_id}/notes")
async def raise_note(
    business_id: UUID, document_id: UUID, body: NoteBody,
    actor: BusinessActorContext = Depends(require_business_actor(INVOICES_ISSUE, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    doc = await InvoiceService.note(session, business_id, document_id, actor.request.identity_id, _body(body)
                                    | {"restock": body.restock})
    await session.commit()
    return {"data": await InvoiceService.detail(session, business_id, doc.id), "meta": _meta(actor)}


@router.post("/{business_id}/invoices/{document_id}/payments")
async def record_payment(
    business_id: UUID, document_id: UUID, body: PaymentBody,
    actor: BusinessActorContext = Depends(require_business_actor(INVOICES_RECORD_PAYMENT, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    await InvoiceService.record_payment(session, business_id, document_id, actor.request.identity_id, _body(body))
    await session.commit()
    return {"data": await InvoiceService.detail(session, business_id, document_id), "meta": _meta(actor)}


@router.get("/{business_id}/invoices/{document_id}/pdf")
async def invoice_pdf(
    business_id: UUID, document_id: UUID,
    layout: Literal["a4", "thermal_80", "thermal_58"] = Query(default="a4"),
    actor: BusinessActorContext = Depends(require_business_actor(INVOICES_READ, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    content, meta = await InvoiceService.pdf(session, business_id, document_id, layout, actor.request.identity_id)
    await session.commit()
    name = str(meta["number"]).replace("/", "-")
    return Response(content=content, media_type="application/pdf", headers={
        "Content-Disposition": f'inline; filename="{name}.pdf"', "X-Document-SHA256": str(meta["sha256"]),
        "Cache-Control": "private, no-store"})


@router.get("/{business_id}/invoices/{document_id}/share")
async def share_invoice(
    business_id: UUID, document_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(INVOICES_ISSUE, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    data = await InvoiceService.share(session, business_id, document_id)
    await session.commit()
    return {"data": data, "meta": _meta(actor)}


# ------------------------------------------------------------------ reports
def _period(start: date | None, end: date | None) -> tuple[date, date]:
    today = local_today()
    if start is None:
        start = today.replace(day=1)
    if end is None:
        end = today
    if end < start:
        raise ValidationError("The end date is before the start date", details={"field": "to"})
    if (end - start).days > 400:
        raise ValidationError("Choose at most about a year at a time", details={"field": "from"})
    return start, end


@router.get("/{business_id}/invoicing/reports/{kind}")
async def report(
    business_id: UUID, kind: str,
    date_from: date | None = Query(default=None, alias="from"),
    date_to: date | None = Query(default=None, alias="to"),
    actor: BusinessActorContext = Depends(require_business_actor(INVOICES_EXPORT, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> Any:
    csv_wanted = kind.endswith(".csv")
    kind = kind.removesuffix(".csv")
    if kind not in reports.REPORTS:
        raise ResourceNotFound("Report")
    start, end = _period(date_from, date_to)
    data = await reports.run(session, business_id, kind, start, end)
    if csv_wanted:
        body = reports.gstr1_csv(data) if kind == "gstr1" else reports.to_csv(data)
        return Response(content=body, media_type="text/csv", headers={
            "Content-Disposition": f'attachment; filename="{kind}_{start}_{end}.csv"',
            "Cache-Control": "private, no-store"})
    return {"data": data | {"kind": kind, "label": reports.REPORTS[kind], "from": start.isoformat(),
                            "to": end.isoformat()}, "meta": _meta(actor, reports=reports.REPORTS)}


# ------------------------------------------------------------------ public
@public_router.get("/gst-states")
async def gst_states() -> dict[str, Any]:
    return {"data": [{"code": k, "name": v} for k, v in STATES.items()]}


@public_router.get("/websites/{slug}/bills/{token}")
async def public_bill_view(slug: str, token: str, session: AsyncSession = Depends(get_db_session)) -> dict[str, Any]:
    data = await public_bill(session, slug, token)
    return {"data": data | {"pdf_path": f"/v1/public/websites/{slug}/bills/{token}/pdf"}}


@public_router.get("/websites/{slug}/bills/{token}/pdf")
async def public_bill_pdf(
    slug: str, token: str, layout: Literal["a4", "thermal_80", "thermal_58"] = Query(default="a4"),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    from platform_core.documents.renderer import render_pdf

    data = await public_bill(session, slug, token)
    content = render_pdf(build_spec(data, thermal=layout != "a4"), layout)
    name = str(data.get("number") or "bill").replace("/", "-")
    return Response(content=content, media_type="application/pdf", headers={
        "Content-Disposition": f'inline; filename="{name}.pdf"', "Cache-Control": "private, no-store",
        "X-Correlation-Id": str(uuid.uuid4())})
