"""Counter billing (Capability Universe §14.1–§14.3, §14.5).

Sales, returns, voids and drawer movements go through `/sync` as offline
mutations (platform_core.pos.sales), so the counter uses one path whether or
not it is online. These routes are what needs a connection: the counter's
setup and catalogue, shifts and number blocks, manager approvals, the UPI QR,
checking UPI taken without confirmation, in-store codes and labels.
"""

from __future__ import annotations

import uuid
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import platform_core.pos.sales  # noqa: F401  (registers the counter's offline mutations)
from platform_api.db import get_db_session
from platform_api.dependencies import BusinessActorContext, require_business_actor
from platform_core.exceptions import ConflictError, ResourceNotFound, ValidationError
from platform_core.models import InvoicingDocument, InvoicingRegister, Offering
from platform_core.permissions import (
    INVOICES_RECORD_PAYMENT,
    OFFERINGS_UPDATE,
    POS_APPROVE,
    POS_CONFIGURE,
    POS_USE,
)
from platform_core.pos.barcodes import clean_weighed_format, decode_weighed, in_store_code, label_sheet
from platform_core.services.pos import PosService

router = APIRouter(prefix="/v1/platform/businesses", tags=["pos"])
MODULE = "pos"


def _meta(actor: BusinessActorContext, **extra: Any) -> dict[str, Any]:
    return {"correlation_id": actor.request.correlation_id, **extra}


class SettingsBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    upi_vpa: str | None = Field(default=None, max_length=320)
    upi_payee_name: str | None = Field(default=None, max_length=100)
    return_window_days: int = Field(default=7, ge=0, le=365)
    discount_caps: dict[str, float] = Field(default_factory=dict)
    block_size: int = Field(default=50, ge=10, le=500)
    weighed_label: dict[str, Any] | None = None
    receipt_footer: str | None = Field(default=None, max_length=300)


class PinBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pin: str = Field(min_length=4, max_length=6)


class ApproveBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approver_id: UUID
    pin: str = Field(min_length=4, max_length=6)
    action: Literal["discount", "void", "return"]
    max_discount_pct: float | None = Field(default=None, ge=0, le=100)
    document_id: UUID | None = None


class OpenShiftBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    register_id: UUID
    device_id: str = Field(min_length=3, max_length=80)
    opening_cash: float = Field(ge=0)


class CloseShiftBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    counted_cash: float = Field(ge=0)
    note: str | None = Field(default=None, max_length=500)
    last_used: int | None = Field(default=None, ge=1)


class VerifyBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    received: bool


