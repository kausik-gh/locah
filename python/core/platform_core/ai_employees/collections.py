"""Collections assistant — overdue bills, reminded with their own payment link.

It finds issued bills past their due date that still owe money, and sends the
same "payment due" WhatsApp template with the bill's own link that the
payment-reminder automation uses. It never writes off, refunds, discounts or
changes a bill: those tools do not exist. A paid bill is simply not
outstanding any more, so reminders stop by themselves. It will not remind the
same bill again inside the owner's minimum gap.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.ai_employees.runtime import AIRuntime, Outcome
from platform_core.models import AIAction, Business, CustomerContact, InvoicingDocument
from platform_core.services.invoicing import INVOICE_KINDS


async def outstanding(session: AsyncSession, business_id: uuid.UUID, *, min_days_overdue: int) -> list[dict[str, Any]]:
    """Issued bills past due by at least ``min_days_overdue`` days that still owe money (T0)."""
    from platform_core.services.invoicing import InvoiceService
    from platform_core.services.invoicing_setup import local_today

    cutoff = local_today() - timedelta(days=min_days_overdue)
    docs = (await session.execute(select(InvoicingDocument).where(
        InvoicingDocument.business_id == business_id, InvoicingDocument.status == "issued",
        InvoicingDocument.doc_kind.in_(tuple(INVOICE_KINDS)), InvoicingDocument.due_date.is_not(None),
        InvoicingDocument.due_date <= cutoff).order_by(InvoicingDocument.due_date.asc()))).scalars().all()
    rows = []
    for doc in docs:
        view = await InvoiceService._money_view(session, doc)
        if view["outstanding"] > 0:
            rows.append({"doc": doc, "outstanding": view["outstanding"]})
    return rows


async def run(session: AsyncSession, business_id: uuid.UUID, *, source: str = "run") -> dict[str, Any]:
    """One pass: find what is overdue, remind within limits. Returns a short report."""
    from platform_core.events.subscribers.messaging_notify import _inr, _send
    from platform_core.services.invoicing import share_token
    from platform_core.site_urls import business_site_url

    emp = await AIRuntime.active(session, business_id, "collections")
    if emp is None:
        return {"ran": False, "reason": "The collections assistant is off, paused, or AI staff is not switched on"}
    limits = emp.limits or {}
    gap = timedelta(days=int(limits.get("min_days_between_reminders", 3)))
    cap = int(limits.get("max_reminders_per_run", 20))
    business = await session.get(Business, business_id)
    assert business is not None
    found: list[dict[str, Any]] = []

    async def look() -> Outcome:
        found.extend(await outstanding(session, business_id, min_days_overdue=int(limits.get("min_days_overdue", 1))))
        return Outcome(f"{len(found)} overdue bill(s) still owe money")

    await AIRuntime.act(session, emp, "find_outstanding", look, input_summary="Overdue, unpaid bills", source=source)
    sent = skipped = 0
    since = datetime.now(timezone.utc) - gap
    for row in found[:cap]:
        doc: InvoicingDocument = row["doc"]
        recent = (await session.execute(select(AIAction.id).where(
            AIAction.business_id == business_id, AIAction.tool == "send_payment_reminder",
            AIAction.related_id == doc.id, AIAction.status == "done", AIAction.created_at >= since))).first()
        if recent is not None:
            skipped += 1
            continue
        contact = await session.get(CustomerContact, doc.customer_contact_id) if doc.customer_contact_id else None
        phone = (doc.buyer or {}).get("phone") or (contact.phone if contact else None)
        amount = row["outstanding"]

        async def remind(doc: InvoicingDocument = doc, phone: Any = phone, amount: Any = amount) -> Outcome:
            link = business_site_url(business.slug, f"/bill/{share_token(business_id, doc.id)}")
            said = await _send(session, business_id, to=phone, key="payment_due", contact_id=doc.customer_contact_id,
                               params=[business.display_name, _inr(amount), link],
                               idem=f"ai:collections:{doc.id}:{datetime.now(timezone.utc).date().isoformat()}")
            if said != "sent":
                return Outcome(f"Bill {doc.number}: {said}", status="failed", related_type="invoice",
                               related_id=doc.id)
            return Outcome(f"Reminded about bill {doc.number} ({_inr(amount)}) with its payment link",
                           related_type="invoice", related_id=doc.id)

        action, _ = await AIRuntime.act(
            session, emp, "send_payment_reminder", remind, source=source, related=("invoice", doc.id),
            input_summary=f"Bill {doc.number}, {_inr(amount)} outstanding, due {doc.due_date}",
            pending_args={"invoice_id": str(doc.id)})
        sent += action.status == "done"
    return {"ran": True, "overdue": len(found), "reminded": sent, "skipped_recently_reminded": skipped}
