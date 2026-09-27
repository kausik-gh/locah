"""Counter sales, returns, voids and drawer movements (Capability Universe
§14.1, §14.2) as offline-sync mutations.

The counter always queues and replays through `/sync`, online or not, so a
sale rung up without a connection takes exactly the path an online one does:
idempotent on the device's id for it, and re-checked on the server — prices
against the catalogue, discounts against the cashier's limit, the number
against the register's block. The device is never trusted to have decided.

What happened at the counter cannot be undone by the server, so:
* a price that changed after the device cached the catalogue is accepted at
  the price the customer paid, and noted;
* stock is never a reason to refuse a sale — a short count is flagged;
* a number from a block the server no longer recognises (a new financial
  year) is replaced with the next number, and noted.
Anything that needs judgement (a discount above the limit, a void outside the
shift, a return past the window) needs a manager's approval token.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.invoicing.tax_engine import ZERO, dec, money
from platform_core.models import (
    BusinessLocation,
    CustomerContact,
    InvoicingDocument,
    InvoicingPayment,
    InvoicingRegister,
    Offering,
    OfferingVariant,
    PosSettings,
)
from platform_core.services.offline_sync import Rejected, SyncContext, mutation
from platform_core.services.number_series import NumberSeriesService, financial_year
from platform_core.services.pos import PosService, holder, read_approval, series_key

TENDERS = {"cash": "Cash", "upi": "UPI", "card": "Card"}


def _sold_at(raw: Any, tz: str | None) -> tuple[datetime, date]:
    now = datetime.now(timezone.utc)
    when = now
    if raw:
        try:
            when = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except ValueError as exc:
            raise Rejected("The sale time from the device is not readable") from exc
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        if when > now + timedelta(minutes=10) or when < now - timedelta(days=30):
            raise Rejected("The device clock is wrong: fix the date and time, then sync again")
    try:
        zone = ZoneInfo(tz or "Asia/Kolkata")
    except Exception:  # noqa: BLE001
        zone = ZoneInfo("Asia/Kolkata")
    return when, when.astimezone(zone).date()


async def _catalogue_price(session: AsyncSession, offering: Offering, variant_id: Any,
                           options: dict[str, Any] | None) -> tuple[Decimal, OfferingVariant | None]:
    variant = None
    if variant_id:
        variant = await session.get(OfferingVariant, uuid.UUID(str(variant_id)))
        if variant is None or variant.offering_id != offering.id:
            raise Rejected(f"{offering.title}: that option no longer exists")
    if options:
        from platform_core.services.offering_pricing import price_selection

        return dec(price_selection(offering, variant, options).unit_price), variant
    if variant is not None and variant.price_amount is not None:
        return dec(variant.price_amount), variant
    if offering.price_amount is None:
        raise Rejected(f"{offering.title} has no price")
    return dec(offering.price_amount), variant


@mutation("pos.sale", permission="pos.use")  # type: ignore[untyped-decorator, unused-ignore]
async def pos_sale(session: AsyncSession, ctx: SyncContext, p: dict[str, Any]) -> dict[str, Any]:
    from platform_core.services.invoicing import InvoiceService, share_token

    shift = await PosService.get_shift(session, ctx.business_id, uuid.UUID(str(p.get("shift_id"))), lock=True)
    register = await session.get(InvoicingRegister, shift.register_id)
    location = await session.get(BusinessLocation, shift.location_id)
    assert register is not None
    sold_at, sold_day = _sold_at(p.get("sold_at"), location.timezone if location else None)
    if shift.status != "open" and not (shift.closed_at and sold_at <= shift.closed_at):
        raise Rejected("This shift is closed. Open a shift to bill.")
    try:
        version = datetime.fromisoformat(str(p.get("catalogue_version") or "").replace("Z", "+00:00"))
    except ValueError:
        version = None

    raw_lines = list(p.get("lines") or [])
    if not raw_lines:
        raise Rejected("The bill has no items")
    lines: list[dict[str, Any]] = []
    notes: list[str] = []
    catalogue_gross = ZERO
    reductions = ZERO
    for raw in raw_lines:
        offering = await session.get(Offering, uuid.UUID(str(raw.get("offering_id"))))
        if offering is None or offering.business_id != ctx.business_id:
            raise Rejected("An item on the bill is not in the catalogue")
        qty = dec(raw.get("quantity") or 0)
        if qty <= 0:
            raise Rejected(f"{offering.title}: quantity must be more than zero")
        options = raw.get("options") or None
        catalogue, _variant = await _catalogue_price(session, offering, raw.get("variant_id"), options)
        charged = money(dec(raw.get("unit_price") if raw.get("unit_price") is not None else catalogue))
        changed_since = version is None or (offering.updated_at and offering.updated_at > version)
        if charged != catalogue:
            if changed_since:
                notes.append(f"{offering.title}: sold at ₹{charged} (price changed to ₹{catalogue} after the "
                             "counter's copy)")
                catalogue = charged
            elif charged > catalogue:
                raise Rejected(f"{offering.title}: ₹{charged} is above the catalogue price ₹{catalogue}")
        line_gross = money(qty * catalogue)
        catalogue_gross += line_gross
        line_discount = money(dec(raw.get("discount") or 0))
        reductions += money(qty * (catalogue - charged)) + line_discount
        lines.append({"offering_id": str(offering.id), "variant_id": raw.get("variant_id"), "quantity": str(qty),
                      "unit_price": str(charged), "discount": str(line_discount), "options": options,
                      "unit_label": raw.get("unit_label")})
    bill_discount = money(dec(p.get("bill_discount") or 0))
    reductions += bill_discount

    # Discount limit (§14.1): owner none; others their role's cap unless approved.
    if reductions > 0 and catalogue_gross > 0:
        pct = float(reductions * 100 / catalogue_gross)
        cap = await PosService.discount_cap(session, ctx.business_id, ctx.actor_id)
        if cap is not None and pct > cap + 1e-9:
            approval = read_approval(p.get("approval"), ctx.business_id, "discount")
            if approval is None or float(approval.get("max_pct", 0)) + 1e-9 < pct:
                raise Rejected(f"A {pct:.1f}% discount is above your {cap:g}% limit — a manager's PIN is needed")
            notes.append(f"Discount {pct:.1f}% approved")

    customer = dict(p.get("customer") or {})
    contact_id = customer.get("contact_id")
    if not contact_id and customer.get("phone"):
        phone = str(customer["phone"]).strip()
        found = (await session.execute(select(CustomerContact.id).where(
            CustomerContact.business_id == ctx.business_id, CustomerContact.phone == phone,
            CustomerContact.deleted_at.is_(None)))).scalars().first()
        if found is None:
            contact = CustomerContact(business_id=ctx.business_id, display_name=str(customer.get("name") or phone)[:120],
                                      phone=phone, preferred_location_id=shift.location_id)
            session.add(contact)
            await session.flush()
            found = contact.id
        contact_id = str(found)

    payload = {
        "register_id": str(register.id), "customer_contact_id": contact_id,
        "buyer": {k: v for k, v in {"name": customer.get("name"), "phone": customer.get("phone"),
                                    "gstin": customer.get("gstin")}.items() if v},
        "lines": lines, "bill_discount": str(bill_discount), "issue": False,
        "idempotency_key": f"pos:{p.get('client_bill_id') or uuid.uuid4()}",
    }
    doc = await InvoiceService.create(session, ctx.business_id, ctx.actor_id, payload)
    if doc.status != "draft":  # idempotent replay of the same bill
        return {"document_id": str(doc.id), "number": doc.number, "amount_due": float(doc.amount_due)}
    doc.source, doc.shift_id, doc.device_id, doc.sold_at = "pos", shift.id, ctx.device_id, sold_at
    doc.pos_meta = {"catalogue_version": p.get("catalogue_version"), "notes": notes,
                    "offline": bool(p.get("sold_offline"))}

    # The number: from the register's block when the device used one.
    preset = None
    number = p.get("number") or {}
    fy = financial_year(sold_day)
    if number.get("block_id") and number.get("value"):
        try:
            blk = await NumberSeriesService.block(session, ctx.business_id, uuid.UUID(str(number["block_id"])))
        except Exception:  # noqa: BLE001 — an unknown block is renumbered below
            blk = None
        value = int(number["value"])
        valid = blk is not None and blk.period == fy and blk.start <= value <= blk.end
        if valid:
            row = (await session.execute(select(InvoicingDocument.id).where(
                InvoicingDocument.business_id == ctx.business_id, InvoicingDocument.series_key == series_key(register.id),
                InvoicingDocument.fy == fy, InvoicingDocument.seq == value))).first()
            owner = await _block_holder(session, ctx.business_id, blk.id if blk else None)
            if row is not None:
                raise Rejected(f"Number {blk.number(value) if blk else value} was already used on another bill")
            if owner != holder(register.id):
                valid = False
        if valid and blk is not None:
            preset = (series_key(register.id), fy, value, blk.number(value))
        else:
            notes.append("Renumbered: the device's number was not from this register's current block")
    await session.flush()
    await InvoiceService.issue(session, ctx.business_id, doc.id, ctx.actor_id, issue_date=sold_day,
                               reresolve=False, preset=preset)

    # Tenders (§14.1): cash, UPI, card; split allowed; change only from cash.
    due = dec(doc.amount_due)
    tenders = list(p.get("tenders") or [])
    total = ZERO
    cash_given = ZERO
    for t in tenders:
        if t.get("method") not in TENDERS:
            raise Rejected("Take cash, UPI or card (khata comes with the credit book)")
        amount = money(dec(t.get("amount") or 0))
        if amount <= 0:
            raise Rejected("A tender amount must be more than zero")
        total += amount
        if t["method"] == "cash":
            cash_given += amount
    if total < due:
        raise Rejected(f"₹{due - total} is still to be paid")
    change = total - due
    if change > cash_given:
        raise Rejected("Change can only be given from cash")
    for t in tenders:
        amount = money(dec(t["amount"]))
        if t["method"] == "cash" and change > 0:
            back = min(change, amount)
            amount -= back
            change -= back
        if amount <= 0:
            continue
        session.add(InvoicingPayment(
            business_id=ctx.business_id, document_id=doc.id, amount=amount, method=t["method"],
            reference=(str(t.get("reference") or "").strip()[:120] or None), received_on=sold_day,
            recorded_by=ctx.actor_id, shift_id=shift.id,
            verification="to_verify" if t["method"] == "upi" and t.get("to_verify") else "verified",
        ))
    doc.amount_paid = min(total, due)
    doc.pos_meta = {**doc.pos_meta, "notes": notes, "tendered": float(total),
                    "change": float(total - due if total > due else 0)}
    await session.flush()
    token = share_token(ctx.business_id, doc.id)
    return {"document_id": str(doc.id), "number": doc.number, "amount_due": float(doc.amount_due),
            "change": float(max(total - due, ZERO)), "notes": notes, "share_token": token,
            "stock_short": (doc.pos_meta or {}).get("stock_short", [])}


async def _block_holder(session: AsyncSession, business_id: uuid.UUID, block_id: uuid.UUID | None) -> str | None:
    if block_id is None:
        return None
    from sqlalchemy import text

    row = (await session.execute(text("SELECT holder FROM number_series_blocks WHERE business_id = :b AND id = :id"),
                                 {"b": str(business_id), "id": str(block_id)})).first()
    return str(row[0]) if row else None


async def _bill(session: AsyncSession, ctx: SyncContext, p: dict[str, Any]) -> InvoicingDocument:
    q = select(InvoicingDocument).where(InvoicingDocument.business_id == ctx.business_id)
    if p.get("document_id"):
        q = q.where(InvoicingDocument.id == uuid.UUID(str(p["document_id"])))
    elif p.get("number"):
        q = q.where(InvoicingDocument.number == str(p["number"]).strip(),
                    InvoicingDocument.doc_kind.in_(("tax_invoice", "bill_of_supply", "bill")))
    else:
        raise Rejected("Which bill?")
    doc = (await session.execute(q.order_by(InvoicingDocument.created_at.desc()).limit(1))).scalars().first()
    if doc is None:
        raise Rejected("No bill with that number")
    return doc


@mutation("pos.return", permission="pos.use")  # type: ignore[untyped-decorator, unused-ignore]
async def pos_return(session: AsyncSession, ctx: SyncContext, p: dict[str, Any]) -> dict[str, Any]:
    """Goods back at the counter: a credit note against the bill, stock back,
    and the refund (cash comes out of this shift's drawer)."""
    from platform_core.services.invoicing import InvoiceService

    shift = await PosService.get_shift(session, ctx.business_id, uuid.UUID(str(p.get("shift_id"))), lock=True)
    if shift.status != "open":
        raise Rejected("Open a shift to take a return")
    original = await _bill(session, ctx, p)
    settings = await session.get(PosSettings, ctx.business_id)
    window = settings.return_window_days if settings else 7
    if original.issue_date and (date.today() - original.issue_date).days > window:
        approval = read_approval(p.get("approval"), ctx.business_id, "return")
        if approval is None:
            raise Rejected(f"This bill is past the {window}-day return window — a manager's PIN is needed")
    method = p.get("refund_method") or "cash"
    if method not in TENDERS:
        raise Rejected("Refund in cash, UPI or card")
    note = await InvoiceService.note(session, ctx.business_id, original.id, ctx.actor_id, {
        "kind": "credit_note", "reason": "return", "restock": bool(p.get("restock", True)),
        "lines": [{"original_line_id": x.get("original_line_id"), "quantity": x.get("quantity")}
                  for x in p.get("lines") or []],
        "notes": p.get("note"),
    })
    note.shift_id, note.device_id = shift.id, ctx.device_id
    note.pos_meta = {"refund_method": method}
    if method == "cash":
        await PosService.cash_movement(session, ctx.business_id, ctx.actor_id, shift.id, kind="refund",
                                       amount=note.amount_due, reason=f"Refund for {original.number}",
                                       document_id=note.id)
    await session.flush()
    return {"document_id": str(note.id), "number": note.number, "refund": float(note.amount_due),
            "refund_method": method}


@mutation("pos.void", permission="pos.use")  # type: ignore[untyped-decorator, unused-ignore]
async def pos_void(session: AsyncSession, ctx: SyncContext, p: dict[str, Any]) -> dict[str, Any]:
    """Cancel a counter bill (it keeps its number). The cashier may void a bill
    of the shift that is still open; anything else needs a manager's PIN."""
    from platform_core.services.invoicing import InvoiceService

    doc = await _bill(session, ctx, p)
    if doc.source != "pos":
        raise Rejected("Only counter bills are voided here")
    same_shift = False
    if doc.shift_id:
        shift = await PosService.get_shift(session, ctx.business_id, doc.shift_id)
        same_shift = shift.status == "open"
    if not same_shift:
        approval = read_approval(p.get("approval"), ctx.business_id, "void")
        if approval is None or approval.get("doc") not in (None, str(doc.id)):
            raise Rejected("This bill is from a closed shift — a manager's PIN is needed to void it")
    await InvoiceService.cancel(session, ctx.business_id, doc.id, ctx.actor_id, str(p.get("reason") or "Voided at the counter"),
                                void=True)
    return {"document_id": str(doc.id), "number": doc.number, "bill_status": "cancelled"}


@mutation("pos.cash", permission="pos.use")  # type: ignore[untyped-decorator, unused-ignore]
async def pos_cash(session: AsyncSession, ctx: SyncContext, p: dict[str, Any]) -> dict[str, Any]:
    row = await PosService.cash_movement(
        session, ctx.business_id, ctx.actor_id, uuid.UUID(str(p.get("shift_id"))), kind=str(p.get("kind") or ""),
        amount=p.get("amount"), reason=str(p.get("reason") or ""))
    return {"id": str(row.id), "kind": row.kind, "amount": float(row.amount)}