@router.get("/{business_id}/pos/setup")
async def pos_setup(
    business_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(POS_USE, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    return {"data": await PosService.setup(session, business_id, actor.request.identity_id), "meta": _meta(actor)}


@router.put("/{business_id}/pos/settings")
async def put_settings(
    business_id: UUID, body: SettingsBody,
    actor: BusinessActorContext = Depends(require_business_actor(POS_CONFIGURE, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    row = await PosService.save_settings(session, business_id, actor.request.identity_id, body.model_dump())
    await session.commit()
    return {"data": PosService.serialize_settings(row), "meta": _meta(actor)}


@router.put("/{business_id}/pos/pin")
async def set_pin(
    business_id: UUID, body: PinBody,
    actor: BusinessActorContext = Depends(require_business_actor(POS_APPROVE, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    await PosService.set_pin(session, business_id, actor.request.identity_id, body.pin)
    await session.commit()
    return {"data": {"set": True}, "meta": _meta(actor)}


@router.post("/{business_id}/pos/approve")
async def approve(
    business_id: UUID, body: ApproveBody,
    actor: BusinessActorContext = Depends(require_business_actor(POS_USE, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """A manager approves on the cashier's screen: their PIN, not the cashier's authority."""
    try:
        data = await PosService.approve(session, business_id, requester_id=actor.request.identity_id,
                                        approver_id=body.approver_id, pin=body.pin, action=body.action,
                                        max_discount_pct=body.max_discount_pct, document_id=body.document_id)
    except ValidationError:
        await session.commit()  # keep the failed-attempt count
        raise
    await session.commit()
    return {"data": data, "meta": _meta(actor)}


@router.get("/{business_id}/pos/catalogue")
async def catalogue(
    business_id: UUID, location_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(POS_USE, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    return {"data": await PosService.catalogue(session, business_id, location_id), "meta": _meta(actor)}


@router.post("/{business_id}/pos/shifts")
async def open_shift(
    business_id: UUID, body: OpenShiftBody,
    actor: BusinessActorContext = Depends(require_business_actor(POS_USE, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    shift, block = await PosService.open_shift(session, business_id, actor.request.identity_id,
                                               register_id=body.register_id, device_id=body.device_id,
                                               opening_cash=body.opening_cash)
    await session.commit()
    summary = await PosService.summary(session, shift)
    return {"data": {"shift": PosService.serialize_shift(shift, summary), "block": block}, "meta": _meta(actor)}


@router.get("/{business_id}/pos/shifts")
async def list_shifts(
    business_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(POS_APPROVE, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    return {"data": await PosService.shifts(session, business_id), "meta": _meta(actor)}


@router.get("/{business_id}/pos/shifts/{shift_id}")
async def get_shift(
    business_id: UUID, shift_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(POS_USE, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    shift = await PosService.get_shift(session, business_id, shift_id)
    return {"data": PosService.serialize_shift(shift, await PosService.summary(session, shift)), "meta": _meta(actor)}


@router.post("/{business_id}/pos/shifts/{shift_id}/close")
async def close_shift(
    business_id: UUID, shift_id: UUID, body: CloseShiftBody,
    actor: BusinessActorContext = Depends(require_business_actor(POS_USE, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    shift = await PosService.close_shift(session, business_id, actor.request.identity_id, shift_id,
                                         counted_cash=body.counted_cash, note=body.note, last_used=body.last_used)
    await session.commit()
    return {"data": PosService.serialize_shift(shift, await PosService.summary(session, shift)), "meta": _meta(actor)}


@router.post("/{business_id}/pos/shifts/{shift_id}/block")
async def more_numbers(
    business_id: UUID, shift_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(POS_USE, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    shift = await PosService.get_shift(session, business_id, shift_id)
    if shift.status != "open":
        raise ConflictError("The shift is closed")
    register = await session.get(InvoicingRegister, shift.register_id)
    assert register is not None
    block = await PosService.ensure_block(session, business_id, register)
    await session.commit()
    return {"data": block, "meta": _meta(actor)}


@router.get("/{business_id}/pos/shifts/{shift_id}/bills")
async def shift_bills(
    business_id: UUID, shift_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(POS_USE, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    rows = (await session.execute(select(InvoicingDocument).where(
        InvoicingDocument.business_id == business_id, InvoicingDocument.shift_id == shift_id,
    ).order_by(InvoicingDocument.created_at.desc()).limit(200))).scalars()
    return {"data": [{"id": str(d.id), "number": d.number, "kind": d.doc_kind, "status": d.status,
                      "amount_due": float(d.amount_due), "buyer": (d.buyer or {}).get("name"),
                      "sold_at": d.sold_at.isoformat() if d.sold_at else None} for d in rows], "meta": _meta(actor)}


@router.get("/{business_id}/pos/upi-qr")
async def upi_qr(
    business_id: UUID, amount: float = Query(gt=0, le=10_000_000), note: str = Query(default="", max_length=40),
    actor: BusinessActorContext = Depends(require_business_actor(POS_USE, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    """A UPI QR for the exact amount, to the business's own UPI ID. Paying it is
    not confirmed automatically (no payment provider is connected): the
    cashier confirms, or marks it 'UPI to verify'."""
    from platform_core.models import Business

    settings = await PosService.settings(session, business_id)
    if settings is None or not settings.upi_vpa:
        raise ConflictError("Add your UPI ID in Settings → Counter billing to show a QR")
    business = await session.get(Business, business_id)
    name = settings.upi_payee_name or (business.display_name if business else "")
    svg = PosService.qr_svg(PosService.upi_uri(settings.upi_vpa, name, amount, note or "Bill"))
    return Response(content=svg, media_type="image/svg+xml", headers={"Cache-Control": "private, no-store"})


@router.get("/{business_id}/pos/upi-to-verify")
async def upi_to_verify(
    business_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(INVOICES_RECORD_PAYMENT, "invoicing")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    return {"data": await PosService.to_verify(session, business_id), "meta": _meta(actor)}


@router.post("/{business_id}/pos/payments/{payment_id}/verify")
async def verify_payment(
    business_id: UUID, payment_id: UUID, body: VerifyBody,
    actor: BusinessActorContext = Depends(require_business_actor(INVOICES_RECORD_PAYMENT, "invoicing")),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    await PosService.verify_payment(session, business_id, actor.request.identity_id, payment_id, body.received)
    await session.commit()
    return {"data": {"verified": body.received}, "meta": _meta(actor)}


@router.get("/{business_id}/pos/scan")
async def scan(
    business_id: UUID, code: str = Query(min_length=1, max_length=64),
    actor: BusinessActorContext = Depends(require_business_actor(POS_USE, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """What a scanned code is (the counter does the same from its cached copy)."""
    code = code.strip()
    settings = await PosService.settings(session, business_id)
    fmt = clean_weighed_format(settings.weighed_label) if settings and settings.weighed_label else None
    weighed = decode_weighed(code, fmt)
    q = select(Offering).where(Offering.business_id == business_id, Offering.deleted_at.is_(None))
    if weighed is not None:
        item = (await session.execute(q.where(Offering.sku == weighed.item_code))).scalars().first()
        if item is None:
            raise ResourceNotFound("Item for that scale code")
        return {"data": {"offering_id": str(item.id), "title": item.title, "weighed": weighed.kind,
                         "value": float(weighed.value)}, "meta": _meta(actor)}
    item = (await session.execute(q.where((Offering.barcode == code) | (Offering.sku == code)))).scalars().first()
    if item is None:
        raise ResourceNotFound("Item with that code")
    return {"data": {"offering_id": str(item.id), "title": item.title}, "meta": _meta(actor)}


@router.post("/{business_id}/pos/in-store-code/{offering_id}")
async def give_in_store_code(
    business_id: UUID, offering_id: UUID,
    actor: BusinessActorContext = Depends(require_business_actor(OFFERINGS_UPDATE, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """An in-store barcode for an item that has none (loose goods, §14.3)."""
    from platform_core.services.number_series import NumberSeriesService

    item = (await session.execute(select(Offering).where(
        Offering.business_id == business_id, Offering.id == offering_id).with_for_update())).scalars().first()
    if item is None or item.deleted_at is not None:
        raise ResourceNotFound("Item")
    if item.barcode:
        raise ConflictError("This item already has a barcode", details={"barcode": item.barcode})
    for _ in range(20):
        got = await NumberSeriesService.next(session, business_id, series_key="instore_code")
        code = in_store_code(got.value)
        taken = (await session.execute(select(Offering.id).where(
            Offering.business_id == business_id, Offering.barcode == code))).first()
        if not taken:
            item.barcode = code
            item.version += 1
            await session.commit()
            return {"data": {"offering_id": str(item.id), "barcode": code}, "meta": _meta(actor)}
    raise ConflictError("Could not find a free in-store code")


@router.get("/{business_id}/pos/labels")
async def labels(
    business_id: UUID, ids: str = Query(min_length=36, max_length=37 * 200),
    copies: int = Query(default=1, ge=1, le=50), layout: Literal["a4", "label_50x25"] = Query(default="a4"),
    actor: BusinessActorContext = Depends(require_business_actor(POS_USE, MODULE)),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    """Printable barcode labels for items (A4 sheet or 50 × 25 mm label printer)."""
    wanted = [uuid.UUID(x) for x in ids.split(",") if x.strip()]
    rows = list((await session.execute(select(Offering).where(
        Offering.business_id == business_id, Offering.id.in_(wanted), Offering.deleted_at.is_(None)))).scalars())
    missing = [o.title for o in rows if not (o.barcode and o.barcode.isdigit() and len(o.barcode) == 13)]
    if missing:
        raise ValidationError("Give these items a barcode first: " + ", ".join(missing[:5]),
                              details={"missing": missing})
    items = []
    for o in rows:
        price = f"₹{float(o.price_amount):,.2f}" + (f" / {(o.attributes or {}).get('price_per')}"
                                                    if (o.attributes or {}).get("price_per") else "") \
            if o.price_amount is not None else ""
        items += [{"title": o.title, "price": price, "code": o.barcode}] * copies
    pdf = label_sheet(items, layout=layout)
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": 'inline; filename="labels.pdf"', "Cache-Control": "private, no-store"})
