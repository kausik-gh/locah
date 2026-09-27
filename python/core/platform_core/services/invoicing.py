"""One billing engine for every bill (Capability Universe §14, §14.4, §14.6).

Counter, website, WhatsApp and B2B bills all come out of here as a correctly
numbered document with a PDF and a stock movement:

* The document follows the seller's scheme: a tax invoice (regular GST), a
  bill of supply (composition — never a tax line) or a bill (not registered —
  no GST fields). Returns and price changes are credit / debit notes that
  reference the original.
* Numbers are taken on issue from a gapless series per GSTIN × financial year
  × register (credit and debit notes: per GSTIN × FY). A draft has no number;
  a cancelled bill keeps its number and stays, marked cancelled.
* Tax is computed by `platform_core.invoicing.tax_engine` from rates that are
  the owner's data. A bill that needs a rate nobody has entered is not issued.
* Bills for orders take the order's own amounts (the order was priced by the
  same engine), so the bill and what the customer paid agree; the order owns
  its stock movement. Bills raised directly move stock on issue and put it
  back on cancel; a return credit note restocks when asked to.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.documents.renderer import DocSpec
from platform_core.exceptions import ConflictError, ResourceNotFound, ValidationError
from platform_core.invoicing.states import STATES, gstin_problem, normalise_gstin, state_label
from platform_core.invoicing.tax_engine import (
    DOC_KIND_FOR_SCHEME,
    ZERO,
    Bill,
    LineIn,
    TaxContext,
    compute,
    dec,
    money,
)
from platform_core.models import (
    Business,
    BusinessLocation,
    CustomerContact,
    InventoryMovement,
    InvoicingDocument,
    InvoicingDocumentLine,
    InvoicingPayment,
    InvoicingRegister,
    InvoicingRegistration,
    InvoicingTaxProfile,
    Offering,
    OfferingVariant,
    OrderLineItem,
    SalesOrder,
)
from platform_core.secrets import resolve_signing_secret
from platform_core.services.audit import AuditService
from platform_core.services.invoicing_setup import InvoicingSetupService, TaxRateService, local_today
from platform_core.services.number_series import NumberSeriesService, financial_year
from platform_core.services.outbox import OutboxService

KIND_LABEL = {
    "tax_invoice": "Tax invoice", "bill_of_supply": "Bill of supply", "bill": "Bill",
    "credit_note": "Credit note", "debit_note": "Debit note",
}
INVOICE_KINDS = ("tax_invoice", "bill_of_supply", "bill")
NOTE_REASONS = {
    "credit_note": {"return": "Goods returned", "price_reduction": "Price reduced", "correction": "Correction",
                    "other": "Other"},
    "debit_note": {"price_increase": "Price increased", "correction": "Correction", "other": "Other"},
}
PAYMENT_METHODS = {"cash": "Cash", "upi": "UPI", "card": "Card", "bank_transfer": "Bank transfer",
                   "cheque": "Cheque", "other": "Other"}
_Q3 = Decimal("0.001")


def _err(field: str, message: str) -> ValidationError:
    return ValidationError(message, details={"errors": [{"field": field, "message": message}], "field": field})


def _f(value: Any) -> float:
    return float(dec(value))


def _inr(value: Any) -> str:
    amount = money(dec(value))
    sign = "-" if amount < 0 else ""
    whole, frac = f"{abs(amount):.2f}".split(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups: list[str] = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join(groups + [tail])
    return f"{sign}₹{whole}.{frac}"


def _qty(value: Any) -> str:
    q = dec(value).normalize()
    return f"{q:f}" if q != q.to_integral() else str(int(q))


def _link_secret() -> str:
    return str(resolve_signing_secret("DOCUMENT_LINK_SECRET", "document-link-dev-secret",
                                      fallback_env="SUPABASE_JWT_SECRET"))


def share_token(business_id: uuid.UUID, document_id: uuid.UUID) -> str:
    """The bill's share credential, derived so it can be re-sent without storing it."""
    mac = hmac.new(_link_secret().encode(), f"bill:{business_id}:{document_id}".encode(), hashlib.sha256)
    return base64.urlsafe_b64encode(mac.digest()).decode().rstrip("=")[:32]


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@dataclass
class _Line:
    offering: Offering | None
    variant_id: uuid.UUID | None
    order_line_id: uuid.UUID | None
    original_line_id: uuid.UUID | None
    title: str
    hsn_sac: str | None
    unit_label: str | None
    quantity: Decimal
    unit_price: Decimal
    discount: Decimal
    rate: Decimal | None
    stock_quantity: int


def _rate_key(line: _Line) -> tuple[uuid.UUID | None, str | None, Any]:
    """What rate resolution needs for a line: its item, its HSN/SAC, the rate typed on the item."""
    o = line.offering
    return (o.id if o else None, line.hsn_sac, o.tax_rate if o else None)


def _unit_label(offering: Offering | None) -> str | None:
    if offering is None:
        return None
    if offering.stock_unit == "g":
        return "kg"
    if offering.stock_unit == "ml":
        return "l"
    if offering.offering_type in ("product", "weighed_product", "digital_product"):
        return "pcs"
    return None


def _stock_for(offering: Offering | None, quantity: Decimal, unit_label: str | None) -> int:
    if offering is None or not offering.track_inventory:
        return 0
    factor = Decimal(1000) if offering.stock_unit in ("g", "ml") and unit_label in ("kg", "l") else Decimal(1)
    units = quantity * factor
    if units != units.to_integral():
        raise _err("quantity", f"{offering.title} is counted in whole {offering.stock_unit}s; adjust the quantity")
    return int(units)


def _clean_buyer(raw: dict[str, Any] | None, contact: CustomerContact | None) -> dict[str, Any]:
    raw = dict(raw or {})
    name = str(raw.get("name") or (contact.display_name if contact else "") or "").strip()
    gstin = normalise_gstin(raw.get("gstin"))
    if gstin:
        problem = gstin_problem(gstin)
        if problem:
            raise _err("buyer.gstin", f"Buyer GSTIN: {problem}")
    state = str(raw.get("state_code") or "").strip() or (gstin[:2] if gstin else "")
    if state and state not in STATES:
        raise _err("buyer.state_code", "Choose the buyer's state")
    if gstin and state != gstin[:2]:
        raise _err("buyer.state_code", "The buyer's state must match their GSTIN")
    if gstin and not name:
        raise _err("buyer.name", "Enter the buyer's registered name")
    return {k: v for k, v in {
        "name": name[:200] or None, "gstin": gstin, "state_code": state or None,
        "address": (str(raw.get("address") or "").strip()[:500] or None),
        "phone": (str(raw.get("phone") or (contact.phone if contact else "") or "").strip() or None),
        "email": (str(raw.get("email") or (contact.email if contact else "") or "").strip() or None),
    }.items() if v}


