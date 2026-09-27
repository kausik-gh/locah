"""Khata / credit book (Capability Universe §6.2 `ledger`, §14.5, §23 #3).

Each customer or supplier has one account. Its balance moves only by
appending an entry, under the account's row lock, so the balance always
equals the sum of its entries — however many counters and people write at
once (§26.3 P1-06). Entries are never edited; a mistake is a new entry.

Sign convention: a customer account's balance is what they owe us, a
supplier account's what we owe them. Credit sales and purchases raise it;
money received / paid and returns lower it.

Credit comes from bills, so the tax record and the khata agree: a counter
sale tendered to khata, or a bill put "on the customer's account", posts the
unpaid amount. Money received against the account is applied to the oldest
open bills first (FIFO), which is also how ageing is worked out.
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

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.exceptions import ConflictError, ResourceNotFound, ValidationError
from platform_core.invoicing.states import gstin_problem, normalise_gstin
from platform_core.invoicing.tax_engine import ZERO, dec, money
from platform_core.models import (
    Business,
    CustomerContact,
    InvoicingDocument,
    InvoicingPayment,
    LedgerAccount,
    LedgerEntry,
)
from platform_core.secrets import resolve_signing_secret
from platform_core.services.audit import AuditService
from platform_core.services.invoicing_setup import local_today
from platform_core.services.outbox import OutboxService

KIND_LABEL = {
    "opening_balance": "Opening balance", "credit_sale": "Sold on credit", "payment_received": "Money received",
    "return_credit": "Goods returned", "purchase": "Bought on credit", "payment_made": "Money paid",
    "adjustment": "Correction",
}
# Which way each kind moves the balance; None = the caller gives the sign.
SIGN: dict[str, int | None] = {
    "opening_balance": None, "credit_sale": 1, "payment_received": -1, "return_credit": -1,
    "purchase": 1, "payment_made": -1, "adjustment": None,
}
CUSTOMER_KINDS = {"opening_balance", "credit_sale", "payment_received", "return_credit", "adjustment"}
SUPPLIER_KINDS = {"opening_balance", "purchase", "payment_made", "adjustment"}
METHODS = {"cash": "Cash", "upi": "UPI", "card": "Card", "bank_transfer": "Bank transfer", "cheque": "Cheque",
           "other": "Other"}
BUCKETS = (("current", "Not due yet"), ("d1_30", "1–30 days late"), ("d31_60", "31–60 days late"),
           ("d61_90", "61–90 days late"), ("d90", "Over 90 days late"))


def _err(field: str, message: str) -> ValidationError:
    return ValidationError(message, details={"errors": [{"field": field, "message": message}], "field": field})


def _f(v: Any) -> float:
    return float(dec(v))


def statement_token(business_id: uuid.UUID, account_id: uuid.UUID) -> str:
    secret = str(resolve_signing_secret("DOCUMENT_LINK_SECRET", "document-link-dev-secret",
                                        fallback_env="SUPABASE_JWT_SECRET"))
    mac = hmac.new(secret.encode(), f"khata:{business_id}:{account_id}".encode(), hashlib.sha256)
    return base64.urlsafe_b64encode(mac.digest()).decode().rstrip("=")[:32]


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@dataclass
class Ageing:
    buckets: dict[str, Decimal]
    overdue: Decimal
    oldest_due: date | None
    advance: Decimal  # paid ahead (a credit balance)

    def view(self) -> dict[str, Any]:
        return {"buckets": [{"key": k, "label": label, "amount": _f(self.buckets[k])} for k, label in BUCKETS],
                "overdue": _f(self.overdue), "oldest_due": self.oldest_due.isoformat() if self.oldest_due else None,
                "advance": _f(self.advance)}


def age(entries: list[LedgerEntry], today: date, credit_days: int | None) -> Ageing:
    """FIFO: money received settles the oldest amounts owed first; what is left
    is aged from its due date (the entry's own, or entry date + credit days)."""
    open_items: list[list[Any]] = []  # [remaining, due]
    advance = ZERO
    for e in sorted(entries, key=lambda x: x.seq):
        amt = dec(e.amount)
        if amt > 0:
            due = e.due_date or (e.entry_date + timedelta(days=credit_days or 0))
            take = min(advance, amt)
            advance -= take
            if amt - take > 0:
                open_items.append([amt - take, due])
        else:
            pay = -amt
            while pay > 0 and open_items:
                take = min(pay, open_items[0][0])
                open_items[0][0] -= take
                pay -= take
                if open_items[0][0] == 0:
                    open_items.pop(0)
            advance += pay
    buckets = {k: ZERO for k, _ in BUCKETS}
    overdue = ZERO
    for remaining, due in open_items:
        late = (today - due).days
        key = "current" if late <= 0 else "d1_30" if late <= 30 else "d31_60" if late <= 60 else \
            "d61_90" if late <= 90 else "d90"
        buckets[key] += remaining
        if late > 0:
            overdue += remaining
    return Ageing(buckets, overdue, min((d for _, d in open_items), default=None), advance)


class LedgerService:
    # ------------------------------------------------------------------ accounts
    @staticmethod
    def serialize(a: LedgerAccount, ageing: Ageing | None = None) -> dict[str, Any]:
        limit = _f(a.credit_limit) if a.credit_limit is not None else None
        return {
            "id": str(a.id), "party_type": a.party_type, "display_name": a.display_name, "phone": a.phone,
            "gstin": a.gstin, "customer_contact_id": str(a.customer_contact_id) if a.customer_contact_id else None,
            "balance": _f(a.balance), "credit_limit": limit, "credit_days": a.credit_days, "status": a.status,
            "over_limit": limit is not None and _f(a.balance) > limit, "notes": a.notes,
            "limit_used_pct": round(_f(a.balance) * 100 / limit, 1) if limit else None,
            "last_entry_at": a.last_entry_at.isoformat() if a.last_entry_at else None, "version": a.version,
            **({"ageing": ageing.view()} if ageing is not None else {}),
        }

    @staticmethod
    async def get(session: AsyncSession, business_id: uuid.UUID, account_id: uuid.UUID, *,
                  lock: bool = False) -> LedgerAccount:
        q = select(LedgerAccount).where(LedgerAccount.business_id == business_id, LedgerAccount.id == account_id)
        if lock:
            # Re-read under the lock even if this session already loaded the
            # row: a stale balance here would lose another writer's entry.
            q = q.with_for_update().execution_options(populate_existing=True)
        a = (await session.execute(q)).scalars().first()
        if a is None:
            raise ResourceNotFound("Account")
        return a

    @staticmethod
    async def for_customer(session: AsyncSession, business_id: uuid.UUID, contact_id: uuid.UUID, actor_id: uuid.UUID,
                           *, create: bool = True) -> LedgerAccount | None:
        found = (await session.execute(select(LedgerAccount).where(
            LedgerAccount.business_id == business_id, LedgerAccount.customer_contact_id == contact_id,
        ))).scalars().first()
        if found is not None or not create:
            return found
        contact = await session.get(CustomerContact, contact_id)
        if contact is None or contact.business_id != business_id:
            raise _err("customer_contact_id", "Choose one of your customers")
        acct = LedgerAccount(business_id=business_id, party_type="customer", customer_contact_id=contact.id,
                             display_name=contact.display_name[:160], phone=contact.phone, created_by=actor_id)
        session.add(acct)
        try:
            async with session.begin_nested():
                await session.flush()
        except Exception:  # noqa: BLE001 — opened at the same moment elsewhere: use that one
            found = (await session.execute(select(LedgerAccount).where(
                LedgerAccount.business_id == business_id, LedgerAccount.customer_contact_id == contact_id,
            ))).scalars().first()
            if found is None:
                raise
            return found
        return acct

    @staticmethod
    async def open(session: AsyncSession, business_id: uuid.UUID, actor_id: uuid.UUID,
                   payload: dict[str, Any]) -> LedgerAccount:
        party = payload.get("party_type")
        if party not in ("customer", "supplier"):
            raise _err("party_type", "A customer or a supplier")
        gstin = normalise_gstin(payload.get("gstin"))
        if gstin and gstin_problem(gstin):
            raise _err("gstin", str(gstin_problem(gstin)))
        if party == "customer":
            contact_id = payload.get("customer_contact_id")
            if not contact_id:
                phone = str(payload.get("phone") or "").strip()
                name = str(payload.get("display_name") or "").strip()
                if not phone or not name:
                    raise _err("phone", "Enter the customer's name and phone")
                existing = (await session.execute(select(CustomerContact.id).where(
                    CustomerContact.business_id == business_id, CustomerContact.phone == phone,
                    CustomerContact.deleted_at.is_(None)))).scalars().first()
                if existing is None:
                    contact = CustomerContact(business_id=business_id, display_name=name[:120], phone=phone)
                    session.add(contact)
                    await session.flush()
                    existing = contact.id
                contact_id = existing
            acct = await LedgerService.for_customer(session, business_id, uuid.UUID(str(contact_id)), actor_id)
            assert acct is not None
        else:
            name = str(payload.get("display_name") or "").strip()
            if not name:
                raise _err("display_name", "Enter the supplier's name")
            acct = LedgerAccount(business_id=business_id, party_type="supplier", display_name=name[:160],
                                 phone=(str(payload.get("phone") or "").strip() or None), created_by=actor_id)
            session.add(acct)
            await session.flush()
        await LedgerService.update(session, business_id, actor_id, acct.id, {
            k: payload[k] for k in ("credit_limit", "credit_days", "notes", "gstin") if k in payload})
        opening = money(dec(payload.get("opening_balance") or 0))
        if opening != 0:
            await LedgerService.post(session, business_id, acct.id, kind="opening_balance", amount=opening,
                                     actor_id=actor_id, note="Carried over from before LOCAH")
        return acct

    @staticmethod
    async def update(session: AsyncSession, business_id: uuid.UUID, actor_id: uuid.UUID, account_id: uuid.UUID,
                     payload: dict[str, Any]) -> LedgerAccount:
        acct = await LedgerService.get(session, business_id, account_id, lock=True)
        before = LedgerService.serialize(acct)
        if "credit_limit" in payload:
            limit = payload["credit_limit"]
            if limit in (None, ""):
                acct.credit_limit = None
            else:
                value = money(dec(limit))
                if value < 0:
                    raise _err("credit_limit", "A limit cannot be negative")
                acct.credit_limit = value
        if "credit_days" in payload:
            days = payload["credit_days"]
            if days not in (None, "") and not 0 <= int(days) <= 365:
                raise _err("credit_days", "Between 0 and 365 days")
            acct.credit_days = int(days) if days not in (None, "") else None
        if "notes" in payload:
            acct.notes = (str(payload.get("notes") or "").strip()[:500] or None)
        if "gstin" in payload:
            gstin = normalise_gstin(payload.get("gstin"))
            if gstin and gstin_problem(gstin):
                raise _err("gstin", str(gstin_problem(gstin)))
            acct.gstin = gstin
        if payload.get("status") in ("active", "closed"):
            if payload["status"] == "closed" and dec(acct.balance) != 0:
                raise ConflictError("Settle the balance before closing the account")
            acct.status = payload["status"]
        acct.version += 1
        acct.updated_at = datetime.now(timezone.utc)
        await session.flush()
        await AuditService.record(session, event_type="ledger.account.updated", actor_identity_id=actor_id,
                                  actor_context="business", action="update", business_id=business_id,
                                  resource_type="ledger_account", resource_id=acct.id, before_state=before,
                                  after_state=LedgerService.serialize(acct))
        return acct

    # ------------------------------------------------------------------ entries
    @staticmethod
    async def post(
        session: AsyncSession, business_id: uuid.UUID, account_id: uuid.UUID, *, kind: str, amount: Any,
        actor_id: uuid.UUID | None, entry_date: date | None = None, due_date: date | None = None,
        method: str | None = None, reference: str | None = None, note: str | None = None,
        document_id: uuid.UUID | None = None, shift_id: uuid.UUID | None = None,
        location_id: uuid.UUID | None = None, approved_by: uuid.UUID | None = None,
        idempotency_key: str | None = None,
    ) -> LedgerEntry:
        """Append one entry and move the balance with it, under the account's lock."""
        if kind not in SIGN:
            raise _err("kind", "Unknown entry")
        if idempotency_key:
            prior = (await session.execute(select(LedgerEntry).where(
                LedgerEntry.business_id == business_id, LedgerEntry.idempotency_key == idempotency_key))).scalars().first()
            if prior is not None:
                return prior
        acct = await LedgerService.get(session, business_id, account_id, lock=True)
        if acct.status != "active":
            raise ConflictError("This account is closed")
        allowed = CUSTOMER_KINDS if acct.party_type == "customer" else SUPPLIER_KINDS
        if kind not in allowed:
            raise _err("kind", f"{KIND_LABEL[kind]} does not apply to a {acct.party_type}")
        value = money(dec(amount))
        sign = SIGN[kind]
        if sign is not None:
            if value <= 0:
                raise _err("amount", "Enter an amount above zero")
            value = value * sign
        elif value == 0:
            raise _err("amount", "Enter an amount")
        seq = int((await session.execute(select(func.coalesce(func.max(LedgerEntry.seq), 0)).where(
            LedgerEntry.account_id == acct.id))).scalar()) + 1
        new_balance = dec(acct.balance) + value
        today = entry_date or local_today()
        if due_date is None and value > 0 and kind in ("credit_sale", "purchase") and acct.credit_days is not None:
            due_date = today + timedelta(days=acct.credit_days)
        if method is not None and method not in METHODS:
            raise _err("method", "Choose how it was paid")
        entry = LedgerEntry(
            business_id=business_id, account_id=acct.id, seq=seq, kind=kind, amount=value, balance_after=new_balance,
            entry_date=today, due_date=due_date, method=method, reference=(reference or "")[:120] or None,
            note=(note or "")[:300] or None, document_id=document_id, shift_id=shift_id, location_id=location_id,
            over_limit_approved_by=approved_by, idempotency_key=idempotency_key, created_by=actor_id,
        )
        session.add(entry)
        acct.balance = new_balance
        acct.last_entry_at = datetime.now(timezone.utc)
        acct.version += 1
        await session.flush()
        event = {"business_id": str(business_id), "account_id": str(acct.id), "party_type": acct.party_type,
                 "customer_contact_id": str(acct.customer_contact_id) if acct.customer_contact_id else None,
                 "entry_id": str(entry.id), "kind": kind, "amount": _f(value), "balance_after": _f(new_balance),
                 "document_id": str(document_id) if document_id else None}
        await OutboxService.publish(session, event_type="ledger.entry.posted", business_id=business_id, payload=event)
        if actor_id is not None:
            await AuditService.record(session, event_type="ledger.entry.posted", actor_identity_id=actor_id,
                                      actor_context="business", action=kind, business_id=business_id,
                                      resource_type="ledger_account", resource_id=acct.id, after_state=event)
        if approved_by is not None:
            from platform_core.permissions import LEDGER_MANAGE
            from platform_core.services.notification import NotificationService

            await OutboxService.publish(session, event_type="ledger.limit.overridden", business_id=business_id,
                                        payload=event | {"approved_by": str(approved_by)})
            await NotificationService.fan_out(
                session, business_id=business_id, notification_type="ledger.limit_overridden",
                title=f"Credit above the limit for {acct.display_name}",
                body=f"₹{_f(value):,.2f} on khata; they now owe ₹{_f(new_balance):,.2f} "
                     f"(limit ₹{_f(acct.credit_limit):,.2f}).",
                required_permission=LEDGER_MANAGE, severity="warning", resource_type="ledger_account",
                resource_id=acct.id, location_id=location_id, exclude_identity_id=approved_by,
            )
        return entry

    @staticmethod
    def within_limit(acct: LedgerAccount, amount: Any) -> bool:
        """Would this much more credit stay within the owner's limit? (§14.5)"""
        if acct.credit_limit is None:
            return True
        return bool(dec(acct.balance) + money(dec(amount)) <= dec(acct.credit_limit))

    @staticmethod
    def limit_problem(acct: LedgerAccount, amount: Any) -> ConflictError:
        room = max(ZERO, dec(acct.credit_limit or 0) - dec(acct.balance))
        return ConflictError(
            f"{acct.display_name} would go over their khata limit of ₹{_f(acct.credit_limit):,.2f} "
            f"(₹{_f(acct.balance):,.2f} owed now, ₹{_f(room):,.2f} left). A manager can allow it.",
            details={"needs": "credit_approval", "account_id": str(acct.id), "limit": _f(acct.credit_limit),
                     "balance": _f(acct.balance), "room": _f(room), "amount": _f(money(dec(amount)))})

    # ------------------------------------------------------------------ bills (§14.5)
    @staticmethod
    async def charge_bill(
        session: AsyncSession, doc: InvoicingDocument, amount: Any, actor_id: uuid.UUID, *,
        approved_by: uuid.UUID | None = None, shift_id: uuid.UUID | None = None,
    ) -> LedgerEntry | None:
        """Put the unpaid part of a bill on the customer's khata."""
        value = money(dec(amount))
        if value <= 0:
            return None
        if doc.customer_contact_id is None:
            raise _err("customer_contact_id", "Choose the customer whose khata this goes on")
        found = await LedgerService.for_customer(session, doc.business_id, doc.customer_contact_id, actor_id)
        assert found is not None
        acct = await LedgerService.get(session, doc.business_id, found.id, lock=True)
        over = not LedgerService.within_limit(acct, value)
        if over and approved_by is None:
            raise LedgerService.limit_problem(acct, value)
        return await LedgerService.post(
            session, doc.business_id, acct.id, kind="credit_sale", amount=value, actor_id=actor_id,
            entry_date=doc.issue_date, due_date=doc.due_date, reference=doc.number, document_id=doc.id,
            shift_id=shift_id, location_id=doc.location_id, approved_by=approved_by if over else None,
            idempotency_key=f"bill:{doc.id}")

    @staticmethod
    async def _doc_account(session: AsyncSession, doc: InvoicingDocument) -> uuid.UUID | None:
        ids = [doc.id] + ([doc.original_document_id] if doc.original_document_id else [])
        return (await session.execute(select(LedgerEntry.account_id).where(
            LedgerEntry.business_id == doc.business_id, LedgerEntry.document_id.in_(ids)).limit(1))).scalar()

    @staticmethod
    async def on_bill_payment(session: AsyncSession, doc: InvoicingDocument, payment: InvoicingPayment,
                              actor_id: uuid.UUID) -> LedgerEntry | None:
        """Money recorded against a khata bill lowers the khata too."""
        account_id = await LedgerService._doc_account(session, doc)
        if account_id is None:
            return None
        return await LedgerService.post(
            session, doc.business_id, account_id, kind="payment_received", amount=payment.amount,
            actor_id=actor_id, entry_date=payment.received_on, method=payment.method, reference=doc.number,
            note=payment.reference, document_id=doc.id, location_id=doc.location_id,
            idempotency_key=f"billpay:{payment.id}")

    @staticmethod
    async def on_note(session: AsyncSession, note: InvoicingDocument, actor_id: uuid.UUID) -> LedgerEntry | None:
        """A credit note on a khata bill (goods back, price cut) lowers what is
        owed; a debit note raises it."""
        account_id = await LedgerService._doc_account(session, note)
        if account_id is None or dec(note.amount_due) <= 0:
            return None
        return await LedgerService.post(
            session, note.business_id, account_id,
            kind="return_credit" if note.doc_kind == "credit_note" else "credit_sale", amount=note.amount_due,
            actor_id=actor_id, entry_date=note.issue_date, reference=note.number, document_id=note.id,
            location_id=note.location_id, idempotency_key=f"note:{note.id}")

    @staticmethod
    async def on_cancel(session: AsyncSession, doc: InvoicingDocument, actor_id: uuid.UUID) -> LedgerEntry | None:
        """A cancelled bill or note takes back what it put on the khata."""
        rows = (await session.execute(select(LedgerEntry.account_id, func.sum(LedgerEntry.amount)).where(
            LedgerEntry.business_id == doc.business_id, LedgerEntry.document_id == doc.id,
            LedgerEntry.kind.in_(("credit_sale", "return_credit"))).group_by(LedgerEntry.account_id))).all()
        last = None
        for account_id, net in rows:
            if dec(net) != 0:
                last = await LedgerService.post(
                    session, doc.business_id, account_id, kind="adjustment", amount=-dec(net), actor_id=actor_id,
                    reference=doc.number, note=f"{doc.number} cancelled", document_id=doc.id,
                    location_id=doc.location_id, idempotency_key=f"cancel:{doc.id}")
        return last

    @staticmethod
    async def receive(
        session: AsyncSession, business_id: uuid.UUID, account_id: uuid.UUID, actor_id: uuid.UUID, *,
        amount: Any, method: str, reference: str | None = None, entry_date: date | None = None,
        shift_id: uuid.UUID | None = None, location_id: uuid.UUID | None = None, idempotency_key: str | None = None,
    ) -> tuple[LedgerEntry, list[dict[str, Any]]]:
        """Money received against the account, applied to the oldest open bills."""
        acct = await LedgerService.get(session, business_id, account_id)
        if idempotency_key:
            prior = (await session.execute(select(LedgerEntry).where(
                LedgerEntry.business_id == business_id, LedgerEntry.idempotency_key == idempotency_key))).scalars().first()
            if prior is not None:
                return prior, []
        kind = "payment_received" if acct.party_type == "customer" else "payment_made"
        entry = await LedgerService.post(session, business_id, account_id, kind=kind, amount=amount,
                                         actor_id=actor_id, method=method, reference=reference,
                                         entry_date=entry_date, shift_id=shift_id, location_id=location_id,
                                         idempotency_key=idempotency_key)
        applied: list[dict[str, Any]] = []
        if acct.party_type == "customer":
            applied = await LedgerService._apply_to_bills(session, business_id, acct, -dec(entry.amount), entry,
                                                          actor_id)
        return entry, applied

    @staticmethod
    async def _apply_to_bills(session: AsyncSession, business_id: uuid.UUID, acct: LedgerAccount, amount: Decimal,
                              entry: LedgerEntry, actor_id: uuid.UUID) -> list[dict[str, Any]]:
        """FIFO: settle the customer's oldest open on-account bills."""
        if acct.customer_contact_id is None:
            return []
        bills = list((await session.execute(select(InvoicingDocument).where(
            InvoicingDocument.business_id == business_id, InvoicingDocument.customer_contact_id == acct.customer_contact_id,
            InvoicingDocument.on_account.is_(True), InvoicingDocument.status == "issued",
            InvoicingDocument.doc_kind != "credit_note", InvoicingDocument.amount_due > InvoicingDocument.amount_paid,
        ).order_by(InvoicingDocument.issue_date, InvoicingDocument.seq).with_for_update()
            .execution_options(skip_location_scope=True, populate_existing=True))).scalars())
        credits = {d: dec(v) for d, v in (await session.execute(
            select(InvoicingDocument.original_document_id, func.sum(InvoicingDocument.amount_due)).where(
                InvoicingDocument.original_document_id.in_([b.id for b in bills]),
                InvoicingDocument.doc_kind == "credit_note", InvoicingDocument.status == "issued")
            .group_by(InvoicingDocument.original_document_id))).all()}
        left = amount
        out = []
        for b in bills:
            if left <= 0:
                break
            open_amt = dec(b.amount_due) - dec(b.amount_paid) - credits.get(b.id, ZERO)
            if open_amt <= 0:
                continue
            take = min(open_amt, left)
            session.add(InvoicingPayment(business_id=business_id, document_id=b.id, amount=take,
                                         method=entry.method or "other", reference=f"Khata {entry.reference or ''}".strip()[:120],
                                         received_on=entry.entry_date, recorded_by=actor_id))
            b.amount_paid = dec(b.amount_paid) + take
            b.version += 1
            left -= take
            out.append({"document_id": str(b.id), "number": b.number, "applied": _f(take)})
        await session.flush()
        return out

    # ------------------------------------------------------------------ reads
    @staticmethod
    async def entries(session: AsyncSession, account_id: uuid.UUID) -> list[LedgerEntry]:
        return list((await session.execute(select(LedgerEntry).where(LedgerEntry.account_id == account_id)
                                           .order_by(LedgerEntry.seq))).scalars())

    @staticmethod
    def serialize_entry(e: LedgerEntry, number: str | None = None) -> dict[str, Any]:
        return {"id": str(e.id), "seq": e.seq, "kind": e.kind, "kind_label": KIND_LABEL[e.kind], "amount": _f(e.amount),
                "balance_after": _f(e.balance_after), "entry_date": e.entry_date.isoformat(),
                "due_date": e.due_date.isoformat() if e.due_date else None, "method": e.method,
                "method_label": METHODS.get(e.method or "", None), "reference": e.reference, "note": e.note,
                "document_id": str(e.document_id) if e.document_id else None, "document_number": number,
                "approved_over_limit": e.over_limit_approved_by is not None}

    @staticmethod
    async def detail(session: AsyncSession, business_id: uuid.UUID, account_id: uuid.UUID) -> dict[str, Any]:
        acct = await LedgerService.get(session, business_id, account_id)
        rows = await LedgerService.entries(session, acct.id)
        numbers: dict[Any, str | None] = {r[0]: r[1] for r in (await session.execute(
            select(InvoicingDocument.id, InvoicingDocument.number).where(
                InvoicingDocument.id.in_([e.document_id for e in rows if e.document_id])))).all()}
        ageing = age(rows, local_today(), acct.credit_days)
        return {**LedgerService.serialize(acct, ageing),
                "entries": [LedgerService.serialize_entry(e, numbers.get(e.document_id)) for e in reversed(rows)],
                "kinds": {k: KIND_LABEL[k] for k in (CUSTOMER_KINDS if acct.party_type == "customer" else SUPPLIER_KINDS)},
                "methods": METHODS}

    @staticmethod
    async def list_accounts(session: AsyncSession, business_id: uuid.UUID, *, party_type: str | None = None,
                            q: str | None = None, due_only: bool = False) -> dict[str, Any]:
        query = select(LedgerAccount).where(LedgerAccount.business_id == business_id)
        if party_type:
            query = query.where(LedgerAccount.party_type == party_type)
        if q:
            like = f"%{q.strip()}%"
            query = query.where((LedgerAccount.display_name.ilike(like)) | (LedgerAccount.phone.ilike(like)))
        accounts = list((await session.execute(query.order_by(LedgerAccount.balance.desc(),
                                                              LedgerAccount.display_name))).scalars())
        by_account: dict[uuid.UUID, list[LedgerEntry]] = {a.id: [] for a in accounts}
        if accounts:
            for e in (await session.execute(select(LedgerEntry).where(
                    LedgerEntry.account_id.in_(list(by_account))).order_by(LedgerEntry.seq))).scalars():
                by_account[e.account_id].append(e)
        today = local_today()
        rows = []
        totals = {"receivable": ZERO, "payable": ZERO, "overdue": ZERO}
        for a in accounts:
            ageing = age(by_account[a.id], today, a.credit_days)
            if due_only and ageing.overdue <= 0:
                continue
            rows.append(LedgerService.serialize(a, ageing))
            if a.party_type == "customer":
                totals["receivable"] += max(ZERO, dec(a.balance))
                totals["overdue"] += ageing.overdue
            else:
                totals["payable"] += max(ZERO, dec(a.balance))
        return {"accounts": rows, "totals": {k: _f(v) for k, v in totals.items()}}

    @staticmethod
    async def lookup(session: AsyncSession, business_id: uuid.UUID, phone: str) -> dict[str, Any] | None:
        contact = (await session.execute(select(CustomerContact).where(
            CustomerContact.business_id == business_id, CustomerContact.phone == phone.strip(),
            CustomerContact.deleted_at.is_(None)))).scalars().first()
        if contact is None:
            return None
        acct = await LedgerService.for_customer(session, business_id, contact.id, contact.id, create=False)
        return {"customer_contact_id": str(contact.id), "name": contact.display_name,
                "account": LedgerService.serialize(acct) if acct else None}

    # ------------------------------------------------------------------ statement
    @staticmethod
    async def statement(session: AsyncSession, business_id: uuid.UUID, account_id: uuid.UUID,
                        start: date | None, end: date | None) -> dict[str, Any]:
        acct = await LedgerService.get(session, business_id, account_id)
        rows = await LedgerService.entries(session, acct.id)
        end = end or local_today()
        start = start or (end - timedelta(days=90))
        before = [e for e in rows if e.entry_date < start]
        within = [e for e in rows if start <= e.entry_date <= end]
        opening = dec(before[-1].balance_after) if before else ZERO
        closing = dec(within[-1].balance_after) if within else opening
        numbers: dict[Any, str | None] = {r[0]: r[1] for r in (await session.execute(
            select(InvoicingDocument.id, InvoicingDocument.number).where(
                InvoicingDocument.id.in_([e.document_id for e in within if e.document_id])))).all()}
        return {"account": LedgerService.serialize(acct, age(rows, local_today(), acct.credit_days)),
                "from": start.isoformat(), "to": end.isoformat(), "opening": _f(opening), "closing": _f(closing),
                "entries": [LedgerService.serialize_entry(e, numbers.get(e.document_id)) for e in within]}

    @staticmethod
    async def share(session: AsyncSession, business_id: uuid.UUID, account_id: uuid.UUID) -> dict[str, Any]:
        """The customer's own statement link (their khata, with a UPI link to pay)."""
        acct = await LedgerService.get(session, business_id, account_id)
        if acct.party_type != "customer":
            raise ConflictError("Statements are shared with customers")
        token = statement_token(business_id, acct.id)
        if acct.public_token_hash != _hash(token):
            acct.public_token_hash = _hash(token)
            await session.flush()
        business = await session.get(Business, business_id)
        name = business.display_name if business else ""
        balance = dec(acct.balance)
        owes = (f"₹{_f(balance):,.2f} is due on your account" if balance > 0
                else "Nothing is due on your account" if balance == 0
                else f"You have ₹{_f(-balance):,.2f} with us")
        return {"token": token, "path": f"/{business.slug if business else ''}/khata/{token}", "business_name": name,
                "phone": acct.phone, "message": f"{name}: {owes}. Your statement:"}

    @staticmethod
    async def public_statement(session: AsyncSession, slug: str, token: str) -> dict[str, Any]:
        if not 16 <= len(token) <= 64:
            raise ResourceNotFound("Statement")
        digest = _hash(token)
        await session.execute(text("SELECT set_config('app.current_statement_token', :h, true)"), {"h": digest})
        acct = (await session.execute(select(LedgerAccount).where(LedgerAccount.public_token_hash == digest))).scalars().first()
        if acct is None:
            raise ResourceNotFound("Statement")
        await session.execute(text("SELECT set_config('app.current_business_id', :b, true)"), {"b": str(acct.business_id)})
        row = (await session.execute(text(
            "SELECT b.slug, b.display_name, s.upi_vpa, s.upi_payee_name FROM businesses b "
            "LEFT JOIN pos_settings s ON s.business_id = b.id WHERE b.id = :b"), {"b": str(acct.business_id)})).first()
        entries = await LedgerService.entries(session, acct.id)
        await session.execute(text("SELECT set_config('app.current_business_id', '', true)"))
        if row is None or row[0] != slug:
            raise ResourceNotFound("Statement")
        ageing = age(entries, local_today(), acct.credit_days)
        upi = None
        if row[2] and dec(acct.balance) > 0 and acct.party_type == "customer":
            from platform_core.services.pos import PosService

            upi = PosService.upi_uri(row[2], row[3] or row[1], acct.balance, "Khata")
        return {"business_name": row[1], "name": acct.display_name, "balance": _f(acct.balance),
                "party_type": acct.party_type, "overdue": _f(ageing.overdue),
                "entries": [{k: v for k, v in LedgerService.serialize_entry(e).items()
                             if k in ("kind_label", "amount", "balance_after", "entry_date", "reference")}
                            for e in reversed(entries[-30:])],
                "upi_uri": upi}

    @staticmethod
    def statement_spec(st: dict[str, Any], business: dict[str, Any]) -> Any:
        from platform_core.documents.renderer import DocSpec

        a = st["account"]

        def inr(v: float) -> str:
            return f"₹{v:,.2f}"

        rows = [[e["entry_date"], e["kind_label"] + (f" · {e['document_number']}" if e.get("document_number") else "")
                 + (f" · {e['reference']}" if e.get("reference") else ""),
                 inr(e["amount"]) if e["amount"] > 0 else "", inr(-e["amount"]) if e["amount"] < 0 else "",
                 inr(e["balance_after"])] for e in st["entries"]]
        owes = "owes you" if a["party_type"] == "customer" else "you owe"
        return DocSpec(
            title="Statement of account", issuer=[business.get("name", "")] + ([business["gstin"]] if business.get("gstin") else []),
            date=f"{st['from']} to {st['to']}", party_label="Account", party=[a["display_name"]] + ([a["phone"]] if a.get("phone") else []),
            meta=[("Opening balance", inr(st["opening"]))],
            columns=["Date", "Details", "Up", "Down", "Balance"], align=["l", "l", "r", "r", "r"], rows=rows,
            totals=[("Overdue", inr(a["ageing"]["overdue"])), ("Balance", inr(st["closing"]))],
            notes=[f"Balance means what {a['display_name']} {owes} on {st['to']}."],
        )
