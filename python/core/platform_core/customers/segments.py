"""Rule-built customer segments (CR-04; MD §6.1 customer-relationships "tags,
segments"; §18.2 Audiences: "ordered biryani 2+ times in 60 days", "membership
expired 15–60 days ago", "lapsed 90 days" — "shows counts; only consented
contacts for WhatsApp").

A segment is a list of rules that must all hold. Members are worked out from
the business's own records each time — orders, bills, bookings, memberships,
khata — so a segment is never a stale copied list. Every query is an ORM
select, so the viewer's location scope applies to the orders, bills and
bookings it reads (a location-limited manager's segments count their
locations' activity only). A rule is offered only when the tool it reads is
switched on. "Within 5 km" and "birthday this month" need a customer location
and a birthday that the customer record does not keep yet; they are not
offered.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import DateTime, Select, and_, cast, column, exists, func, or_, select, table, text, union_all
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.exceptions import ConflictError, ResourceNotFound, ValidationError
from platform_core.models import (
    Booking,
    CustomerContact,
    CustomerSegment,
    InvoicingDocument,
    InvoicingDocumentLine,
    LedgerAccount,
    MembershipEnrolment,
    Offering,
    OrderLineItem,
    SalesOrder,
)
from platform_core.services.audit import AuditService

SALE_KINDS = ("tax_invoice", "bill_of_supply", "bill")
# The consent store (P1-02) is read through its table: marketing consent on WhatsApp.
_CONSENTS = table("customer_consents", column("business_id"), column("contact_id"), column("purpose"),
                  column("channel"), column("withdrawn_at"))
ENDED_ORDER = ("cancelled", "rejected")
NOT_HELD = ("cancelled", "rejected", "no_show")
MAX_RULES = 6

# kind → (words, the tools any one of which it reads, fields)
KINDS: dict[str, dict[str, Any]] = {
    "bought": {"label": "Bought an item", "needs": ("orders", "invoicing"), "fields": ("offering_id", "times", "days")},
    "spent": {"label": "Spent at least", "needs": ("orders", "invoicing"), "fields": ("amount", "days")},
    "lapsed": {"label": "Has not bought or visited for", "needs": ("orders", "invoicing", "bookings"),
               "fields": ("days",)},
    "new": {"label": "Became a customer in the last", "needs": (), "fields": ("days",)},
    "booked": {"label": "Booked", "needs": ("bookings",), "fields": ("times", "days")},
    "membership_ended": {"label": "Membership ended and not renewed", "needs": ("memberships",),
                         "fields": ("from_days", "to_days")},
    "owes": {"label": "Owes on khata", "needs": ("ledger",), "fields": ()},
    "tag": {"label": "Has the tag", "needs": (), "fields": ("tag",)},
}


def _bad(message: str, fld: str = "rules") -> ValidationError:
    return ValidationError(message, details={"field": fld, "errors": [{"field": fld, "message": message}]})


def _int(value: Any, fld: str, lo: int, hi: int) -> int:
    try:
        n = int(str(value).strip())
    except (TypeError, ValueError):
        raise _bad(f"Enter a whole number for {fld.replace('_', ' ')}", fld) from None
    if not lo <= n <= hi:
        raise _bad(f"{fld.replace('_', ' ').capitalize()} must be between {lo} and {hi}", fld)
    return n


def available(live: set[str]) -> list[dict[str, Any]]:
    """The rules this business can use — each only when a tool it reads is on."""
    return [{"kind": k, "label": v["label"], "fields": list(v["fields"])} for k, v in KINDS.items()
            if not v["needs"] or any(m in live for m in v["needs"])]


def clean_rules(raw: Any, live: set[str]) -> list[dict[str, Any]]:
    if not isinstance(raw, list) or not raw:
        raise _bad("Add at least one rule")
    if len(raw) > MAX_RULES:
        raise _bad(f"At most {MAX_RULES} rules in one segment")
    offered = {k["kind"] for k in available(live)}
    out: list[dict[str, Any]] = []
    for r in raw:
        kind = (r or {}).get("kind") if isinstance(r, dict) else None
        if kind not in KINDS:
            raise _bad("Unknown rule")
        if kind not in offered:
            raise _bad(f"“{KINDS[kind]['label']}” needs a tool that is switched off")
        rule: dict[str, Any] = {"kind": kind}
        if "offering_id" in KINDS[kind]["fields"]:
            try:
                rule["offering_id"] = str(uuid.UUID(str(r.get("offering_id"))))
            except (TypeError, ValueError):
                raise _bad("Choose the item", "offering_id") from None
        if "times" in KINDS[kind]["fields"]:
            rule["times"] = _int(r.get("times", 1), "times", 1, 1000)
        if "days" in KINDS[kind]["fields"]:
            rule["days"] = _int(r.get("days"), "days", 1, 1095)
        if kind == "spent":
            try:
                amount = Decimal(str(r.get("amount")).replace(",", "").replace("₹", "").strip())
            except (InvalidOperation, ValueError):
                raise _bad("Enter an amount", "amount") from None
            if amount <= 0:
                raise _bad("Enter an amount above zero", "amount")
            rule["amount"] = str(amount.quantize(Decimal("1")))
        if kind == "membership_ended":
            rule["from_days"] = _int(r.get("from_days", 0), "from_days", 0, 1095)
            rule["to_days"] = _int(r.get("to_days"), "to_days", 1, 1095)
            if rule["to_days"] <= rule["from_days"]:
                raise _bad("The second number of days must be larger than the first", "to_days")
        if kind == "tag":
            tag = " ".join(str(r.get("tag") or "").split()).lower()
            if not tag or len(tag) > 64:
                raise _bad("Choose a tag", "tag")
            rule["tag"] = tag
        out.append(rule)
    return out


def words(rule: dict[str, Any], titles: dict[str, str] | None = None) -> str:
    k = rule["kind"]
    times = f"{rule.get('times', 1)}+ time{'s' if rule.get('times', 1) != 1 else ''}"
    if k == "bought":
        item = (titles or {}).get(rule["offering_id"], "an item")
        return f"Bought {item} {times} in the last {rule['days']} days"
    if k == "spent":
        return f"Spent ₹{int(rule['amount']):,}+ in the last {rule['days']} days"
    if k == "lapsed":
        return f"No purchase or visit in the last {rule['days']} days"
    if k == "new":
        return f"Became a customer in the last {rule['days']} days"
    if k == "booked":
        return f"Booked {times} in the last {rule['days']} days"
    if k == "membership_ended":
        return f"Membership ended {rule['from_days']}–{rule['to_days']} days ago and not renewed"
    if k == "owes":
        return "Owes on khata"
    return f"Tagged “{rule['tag']}”"


# ---------------------------------------------------------------- rule → contact ids
def _purchases(b: uuid.UUID, since: datetime, *, offering_id: uuid.UUID | None = None) -> Any:
    """(contact, transaction, amount, at): orders, and bills not made from an order
    (an order's bill is the same sale — never counted twice)."""
    o = select(SalesOrder.customer_contact_id.label("c"), SalesOrder.id.label("t"),
               SalesOrder.total_amount.label("amount"), SalesOrder.created_at.label("at")).where(
        SalesOrder.business_id == b, SalesOrder.deleted_at.is_(None), SalesOrder.status.notin_(ENDED_ORDER),
        SalesOrder.customer_contact_id.is_not(None), SalesOrder.created_at >= since)
    d = select(InvoicingDocument.customer_contact_id.label("c"), InvoicingDocument.id.label("t"),
               InvoicingDocument.grand_total.label("amount"),
               cast(InvoicingDocument.issue_date, DateTime(timezone=True)).label("at")).where(
        InvoicingDocument.business_id == b, InvoicingDocument.status == "issued",
        InvoicingDocument.doc_kind.in_(SALE_KINDS), InvoicingDocument.order_id.is_(None),
        InvoicingDocument.customer_contact_id.is_not(None), InvoicingDocument.issue_date >= since.date())
    if offering_id is not None:
        o = o.where(exists().where(OrderLineItem.order_id == SalesOrder.id, OrderLineItem.offering_id == offering_id))
        d = d.where(exists().where(InvoicingDocumentLine.document_id == InvoicingDocument.id,
                                   InvoicingDocumentLine.offering_id == offering_id))
    return union_all(o, d).subquery()


def _rule(rule: dict[str, Any], b: uuid.UUID, now: datetime) -> ColumnElement[bool]:
    """A condition on CustomerContact for one rule."""
    k = rule["kind"]
    cond: ColumnElement[bool]
    if k == "new":
        cond = CustomerContact.customer_since >= now - timedelta(days=int(rule["days"]))
    elif k == "tag":
        cond = CustomerContact.tags.any(rule["tag"])
    else:
        cond = CustomerContact.id.in_(_ids(rule, b, now))
    return cond


def _ids(rule: dict[str, Any], b: uuid.UUID, now: datetime) -> Select[Any]:
    k = rule["kind"]
    days = timedelta(days=int(rule.get("days", 0)))
    if k == "bought":
        u = _purchases(b, now - days, offering_id=uuid.UUID(rule["offering_id"]))
        return select(u.c.c).group_by(u.c.c).having(func.count(func.distinct(u.c.t)) >= rule["times"])
    if k == "spent":
        u = _purchases(b, now - days)
        return select(u.c.c).group_by(u.c.c).having(func.sum(u.c.amount) >= Decimal(rule["amount"]))
    if k == "lapsed":
        ever = union_all(
            _purchases_all(b),
            select(Booking.customer_contact_id.label("c"), Booking.starts_at.label("at")).where(
                Booking.business_id == b, Booking.deleted_at.is_(None), Booking.status.notin_(NOT_HELD),
                Booking.customer_contact_id.is_not(None), Booking.starts_at <= now),
        ).subquery()
        return select(ever.c.c).group_by(ever.c.c).having(func.max(ever.c.at) < now - days)
    if k == "booked":
        return (select(Booking.customer_contact_id).where(
            Booking.business_id == b, Booking.deleted_at.is_(None), Booking.status.notin_(NOT_HELD),
            Booking.customer_contact_id.is_not(None), Booking.starts_at >= now - days, Booking.starts_at <= now)
            .group_by(Booking.customer_contact_id).having(func.count() >= rule["times"]))
    if k == "membership_ended":
        current = select(MembershipEnrolment.customer_contact_id).where(
            MembershipEnrolment.business_id == b, MembershipEnrolment.deleted_at.is_(None),
            MembershipEnrolment.status == "active",
            or_(MembershipEnrolment.ends_at.is_(None), MembershipEnrolment.ends_at > now))
        return select(MembershipEnrolment.customer_contact_id).where(
            MembershipEnrolment.business_id == b, MembershipEnrolment.deleted_at.is_(None),
            MembershipEnrolment.ends_at >= now - timedelta(days=rule["to_days"]),
            MembershipEnrolment.ends_at <= now - timedelta(days=rule["from_days"]),
            MembershipEnrolment.customer_contact_id.notin_(current))
    # owes
    return select(LedgerAccount.customer_contact_id).where(
        LedgerAccount.business_id == b, LedgerAccount.party_type == "customer",
        LedgerAccount.customer_contact_id.is_not(None), LedgerAccount.balance > 0)


def _purchases_all(b: uuid.UUID) -> Any:
    o = select(SalesOrder.customer_contact_id.label("c"), SalesOrder.created_at.label("at")).where(
        SalesOrder.business_id == b, SalesOrder.deleted_at.is_(None), SalesOrder.status.notin_(ENDED_ORDER),
        SalesOrder.customer_contact_id.is_not(None))
    d = select(InvoicingDocument.customer_contact_id.label("c"),
               cast(InvoicingDocument.issue_date, DateTime(timezone=True)).label("at")).where(
        InvoicingDocument.business_id == b, InvoicingDocument.status == "issued",
        InvoicingDocument.doc_kind.in_(SALE_KINDS), InvoicingDocument.customer_contact_id.is_not(None))
    return union_all(o, d)


async def evaluate(session: AsyncSession, business_id: uuid.UUID, rules: list[dict[str, Any]], *,
                   limit: int = 200, now: datetime | None = None) -> dict[str, Any]:
    """Who matches every rule: how many, a page of them, and how many said yes
    to offers on WhatsApp (only they may receive a WhatsApp offer — §18.2)."""
    now = now or datetime.now(timezone.utc)
    conds = [_rule(r, business_id, now) for r in rules]
    base = and_(CustomerContact.business_id == business_id, CustomerContact.deleted_at.is_(None),
                CustomerContact.status == "active", *conds)
    count = int((await session.execute(select(func.count()).select_from(CustomerContact).where(base))).scalar() or 0)
    members = (await session.execute(select(CustomerContact).where(base).order_by(CustomerContact.display_name)
                                     .limit(limit))).scalars().all() if limit else []
    consented = int((await session.execute(select(func.count(func.distinct(_CONSENTS.c.contact_id))).where(
        _CONSENTS.c.business_id == business_id, _CONSENTS.c.purpose == "marketing",
        _CONSENTS.c.channel.in_(("whatsapp", "any")), _CONSENTS.c.withdrawn_at.is_(None),
        _CONSENTS.c.contact_id.in_(select(CustomerContact.id).where(base))))).scalar() or 0)
    return {"count": count, "whatsapp_offers": consented,
            "members": [{"id": str(c.id), "display_name": c.display_name, "phone": c.phone,
                         "tags": list(c.tags or []),
                         "last_interaction_at": c.last_interaction_at.isoformat() if c.last_interaction_at else None}
                        for c in members]}


async def titles(session: AsyncSession, business_id: uuid.UUID, rules: list[dict[str, Any]]) -> dict[str, str]:
    ids = [uuid.UUID(r["offering_id"]) for r in rules if r.get("offering_id")]
    if not ids:
        return {}
    rows = (await session.execute(select(Offering.id, Offering.title).where(
        Offering.business_id == business_id, Offering.id.in_(ids)))).all()
    return {str(r[0]): r[1] for r in rows}


class SegmentService:
    @staticmethod
    async def _get(session: AsyncSession, business_id: uuid.UUID, segment_id: uuid.UUID) -> CustomerSegment:
        seg = (await session.execute(select(CustomerSegment).where(
            CustomerSegment.business_id == business_id, CustomerSegment.id == segment_id,
            CustomerSegment.archived_at.is_(None)))).scalars().first()
        if seg is None:
            raise ResourceNotFound("Segment")
        return seg

    @staticmethod
    def _name(raw: Any) -> str:
        name = " ".join(str(raw or "").split())[:80]
        if not name:
            raise _bad("Name the segment, for example “Regulars”", "name")
        return name

    @staticmethod
    async def _unique(session: AsyncSession, business_id: uuid.UUID, name: str, exclude: uuid.UUID | None) -> None:
        q = select(CustomerSegment.id).where(CustomerSegment.business_id == business_id,
                                             CustomerSegment.archived_at.is_(None),
                                             func.lower(CustomerSegment.name) == name.lower())
        if exclude is not None:
            q = q.where(CustomerSegment.id != exclude)
        if (await session.execute(q)).first() is not None:
            raise ConflictError(f"You already have a segment called {name}")

    @staticmethod
    async def serialize(session: AsyncSession, business_id: uuid.UUID, seg: CustomerSegment, *,
                        members: bool = False, limit: int = 200) -> dict[str, Any]:
        names = await titles(session, business_id, seg.rules)
        found = await evaluate(session, business_id, seg.rules, limit=limit if members else 0)
        out = {"id": str(seg.id), "name": seg.name, "rules": seg.rules,
               "rule_words": [words(r, names) for r in seg.rules], "count": found["count"],
               "whatsapp_offers": found["whatsapp_offers"], "version": seg.version,
               "updated_at": seg.updated_at.isoformat() if seg.updated_at else None}
        if members:
            out["members"] = found["members"]
        return out

    @staticmethod
    async def all(session: AsyncSession, business_id: uuid.UUID) -> list[dict[str, Any]]:
        segs = (await session.execute(select(CustomerSegment).where(
            CustomerSegment.business_id == business_id, CustomerSegment.archived_at.is_(None))
            .order_by(CustomerSegment.name))).scalars().all()
        return [await SegmentService.serialize(session, business_id, s) for s in segs]

    @staticmethod
    async def create(session: AsyncSession, business_id: uuid.UUID, actor_id: uuid.UUID, *, name: Any,
                     rules: Any, live: set[str]) -> CustomerSegment:
        clean_name = SegmentService._name(name)
        clean = clean_rules(rules, live)
        await SegmentService._unique(session, business_id, clean_name, None)
        seg = CustomerSegment(business_id=business_id, name=clean_name, rules=clean, created_by=actor_id)
        session.add(seg)
        await session.flush()
        await AuditService.record(session, event_type="customer.segment.created", actor_identity_id=actor_id,
                                  actor_context="business", action="create", business_id=business_id,
                                  resource_type="customer_segment", resource_id=seg.id,
                                  after_state={"name": clean_name, "rules": clean})
        return seg

    @staticmethod
    async def update(session: AsyncSession, business_id: uuid.UUID, actor_id: uuid.UUID, segment_id: uuid.UUID,
                     *, name: Any = None, rules: Any = None, live: set[str], version: int | None = None,
                     archive: bool = False) -> CustomerSegment:
        seg = await SegmentService._get(session, business_id, segment_id)
        if version is not None and version != seg.version:
            raise ConflictError("This segment was changed by someone else — reload and try again")
        before = {"name": seg.name, "rules": seg.rules}
        if archive:
            seg.archived_at = datetime.now(timezone.utc)
        if name is not None:
            seg.name = SegmentService._name(name)
            await SegmentService._unique(session, business_id, seg.name, seg.id)
        if rules is not None:
            seg.rules = clean_rules(rules, live)
        seg.version += 1
        await session.flush()
        await AuditService.record(session, event_type="customer.segment.updated", actor_identity_id=actor_id,
                                  actor_context="business", action="archive" if archive else "update",
                                  business_id=business_id, resource_type="customer_segment", resource_id=seg.id,
                                  before_state=before, after_state={"name": seg.name, "rules": seg.rules})
        return seg

    @staticmethod
    async def tags(session: AsyncSession, business_id: uuid.UUID) -> list[dict[str, Any]]:
        rows = (await session.execute(text(
            "SELECT t, count(*) FROM customer_relationships_contacts c, unnest(c.tags) t "
            "WHERE c.business_id = :b AND c.deleted_at IS NULL GROUP BY t ORDER BY count(*) DESC, t LIMIT 200"),
            {"b": str(business_id)})).all()
        return [{"tag": r[0], "count": int(r[1])} for r in rows]