class InvoiceService:
    # ------------------------------------------------------------------ setup
    @staticmethod
    async def _setup(
        session: AsyncSession, business_id: uuid.UUID, *, register_id: uuid.UUID | None,
        location_id: uuid.UUID | None,
    ) -> tuple[InvoicingTaxProfile, InvoicingRegister, InvoicingRegistration]:
        profile = await session.get(InvoicingTaxProfile, business_id)
        if profile is None:
            raise ConflictError("Set up how you bill first: Settings → Tax & invoicing",
                                details={"needs": "tax_profile"})
        register: InvoicingRegister | None = None
        if register_id:
            register = await session.get(InvoicingRegister, register_id)
            if register is None or register.business_id != business_id:
                raise _err("register_id", "Choose one of your billing registers")
        elif location_id:
            register = await InvoicingSetupService.register_for_location(session, business_id, location_id)
        else:
            rows = list((await session.execute(
                select(InvoicingRegister).where(InvoicingRegister.business_id == business_id,
                                                InvoicingRegister.status == "active")
            )).scalars())
            if len(rows) > 1:
                raise _err("register_id", "Choose which register this bill is from")
            register = rows[0] if rows else None
        if register is None:
            raise ConflictError("Add a billing register for this location: Settings → Tax & invoicing",
                                details={"needs": "register"})
        if register.status != "active":
            raise _err("register_id", "That register is switched off")
        registration = await session.get(InvoicingRegistration, register.registration_id)
        assert registration is not None
        if registration.status != "active":
            raise ConflictError("The GST registration for this register is inactive")
        return profile, register, registration

    @staticmethod
    async def _seller(session: AsyncSession, business_id: uuid.UUID, reg: InvoicingRegistration,
                      location_id: uuid.UUID) -> dict[str, Any]:
        business = await session.get(Business, business_id)
        location = await session.get(BusinessLocation, location_id)
        addr = reg.address
        if not addr and location and isinstance(location.address, dict):
            a = location.address
            addr = ", ".join(str(a[k]) for k in ("line1", "line2", "city", "state", "postal_code") if a.get(k)) or None
        return {k: v for k, v in {
            "business_name": business.display_name if business else None,
            "legal_name": reg.legal_name, "trade_name": reg.trade_name, "gstin": reg.gstin,
            "scheme": reg.scheme, "state_code": reg.state_code, "address": addr,
            "declaration": reg.composition_declaration, "location_name": location.name if location else None,
            "phone": location.phone if location else None,
        }.items() if v is not None}

    @staticmethod
    def _place(reg: InvoicingRegistration, explicit: str | None, buyer: dict[str, Any],
               fallback: str | None) -> tuple[str | None, bool]:
        if reg.scheme == "unregistered":
            return None, True
        pos = (explicit or buyer.get("state_code") or fallback or reg.state_code)
        if pos not in STATES:
            raise _err("place_of_supply", "Choose the place of supply")
        return pos, pos == reg.state_code

    # ------------------------------------------------------------------ lines
    @staticmethod
    async def _manual_lines(session: AsyncSession, business_id: uuid.UUID, raw_lines: list[dict[str, Any]],
                            on: date) -> list[_Line]:
        if not raw_lines:
            raise _err("lines", "Add at least one line")
        if len(raw_lines) > 300:
            raise _err("lines", "At most 300 lines on one bill")
        out: list[_Line] = []
        for i, raw in enumerate(raw_lines):
            offering = variant = None
            if raw.get("offering_id"):
                offering = await session.get(Offering, uuid.UUID(str(raw["offering_id"])))
                if offering is None or offering.business_id != business_id or offering.deleted_at is not None:
                    raise _err(f"lines.{i}.offering_id", "That item is not in your catalogue")
                if raw.get("variant_id"):
                    variant = await session.get(OfferingVariant, uuid.UUID(str(raw["variant_id"])))
                    if variant is None or variant.offering_id != offering.id:
                        raise _err(f"lines.{i}.variant_id", "That option does not belong to the item")
            title = str(raw.get("title") or "").strip()
            if not title and offering:
                title = offering.title + (f" — {variant.name}" if variant else "")
            if not title:
                raise _err(f"lines.{i}.title", "Describe the line")
            try:
                quantity = Decimal(str(raw.get("quantity", 1))).quantize(_Q3)
            except Exception as exc:  # noqa: BLE001
                raise _err(f"lines.{i}.quantity", "Enter a quantity") from exc
            if quantity <= 0:
                raise _err(f"lines.{i}.quantity", "Quantity must be more than zero")
            price = raw.get("unit_price")
            stock_per_unit: int | None = None
            if offering is not None and raw.get("options"):
                # A pack or choices (§6.3): priced and sized by the catalogue.
                from platform_core.services.offering_pricing import price_selection

                priced = price_selection(offering, variant, raw.get("options"))
                if priced.title_suffix and not raw.get("title"):
                    title = f"{title} — {priced.title_suffix}"
                if price is None:
                    price = priced.unit_price
                stock_per_unit = priced.stock_per_unit
            if price is None and offering is not None:
                price = variant.price_amount if variant is not None and variant.price_amount is not None \
                    else offering.price_amount
            if price is None:
                raise _err(f"lines.{i}.unit_price", f"Enter a price for {title}")
            unit_price = money(dec(price))
            discount = money(dec(raw.get("discount") or 0))
            if unit_price < 0 or discount < 0:
                raise _err(f"lines.{i}.unit_price", "Prices and discounts cannot be negative")
            hsn = str(raw.get("hsn_sac") or (offering.hsn_sac if offering else "") or "").strip() or None
            if hsn and not (hsn.isdigit() and 2 <= len(hsn) <= 8):
                raise _err(f"lines.{i}.hsn_sac", "HSN/SAC codes are 2 to 8 digits")
            explicit = raw.get("rate")
            rate: Decimal | None = None
            if offering is None and explicit is not None and explicit != "":
                rate = dec(explicit)
                if not ZERO <= rate <= 100:
                    raise _err(f"lines.{i}.rate", "A rate between 0 and 100")
            unit_label = str(raw.get("unit_label") or "").strip()[:20] or _unit_label(offering)
            if stock_per_unit is not None:
                unit_label = "pack"
                if quantity != quantity.to_integral():
                    raise _err(f"lines.{i}.quantity", "Packs are sold whole")
                stock = int(quantity) * stock_per_unit if offering is not None and offering.track_inventory else 0
            else:
                stock = _stock_for(offering, quantity, unit_label)
            out.append(_Line(offering, variant.id if variant else None, None, None, title[:300], hsn, unit_label,
                             quantity, unit_price, discount, rate, stock))
        # Rates for catalogue lines (and free lines with only an HSN/SAC) come from data.
        need = [i for i, x in enumerate(out) if x.offering is not None or x.rate is None]
        resolved = await TaxRateService.resolve(session, business_id, [_rate_key(out[i]) for i in need], on)
        for i, rate in zip(need, resolved):
            out[i].rate = rate
        return out

    @staticmethod
    async def _order_lines(session: AsyncSession, business_id: uuid.UUID, order: SalesOrder,
                           on: date) -> list[_Line]:
        items = list((await session.execute(
            select(OrderLineItem).where(OrderLineItem.order_id == order.id).order_by(OrderLineItem.sort_order)
        )).scalars())
        offerings = {o.id: o for o in (await session.execute(
            select(Offering).where(Offering.id.in_([i.offering_id for i in items]))
        )).scalars()}
        out: list[_Line] = []
        for item in items:
            offering = offerings.get(item.offering_id)
            out.append(_Line(
                offering, item.variant_id, item.id, None, item.title, offering.hsn_sac if offering else None,
                _unit_label(offering), Decimal(item.quantity), money(dec(item.unit_price)), ZERO,
                dec(item.tax_rate) if item.tax_rate is not None else None, int(item.stock_quantity or 0),
            ))
        missing = [i for i, x in enumerate(out) if x.rate is None]
        if missing:
            resolved = await TaxRateService.resolve(session, business_id, [_rate_key(out[i]) for i in missing], on)
            for i, rate in zip(missing, resolved):
                out[i].rate = rate
        return out

    @staticmethod
    def _compute(lines: list[_Line], ctx: TaxContext, bill_discount: Any = ZERO) -> Bill:
        return compute([LineIn(x.quantity, x.unit_price, x.rate, x.discount) for x in lines], ctx,
                       bill_discount=bill_discount)

    @staticmethod
    def _apply(doc: InvoicingDocument, lines: list[_Line], bill: Bill) -> list[InvoicingDocumentLine]:
        doc.taxable_total = bill.taxable
        doc.cgst_total, doc.sgst_total, doc.igst_total = bill.cgst, bill.sgst, bill.igst
        doc.tax_total = bill.tax
        doc.round_off = bill.round_off
        doc.grand_total = bill.grand_total
        doc.amount_due = bill.amount_due
        rows = []
        for i, (x, out) in enumerate(zip(lines, bill.lines)):
            rows.append(InvoicingDocumentLine(
                business_id=doc.business_id, document_id=doc.id,
                offering_id=x.offering.id if x.offering else None, variant_id=x.variant_id,
                order_line_id=x.order_line_id, original_line_id=x.original_line_id, title=x.title,
                hsn_sac=x.hsn_sac, unit_label=x.unit_label, quantity=x.quantity, unit_price=x.unit_price,
                discount=out.discount, taxable_value=out.taxable, tax_rate=out.rate,
                cgst=out.cgst, sgst=out.sgst, igst=out.igst, line_total=out.total,
                stock_quantity=x.stock_quantity, sort_order=i,
            ))
        return rows

    @staticmethod
    def _lines_from_rows(rows: list[InvoicingDocumentLine], offerings: dict[uuid.UUID, Offering]) -> list[_Line]:
        return [_Line(offerings.get(r.offering_id) if r.offering_id else None, r.variant_id, r.order_line_id,
                      r.original_line_id, r.title, r.hsn_sac, r.unit_label, dec(r.quantity), dec(r.unit_price),
                      dec(r.discount), dec(r.tax_rate) if r.tax_rate is not None else None, r.stock_quantity)
                for r in rows]

    # ------------------------------------------------------------------ stock
    @staticmethod
    async def _move_stock(
        session: AsyncSession, doc: InvoicingDocument, rows: list[InvoicingDocumentLine], *, sign: int,
        movement_type: str, reason: str, actor_id: uuid.UUID, allow_short: bool = False,
    ) -> list[dict[str, Any]]:
        """Move stock for a bill's lines. A counter sale already happened, so it
        is never refused for a stale count (`allow_short`): stock goes to zero
        and the shortfall is returned so the team can recount."""
        from platform_core.services.inventory import InventoryService

        short: list[dict[str, Any]] = []
        for row in rows:
            if not row.offering_id or row.stock_quantity <= 0:
                continue
            offering = await session.get(Offering, row.offering_id)
            if offering is None or not offering.track_inventory:
                continue
            record = await InventoryService._get_or_create_record(
                session, business_id=doc.business_id, offering=offering, location_id=doc.location_id,
                variant_id=row.variant_id)
            delta = sign * row.stock_quantity
            before = InventoryService.serialize_record(record, offering=offering)
            available = record.quantity_on_hand - record.quantity_reserved
            if delta < 0 and allow_short and record.quantity_on_hand < -delta:
                short.append({"offering_id": str(offering.id), "title": offering.title,
                              "sold": -delta, "on_record": record.quantity_on_hand})
                delta = -record.quantity_on_hand
                if delta == 0:
                    continue
            elif delta < 0 and not allow_short and available < -delta:
                raise ValidationError(
                    f"Only {max(available, 0)} of {offering.title} in stock here — adjust stock or change the line",
                    details={"offering_id": str(offering.id), "available": available, "needed": -delta})
            record.quantity_on_hand += delta
            record.version += 1
            session.add(InventoryMovement(
                business_id=doc.business_id, offering_id=offering.id, variant_id=row.variant_id,
                location_id=doc.location_id, inventory_record_id=record.id, movement_type=movement_type,
                quantity_delta=delta, quantity_after=record.quantity_on_hand, reason=reason,
                actor_identity_id=actor_id,
            ))
            await session.flush()
            await InventoryService._publish_stock_events(
                session, business_id=doc.business_id, offering=offering, record=record, actor_id=actor_id,
                correlation_id=str(uuid.uuid4()), quantity_delta=delta, movement_type=movement_type, reason=reason,
                before_state=before, after_state=InventoryService.serialize_record(record, offering=offering))
        return short

    # ------------------------------------------------------------------ create
    @staticmethod
    async def create(
        session: AsyncSession, business_id: uuid.UUID, actor_id: uuid.UUID, payload: dict[str, Any],
    ) -> InvoicingDocument:
        """A bill raised directly (B2B, a service, a walk-in without an order)."""
        key = (str(payload.get("idempotency_key") or "").strip() or None)
        if key:
            found = (await session.execute(select(InvoicingDocument).where(
                InvoicingDocument.business_id == business_id, InvoicingDocument.idempotency_key == key))).scalars().first()
            if found:
                return found
        register_id = uuid.UUID(str(payload["register_id"])) if payload.get("register_id") else None
        profile, register, reg = await InvoiceService._setup(session, business_id, register_id=register_id,
                                                             location_id=None)
        contact = None
        if payload.get("customer_contact_id"):
            contact = await session.get(CustomerContact, uuid.UUID(str(payload["customer_contact_id"])))
            if contact is None or contact.business_id != business_id:
                raise _err("customer_contact_id", "Choose one of your customers")
        buyer = _clean_buyer(payload.get("buyer"), contact)
        location = await session.get(BusinessLocation, register.location_id)
        today = local_today(location.timezone if location else None)
        pos, intra = InvoiceService._place(reg, payload.get("place_of_supply"), buyer, None)
        reverse = bool(payload.get("reverse_charge"))
        if reverse and (reg.scheme != "regular" or not buyer.get("gstin")):
            raise _err("reverse_charge", "Reverse charge applies only to a registered buyer on a tax invoice")
        lines = await InvoiceService._manual_lines(session, business_id, list(payload.get("lines") or []), today)
        ctx = TaxContext(reg.scheme, profile.prices_include_tax, intra, profile.round_off, reverse)
        bill = InvoiceService._compute(lines, ctx, payload.get("bill_discount") or 0)
        due = payload.get("due_date")
        doc = InvoicingDocument(
            id=uuid.uuid4(), business_id=business_id, location_id=register.location_id, register_id=register.id,
            registration_id=reg.id, doc_kind=DOC_KIND_FOR_SCHEME[reg.scheme], status="draft", source="manual",
            customer_contact_id=contact.id if contact else None, buyer=buyer,
            seller=await InvoiceService._seller(session, business_id, reg, register.location_id),
            place_of_supply=pos, intra_state=intra if reg.scheme != "unregistered" else None,
            reverse_charge=reverse, prices_include_tax=profile.prices_include_tax,
            due_date=date.fromisoformat(due) if due else None,
            notes=(str(payload.get("notes") or "").strip()[:2000] or None), terms=profile.terms,
            idempotency_key=key, created_by=actor_id,
        )
        session.add(doc)
        await session.flush()
        for row in InvoiceService._apply(doc, lines, bill):
            session.add(row)
        await session.flush()
        if payload.get("issue", True):
            await InvoiceService.issue(session, business_id, doc.id, actor_id)
        return doc

    @staticmethod
    async def update_draft(
        session: AsyncSession, business_id: uuid.UUID, document_id: uuid.UUID, actor_id: uuid.UUID,
        payload: dict[str, Any],
    ) -> InvoicingDocument:
        doc = await InvoiceService.get(session, business_id, document_id)
        if doc.status != "draft":
            raise ConflictError("Only a draft can be edited; issued bills are corrected with a credit or debit note")
        profile, register, reg = await InvoiceService._setup(
            session, business_id,
            register_id=uuid.UUID(str(payload["register_id"])) if payload.get("register_id") else doc.register_id,
            location_id=None)
        contact = None
        cid = payload.get("customer_contact_id", str(doc.customer_contact_id) if doc.customer_contact_id else None)
        if cid:
            contact = await session.get(CustomerContact, uuid.UUID(str(cid)))
            if contact is None or contact.business_id != business_id:
                raise _err("customer_contact_id", "Choose one of your customers")
        buyer = _clean_buyer(payload.get("buyer", doc.buyer), contact)
        location = await session.get(BusinessLocation, register.location_id)
        today = local_today(location.timezone if location else None)
        pos, intra = InvoiceService._place(reg, payload.get("place_of_supply"), buyer, None)
        reverse = bool(payload.get("reverse_charge", doc.reverse_charge))
        if reverse and (reg.scheme != "regular" or not buyer.get("gstin")):
            raise _err("reverse_charge", "Reverse charge applies only to a registered buyer on a tax invoice")
        lines = await InvoiceService._manual_lines(session, business_id, list(payload.get("lines") or []), today)
        bill = InvoiceService._compute(lines, TaxContext(reg.scheme, profile.prices_include_tax, intra,
                                                         profile.round_off, reverse), payload.get("bill_discount") or 0)
        for old in (await session.execute(select(InvoicingDocumentLine).where(
                InvoicingDocumentLine.document_id == doc.id))).scalars():
            await session.delete(old)
        await session.flush()
        doc.register_id, doc.location_id, doc.registration_id = register.id, register.location_id, reg.id
        doc.doc_kind = DOC_KIND_FOR_SCHEME[reg.scheme]
        doc.customer_contact_id = contact.id if contact else None
        doc.buyer, doc.place_of_supply = buyer, pos
        doc.intra_state = intra if reg.scheme != "unregistered" else None
        doc.reverse_charge, doc.prices_include_tax = reverse, profile.prices_include_tax
        if "due_date" in payload:
            doc.due_date = date.fromisoformat(payload["due_date"]) if payload["due_date"] else None
        if "notes" in payload:
            doc.notes = str(payload.get("notes") or "").strip()[:2000] or None
        doc.seller = await InvoiceService._seller(session, business_id, reg, register.location_id)
        for row in InvoiceService._apply(doc, lines, bill):
            session.add(row)
        doc.version += 1
        doc.updated_at = datetime.now(timezone.utc)
        await session.flush()
        return doc

    @staticmethod
    async def delete_draft(session: AsyncSession, business_id: uuid.UUID, document_id: uuid.UUID) -> None:
        doc = await InvoiceService.get(session, business_id, document_id)
        if doc.status != "draft":
            raise ConflictError("Issued bills are never deleted; cancel it instead and it stays, marked cancelled")
        await session.delete(doc)
        await session.flush()

    @staticmethod
    async def from_order(
        session: AsyncSession, business_id: uuid.UUID, order_id: uuid.UUID, actor_id: uuid.UUID, *,
        register_id: uuid.UUID | None = None, place_of_supply: str | None = None,
        buyer: dict[str, Any] | None = None, reverse_charge: bool = False, actor_context: str = "business",
    ) -> InvoicingDocument:
        order = await session.get(SalesOrder, order_id)
        if order is None or order.business_id != business_id or order.deleted_at is not None:
            raise ResourceNotFound("Order")
        if order.status in ("cancelled", "rejected"):
            raise ConflictError("A cancelled or rejected order is not billed")
        live = (await session.execute(select(InvoicingDocument).where(
            InvoicingDocument.business_id == business_id, InvoicingDocument.order_id == order.id,
            InvoicingDocument.doc_kind.in_(INVOICE_KINDS), InvoicingDocument.status != "cancelled",
        ))).scalars().first()
        if live is not None:
            return live
        profile, register, reg = await InvoiceService._setup(session, business_id, register_id=register_id,
                                                             location_id=order.location_id)
        if register.location_id != order.location_id:
            raise _err("register_id", "Bill an order from a register at the order's location")
        contact = await session.get(CustomerContact, order.customer_contact_id) if order.customer_contact_id else None
        clean_buyer = _clean_buyer(buyer, contact)
        basis = dict(order.tax_basis or {})
        pos, intra = InvoiceService._place(reg, place_of_supply, clean_buyer, basis.get("place_of_supply"))
        if reverse_charge and (reg.scheme != "regular" or not clean_buyer.get("gstin")):
            raise _err("reverse_charge", "Reverse charge applies only to a registered buyer on a tax invoice")
        location = await session.get(BusinessLocation, order.location_id)
        today = local_today(location.timezone if location else None)
        lines = await InvoiceService._order_lines(session, business_id, order, today)
        # The order was priced by this engine: same basis → same amounts.
        inclusive = bool(basis.get("inclusive", False)) if basis else False
        round_off = bool(basis.get("round_off", profile.round_off)) if basis else profile.round_off
        ctx = TaxContext(reg.scheme, inclusive, intra, round_off, reverse_charge)
        bill = InvoiceService._compute(lines, ctx, order.discount_amount or 0)
        doc = InvoicingDocument(
            id=uuid.uuid4(), business_id=business_id, location_id=order.location_id, register_id=register.id,
            registration_id=reg.id, doc_kind=DOC_KIND_FOR_SCHEME[reg.scheme], status="draft", source="order",
            order_id=order.id, customer_contact_id=order.customer_contact_id, buyer=clean_buyer,
            seller=await InvoiceService._seller(session, business_id, reg, order.location_id),
            place_of_supply=pos, intra_state=intra if reg.scheme != "unregistered" else None,
            reverse_charge=reverse_charge, prices_include_tax=inclusive, currency=order.currency,
            terms=profile.terms, created_by=actor_id,
        )
        session.add(doc)
        await session.flush()
        for row in InvoiceService._apply(doc, lines, bill):
            session.add(row)
        await session.flush()
        await InvoiceService.issue(session, business_id, doc.id, actor_id, actor_context=actor_context,
                                   reresolve=False)
        return doc

    # ------------------------------------------------------------------ issue
    @staticmethod
    async def _allocate(session: AsyncSession, doc: InvoicingDocument, register: InvoicingRegister) -> None:
        fy = financial_year(doc.issue_date)
        if doc.doc_kind in INVOICE_KINDS:
            key, prefix, pad = f"inv:{register.id}", register.code, register.pad
        else:
            key = f"{'cn' if doc.doc_kind == 'credit_note' else 'dn'}:{doc.registration_id}"
            prefix, pad = ("CN" if doc.doc_kind == "credit_note" else "DN"), 5
        got = await NumberSeriesService.next(session, doc.business_id, series_key=key, period=fy, prefix=prefix,
                                             pad=pad)
        doc.series_key, doc.fy, doc.seq, doc.number = key, fy, got.value, got.number

    @staticmethod
    async def issue(
        session: AsyncSession, business_id: uuid.UUID, document_id: uuid.UUID, actor_id: uuid.UUID, *,
        actor_context: str = "business", reresolve: bool = True, issue_date: date | None = None,
        preset: tuple[str, str, int, str] | None = None,
    ) -> InvoicingDocument:
        """Number and issue a draft. `issue_date` is the day of sale for a counter
        bill rung up offline; `preset` (series, FY, value, number) is a number
        from the register's reserved block (§14.2)."""
        doc = await InvoiceService.get(session, business_id, document_id, lock=True)
        if doc.status != "draft":
            raise ConflictError("This bill is already issued")
        register = await session.get(InvoicingRegister, doc.register_id)
        reg = await session.get(InvoicingRegistration, doc.registration_id)
        assert register is not None and reg is not None
        location = await session.get(BusinessLocation, doc.location_id)
        doc.issue_date = issue_date or local_today(location.timezone if location else None)
        rows = list((await session.execute(select(InvoicingDocumentLine).where(
            InvoicingDocumentLine.document_id == doc.id).order_by(InvoicingDocumentLine.sort_order))).scalars())
        if reresolve and doc.source == "manual" and doc.doc_kind in INVOICE_KINDS:
            # A draft is priced at today's rates when it is issued.
            offerings = {o.id: o for o in (await session.execute(select(Offering).where(
                Offering.id.in_([r.offering_id for r in rows if r.offering_id])))).scalars()}
            lines = InvoiceService._lines_from_rows(rows, offerings)
            need = [i for i, x in enumerate(lines) if x.offering is not None or x.rate is None]
            got = await TaxRateService.resolve(session, business_id, [_rate_key(lines[i]) for i in need],
                                               doc.issue_date)
            for i, rate in zip(need, got):
                lines[i].rate = rate
            profile = await session.get(InvoicingTaxProfile, business_id)
            ctx = TaxContext(reg.scheme, doc.prices_include_tax, bool(doc.intra_state) or reg.scheme != "regular",
                             bool(profile.round_off) if profile else False, doc.reverse_charge)
            bill = InvoiceService._compute(lines, ctx)
            for old in rows:
                await session.delete(old)
            await session.flush()
            rows = InvoiceService._apply(doc, lines, bill)
            for row in rows:
                session.add(row)
            await session.flush()
        if reg.scheme == "regular" and doc.doc_kind == "tax_invoice":
            missing = [r.title for r in rows if r.tax_rate is None]
            if missing:
                raise ValidationError(
                    "Set a GST rate before billing: " + ", ".join(missing[:5])
                    + (" …" if len(missing) > 5 else "") + " (Money → Tax rates, or on the item)",
                    details={"missing_rates": missing, "needs": "tax_rates"})
        if doc.due_date is None and doc.doc_kind in INVOICE_KINDS and doc.source == "manual":
            profile = await session.get(InvoicingTaxProfile, business_id)
            if profile and profile.default_due_days:
                doc.due_date = doc.issue_date + timedelta(days=profile.default_due_days)
        doc.seller = await InvoiceService._seller(session, business_id, reg, doc.location_id)
        if preset is not None:
            doc.series_key, doc.fy, doc.seq, doc.number = preset
        else:
            await InvoiceService._allocate(session, doc, register)
        now = datetime.now(timezone.utc)
        doc.status, doc.issued_at, doc.issued_by = "issued", now, actor_id
        doc.public_token_hash = token_hash(share_token(business_id, doc.id))
        doc.version += 1
        doc.updated_at = now
        await session.flush()
        if doc.source in ("manual", "pos") and doc.doc_kind in INVOICE_KINDS:
            short = await InvoiceService._move_stock(
                session, doc, rows, sign=-1, movement_type="deduction", reason=f"Bill {doc.number}",
                actor_id=actor_id, allow_short=doc.source == "pos")
            if short:
                doc.pos_meta = {**(doc.pos_meta or {}), "stock_short": short}
                await session.flush()
        payload = InvoiceService._event_payload(doc)
        await OutboxService.publish(session, event_type="invoice.issued", business_id=business_id, payload=payload)
        await AuditService.record(session, event_type="invoice.issued", actor_identity_id=actor_id,
                                  actor_context=actor_context, action="issue", business_id=business_id,
                                  resource_type="invoice", resource_id=doc.id, after_state=payload)
        return doc

    @staticmethod
    def _event_payload(doc: InvoicingDocument) -> dict[str, Any]:
        return {
            "business_id": str(doc.business_id), "document_id": str(doc.id), "number": doc.number,
            "doc_kind": doc.doc_kind, "status": doc.status, "grand_total": _f(doc.grand_total),
            "amount_due": _f(doc.amount_due), "order_id": str(doc.order_id) if doc.order_id else None,
            "customer_contact_id": str(doc.customer_contact_id) if doc.customer_contact_id else None,
            "original_document_id": str(doc.original_document_id) if doc.original_document_id else None,
            "location_id": str(doc.location_id),
        }

    # ------------------------------------------------------------------ cancel
    @staticmethod
    async def cancel(
        session: AsyncSession, business_id: uuid.UUID, document_id: uuid.UUID, actor_id: uuid.UUID, reason: str,
        *, void: bool = False,
    ) -> InvoicingDocument:
        """Cancel an issued bill; it keeps its number. `void` is a counter bill
        cancelled at the counter: its money goes back to the customer there,
        so recorded payments stay (for the audit) and stop counting in the
        drawer."""
        reason = (reason or "").strip()
        if not reason:
            raise _err("reason", "Say why the bill is cancelled")
        doc = await InvoiceService.get(session, business_id, document_id, lock=True)
        if doc.status != "issued":
            raise ConflictError("Only an issued bill can be cancelled" if doc.status == "draft"
                                else "This bill is already cancelled")
        notes = (await session.execute(select(func.count()).select_from(InvoicingDocument).where(
            InvoicingDocument.original_document_id == doc.id, InvoicingDocument.status == "issued"))).scalar()
        if notes:
            raise ConflictError("Cancel the credit or debit notes raised against this bill first")
        paid = (await session.execute(select(func.count()).select_from(InvoicingPayment).where(
            InvoicingPayment.document_id == doc.id))).scalar()
        if paid and not (void and doc.source == "pos"):
            raise ConflictError("Money has been recorded against this bill; raise a credit note instead")
        rows = list((await session.execute(select(InvoicingDocumentLine).where(
            InvoicingDocumentLine.document_id == doc.id))).scalars())
        if doc.source in ("manual", "pos") and doc.doc_kind in INVOICE_KINDS:
            await InvoiceService._move_stock(session, doc, rows, sign=1, movement_type="reversal",
                                             reason=f"Bill {doc.number} cancelled", actor_id=actor_id)
        if doc.doc_kind == "credit_note" and doc.restock:
            await InvoiceService._move_stock(session, doc, rows, sign=-1, movement_type="deduction",
                                             reason=f"Credit note {doc.number} cancelled", actor_id=actor_id)
        now = datetime.now(timezone.utc)
        doc.status, doc.cancelled_at, doc.cancelled_by, doc.cancel_reason = "cancelled", now, actor_id, reason[:500]
        doc.version += 1
        doc.updated_at = now
        await session.flush()
        payload = InvoiceService._event_payload(doc) | {"reason": doc.cancel_reason}
        await OutboxService.publish(session, event_type="invoice.cancelled", business_id=business_id, payload=payload)
        await AuditService.record(session, event_type="invoice.cancelled", actor_identity_id=actor_id,
                                  actor_context="business", action="cancel", business_id=business_id,
                                  resource_type="invoice", resource_id=doc.id, after_state=payload, reason=reason)
        return doc

    # ------------------------------------------------------------------ notes
    @staticmethod
    async def note(
        session: AsyncSession, business_id: uuid.UUID, original_id: uuid.UUID, actor_id: uuid.UUID,
        payload: dict[str, Any],
    ) -> InvoicingDocument:
        kind = payload.get("kind")
        if kind not in NOTE_REASONS:
            raise _err("kind", "Choose a credit note or a debit note")
        reason = payload.get("reason")
        if reason not in NOTE_REASONS[kind]:
            raise _err("reason", "Choose why")
        original = await InvoiceService.get(session, business_id, original_id, lock=True)
        if original.status != "issued" or original.doc_kind not in INVOICE_KINDS:
            raise ConflictError("Notes are raised against an issued bill")
        rows = {r.id: r for r in (await session.execute(select(InvoicingDocumentLine).where(
            InvoicingDocumentLine.document_id == original.id))).scalars()}
        prior = list((await session.execute(
            select(InvoicingDocumentLine.original_line_id, InvoicingDocumentLine.quantity,
                   InvoicingDocumentLine.line_total, InvoicingDocument.doc_kind)
            .join(InvoicingDocument, InvoicingDocument.id == InvoicingDocumentLine.document_id)
            .where(InvoicingDocument.original_document_id == original.id, InvoicingDocument.status == "issued")
        )).all())
        raw_lines = list(payload.get("lines") or [])
        if not raw_lines:
            raise _err("lines", "Choose at least one line")
        lines: list[_Line] = []
        for i, raw in enumerate(raw_lines):
            try:
                orig = rows[uuid.UUID(str(raw.get("original_line_id")))]
            except (KeyError, ValueError) as exc:
                raise _err(f"lines.{i}.original_line_id", "That line is not on the bill") from exc
            offering = await session.get(Offering, orig.offering_id) if orig.offering_id else None
            oq = dec(orig.quantity)
            if kind == "credit_note" and reason == "return":
                qty = dec(raw.get("quantity") or 0).quantize(_Q3)
                returned = sum((dec(q) for lid, q, _, k in prior if lid == orig.id and k == "credit_note"), ZERO)
                if qty <= 0 or qty > oq - returned:
                    raise _err(f"lines.{i}.quantity", f"Up to {_qty(oq - returned)} of {orig.title} can come back")
                disc = money(dec(orig.discount) * qty / oq)
                stock = int((Decimal(orig.stock_quantity) * qty / oq).to_integral_value())
                lines.append(_Line(offering, orig.variant_id, None, orig.id, orig.title, orig.hsn_sac,
                                   orig.unit_label, qty, dec(orig.unit_price), disc,
                                   dec(orig.tax_rate) if orig.tax_rate is not None else None, stock))
            else:
                amount = money(dec(raw.get("amount") or 0))
                if amount <= 0:
                    raise _err(f"lines.{i}.amount", "Enter the amount")
                lines.append(_Line(offering, orig.variant_id, None, orig.id, orig.title, orig.hsn_sac,
                                   orig.unit_label, Decimal(1), amount, ZERO,
                                   dec(orig.tax_rate) if orig.tax_rate is not None else None, 0))
        reg = await session.get(InvoicingRegistration, original.registration_id)
        assert reg is not None
        scheme = str((original.seller or {}).get("scheme") or reg.scheme)
        ctx = TaxContext(scheme, original.prices_include_tax, original.intra_state is not False, False,
                         original.reverse_charge)
        bill = InvoiceService._compute(lines, ctx)
        if kind == "credit_note":
            for line, out in zip(lines, bill.lines):
                assert line.original_line_id is not None
                orig = rows[line.original_line_id]
                credited = sum((dec(t) for lid, _, t, k in prior if lid == orig.id and k == "credit_note"), ZERO)
                if credited + out.total > dec(orig.line_total) + Decimal("0.01"):
                    raise _err("lines", f"Credit for {orig.title} would exceed what was billed "
                                        f"({_inr(dec(orig.line_total) - credited)} left)")
        doc = InvoicingDocument(
            id=uuid.uuid4(), business_id=business_id, location_id=original.location_id,
            register_id=original.register_id, registration_id=original.registration_id, doc_kind=kind,
            status="draft", source=original.source, order_id=original.order_id, original_document_id=original.id,
            note_reason=reason, restock=bool(payload.get("restock")) and kind == "credit_note" and reason == "return",
            customer_contact_id=original.customer_contact_id, buyer=original.buyer, seller=original.seller,
            place_of_supply=original.place_of_supply, intra_state=original.intra_state,
            reverse_charge=original.reverse_charge, prices_include_tax=original.prices_include_tax,
            currency=original.currency, notes=(str(payload.get("notes") or "").strip()[:2000] or None),
            created_by=actor_id,
        )
        session.add(doc)
        await session.flush()
        new_rows = InvoiceService._apply(doc, lines, bill)
        for row in new_rows:
            session.add(row)
        await session.flush()
        register = await session.get(InvoicingRegister, doc.register_id)
        assert register is not None
        location = await session.get(BusinessLocation, doc.location_id)
        doc.issue_date = local_today(location.timezone if location else None)
        await InvoiceService._allocate(session, doc, register)
        now = datetime.now(timezone.utc)
        doc.status, doc.issued_at, doc.issued_by = "issued", now, actor_id
        doc.public_token_hash = token_hash(share_token(business_id, doc.id))
        await session.flush()
        if doc.restock:
            await InvoiceService._move_stock(session, doc, new_rows, sign=1, movement_type="reversal",
                                             reason=f"Returned — credit note {doc.number}", actor_id=actor_id)
        event = InvoiceService._event_payload(doc)
        await OutboxService.publish(session, event_type="invoice.issued", business_id=business_id, payload=event)
        await AuditService.record(session, event_type="invoice.issued", actor_identity_id=actor_id,
                                  actor_context="business", action=f"issue_{kind}", business_id=business_id,
                                  resource_type="invoice", resource_id=doc.id, after_state=event)
        return doc

    # ------------------------------------------------------------------ payments
    @staticmethod
    async def record_payment(
        session: AsyncSession, business_id: uuid.UUID, document_id: uuid.UUID, actor_id: uuid.UUID,
        payload: dict[str, Any],
    ) -> InvoicingPayment:
        doc = await InvoiceService.get(session, business_id, document_id, lock=True)
        if doc.status != "issued" or doc.doc_kind == "credit_note":
            raise ConflictError("Money is recorded against an issued bill or debit note")
        summary = await InvoiceService._money_view(session, doc)
        amount = money(dec(payload.get("amount") or 0))
        if amount <= 0:
            raise _err("amount", "Enter the amount received")
        if amount > dec(summary["outstanding"]):
            raise _err("amount", f"Only {_inr(summary['outstanding'])} is outstanding on this bill")
        method = payload.get("method")
        if method not in PAYMENT_METHODS:
            raise _err("method", "Choose how it was paid")
        location = await session.get(BusinessLocation, doc.location_id)
        today = local_today(location.timezone if location else None)
        received = date.fromisoformat(payload["received_on"]) if payload.get("received_on") else today
        if received > today:
            raise _err("received_on", "The date cannot be in the future")
        row = InvoicingPayment(business_id=business_id, document_id=doc.id, amount=amount, method=method,
                               reference=(str(payload.get("reference") or "").strip()[:120] or None),
                               received_on=received, recorded_by=actor_id)
        session.add(row)
        doc.amount_paid = dec(doc.amount_paid) + amount
        doc.version += 1
        doc.updated_at = datetime.now(timezone.utc)
        await session.flush()
        event = InvoiceService._event_payload(doc) | {"amount": _f(amount), "method": method}
        await OutboxService.publish(session, event_type="invoice.payment_recorded", business_id=business_id,
                                    payload=event)
        if dec(summary["outstanding"]) - amount <= 0:
            await OutboxService.publish(session, event_type="invoice.paid", business_id=business_id, payload=event)
        await AuditService.record(session, event_type="invoice.payment_recorded", actor_identity_id=actor_id,
                                  actor_context="business", action="record_payment", business_id=business_id,
                                  resource_type="invoice", resource_id=doc.id, after_state=event)
        return row

    # ------------------------------------------------------------------ reads
    @staticmethod
    async def get(session: AsyncSession, business_id: uuid.UUID, document_id: uuid.UUID, *,
                  lock: bool = False) -> InvoicingDocument:
        q = select(InvoicingDocument).where(InvoicingDocument.business_id == business_id,
                                            InvoicingDocument.id == document_id)
        if lock:
            q = q.with_for_update()
        doc = (await session.execute(q)).scalars().first()
        if doc is None:
            raise ResourceNotFound("Bill")
        return doc

    @staticmethod
    async def _money_view(session: AsyncSession, doc: InvoicingDocument) -> dict[str, Any]:
        credits = ZERO
        if doc.doc_kind in INVOICE_KINDS:
            credits = dec((await session.execute(select(func.coalesce(func.sum(InvoicingDocument.amount_due), 0)).where(
                InvoicingDocument.original_document_id == doc.id, InvoicingDocument.doc_kind == "credit_note",
                InvoicingDocument.status == "issued"))).scalar())
        order_paid = False
        if doc.order_id:
            status = (await session.execute(select(SalesOrder.payment_status).where(
                SalesOrder.id == doc.order_id))).scalar()
            order_paid = status == "paid"
        return InvoiceService._payment_state(doc, credits, order_paid)

    @staticmethod
    def _payment_state(doc: InvoicingDocument, credits: Decimal, order_paid: bool) -> dict[str, Any]:
        due = dec(doc.amount_due)
        if doc.doc_kind == "credit_note" or doc.status != "issued":
            return {"payment_status": "not_applicable", "outstanding": 0.0, "credited": _f(credits),
                    "paid_via_order": False}
        outstanding = ZERO if order_paid else max(ZERO, due - dec(doc.amount_paid) - credits)
        paid = order_paid or outstanding <= 0
        state = "paid" if paid else ("part_paid" if dec(doc.amount_paid) > 0 or credits > 0 else "unpaid")
        return {"payment_status": state, "outstanding": _f(outstanding), "credited": _f(credits),
                "paid_via_order": order_paid}

    @staticmethod
    def serialize(doc: InvoicingDocument, money_view: dict[str, Any], *, order_number: str | None = None,
                  today: date | None = None) -> dict[str, Any]:
        overdue = bool(doc.due_date and money_view["payment_status"] in ("unpaid", "part_paid")
                       and doc.due_date < (today or local_today()))
        return {
            "id": str(doc.id), "doc_kind": doc.doc_kind, "kind_label": KIND_LABEL[doc.doc_kind],
            "status": doc.status, "number": doc.number, "fy": doc.fy,
            "issue_date": doc.issue_date.isoformat() if doc.issue_date else None,
            "due_date": doc.due_date.isoformat() if doc.due_date else None, "overdue": overdue,
            "source": doc.source, "order_id": str(doc.order_id) if doc.order_id else None,
            "order_number": order_number,
            "original_document_id": str(doc.original_document_id) if doc.original_document_id else None,
            "note_reason": doc.note_reason, "restock": doc.restock,
            "customer_contact_id": str(doc.customer_contact_id) if doc.customer_contact_id else None,
            "buyer": doc.buyer, "seller": doc.seller, "place_of_supply": doc.place_of_supply,
            "place_of_supply_label": state_label(doc.place_of_supply), "intra_state": doc.intra_state,
            "reverse_charge": doc.reverse_charge, "prices_include_tax": doc.prices_include_tax,
            "currency": doc.currency, "location_id": str(doc.location_id), "register_id": str(doc.register_id),
            "taxable_total": _f(doc.taxable_total), "cgst_total": _f(doc.cgst_total),
            "sgst_total": _f(doc.sgst_total), "igst_total": _f(doc.igst_total), "tax_total": _f(doc.tax_total),
            "round_off": _f(doc.round_off), "grand_total": _f(doc.grand_total), "amount_due": _f(doc.amount_due),
            "amount_paid": _f(doc.amount_paid), **money_view,
            "notes": doc.notes, "terms": doc.terms,
            "issued_at": doc.issued_at.isoformat() if doc.issued_at else None,
            "cancelled_at": doc.cancelled_at.isoformat() if doc.cancelled_at else None,
            "cancel_reason": doc.cancel_reason, "version": doc.version,
            "created_at": doc.created_at.isoformat() if doc.created_at else None,
        }

    @staticmethod
    async def list_documents(
        session: AsyncSession, business_id: uuid.UUID, *, kind: str | None = None, status: str | None = None,
        payment: str | None = None, q: str | None = None, order_id: uuid.UUID | None = None,
        customer_contact_id: uuid.UUID | None = None, date_from: date | None = None, date_to: date | None = None,
        limit: int = 100, offset: int = 0,
    ) -> list[dict[str, Any]]:
        credit = (select(InvoicingDocument.original_document_id.label("oid"),
                         func.sum(InvoicingDocument.amount_due).label("credited"))
                  .where(InvoicingDocument.business_id == business_id, InvoicingDocument.doc_kind == "credit_note",
                         InvoicingDocument.status == "issued")
                  .group_by(InvoicingDocument.original_document_id).subquery())
        query = (select(InvoicingDocument, SalesOrder.order_number, SalesOrder.payment_status,
                        func.coalesce(credit.c.credited, 0))
                 .outerjoin(SalesOrder, SalesOrder.id == InvoicingDocument.order_id)
                 .outerjoin(credit, credit.c.oid == InvoicingDocument.id)
                 .where(InvoicingDocument.business_id == business_id))
        if kind == "invoices":
            query = query.where(InvoicingDocument.doc_kind.in_(INVOICE_KINDS))
        elif kind == "notes":
            query = query.where(InvoicingDocument.doc_kind.in_(("credit_note", "debit_note")))
        elif kind:
            query = query.where(InvoicingDocument.doc_kind == kind)
        if status:
            query = query.where(InvoicingDocument.status == status)
        if order_id:
            query = query.where(InvoicingDocument.order_id == order_id)
        if customer_contact_id:
            query = query.where(InvoicingDocument.customer_contact_id == customer_contact_id)
        if date_from:
            query = query.where(InvoicingDocument.issue_date >= date_from)
        if date_to:
            query = query.where(InvoicingDocument.issue_date <= date_to)
        if q:
            like = f"%{q.strip()}%"
            query = query.where(or_(InvoicingDocument.number.ilike(like),
                                    InvoicingDocument.buyer["name"].astext.ilike(like),
                                    InvoicingDocument.buyer["gstin"].astext.ilike(like),
                                    SalesOrder.order_number.ilike(like)))
        if payment in ("unpaid", "overdue"):
            query = query.where(
                InvoicingDocument.status == "issued", InvoicingDocument.doc_kind != "credit_note",
                or_(SalesOrder.payment_status.is_(None), SalesOrder.payment_status != "paid"),
                InvoicingDocument.amount_due - InvoicingDocument.amount_paid - func.coalesce(credit.c.credited, 0) > 0)
            if payment == "overdue":
                query = query.where(InvoicingDocument.due_date < local_today())
        query = query.order_by(InvoicingDocument.issue_date.desc().nulls_first(),
                               InvoicingDocument.created_at.desc()).limit(limit).offset(offset)
        today = local_today()
        out = []
        for doc, order_number, order_payment, credited in (await session.execute(query)).all():
            view = InvoiceService._payment_state(doc, dec(credited), order_payment == "paid")
            out.append(InvoiceService.serialize(doc, view, order_number=order_number, today=today))
        return out

    @staticmethod
    async def detail(session: AsyncSession, business_id: uuid.UUID, document_id: uuid.UUID) -> dict[str, Any]:
        doc = await InvoiceService.get(session, business_id, document_id)
        view = await InvoiceService._money_view(session, doc)
        order_number = None
        if doc.order_id:
            order_number = (await session.execute(select(SalesOrder.order_number).where(
                SalesOrder.id == doc.order_id))).scalar()
        data = InvoiceService.serialize(doc, view, order_number=order_number)
        rows = list((await session.execute(select(InvoicingDocumentLine).where(
            InvoicingDocumentLine.document_id == doc.id).order_by(InvoicingDocumentLine.sort_order))).scalars())
        returned: dict[uuid.UUID, Decimal] = {}
        credited: dict[uuid.UUID, Decimal] = {}
        if doc.doc_kind in INVOICE_KINDS:
            for lid, q, t in (await session.execute(
                select(InvoicingDocumentLine.original_line_id, InvoicingDocumentLine.quantity,
                       InvoicingDocumentLine.line_total)
                .join(InvoicingDocument, InvoicingDocument.id == InvoicingDocumentLine.document_id)
                .where(InvoicingDocument.original_document_id == doc.id, InvoicingDocument.status == "issued",
                       InvoicingDocument.doc_kind == "credit_note", InvoicingDocument.note_reason == "return")
            )).all():
                returned[lid] = returned.get(lid, ZERO) + dec(q)
            for lid, t in (await session.execute(
                select(InvoicingDocumentLine.original_line_id, InvoicingDocumentLine.line_total)
                .join(InvoicingDocument, InvoicingDocument.id == InvoicingDocumentLine.document_id)
                .where(InvoicingDocument.original_document_id == doc.id, InvoicingDocument.status == "issued",
                       InvoicingDocument.doc_kind == "credit_note")
            )).all():
                credited[lid] = credited.get(lid, ZERO) + dec(t)
        data["lines"] = [{
            "id": str(r.id), "offering_id": str(r.offering_id) if r.offering_id else None, "title": r.title,
            "hsn_sac": r.hsn_sac, "unit_label": r.unit_label, "quantity": _f(r.quantity),
            "unit_price": _f(r.unit_price), "discount": _f(r.discount), "taxable_value": _f(r.taxable_value),
            "tax_rate": _f(r.tax_rate) if r.tax_rate is not None else None, "cgst": _f(r.cgst), "sgst": _f(r.sgst),
            "igst": _f(r.igst), "line_total": _f(r.line_total), "stock_quantity": r.stock_quantity,
            "returnable_quantity": _f(dec(r.quantity) - returned.get(r.id, ZERO)),
            "creditable_amount": _f(dec(r.line_total) - credited.get(r.id, ZERO)),
        } for r in rows]
        data["payments"] = [{
            "id": str(p.id), "amount": _f(p.amount), "method": p.method, "method_label": PAYMENT_METHODS[p.method],
            "reference": p.reference, "received_on": p.received_on.isoformat(),
        } for p in (await session.execute(select(InvoicingPayment).where(
            InvoicingPayment.document_id == doc.id).order_by(InvoicingPayment.received_on))).scalars()]
        related = (await session.execute(select(InvoicingDocument).where(
            InvoicingDocument.business_id == business_id,
            or_(InvoicingDocument.original_document_id == doc.id,
                and_(InvoicingDocument.id == doc.original_document_id)) if doc.original_document_id
            else InvoicingDocument.original_document_id == doc.id,
        ).order_by(InvoicingDocument.created_at))).scalars()
        data["related"] = [{"id": str(r.id), "kind_label": KIND_LABEL[r.doc_kind], "number": r.number,
                            "status": r.status, "amount_due": _f(r.amount_due),
                            "issue_date": r.issue_date.isoformat() if r.issue_date else None} for r in related]
        data["tax_by_rate"] = InvoiceService._tax_by_rate(rows)
        return data

    @staticmethod
    def _tax_by_rate(rows: list[InvoicingDocumentLine]) -> list[dict[str, Any]]:
        groups: dict[Decimal, dict[str, Decimal]] = {}
        for r in rows:
            if r.tax_rate is None:
                continue
            g = groups.setdefault(dec(r.tax_rate), {"taxable": ZERO, "cgst": ZERO, "sgst": ZERO, "igst": ZERO})
            g["taxable"] += dec(r.taxable_value)
            g["cgst"] += dec(r.cgst)
            g["sgst"] += dec(r.sgst)
            g["igst"] += dec(r.igst)
        return [{"rate": _f(k), **{n: _f(v) for n, v in g.items()}} for k, g in sorted(groups.items())]

    # ------------------------------------------------------------------ documents
    @staticmethod
    async def spec(session: AsyncSession, business_id: uuid.UUID, document_id: uuid.UUID,
                   *, thermal: bool = False) -> DocSpec:
        d = await InvoiceService.detail(session, business_id, document_id)
        return build_spec(d, thermal=thermal)

    @staticmethod
    async def pdf(session: AsyncSession, business_id: uuid.UUID, document_id: uuid.UUID, layout: str,
                  actor_id: uuid.UUID | None) -> tuple[bytes, dict[str, Any]]:
        from platform_core.services.documents_store import DocumentStore

        if layout not in ("a4", "thermal_80", "thermal_58"):
            raise _err("layout", "Choose A4, 80 mm or 58 mm")
        doc = await InvoiceService.get(session, business_id, document_id)
        spec = await InvoiceService.spec(session, business_id, document_id, thermal=layout != "a4")
        stored = await DocumentStore.store(session, business_id, doc_type=doc.doc_kind, source_type="invoice",
                                           source_id=doc.id, spec=spec, layout=layout, actor_id=actor_id)
        content, meta = await DocumentStore.fetch(session, business_id, uuid.UUID(stored["id"]))
        return content, meta | {"number": doc.number or "draft"}

    @staticmethod
    async def share(session: AsyncSession, business_id: uuid.UUID, document_id: uuid.UUID) -> dict[str, Any]:
        doc = await InvoiceService.get(session, business_id, document_id)
        if doc.status == "draft":
            raise ConflictError("Issue the bill before sharing it")
        token = share_token(business_id, doc.id)
        if doc.public_token_hash != token_hash(token):
            doc.public_token_hash = token_hash(token)  # the signing secret was rotated
            await session.flush()
        business = await session.get(Business, business_id)
        name = (doc.seller or {}).get("trade_name") or (business.display_name if business else "")
        slug = business.slug if business else ""
        return {"token": token, "path": f"/{slug}/bill/{token}", "business_name": name,
                "phone": (doc.buyer or {}).get("phone"),
                "message": f"Your bill from {name}: {KIND_LABEL[doc.doc_kind]} {doc.number} for "
                           f"{_inr(doc.amount_due)}."}


