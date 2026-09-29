"""Per-customer export and erasure (CR-08, CO-01; MD §25.1 DPDP "consent, purpose
limits, access / erasure rights … per-customer export and delete, retention
defaults").

Export: everything this business holds about one customer, in one file — their
record, tags, what they agreed to, notes, activity, orders, bookings, bills,
payments, khata, memberships, quotes, enquiries, reviews and WhatsApp messages.

Erasure: their personal details are removed for good — name, phone, email,
tags, notes, enquiry text, WhatsApp messages, delivery addresses, their "My
activity" entries — and consents are withdrawn. What the law makes the business
keep stays, attached to an anonymous record: issued bills with the buyer as
billed (CGST Act s.36: 72 months) and khata entries (books of account). Erasure
waits while something is still open with them — an order in progress, an
upcoming booking, a running membership or a khata balance — so the business
can finish it; the owner is told exactly what.

A customer asks from their own account; the request reaches the business
(Home "Needs you now") and is closed when the business erases or declines
with a reason.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.exceptions import ConflictError, ResourceNotFound, ValidationError
from platform_core.services.audit import AuditService

ERASED_NAME = "Erased customer"
OPEN_ORDER = ("pending", "accepted", "preparing", "ready")
# What is kept after an erasure, and for how long — shown to the owner before
# they confirm and returned with the result (the retention defaults, CO-01).
KEPT = [
    {"what": "Issued bills, with the buyer as billed", "why": "GST law (CGST Act s.36)", "for": "72 months"},
    {"what": "Khata entries (amounts and dates)", "why": "Books of account", "for": "8 years"},
    {"what": "Orders, bookings, payments and memberships — amounts and dates, no name or contact",
     "why": "Your sales records", "for": "As long as you keep your records"},
    {"what": "The record that they agreed to or withdrew consent", "why": "Proof of consent (DPDP)",
     "for": "As long as you keep your records"},
]


def _j(v: Any) -> Any:
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (datetime,)):
        return v.isoformat()
    if isinstance(v, uuid.UUID):
        return str(v)
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return v


async def _rows(session: AsyncSession, sql: str, **params: Any) -> list[dict[str, Any]]:
    res = await session.execute(text(sql), {k: str(v) if isinstance(v, uuid.UUID) else v for k, v in params.items()})
    return [{k: _j(v) for k, v in r._mapping.items()} for r in res.all()]


async def _contact(session: AsyncSession, business_id: uuid.UUID, contact_id: uuid.UUID) -> dict[str, Any]:
    rows = await _rows(session, "SELECT id, display_name, phone, email, status, tags, customer_since, "
                                "last_interaction_at, erased_at, identity_id FROM customer_relationships_contacts "
                                "WHERE business_id = CAST(:b AS uuid) AND id = CAST(:c AS uuid) "
                                "AND deleted_at IS NULL", b=business_id, c=contact_id)
    if not rows:
        raise ResourceNotFound("Customer")
    return rows[0]


async def export(session: AsyncSession, business_id: uuid.UUID, contact_ids: list[uuid.UUID], *,
                 business_name: str) -> dict[str, Any]:
    """One file with everything held about these contacts (one person may have
    more than one record with a business)."""
    if not contact_ids:
        raise ResourceNotFound("Customer")
    q = {"b": business_id, "ids": [str(c) for c in contact_ids]}
    b = "CAST(:b AS uuid)"
    ids = "ANY(CAST(:ids AS uuid[]))"

    async def rows(sql: str) -> list[dict[str, Any]]:
        return await _rows(session, sql, **q)

    return {
        "business": business_name,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "about": "Everything this business keeps about you in LOCAH.",
        "records": await rows(
            "SELECT id, display_name, phone, email, status, tags, language, customer_since, last_interaction_at "
            f"FROM customer_relationships_contacts WHERE business_id = {b} AND id = {ids} AND deleted_at IS NULL"),
        "consents": await rows(
            "SELECT purpose, channel, source, granted_at, withdrawn_at, withdrawn_source FROM customer_consents "
            f"WHERE business_id = {b} AND contact_id = {ids} ORDER BY granted_at"),
        "notes": await rows(
            f"SELECT body, created_at FROM customer_relationships_notes WHERE business_id = {b} AND contact_id = {ids} "
            "ORDER BY created_at"),
        "activity": await rows(
            "SELECT activity_type, summary, occurred_at FROM customer_relationships_timeline_entries "
            f"WHERE business_id = {b} AND contact_id = {ids} ORDER BY occurred_at"),
        "orders": await rows(
            "SELECT o.order_number, o.status, o.channel, o.total_amount, o.payment_status, o.created_at, o.due_at, "
            "(SELECT json_agg(json_build_object('item', li.title, 'quantity', li.quantity, 'price', li.unit_price) "
            "ORDER BY li.sort_order) FROM orders_order_line_items li WHERE li.order_id = o.id) AS items, "
            "(SELECT j.delivery_address FROM fulfilment_jobs j WHERE j.order_id = o.id LIMIT 1) AS delivery_address "
            f"FROM orders_orders o WHERE o.business_id = {b} AND o.customer_contact_id = {ids} "
            "AND o.deleted_at IS NULL ORDER BY o.created_at"),
        "bookings": await rows(
            "SELECT booking_number, title, status, reservation_mode, starts_at, ends_at, total_amount "
            f"FROM bookings_bookings WHERE business_id = {b} AND customer_contact_id = {ids} AND deleted_at IS NULL "
            "ORDER BY starts_at"),
        "bills": await rows(
            "SELECT number, doc_kind, status, issue_date, grand_total, buyer FROM invoicing_documents "
            f"WHERE business_id = {b} AND customer_contact_id = {ids} AND status <> 'draft' ORDER BY issue_date"),
        "payments": await rows(
            "SELECT amount, payment_method, status, purpose, created_at FROM payments_payment_attempts "
            f"WHERE business_id = {b} AND customer_contact_id = {ids} AND deleted_at IS NULL ORDER BY created_at"),
        "khata": await rows(
            "SELECT a.display_name, a.phone, a.balance, a.credit_limit, (SELECT json_agg(json_build_object("
            "'kind', e.kind, 'amount', e.amount, 'date', e.entry_date, 'reference', e.reference) ORDER BY e.seq) "
            f"FROM ledger_entries e WHERE e.account_id = a.id) AS entries FROM ledger_accounts a "
            f"WHERE a.business_id = {b} AND a.customer_contact_id = {ids}"),
        "memberships": await rows(
            "SELECT p.name AS plan, e.status, e.starts_at, e.ends_at FROM memberships_enrolments e "
            f"JOIN memberships_plans p ON p.id = e.plan_id WHERE e.business_id = {b} AND e.customer_contact_id = {ids} "
            "AND e.deleted_at IS NULL"),
        "quotes": await rows(
            f"SELECT quote_number, status, total, created_at FROM quotes_quotes WHERE business_id = {b} "
            f"AND customer_contact_id = {ids} AND deleted_at IS NULL ORDER BY created_at"),
        "enquiries": await rows(
            f"SELECT display_name, phone, email, message, status, created_at FROM leads_leads WHERE business_id = {b} "
            f"AND customer_contact_id = {ids} AND deleted_at IS NULL ORDER BY created_at"),
        "reviews": await rows(
            f"SELECT rating, body, reviewer_name, status, created_at FROM reviews_reviews WHERE business_id = {b} "
            f"AND customer_contact_id = {ids} ORDER BY created_at"),
        "whatsapp_messages": await rows(
            "SELECT m.direction, m.body, m.created_at FROM messaging_messages m JOIN messaging_conversations c "
            f"ON c.id = m.conversation_id WHERE c.business_id = {b} AND c.contact_id = {ids} "
            "ORDER BY m.created_at LIMIT 2000"),
    }


async def blockers(session: AsyncSession, business_id: uuid.UUID, contact_id: uuid.UUID) -> list[str]:
    """What is still open with this customer — erasure waits until it is finished."""
    p = {"b": str(business_id), "c": str(contact_id)}
    out = []
    n = (await session.execute(text(
        "SELECT count(*) FROM orders_orders WHERE business_id = CAST(:b AS uuid) AND customer_contact_id = "
        "CAST(:c AS uuid) AND deleted_at IS NULL AND status = ANY(:s)"), {**p, "s": list(OPEN_ORDER)})).scalar() or 0
    if n:
        out.append(f"{n} order{'s' if n != 1 else ''} still in progress")
    n = (await session.execute(text(
        "SELECT count(*) FROM bookings_bookings WHERE business_id = CAST(:b AS uuid) AND customer_contact_id = "
        "CAST(:c AS uuid) AND deleted_at IS NULL AND starts_at > now() AND status IN ('pending', 'confirmed')"),
        p)).scalar() or 0
    if n:
        out.append(f"{n} upcoming booking{'s' if n != 1 else ''}")
    n = (await session.execute(text(
        "SELECT count(*) FROM memberships_enrolments WHERE business_id = CAST(:b AS uuid) AND customer_contact_id = "
        "CAST(:c AS uuid) AND deleted_at IS NULL AND status = 'active' AND (ends_at IS NULL OR ends_at > now())"),
        p)).scalar() or 0
    if n:
        out.append("a running membership")
    bal = (await session.execute(text(
        "SELECT coalesce(sum(balance), 0) FROM ledger_accounts WHERE business_id = CAST(:b AS uuid) "
        "AND customer_contact_id = CAST(:c AS uuid)"), p)).scalar() or 0
    if Decimal(str(bal)) != 0:
        out.append(f"a khata balance of ₹{abs(Decimal(str(bal))):,.0f}"
                   + (" they owe" if Decimal(str(bal)) > 0 else " you owe them"))
    return out


async def erase(session: AsyncSession, business_id: uuid.UUID, contact_id: uuid.UUID, actor_id: uuid.UUID, *,
                reason: str | None, confirm: str) -> dict[str, Any]:
    contact = await _contact(session, business_id, contact_id)
    if contact["erased_at"]:
        raise ConflictError("This customer's details were already erased")
    if " ".join(str(confirm or "").split()).lower() != " ".join(contact["display_name"].split()).lower():
        raise ValidationError("Type the customer's name exactly to confirm",
                              details={"field": "confirm", "errors": [{"field": "confirm", "message": "Type the name"}]})
    open_items = await blockers(session, business_id, contact_id)
    if open_items:
        raise ConflictError("Finish what is still open first: " + "; ".join(open_items),
                            details={"open": open_items})
    p = {"b": str(business_id), "c": str(contact_id), "now": datetime.now(timezone.utc)}
    scope_c = "business_id = CAST(:b AS uuid) AND customer_contact_id = CAST(:c AS uuid)"
    removed: dict[str, int] = {}

    async def run(key: str, sql: str) -> None:
        res = await session.execute(text(sql), p)
        removed[key] = removed.get(key, 0) + int(getattr(res, "rowcount", 0) or 0)

    await run("notes", "DELETE FROM customer_relationships_notes WHERE business_id = CAST(:b AS uuid) "
                       "AND contact_id = CAST(:c AS uuid)")
    await run("whatsapp_messages", "DELETE FROM messaging_messages WHERE business_id = CAST(:b AS uuid) AND "
                                   "conversation_id IN (SELECT id FROM messaging_conversations WHERE "
                                   "business_id = CAST(:b AS uuid) AND contact_id = CAST(:c AS uuid))")
    await run("whatsapp_chats", "DELETE FROM messaging_conversations WHERE business_id = CAST(:b AS uuid) "
                                "AND contact_id = CAST(:c AS uuid)")
    await run("enquiries", f"UPDATE leads_leads SET display_name = '{ERASED_NAME}', phone = NULL, email = NULL, "
                           f"message = NULL, origin_context = '{{}}'::jsonb WHERE {scope_c}")
    await run("delivery_addresses", "UPDATE fulfilment_jobs SET delivery_address = NULL WHERE business_id = "
                                    "CAST(:b AS uuid) AND order_id IN (SELECT id FROM orders_orders WHERE "
                                    f"{scope_c}) AND delivery_address IS NOT NULL")
    await run("khata_name", f"UPDATE ledger_accounts SET display_name = '{ERASED_NAME}', phone = NULL, notes = NULL "
                            f"WHERE {scope_c}")
    await run("reviews_name", f"UPDATE reviews_reviews SET reviewer_name = NULL WHERE {scope_c}")
    await run("quotes_name", f"UPDATE quotes_quotes SET decided_by_name = NULL WHERE {scope_c}")
    await run("payment_link_notes", f"UPDATE payments_requests SET note = NULL WHERE {scope_c}")
    await run("activity_details", "UPDATE customer_relationships_timeline_entries SET summary = summary - "
                                  "ARRAY['name', 'display_name', 'phone', 'email', 'address', 'message', 'body'] "
                                  "WHERE business_id = CAST(:b AS uuid) AND contact_id = CAST(:c AS uuid)")
    if contact["identity_id"]:
        p["i"] = str(contact["identity_id"])
        await run("my_activity", "DELETE FROM consumer_activity_projections WHERE business_id = CAST(:b AS uuid) "
                                 "AND identity_id = CAST(:i AS uuid)")
    await run("consents_withdrawn", "UPDATE customer_consents SET withdrawn_at = :now, withdrawn_source = 'erasure' "
                                    "WHERE business_id = CAST(:b AS uuid) AND contact_id = CAST(:c AS uuid) "
                                    "AND withdrawn_at IS NULL")
    await session.execute(text(
        f"UPDATE customer_relationships_contacts SET display_name = '{ERASED_NAME}', phone = NULL, email = NULL, "
        "tags = '{}', language = NULL, language_source = NULL, identity_id = NULL, preferred_location_id = NULL, "
        "status = 'archived', erased_at = :now, "
        "updated_at = :now, version = version + 1 WHERE business_id = CAST(:b AS uuid) AND id = CAST(:c AS uuid)"), p)
    await session.execute(text(
        "UPDATE customer_relationships_privacy_requests SET status = 'done', resolved_at = :now, resolved_by = "
        "CAST(:a AS uuid), resolution_note = 'Erased' WHERE business_id = CAST(:b AS uuid) AND contact_id = "
        "CAST(:c AS uuid) AND kind = 'erasure' AND status = 'open'"), {**p, "a": str(actor_id)})
    # The audit keeps who erased and when — never the erased details themselves.
    await AuditService.record(session, event_type="customer.erased", actor_identity_id=actor_id,
                              actor_context="business", action="erase", business_id=business_id,
                              resource_type="customer", resource_id=contact_id,
                              after_state={"reason": (reason or "").strip()[:300] or None,
                                           "removed": {k: v for k, v in removed.items() if v}})
    return {"erased": True, "removed": {k: v for k, v in removed.items() if v}, "kept": KEPT}


class PrivacyRequests:
    @staticmethod
    async def open_for(session: AsyncSession, business_id: uuid.UUID) -> list[dict[str, Any]]:
        return await _rows(session, "SELECT r.id, r.contact_id, r.kind, r.note, r.created_at, c.display_name "
                                    "FROM customer_relationships_privacy_requests r JOIN customer_relationships_contacts c "
                                    "ON c.id = r.contact_id WHERE r.business_id = CAST(:b AS uuid) AND r.status = 'open' "
                                    "ORDER BY r.created_at", b=business_id)

    @staticmethod
    async def for_contact(session: AsyncSession, business_id: uuid.UUID, contact_id: uuid.UUID) -> list[dict[str, Any]]:
        return await _rows(session, "SELECT id, kind, status, source, note, resolution_note, created_at, resolved_at "
                                    "FROM customer_relationships_privacy_requests WHERE business_id = CAST(:b AS uuid) "
                                    "AND contact_id = CAST(:c AS uuid) ORDER BY created_at DESC", b=business_id, c=contact_id)

    @staticmethod
    async def record(session: AsyncSession, business_id: uuid.UUID, contact_id: uuid.UUID, *, kind: str, source: str,
                     identity_id: uuid.UUID | None, note: str | None, status: str = "open") -> dict[str, Any]:
        if kind == "erasure" and status == "open":
            existing = await _rows(session, "SELECT id, created_at FROM customer_relationships_privacy_requests WHERE "
                                            "business_id = CAST(:b AS uuid) AND contact_id = CAST(:c AS uuid) AND "
                                            "kind = 'erasure' AND status = 'open'", b=business_id, c=contact_id)
            if existing:
                return {**existing[0], "already": True}
        row = await _rows(session, "INSERT INTO customer_relationships_privacy_requests (business_id, contact_id, kind, "
                                   "status, source, identity_id, note, resolved_at) VALUES (CAST(:b AS uuid), "
                                   "CAST(:c AS uuid), :k, :s, :src, CAST(:i AS uuid), :n, "
                                   "CASE WHEN :s = 'done' THEN now() END) RETURNING id, created_at",
                          b=business_id, c=contact_id, k=kind, s=status, src=source,
                          i=str(identity_id) if identity_id else None, n=(note or "").strip()[:500] or None)
        return {**row[0], "already": False}

    @staticmethod
    async def decline(session: AsyncSession, business_id: uuid.UUID, request_id: uuid.UUID, actor_id: uuid.UUID,
                      reason: str) -> None:
        reason = " ".join(str(reason or "").split())[:500]
        if not reason:
            raise ValidationError("Say why, so the customer can be told",
                                  details={"field": "reason", "errors": [{"field": "reason", "message": "Say why"}]})
        res = await session.execute(text(
            "UPDATE customer_relationships_privacy_requests SET status = 'declined', resolution_note = :r, "
            "resolved_by = CAST(:a AS uuid), resolved_at = now() WHERE business_id = CAST(:b AS uuid) AND "
            "id = CAST(:id AS uuid) AND status = 'open' RETURNING contact_id"),
            {"r": reason, "a": str(actor_id), "b": str(business_id), "id": str(request_id)})
        row = res.first()
        if row is None:
            raise ResourceNotFound("Request")
        await AuditService.record(session, event_type="customer.privacy_request.declined", actor_identity_id=actor_id,
                                  actor_context="business", action="decline", business_id=business_id,
                                  resource_type="customer", resource_id=row[0], after_state={"reason": reason})
