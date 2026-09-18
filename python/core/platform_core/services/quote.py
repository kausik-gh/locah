"""Quotations — issuing a commercial offer and holding the business to it.

The rule everything else follows from: once a quote is issued, it is a record of
what the customer was actually sent, and nothing may change it. Editing is a
draft-only operation. A change after issue produces a revision — a new row
carrying the same number with a higher revision — and the old one is marked
superseded with its figures untouched.

That is also why every line stores its own title, price and tax rate rather than
joining to the catalogue. A business that raises its prices on Monday has not
raised the price of the quote it sent on Friday.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.exceptions import ConflictError, ResourceNotFound, ValidationError
from platform_core.gates import assert_business_mutable
from platform_core.models import Quote, QuoteCharge, QuoteItem
from platform_core.resolvers.customer_resolver import CustomerResolver
from platform_core.resolvers.offering_resolver import OfferingResolver
from platform_core.services.audit import AuditService
from platform_core.services.business import BusinessService
from platform_core.services.outbox import OutboxService
from platform_core.services.quote_calculation import calculate_quote

# Only a draft can be changed. Everything else is a record of something that was
# already communicated.
EDITABLE_STATUSES = frozenset({"draft"})
# States a customer can still act on.
OPEN_STATUSES = frozenset({"issued"})
TERMINAL_STATUSES = frozenset({"accepted", "rejected", "expired", "cancelled", "superseded"})

SHARE_TOKEN_DAYS = 120
TITLE_MAX = 200
TERMS_MAX = 20000


def _money_str(value: Any) -> str:
    return str(Decimal(str(value or 0)).quantize(Decimal("0.01")))


class QuoteService:
    # ------------------------------------------------------------- reading

    @staticmethod
    def effective_status(quote: Quote, *, now: datetime | None = None) -> str:
        """The status a reader should see, accounting for time passing.

        An issued quote whose validity has run out is expired whether or not a
        sweep has got to it yet. Computing it here means the API never shows a
        customer an offer the business is no longer bound by, even if the worker
        is behind.
        """
        if quote.status != "issued" or quote.valid_until is None:
            return str(quote.status)
        moment = now or datetime.now(timezone.utc)
        return "expired" if quote.valid_until <= moment else "issued"

    @staticmethod
    def serialize(
        quote: Quote,
        items: list[QuoteItem] | None = None,
        charges: list[QuoteCharge] | None = None,
    ) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": str(quote.id),
            "quote_number": quote.quote_number,
            "revision": quote.revision,
            "status": QuoteService.effective_status(quote),
            "stored_status": quote.status,
            "title": quote.title,
            "customer_contact_id": (
                str(quote.customer_contact_id) if quote.customer_contact_id else None
            ),
            "location_id": str(quote.location_id) if quote.location_id else None,
            "currency": quote.currency,
            "subtotal": _money_str(quote.subtotal),
            "discount_amount": _money_str(quote.discount_amount),
            "charges_amount": _money_str(quote.charges_amount),
            "tax_amount": _money_str(quote.tax_amount),
            "total": _money_str(quote.total),
            "deposit_amount": _money_str(quote.deposit_amount),
            "discount_type": quote.discount_type,
            "discount_value": (
                _money_str(quote.discount_value) if quote.discount_value is not None else None
            ),
            "deposit_type": quote.deposit_type,
            "deposit_value": (
                _money_str(quote.deposit_value) if quote.deposit_value is not None else None
            ),
            "terms": quote.terms,
            "notes": quote.notes,
            "valid_until": quote.valid_until.isoformat() if quote.valid_until else None,
            "issued_at": quote.issued_at.isoformat() if quote.issued_at else None,
            "accepted_at": quote.accepted_at.isoformat() if quote.accepted_at else None,
            "rejected_at": quote.rejected_at.isoformat() if quote.rejected_at else None,
            "cancelled_at": quote.cancelled_at.isoformat() if quote.cancelled_at else None,
            "decision_reason": quote.decision_reason,
            "supersedes_quote_id": (
                str(quote.supersedes_quote_id) if quote.supersedes_quote_id else None
            ),
            "root_quote_id": str(quote.root_quote_id) if quote.root_quote_id else None,
            "converted_to_type": quote.converted_to_type,
            "converted_to_id": str(quote.converted_to_id) if quote.converted_to_id else None,
            "is_editable": quote.status in EDITABLE_STATUSES,
            "version": quote.version,
        }
        if items is not None:
            data["items"] = [
                {
                    "id": str(i.id),
                    "offering_id": str(i.offering_id) if i.offering_id else None,
                    "title": i.title,
                    "description": i.description,
                    "unit_label": i.unit_label,
                    "quantity": str(Decimal(str(i.quantity)).normalize()),
                    "unit_price": _money_str(i.unit_price),
                    "tax_rate": str(Decimal(str(i.tax_rate)).normalize()),
                    "discount_type": i.discount_type,
                    "discount_value": (
                        _money_str(i.discount_value) if i.discount_value is not None else None
                    ),
                    "line_subtotal": _money_str(i.line_subtotal),
                    "line_discount": _money_str(i.line_discount),
                    "line_tax": _money_str(i.line_tax),
                    "line_total": _money_str(i.line_total),
                    "sort_order": i.sort_order,
                }
                for i in items
            ]
        if charges is not None:
            data["charges"] = [
                {
                    "id": str(c.id),
                    "label": c.label,
                    "amount": _money_str(c.amount),
                    "taxable": c.taxable,
                    "tax_rate": str(Decimal(str(c.tax_rate)).normalize()),
                    "sort_order": c.sort_order,
                }
                for c in charges
            ]
        return data

    @staticmethod
    async def resolve(
        session: AsyncSession, *, business_id: uuid.UUID, quote_id: uuid.UUID
    ) -> Quote:
        result = await session.execute(
            select(Quote).where(
                Quote.id == quote_id,
                Quote.business_id == business_id,
                Quote.deleted_at.is_(None),
            )
        )
        quote = result.scalars().first()
        if quote is None:
            raise ResourceNotFound("Quote")
        return quote

    @staticmethod
    async def load_lines(
        session: AsyncSession, *, quote_id: uuid.UUID
    ) -> tuple[list[QuoteItem], list[QuoteCharge]]:
        """Items and charges for one quote, in two queries rather than per-line."""
        items = list(
            (
                await session.execute(
                    select(QuoteItem)
                    .where(QuoteItem.quote_id == quote_id)
                    .order_by(QuoteItem.sort_order, QuoteItem.created_at)
                )
            )
            .scalars()
            .all()
        )
        charges = list(
            (
                await session.execute(
                    select(QuoteCharge)
                    .where(QuoteCharge.quote_id == quote_id)
                    .order_by(QuoteCharge.sort_order, QuoteCharge.created_at)
                )
            )
            .scalars()
            .all()
        )
        return items, charges

    @staticmethod
    async def get_detail(
        session: AsyncSession, *, business_id: uuid.UUID, quote_id: uuid.UUID
    ) -> dict[str, Any]:
        quote = await QuoteService.resolve(session, business_id=business_id, quote_id=quote_id)
        items, charges = await QuoteService.load_lines(session, quote_id=quote.id)
        return QuoteService.serialize(quote, items, charges)

    @staticmethod
    async def list_quotes(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        status: str | None = None,
        customer_contact_id: uuid.UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """The list view. Deliberately without items — a list of fifty quotes
        does not need three hundred lines fetched to render."""
        query = select(Quote).where(Quote.business_id == business_id, Quote.deleted_at.is_(None))
        if status:
            query = query.where(Quote.status == status)
        if customer_contact_id:
            query = query.where(Quote.customer_contact_id == customer_contact_id)
        query = query.order_by(Quote.created_at.desc()).limit(min(limit, 200)).offset(offset)
        rows = (await session.execute(query)).scalars().all()
        return [QuoteService.serialize(q) for q in rows]

    # ------------------------------------------------------------- numbering

    @staticmethod
    async def _next_number(session: AsyncSession, business_id: uuid.UUID) -> str:
        """Per-business sequential number, readable to a human.

        Derived from a count rather than a sequence so each business starts at 1
        and the number means something to them. Collisions are prevented by the
        unique index, and the retry in `create` handles the race.
        """
        year = datetime.now(timezone.utc).year
        prefix = f"Q-{year}-"
        highest = await session.scalar(
            select(func.max(Quote.quote_number)).where(
                Quote.business_id == business_id,
                Quote.quote_number.like(f"{prefix}%"),
            )
        )
        nxt = 1
        if highest:
            try:
                nxt = int(str(highest).rsplit("-", 1)[-1]) + 1
            except ValueError:
                nxt = 1
        return f"{prefix}{nxt:04d}"

    # ------------------------------------------------------------- writing

    @staticmethod
    def _assert_editable(quote: Quote) -> None:
        if quote.status not in EDITABLE_STATUSES:
            raise ConflictError(
                f"A {quote.status} quote cannot be edited. Create a revision instead.",
                details={"quote_id": str(quote.id), "status": quote.status},
            )

    @staticmethod
    async def _snapshot_offering(
        session: AsyncSession, *, business_id: uuid.UUID, offering_id: uuid.UUID
    ) -> dict[str, Any]:
        """Copy what the catalogue says *now* onto the line.

        Read once, at the moment the line is added. Everything after that reads
        the copy, which is what makes an issued quote stable.
        """
        offering = await OfferingResolver.resolve(
            session, business_id=business_id, offering_id=offering_id
        )
        return {
            "title": offering.title,
            "description": offering.description,
            "unit_price": Decimal(str(offering.price_amount or 0)),
        }

    @staticmethod
    async def _recalculate(session: AsyncSession, quote: Quote) -> None:
        """Recompute and persist every figure from the current lines."""
        items, charges = await QuoteService.load_lines(session, quote_id=quote.id)
        result = calculate_quote(
            lines=[
                {
                    "quantity": i.quantity,
                    "unit_price": i.unit_price,
                    "tax_rate": i.tax_rate,
                    "discount_type": i.discount_type,
                    "discount_value": i.discount_value,
                }
                for i in items
            ],
            charges=[
                {"amount": c.amount, "taxable": c.taxable, "tax_rate": c.tax_rate} for c in charges
            ],
            discount_type=quote.discount_type,
            discount_value=quote.discount_value,
            deposit_type=quote.deposit_type,
            deposit_value=quote.deposit_value,
        )
        for item, priced in zip(items, result["lines"], strict=False):
            item.line_subtotal = priced["line_subtotal"]
            item.line_discount = priced["line_discount"]
            item.line_tax = priced["line_tax"]
            item.line_total = priced["line_total"]

        quote.subtotal = result["subtotal"]
        quote.discount_amount = result["discount_amount"]
        quote.charges_amount = result["charges_amount"]
        quote.tax_amount = result["tax_amount"]
        quote.total = result["total"]
        quote.deposit_amount = result["deposit_amount"]
        quote.updated_at = datetime.now(timezone.utc)
        await session.flush()

    @staticmethod
    async def create(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        actor_id: uuid.UUID,
        correlation_id: str,
        payload: dict[str, Any],
    ) -> Quote:
        business = await BusinessService.get_by_id(session, business_id)
        assert_business_mutable(business.state, action="create quote")

        idempotency_key = payload.get("idempotency_key")
        if idempotency_key:
            existing = (
                (
                    await session.execute(
                        select(Quote).where(
                            Quote.business_id == business_id,
                            Quote.idempotency_key == str(idempotency_key),
                            Quote.deleted_at.is_(None),
                        )
                    )
                )
                .scalars()
                .first()
            )
            if existing is not None:
                return existing

        customer_contact_id = payload.get("customer_contact_id")
        if customer_contact_id:
            contact = await CustomerResolver.resolve(
                session,
                business_id=business_id,
                contact_id=uuid.UUID(str(customer_contact_id)),
            )
            customer_contact_id = contact.id

        title = (payload.get("title") or "").strip() or None
        if title and len(title) > TITLE_MAX:
            raise ValidationError("Quote title is too long")
        terms = payload.get("terms")
        if terms and len(str(terms)) > TERMS_MAX:
            raise ValidationError("Terms are too long")

        valid_until = payload.get("valid_until")
        if isinstance(valid_until, str):
            valid_until = datetime.fromisoformat(valid_until.replace("Z", "+00:00"))

        quote = Quote(
            business_id=business_id,
            location_id=(
                uuid.UUID(str(payload["location_id"])) if payload.get("location_id") else None
            ),
            customer_contact_id=customer_contact_id,
            quote_number=await QuoteService._next_number(session, business_id),
            revision=1,
            status="draft",
            title=title,
            terms=terms,
            notes=payload.get("notes"),
            internal_notes=payload.get("internal_notes"),
            currency=str(payload.get("currency") or "INR").upper(),
            discount_type=payload.get("discount_type"),
            discount_value=payload.get("discount_value"),
            deposit_type=payload.get("deposit_type"),
            deposit_value=payload.get("deposit_value"),
            valid_until=valid_until,
            idempotency_key=str(idempotency_key) if idempotency_key else None,
            created_by=actor_id,
        )
        session.add(quote)
        await session.flush()
        quote.root_quote_id = quote.id
        await session.flush()

        for index, raw in enumerate(payload.get("items") or []):
            await QuoteService._add_item_row(
                session, business_id=business_id, quote=quote, raw=raw, sort_order=index
            )
        for index, raw in enumerate(payload.get("charges") or []):
            session.add(
                QuoteCharge(
                    business_id=business_id,
                    quote_id=quote.id,
                    label=str(raw.get("label") or "Charge").strip()[:120],
                    amount=Decimal(str(raw.get("amount") or 0)),
                    taxable=bool(raw.get("taxable")),
                    tax_rate=Decimal(str(raw.get("tax_rate") or 0)),
                    sort_order=index,
                )
            )
        await session.flush()
        await QuoteService._recalculate(session, quote)

        await AuditService.record(
            session,
            event_type="quote.created",
            actor_identity_id=actor_id,
            actor_context="business",
            business_id=business_id,
            resource_type="quote",
            resource_id=quote.id,
            action="created",
            after_state=QuoteService.serialize(quote),
        )
        await OutboxService.publish(
            session,
            event_type="quote.created",
            payload={
                "business_id": str(business_id),
                "quote_id": str(quote.id),
                "quote_number": quote.quote_number,
                "total": _money_str(quote.total),
            },
            business_id=business_id,
            correlation_id=correlation_id,
        )
        return quote

    @staticmethod
    async def _add_item_row(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        quote: Quote,
        raw: dict[str, Any],
        sort_order: int,
    ) -> QuoteItem:
        offering_id = raw.get("offering_id")
        snapshot: dict[str, Any] = {}
        if offering_id:
            snapshot = await QuoteService._snapshot_offering(
                session, business_id=business_id, offering_id=uuid.UUID(str(offering_id))
            )

        # An explicit value always wins over the snapshot: a business quoting a
        # bespoke price for this customer is the normal case, not an exception.
        title = (raw.get("title") or snapshot.get("title") or "").strip()
        if not title:
            raise ValidationError("Each quote line needs a title")
        unit_price = raw.get("unit_price")
        if unit_price is None:
            unit_price = snapshot.get("unit_price", 0)

        quantity = Decimal(str(raw.get("quantity") if raw.get("quantity") is not None else 1))
        if quantity <= 0:
            raise ValidationError("Quantity must be greater than zero")

        item = QuoteItem(
            business_id=business_id,
            quote_id=quote.id,
            offering_id=uuid.UUID(str(offering_id)) if offering_id else None,
            title=title[:TITLE_MAX],
            description=raw.get("description") or snapshot.get("description"),
            unit_label=raw.get("unit_label"),
            quantity=quantity,
            unit_price=Decimal(str(unit_price or 0)),
            tax_rate=Decimal(str(raw.get("tax_rate") or 0)),
            discount_type=raw.get("discount_type"),
            discount_value=raw.get("discount_value"),
            sort_order=sort_order,
            item_metadata=raw.get("metadata") or {},
        )
        session.add(item)
        await session.flush()
        return item

    @staticmethod
    async def update_draft(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        quote_id: uuid.UUID,
        actor_id: uuid.UUID,
        correlation_id: str,
        payload: dict[str, Any],
        expected_version: int | None = None,
    ) -> Quote:
        """Replace a draft's contents. Refuses on anything already issued."""
        business = await BusinessService.get_by_id(session, business_id)
        assert_business_mutable(business.state, action="edit quote")
        quote = await QuoteService.resolve(session, business_id=business_id, quote_id=quote_id)
        QuoteService._assert_editable(quote)
        if expected_version is not None and quote.version != expected_version:
            raise ConflictError(
                "This quote was changed by someone else",
                details={"expected": expected_version, "actual": quote.version},
            )
        before = QuoteService.serialize(quote)

        for field in (
            "title",
            "terms",
            "notes",
            "internal_notes",
            "discount_type",
            "discount_value",
            "deposit_type",
            "deposit_value",
        ):
            if field in payload:
                setattr(quote, field, payload[field])
        if "valid_until" in payload:
            value = payload["valid_until"]
            if isinstance(value, str):
                value = datetime.fromisoformat(value.replace("Z", "+00:00"))
            quote.valid_until = value
        if "customer_contact_id" in payload and payload["customer_contact_id"]:
            contact = await CustomerResolver.resolve(
                session,
                business_id=business_id,
                contact_id=uuid.UUID(str(payload["customer_contact_id"])),
            )
            quote.customer_contact_id = contact.id

        # Lines are replaced wholesale rather than patched. A quote is read as a
        # document, and partial line edits make ordering and totals ambiguous.
        if "items" in payload:
            items, _ = await QuoteService.load_lines(session, quote_id=quote.id)
            for item in items:
                await session.delete(item)
            await session.flush()
            for index, raw in enumerate(payload["items"] or []):
                await QuoteService._add_item_row(
                    session, business_id=business_id, quote=quote, raw=raw, sort_order=index
                )
        if "charges" in payload:
            _, charges = await QuoteService.load_lines(session, quote_id=quote.id)
            for charge in charges:
                await session.delete(charge)
            await session.flush()
            for index, raw in enumerate(payload["charges"] or []):
                session.add(
                    QuoteCharge(
                        business_id=business_id,
                        quote_id=quote.id,
                        label=str(raw.get("label") or "Charge").strip()[:120],
                        amount=Decimal(str(raw.get("amount") or 0)),
                        taxable=bool(raw.get("taxable")),
                        tax_rate=Decimal(str(raw.get("tax_rate") or 0)),
                        sort_order=index,
                    )
                )
            await session.flush()

        quote.version += 1
        await QuoteService._recalculate(session, quote)
        await AuditService.record(
            session,
            event_type="quote.updated",
            actor_identity_id=actor_id,
            actor_context="business",
            business_id=business_id,
            resource_type="quote",
            resource_id=quote.id,
            action="updated",
            before_state=before,
            after_state=QuoteService.serialize(quote),
        )
        await OutboxService.publish(
            session,
            event_type="quote.updated",
            payload={"business_id": str(business_id), "quote_id": str(quote.id)},
            business_id=business_id,
            correlation_id=correlation_id,
        )
        return quote

    # ------------------------------------------------------------- lifecycle

    @staticmethod
    async def issue(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        quote_id: uuid.UUID,
        actor_id: uuid.UUID,
        correlation_id: str,
        valid_days: int | None = None,
    ) -> Quote:
        """Send it. After this the figures are fixed and a share link exists."""
        business = await BusinessService.get_by_id(session, business_id)
        assert_business_mutable(business.state, action="issue quote")
        quote = await QuoteService.resolve(session, business_id=business_id, quote_id=quote_id)
        if quote.status != "draft":
            raise ConflictError(
                f"Only a draft can be issued; this quote is {quote.status}",
                details={"quote_id": str(quote.id), "status": quote.status},
            )
        items, _ = await QuoteService.load_lines(session, quote_id=quote.id)
        if not items:
            raise ValidationError("A quote needs at least one line before it can be issued")

        now = datetime.now(timezone.utc)
        if valid_days:
            quote.valid_until = now + timedelta(days=int(valid_days))
        quote.status = "issued"
        quote.issued_at = now
        # Opaque, single-purpose, and expiring — the same shape bookings use for
        # guests, because a quote link also goes to someone with no account.
        quote.access_token = secrets.token_urlsafe(32)
        quote.access_token_expires_at = now + timedelta(days=SHARE_TOKEN_DAYS)
        quote.version += 1
        await session.flush()

        await AuditService.record(
            session,
            event_type="quote.issued",
            actor_identity_id=actor_id,
            actor_context="business",
            business_id=business_id,
            resource_type="quote",
            resource_id=quote.id,
            action="issued",
            after_state=QuoteService.serialize(quote),
        )
        await OutboxService.publish(
            session,
            event_type="quote.issued",
            payload={
                "business_id": str(business_id),
                "quote_id": str(quote.id),
                "quote_number": quote.quote_number,
                "customer_contact_id": (
                    str(quote.customer_contact_id) if quote.customer_contact_id else None
                ),
                "total": _money_str(quote.total),
                "valid_until": quote.valid_until.isoformat() if quote.valid_until else None,
            },
            business_id=business_id,
            correlation_id=correlation_id,
        )
        return quote

    @staticmethod
    async def decide(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        quote_id: uuid.UUID,
        decision: str,
        actor_id: uuid.UUID | None,
        correlation_id: str,
        reason: str | None = None,
        decided_by_name: str | None = None,
        actor_context: str = "business",
    ) -> Quote:
        """Accept or reject. Used by staff and by the customer's share link.

        Expiry is checked against the clock rather than the stored status, so a
        customer cannot accept an offer that has already lapsed just because no
        sweep has run.
        """
        if decision not in {"accepted", "rejected"}:
            raise ValidationError("Decision must be accepted or rejected")
        quote = await QuoteService.resolve(session, business_id=business_id, quote_id=quote_id)
        current = QuoteService.effective_status(quote)
        if current != "issued":
            raise ConflictError(
                f"A {current} quote cannot be {decision}",
                details={"quote_id": str(quote.id), "status": current},
            )

        now = datetime.now(timezone.utc)
        quote.status = decision
        quote.decision_reason = reason
        quote.decided_by_name = decided_by_name
        if decision == "accepted":
            quote.accepted_at = now
        else:
            quote.rejected_at = now
        quote.version += 1
        await session.flush()

        await AuditService.record(
            session,
            event_type=f"quote.{decision}",
            actor_identity_id=actor_id,
            actor_context=actor_context,
            business_id=business_id,
            resource_type="quote",
            resource_id=quote.id,
            action=decision,
            after_state=QuoteService.serialize(quote),
        )
        await OutboxService.publish(
            session,
            event_type=f"quote.{decision}",
            payload={
                "business_id": str(business_id),
                "quote_id": str(quote.id),
                "quote_number": quote.quote_number,
                "total": _money_str(quote.total),
                "customer_contact_id": (
                    str(quote.customer_contact_id) if quote.customer_contact_id else None
                ),
            },
            business_id=business_id,
            correlation_id=correlation_id,
        )
        return quote

    @staticmethod
    async def cancel(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        quote_id: uuid.UUID,
        actor_id: uuid.UUID,
        correlation_id: str,
        reason: str | None = None,
    ) -> Quote:
        """Withdraw an offer. The share link stops working immediately."""
        quote = await QuoteService.resolve(session, business_id=business_id, quote_id=quote_id)
        if quote.status in TERMINAL_STATUSES:
            raise ConflictError(
                f"A {quote.status} quote cannot be cancelled",
                details={"quote_id": str(quote.id), "status": quote.status},
            )
        quote.status = "cancelled"
        quote.cancelled_at = datetime.now(timezone.utc)
        quote.decision_reason = reason
        quote.access_token = None
        quote.version += 1
        await session.flush()

        await AuditService.record(
            session,
            event_type="quote.cancelled",
            actor_identity_id=actor_id,
            actor_context="business",
            business_id=business_id,
            resource_type="quote",
            resource_id=quote.id,
            action="cancelled",
            after_state=QuoteService.serialize(quote),
        )
        await OutboxService.publish(
            session,
            event_type="quote.cancelled",
            payload={"business_id": str(business_id), "quote_id": str(quote.id)},
            business_id=business_id,
            correlation_id=correlation_id,
        )
        return quote

    @staticmethod
    async def revise(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        quote_id: uuid.UUID,
        actor_id: uuid.UUID,
        correlation_id: str,
    ) -> Quote:
        """Copy an issued quote into a new editable revision.

        The original keeps every figure it was sent with and becomes superseded.
        The copy carries the same number so the customer recognises it, and a
        higher revision so both parties can say which one they mean.
        """
        business = await BusinessService.get_by_id(session, business_id)
        assert_business_mutable(business.state, action="revise quote")
        original = await QuoteService.resolve(session, business_id=business_id, quote_id=quote_id)
        if original.status == "draft":
            raise ConflictError(
                "This quote is still a draft — edit it instead of revising it",
                details={"quote_id": str(original.id)},
            )
        if original.status in {"superseded", "cancelled"}:
            raise ConflictError(
                f"A {original.status} quote cannot be revised",
                details={"quote_id": str(original.id), "status": original.status},
            )

        items, charges = await QuoteService.load_lines(session, quote_id=original.id)
        revision = Quote(
            business_id=business_id,
            location_id=original.location_id,
            customer_contact_id=original.customer_contact_id,
            quote_number=original.quote_number,
            revision=original.revision + 1,
            supersedes_quote_id=original.id,
            root_quote_id=original.root_quote_id or original.id,
            status="draft",
            title=original.title,
            terms=original.terms,
            notes=original.notes,
            internal_notes=original.internal_notes,
            currency=original.currency,
            discount_type=original.discount_type,
            discount_value=original.discount_value,
            deposit_type=original.deposit_type,
            deposit_value=original.deposit_value,
            valid_until=original.valid_until,
            created_by=actor_id,
        )
        session.add(revision)
        await session.flush()

        for item in items:
            session.add(
                QuoteItem(
                    business_id=business_id,
                    quote_id=revision.id,
                    offering_id=item.offering_id,
                    title=item.title,
                    description=item.description,
                    unit_label=item.unit_label,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    tax_rate=item.tax_rate,
                    discount_type=item.discount_type,
                    discount_value=item.discount_value,
                    sort_order=item.sort_order,
                    item_metadata=item.item_metadata,
                )
            )
        for charge in charges:
            session.add(
                QuoteCharge(
                    business_id=business_id,
                    quote_id=revision.id,
                    label=charge.label,
                    amount=charge.amount,
                    taxable=charge.taxable,
                    tax_rate=charge.tax_rate,
                    sort_order=charge.sort_order,
                )
            )
        await session.flush()
        await QuoteService._recalculate(session, revision)

        original.status = "superseded"
        # The old link stops working; the customer should be reading the new one.
        original.access_token = None
        original.version += 1
        await session.flush()

        await AuditService.record(
            session,
            event_type="quote.revised",
            actor_identity_id=actor_id,
            actor_context="business",
            business_id=business_id,
            resource_type="quote",
            resource_id=revision.id,
            action="revised",
            before_state=QuoteService.serialize(original),
            after_state=QuoteService.serialize(revision),
        )
        await OutboxService.publish(
            session,
            event_type="quote.revised",
            payload={
                "business_id": str(business_id),
                "quote_id": str(revision.id),
                "supersedes_quote_id": str(original.id),
                "quote_number": revision.quote_number,
                "revision": revision.revision,
            },
            business_id=business_id,
            correlation_id=correlation_id,
        )
        return revision

    # ------------------------------------------------------------- sweeping

    @staticmethod
    async def expire_due(session: AsyncSession, *, correlation_id: str, limit: int = 200) -> int:
        """Move lapsed quotes to expired and announce it.

        Readers already treat a lapsed quote as expired, so this exists for the
        event — a follow-up or a notification needs a moment to fire at, not a
        computed property.
        """
        now = datetime.now(timezone.utc)
        due = (
            (
                await session.execute(
                    select(Quote)
                    .where(
                        Quote.status == "issued",
                        Quote.deleted_at.is_(None),
                        Quote.valid_until.is_not(None),
                        Quote.valid_until <= now,
                    )
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )
        for quote in due:
            quote.status = "expired"
            quote.version += 1
            await OutboxService.publish(
                session,
                event_type="quote.expired",
                payload={
                    "business_id": str(quote.business_id),
                    "quote_id": str(quote.id),
                    "quote_number": quote.quote_number,
                },
                business_id=quote.business_id,
                correlation_id=correlation_id,
            )
        await session.flush()
        return len(due)
