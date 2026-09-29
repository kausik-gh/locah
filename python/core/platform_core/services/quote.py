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
from platform_core.models import (
    Quote,
    QuoteCharge,
    QuoteItem,
    QuotePaymentPlanLine,
    QuoteRfqIntake,
    QuoteSettings,
    QuoteView,
)
from platform_core.permissions import QUOTES_APPROVE
from platform_core.resolvers.customer_resolver import CustomerResolver
from platform_core.resolvers.offering_resolver import OfferingResolver
from platform_core.services.audit import AuditService
from platform_core.services.business import BusinessService
from platform_core.services.outbox import OutboxService
from platform_core.services.quote_calculation import calculate_quote
from platform_core.services.quote_commercial import (
    CONVERSION_TARGETS,
    DEFAULT_DISCOUNT_LIMIT,
    DEFAULT_VALID_DAYS,
    OTP_MAX_ATTEMPTS,
    OTP_TTL_MINUTES,
    RFQ_CHANNELS,
    conversion_contract,
    discount_percent,
    hash_acceptance_code,
    money_str,
    new_acceptance_code,
    normalize_plan,
    payment_handoff,
    prepare_line,
    qty_str,
    resolve_plan_amounts,
)

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
    return money_str(value)


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
        plan: list[QuotePaymentPlanLine] | None = None,
    ) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": str(quote.id),
            "business_id": str(quote.business_id),
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
            "decided_by_name": quote.decided_by_name,
            "supersedes_quote_id": (
                str(quote.supersedes_quote_id) if quote.supersedes_quote_id else None
            ),
            "root_quote_id": str(quote.root_quote_id) if quote.root_quote_id else None,
            "converted_to_type": quote.converted_to_type,
            "converted_to_id": str(quote.converted_to_id) if quote.converted_to_id else None,
            "source": quote.source,
            "source_ref": quote.source_ref,
            "approval_status": quote.approval_status,
            "opened_at": quote.opened_at.isoformat() if quote.opened_at else None,
            "last_opened_at": quote.last_opened_at.isoformat() if quote.last_opened_at else None,
            "open_count": int(quote.open_count or 0),
            "price_locked_at": quote.price_locked_at.isoformat() if quote.price_locked_at else None,
            "prices_locked": quote.status == "accepted",
            "conversion_target": quote.conversion_target,
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
                    "line_kind": i.line_kind or "item",
                    "moq": qty_str(i.moq) if i.moq is not None else None,
                    "lead_time_days": i.lead_time_days,
                    "quantity_breaks": i.quantity_breaks or [],
                    "boq_section": i.boq_section,
                    "size_matrix": i.size_matrix or [],
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
        if plan is not None:
            data["payment_plan"] = [
                {
                    "id": str(stage.id),
                    "label": stage.label,
                    "amount_type": stage.amount_type,
                    "amount_value": _money_str(stage.amount_value),
                    "due_rule": stage.due_rule,
                    "due_days": stage.due_days,
                    "sort_order": stage.sort_order,
                }
                for stage in plan
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
    async def load_plan(
        session: AsyncSession, *, quote_id: uuid.UUID
    ) -> list[QuotePaymentPlanLine]:
        return list(
            (
                await session.execute(
                    select(QuotePaymentPlanLine)
                    .where(QuotePaymentPlanLine.quote_id == quote_id)
                    .order_by(QuotePaymentPlanLine.sort_order, QuotePaymentPlanLine.created_at)
                )
            )
            .scalars()
            .all()
        )

    @staticmethod
    async def get_detail(
        session: AsyncSession, *, business_id: uuid.UUID, quote_id: uuid.UUID
    ) -> dict[str, Any]:
        quote = await QuoteService.resolve(session, business_id=business_id, quote_id=quote_id)
        items, charges = await QuoteService.load_lines(session, quote_id=quote.id)
        plan = await QuoteService.load_plan(session, quote_id=quote.id)
        return QuoteService.serialize(quote, items, charges, plan)

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
            source=str(payload.get("source") or "manual"),
            source_ref=payload.get("source_ref"),
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
        await QuoteService._replace_plan(
            session, business_id=business_id, quote=quote, raw_plan=payload.get("payment_plan") or []
        )
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

        prepared = prepare_line({**raw, "unit_price": unit_price})

        item = QuoteItem(
            business_id=business_id,
            quote_id=quote.id,
            offering_id=uuid.UUID(str(offering_id)) if offering_id else None,
            title=title[:TITLE_MAX],
            description=raw.get("description") or snapshot.get("description"),
            unit_label=raw.get("unit_label"),
            quantity=prepared["quantity"],
            unit_price=prepared["unit_price"],
            tax_rate=Decimal(str(raw.get("tax_rate") or 0)),
            discount_type=raw.get("discount_type"),
            discount_value=raw.get("discount_value"),
            sort_order=sort_order,
            line_kind=prepared["line_kind"],
            moq=prepared["moq"],
            lead_time_days=prepared["lead_time_days"],
            quantity_breaks=prepared["quantity_breaks"],
            boq_section=prepared["boq_section"],
            size_matrix=prepared["size_matrix"],
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

        if "payment_plan" in payload:
            await QuoteService._replace_plan(
                session,
                business_id=business_id,
                quote=quote,
                raw_plan=payload.get("payment_plan") or [],
            )

        quote.version += 1
        await QuoteService._recalculate(session, quote)
        await QuoteService._sync_approval(session, quote)
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
        permissions: frozenset[str] | None = None,
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

        await QuoteService._assert_discount_allowed(
            session, quote, permissions or frozenset()
        )

        now = datetime.now(timezone.utc)
        if valid_days:
            quote.valid_until = now + timedelta(days=int(valid_days))
        elif quote.valid_until is None:
            # Capability Universe §19.4: a quote is valid for 7 days unless the
            # business names another date.
            quote.valid_until = now + timedelta(days=DEFAULT_VALID_DAYS)
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
            quote.price_locked_at = now
        else:
            quote.rejected_at = now
        quote.otp_hash = None
        quote.otp_expires_at = None
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
        if decision == "accepted":
            detail = await QuoteService.get_detail(
                session, business_id=business_id, quote_id=quote.id
            )
            plan = resolve_plan_amounts(
                [
                    {
                        "label": stage["label"],
                        "amount_type": stage["amount_type"],
                        "amount_value": stage["amount_value"],
                        "due_rule": stage["due_rule"],
                        "due_days": stage["due_days"],
                    }
                    for stage in detail.get("payment_plan") or []
                ],
                quote.total,
            )
            await OutboxService.publish(
                session,
                event_type="quote.payment_handoff",
                payload=payment_handoff(quote=detail, plan=plan),
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
        if original.status == "accepted":
            raise ConflictError(
                "An accepted quote is locked. Its prices cannot be revised.",
                details={"quote_id": str(original.id), "code": "quote_locked"},
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
                    line_kind=item.line_kind,
                    moq=item.moq,
                    lead_time_days=item.lead_time_days,
                    quantity_breaks=item.quantity_breaks,
                    boq_section=item.boq_section,
                    size_matrix=item.size_matrix,
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
        original_plan = await QuoteService.load_plan(session, quote_id=original.id)
        for stage in original_plan:
            session.add(
                QuotePaymentPlanLine(
                    business_id=business_id,
                    quote_id=revision.id,
                    label=stage.label,
                    amount_type=stage.amount_type,
                    amount_value=stage.amount_value,
                    due_rule=stage.due_rule,
                    due_days=stage.due_days,
                    sort_order=stage.sort_order,
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

    # ------------------------------------------------------------- commercial rules

    @staticmethod
    async def _replace_plan(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        quote: Quote,
        raw_plan: Any,
    ) -> None:
        stages = normalize_plan(raw_plan)
        existing = await QuoteService.load_plan(session, quote_id=quote.id)
        for stage in existing:
            await session.delete(stage)
        await session.flush()
        for stage in stages:
            session.add(
                QuotePaymentPlanLine(
                    business_id=business_id,
                    quote_id=quote.id,
                    label=stage["label"],
                    amount_type=stage["amount_type"],
                    amount_value=stage["amount_value"],
                    due_rule=stage["due_rule"],
                    due_days=stage["due_days"],
                    sort_order=stage["sort_order"],
                )
            )
        await session.flush()

    @staticmethod
    async def discount_limit(session: AsyncSession, business_id: uuid.UUID) -> Decimal:
        row = await session.get(QuoteSettings, business_id)
        if row is None:
            return DEFAULT_DISCOUNT_LIMIT
        return Decimal(str(row.executive_discount_limit_percent))

    @staticmethod
    async def set_discount_limit(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        percent: Decimal,
    ) -> Decimal:
        if percent < 0 or percent > 100:
            raise ValidationError("The discount limit is a percent from 0 to 100")
        row = await session.get(QuoteSettings, business_id)
        if row is None:
            row = QuoteSettings(business_id=business_id, executive_discount_limit_percent=percent)
            session.add(row)
        else:
            row.executive_discount_limit_percent = percent
            row.updated_at = datetime.now(timezone.utc)
        await session.flush()
        return percent

    @staticmethod
    async def _sync_approval(session: AsyncSession, quote: Quote) -> None:
        """A discount edited after approval has to be approved again."""
        limit = await QuoteService.discount_limit(session, quote.business_id)
        pct = discount_percent(quote.subtotal, quote.discount_amount)
        if pct <= limit:
            quote.approval_status = "not_required"
        elif quote.approval_status == "approved":
            quote.approval_status = "pending"
        await session.flush()

    @staticmethod
    async def _assert_discount_allowed(
        session: AsyncSession, quote: Quote, permissions: frozenset[str]
    ) -> None:
        limit = await QuoteService.discount_limit(session, quote.business_id)
        pct = discount_percent(quote.subtotal, quote.discount_amount)
        if pct <= limit or QUOTES_APPROVE in permissions or quote.approval_status == "approved":
            if pct <= limit:
                quote.approval_status = "not_required"
            elif QUOTES_APPROVE in permissions and quote.approval_status != "approved":
                quote.approval_status = "approved"
            return
        quote.approval_status = "pending"
        await session.flush()
        raise ValidationError(
            "This discount is above the executive's limit and needs the owner",
            details={
                "code": "discount_approval_required",
                "discount_percent": str(pct),
                "limit_percent": str(limit),
            },
        )

    @staticmethod
    async def decide_discount(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        quote_id: uuid.UUID,
        decision: str,
        actor_id: uuid.UUID,
        correlation_id: str,
    ) -> Quote:
        if decision not in {"approved", "rejected"}:
            raise ValidationError("Approval is approved or rejected")
        quote = await QuoteService.resolve(session, business_id=business_id, quote_id=quote_id)
        QuoteService._assert_editable(quote)
        if quote.approval_status != "pending":
            raise ConflictError(
                "This quote is not waiting on a discount approval",
                details={"approval_status": quote.approval_status},
            )
        quote.approval_status = decision
        quote.version += 1
        await session.flush()
        await OutboxService.publish(
            session,
            event_type="quote.discount_decided",
            payload={
                "business_id": str(business_id),
                "quote_id": str(quote.id),
                "decision": decision,
            },
            business_id=business_id,
            correlation_id=correlation_id,
        )
        await AuditService.record(
            session,
            event_type="quote.discount_decided",
            actor_identity_id=actor_id,
            actor_context="business",
            business_id=business_id,
            resource_type="quote",
            resource_id=quote.id,
            action=decision,
            after_state={"approval_status": decision},
        )
        return quote

    @staticmethod
    async def record_view(session: AsyncSession, quote: Quote) -> None:
        """The customer opened this version. Each open is its own row."""
        now = datetime.now(timezone.utc)
        session.add(
            QuoteView(business_id=quote.business_id, quote_id=quote.id, opened_at=now)
        )
        if quote.opened_at is None:
            quote.opened_at = now
        quote.last_opened_at = now
        quote.open_count = int(quote.open_count or 0) + 1
        await session.flush()
        await OutboxService.publish(
            session,
            event_type="quote.viewed",
            payload={
                "business_id": str(quote.business_id),
                "quote_id": str(quote.id),
                "revision": quote.revision,
                "quote_number": quote.quote_number,
                "opened_at": now.isoformat(),
                "open_count": quote.open_count,
            },
            business_id=quote.business_id,
            correlation_id=str(uuid.uuid4()),
        )

    @staticmethod
    async def issue_acceptance_code(
        session: AsyncSession,
        *,
        quote: Quote,
        name: str,
        correlation_id: str,
    ) -> None:
        cleaned = name.strip()
        if not 1 <= len(cleaned) <= 80:
            raise ValidationError("Tell us the name to put on the acceptance")
        current = QuoteService.effective_status(quote)
        if current != "issued":
            raise ConflictError(
                f"A {current} quote cannot be accepted",
                details={"status": current},
            )
        code = new_acceptance_code()
        quote.otp_hash = hash_acceptance_code(quote.id, code)
        quote.otp_expires_at = datetime.now(timezone.utc) + timedelta(minutes=OTP_TTL_MINUTES)
        quote.otp_attempts = 0
        quote.decided_by_name = cleaned
        await session.flush()
        # The code travels on the event so messaging can send it. The page
        # the customer is looking at does not receive it.
        await OutboxService.publish(
            session,
            event_type="quote.acceptance_code_issued",
            payload={
                "business_id": str(quote.business_id),
                "quote_id": str(quote.id),
                "quote_number": quote.quote_number,
                "name": cleaned,
                "code": code,
                "customer_contact_id": (
                    str(quote.customer_contact_id) if quote.customer_contact_id else None
                ),
            },
            business_id=quote.business_id,
            correlation_id=correlation_id,
        )

    @staticmethod
    def verify_acceptance_code(quote: Quote, code: str) -> None:
        if quote.otp_attempts >= OTP_MAX_ATTEMPTS:
            raise ValidationError(
                "Too many attempts. Ask for a new code.",
                details={"code": "otp_locked"},
            )
        now = datetime.now(timezone.utc)
        presented = (code or "").strip()
        expires = quote.otp_expires_at
        matches = (
            quote.otp_hash
            and expires is not None
            and expires > now
            and hash_acceptance_code(quote.id, presented) == quote.otp_hash
        )
        if not matches:
            quote.otp_attempts = int(quote.otp_attempts or 0) + 1
            raise ValidationError(
                "That code does not match",
                details={"code": "otp_mismatch"},
            )

    @staticmethod
    async def intake_rfq(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        actor_id: uuid.UUID,
        correlation_id: str,
        channel: str,
        idempotency_key: str,
        customer_name: str,
        phone: str | None,
        email: str | None,
        brief: str | None,
        lines: list[dict[str, Any]] | None,
        offering_title: str | None = None,
        source_ref: str | None = None,
    ) -> Quote:
        """A website or WhatsApp request becomes one draft quote.

        The same key returns the draft already opened. Prices stay at zero
        until someone at the business writes them — an RFQ is a request, not
        an offer.
        """
        if channel not in RFQ_CHANNELS:
            raise ValidationError("An RFQ arrives from the website or WhatsApp")
        key = idempotency_key.strip()
        if not key:
            raise ValidationError("An RFQ needs an idempotency key")
        existing = (
            await session.execute(
                select(QuoteRfqIntake).where(
                    QuoteRfqIntake.business_id == business_id,
                    QuoteRfqIntake.channel == channel,
                    QuoteRfqIntake.idempotency_key == key,
                )
            )
        ).scalars().first()
        if existing is not None:
            return await QuoteService.resolve(
                session, business_id=business_id, quote_id=existing.quote_id
            )

        from platform_core.services.customer import CustomerService

        name = customer_name.strip()
        if not 1 <= len(name) <= 80:
            raise ValidationError("An RFQ needs the customer's name")
        contact = await CustomerService.find_or_create_contact(
            session,
            business_id=business_id,
            correlation_id=correlation_id,
            actor_id=actor_id,
            display_name=name,
            email=email,
            phone=phone,
            actor_context=f"rfq_{channel}",
        )
        item_rows = list(lines or [])
        if not item_rows:
            title = (offering_title or brief or "Quote request").strip()[:TITLE_MAX] or "Quote request"
            item_rows = [{"title": title, "quantity": 1, "unit_price": 0}]
        quote = await QuoteService.create(
            session,
            business_id=business_id,
            actor_id=actor_id,
            correlation_id=correlation_id,
            payload={
                "customer_contact_id": str(contact.id),
                "title": (offering_title or "Quote request")[:TITLE_MAX],
                "notes": (brief or "")[:4000] or None,
                "items": item_rows,
                "source": channel,
                "source_ref": source_ref,
                "idempotency_key": f"rfq:{channel}:{key}",
            },
        )
        session.add(
            QuoteRfqIntake(
                business_id=business_id,
                channel=channel,
                idempotency_key=key,
                quote_id=quote.id,
            )
        )
        await session.flush()
        await OutboxService.publish(
            session,
            event_type="quote.rfq_received",
            payload={
                "business_id": str(business_id),
                "quote_id": str(quote.id),
                "channel": channel,
                "source_ref": source_ref,
            },
            business_id=business_id,
            correlation_id=correlation_id,
        )
        return quote

    @staticmethod
    async def request_conversion(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        quote_id: uuid.UUID,
        target: str,
        actor_id: uuid.UUID,
        correlation_id: str,
    ) -> dict[str, Any]:
        """Hand the locked accepted version to Orders, Projects or Invoicing.

        The contract is the whole handoff. This does not insert an order, a
        project or an invoice.
        """
        if target not in CONVERSION_TARGETS:
            raise ValidationError("Choose an order, a project, or an invoice")
        quote = await QuoteService.resolve(session, business_id=business_id, quote_id=quote_id)
        if quote.status != "accepted" or quote.price_locked_at is None:
            raise ConflictError(
                "Only an accepted, locked quote can be handed on",
                details={"status": quote.status, "code": "quote_not_locked"},
            )
        if quote.conversion_target and quote.conversion_target != target:
            raise ConflictError(
                f"This quote is already handed to {quote.conversion_target}",
                details={"conversion_target": quote.conversion_target},
            )
        detail = await QuoteService.get_detail(
            session, business_id=business_id, quote_id=quote.id
        )
        plan = resolve_plan_amounts(
            [
                {
                    "label": stage["label"],
                    "amount_type": stage["amount_type"],
                    "amount_value": stage["amount_value"],
                    "due_rule": stage["due_rule"],
                    "due_days": stage["due_days"],
                }
                for stage in detail.get("payment_plan") or []
            ],
            quote.total,
        )
        contract = conversion_contract(quote=detail, plan=plan, target=target)
        if quote.conversion_target == target:
            return contract
        quote.conversion_target = target
        quote.version += 1
        await session.flush()
        await OutboxService.publish(
            session,
            event_type="quote.conversion_requested",
            payload=contract,
            business_id=business_id,
            correlation_id=correlation_id,
        )
        await AuditService.record(
            session,
            event_type="quote.conversion_requested",
            actor_identity_id=actor_id,
            actor_context="business",
            business_id=business_id,
            resource_type="quote",
            resource_id=quote.id,
            action="conversion_requested",
            after_state={"target": target},
        )
        return contract

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