# ---------------------------------------------------------------------- the PDF
def build_spec(d: dict[str, Any], *, thermal: bool = False) -> DocSpec:
    """The printed bill. Every figure was computed and stored at issue; this
    only lays it out. A bill of supply and a bill never carry a tax line."""
    seller = d.get("seller") or {}
    buyer = d.get("buyer") or {}
    kind = d["doc_kind"]
    gst_doc = kind == "tax_invoice" or (kind in ("credit_note", "debit_note") and seller.get("scheme") == "regular")
    issuer = [seller.get("trade_name") or seller.get("legal_name") or seller.get("business_name") or ""]
    if seller.get("trade_name") and seller.get("legal_name") and seller["legal_name"] != seller["trade_name"]:
        issuer.append(seller["legal_name"])
    if seller.get("address"):
        issuer.append(seller["address"])
    if seller.get("gstin") and seller.get("scheme") != "unregistered":
        issuer.append(f"GSTIN {seller['gstin']} · {state_label(seller.get('state_code'))}")
    if seller.get("phone"):
        issuer.append(f"Phone {seller['phone']}")
    party = [x for x in (buyer.get("name"), buyer.get("address")) if x]
    if buyer.get("gstin") and seller.get("scheme") != "unregistered":
        party.append(f"GSTIN {buyer['gstin']}")
    if buyer.get("state_code") and seller.get("scheme") != "unregistered":
        party.append(state_label(buyer["state_code"]))
    if buyer.get("phone") and not buyer.get("gstin"):
        party.append(buyer["phone"])
    meta: list[tuple[str, str]] = []
    if seller.get("scheme") != "unregistered" and d.get("place_of_supply"):
        meta.append(("Place of supply", d["place_of_supply_label"]))
    if kind == "tax_invoice":
        meta.append(("Reverse charge", "Yes" if d.get("reverse_charge") else "No"))
    original = next((r for r in d.get("related", []) if kind in ("credit_note", "debit_note")), None)
    if original and original.get("number"):
        meta.append(("Against", f"{original['kind_label']} {original['number']} of {_date(original['issue_date'])}"))
    if d.get("note_reason"):
        meta.append(("Reason", NOTE_REASONS.get(kind, {}).get(d["note_reason"], d["note_reason"])))
    if d.get("order_number"):
        meta.append(("Order", d["order_number"]))
    if d.get("due_date") and kind in INVOICE_KINDS:
        meta.append(("Due", _date(d["due_date"])))

    intra = d.get("intra_state") is not False
    rows: list[list[str]] = []
    if thermal:
        columns, align = ["Item", "Qty", "Amount"], ["l", "r", "r"]
        for ln in d["lines"]:
            label = ln["title"] + (f" · {ln['tax_rate']:g}%" if gst_doc and ln["tax_rate"] is not None else "")
            rows.append([label, _qty(ln["quantity"]), _inr(ln["line_total"])])
    elif gst_doc:
        tax_cols = ["CGST", "SGST"] if intra else ["IGST"]
        columns = ["Item", "HSN/SAC", "Qty", "Rate", "Taxable", "GST %"] + tax_cols + ["Amount"]
        align = ["l", "l", "r", "r", "r", "r"] + ["r"] * len(tax_cols) + ["r"]
        for ln in d["lines"]:
            taxes = [_inr(ln["cgst"]), _inr(ln["sgst"])] if intra else [_inr(ln["igst"])]
            rows.append([ln["title"], ln["hsn_sac"] or "", _qty(ln["quantity"]) + (f" {ln['unit_label']}" if ln["unit_label"] else ""),
                         _inr(ln["unit_price"]), _inr(ln["taxable_value"]),
                         f"{ln['tax_rate']:g}" if ln["tax_rate"] is not None else "—"] + taxes + [_inr(ln["line_total"])])
    else:
        columns, align = ["Item", "Qty", "Rate", "Amount"], ["l", "r", "r", "r"]
        for ln in d["lines"]:
            rows.append([ln["title"], _qty(ln["quantity"]) + (f" {ln['unit_label']}" if ln["unit_label"] else ""),
                         _inr(ln["unit_price"]), _inr(ln["line_total"])])

    totals: list[tuple[str, str]] = []
    discount = sum(dec(ln["discount"]) for ln in d["lines"])
    if gst_doc:
        totals.append(("Taxable value", _inr(d["taxable_total"])))
        suffix = " (payable by the recipient — reverse charge)" if d.get("reverse_charge") else ""
        if intra:
            totals += [(f"CGST{suffix}", _inr(d["cgst_total"])), (f"SGST{suffix}", _inr(d["sgst_total"]))]
        else:
            totals.append((f"IGST{suffix}", _inr(d["igst_total"])))
    elif discount > 0:
        totals.append(("Discount", _inr(-discount)))
    if dec(d["round_off"]) != 0:
        totals.append(("Round-off", _inr(d["round_off"])))
    label = "Credit" if kind == "credit_note" else "Total" if not d.get("reverse_charge") else "Amount payable"
    totals.append((label, _inr(d["amount_due"])))

    notes: list[str] = []
    if kind == "bill_of_supply" and seller.get("declaration"):
        notes.append(seller["declaration"])
    if kind == "tax_invoice" and d.get("prices_include_tax"):
        notes.append("Prices include GST.")
    if gst_doc and not thermal and len(d.get("tax_by_rate", [])) > 1:
        for g in d["tax_by_rate"]:
            tax = g["cgst"] + g["sgst"] + g["igst"]
            notes.append(f"GST {g['rate']:g}%: taxable {_inr(g['taxable'])}, tax {_inr(tax)}")
    if d.get("notes"):
        notes.append(d["notes"])
    if d.get("terms") and kind in INVOICE_KINDS:
        notes.append(d["terms"])
    banner = "CANCELLED" if d["status"] == "cancelled" else ("DRAFT — not a valid bill" if d["status"] == "draft" else "")
    return DocSpec(
        title=KIND_LABEL[kind], issuer=issuer, number=d.get("number") or "", date=_date(d.get("issue_date")),
        party_label="Bill to" if kind in INVOICE_KINDS else "Customer", party=party, meta=meta, columns=columns,
        align=align, rows=rows, totals=totals, notes=notes, status_banner=banner,
    )


def _date(value: str | None) -> str:
    if not value:
        return ""
    return date.fromisoformat(value[:10]).strftime("%d %b %Y")


async def public_bill(session: AsyncSession, slug: str, token: str) -> dict[str, Any]:
    """What the customer's link shows: the bill as issued, nothing else.

    The token is the credential (read through the bill-token RLS arm). The
    request is never bound to the business as a tenant; only the business's
    slug is read, transaction-locally, to check the link names the right shop
    — a private business with no website still has bills."""
    if not 16 <= len(token) <= 64:
        raise ResourceNotFound("Bill")
    digest = token_hash(token)
    await session.execute(text("SELECT set_config('app.current_bill_token', :h, true)"), {"h": digest})
    doc = (await session.execute(select(InvoicingDocument).where(
        InvoicingDocument.public_token_hash == digest).execution_options(skip_location_scope=True))).scalars().first()
    if doc is None or doc.status == "draft":
        raise ResourceNotFound("Bill")
    await session.execute(text("SELECT set_config('app.current_business_id', :b, true)"), {"b": str(doc.business_id)})
    owner_slug = (await session.execute(text("SELECT slug FROM businesses WHERE id = :b"),
                                        {"b": str(doc.business_id)})).scalar()
    await session.execute(text("SELECT set_config('app.current_business_id', '', true)"))
    if owner_slug != slug:
        raise ResourceNotFound("Bill")
    rows = list((await session.execute(select(InvoicingDocumentLine).where(
        InvoicingDocumentLine.document_id == doc.id).order_by(InvoicingDocumentLine.sort_order))).scalars())
    original = None
    if doc.original_document_id:
        o = await session.get(InvoicingDocument, doc.original_document_id)
        if o is not None:
            original = {"id": str(o.id), "kind_label": KIND_LABEL[o.doc_kind], "number": o.number,
                        "status": o.status, "amount_due": _f(o.amount_due),
                        "issue_date": o.issue_date.isoformat() if o.issue_date else None}
    view = {"payment_status": "not_applicable", "outstanding": 0.0, "credited": 0.0, "paid_via_order": False}
    data = InvoiceService.serialize(doc, view)
    for private in ("customer_contact_id", "register_id", "location_id", "order_id", "version", "created_at"):
        data.pop(private, None)
    data["lines"] = [{
        "id": str(r.id), "title": r.title, "hsn_sac": r.hsn_sac, "unit_label": r.unit_label,
        "quantity": _f(r.quantity), "unit_price": _f(r.unit_price), "discount": _f(r.discount),
        "taxable_value": _f(r.taxable_value), "tax_rate": _f(r.tax_rate) if r.tax_rate is not None else None,
        "cgst": _f(r.cgst), "sgst": _f(r.sgst), "igst": _f(r.igst), "line_total": _f(r.line_total),
    } for r in rows]
    data["related"] = [original] if original else []
    data["tax_by_rate"] = InvoiceService._tax_by_rate(rows)
    return data
