"""What a business's website shows about each offering, by kind (Capability
Universe §6.3: the kind decides the fields, website section and flow).

Pack prices and choice prices are computed here from the catalogue so the site
never works a price out itself; checkout prices the line again on the server.
A cause shows what has actually been given — the sum of its paid gifts — and
nothing else.
"""

from __future__ import annotations

import uuid
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.catalog.offering_kinds import KINDS
from platform_core.models import Offering, OfferingVariant, OrderLineItem, SalesOrder

PAISE = Decimal("0.01")


async def public_details(
    session: AsyncSession, business_id: uuid.UUID, offerings: list[Offering]
) -> dict[str, dict[str, Any]]:
    ids = [o.id for o in offerings]
    variants: dict[str, list[dict[str, Any]]] = {}
    if ids:
        for v in (await session.execute(
            select(OfferingVariant).where(OfferingVariant.offering_id.in_(ids), OfferingVariant.deleted_at.is_(None),
                                          OfferingVariant.status == "active")
            .order_by(OfferingVariant.sort_order, OfferingVariant.name)
        )).scalars().all():
            variants.setdefault(str(v.offering_id), []).append({
                "id": str(v.id), "name": v.name, "attributes": dict(v.attributes or {}),
                "price_amount": float(v.price_amount) if v.price_amount is not None else None})
    causes = [o.id for o in offerings if o.offering_type == "cause"]
    raised: dict[str, Decimal] = {}
    if causes:
        for oid, total in (await session.execute(
            select(OrderLineItem.offering_id, func.coalesce(func.sum(OrderLineItem.line_total), 0))
            .join(SalesOrder, SalesOrder.id == OrderLineItem.order_id)
            .where(OrderLineItem.offering_id.in_(causes), SalesOrder.payment_status == "paid",
                   SalesOrder.status.notin_(("cancelled", "rejected")), SalesOrder.deleted_at.is_(None))
            .group_by(OrderLineItem.offering_id)
        )).all():
            raised[str(oid)] = Decimal(str(total))

    out: dict[str, dict[str, Any]] = {}
    for o in offerings:
        k = KINDS.get(o.offering_type)
        attrs = dict(o.attributes or {})
        public_keys = {f.key for f in k.fields if f.public} if k else set()
        base = Decimal(str(o.price_amount)) if o.price_amount is not None else None
        packs = []
        for p in o.sell_units or []:
            price = (base * Decimal(p["qty"]) / Decimal(1000)).quantize(PAISE, ROUND_HALF_UP) if base is not None else None
            packs.append({"label": p["label"], "price_amount": float(price) if price is not None else None})
        item: dict[str, Any] = {
            "kind": {"label": k.label, "flow": k.flow, "cta": k.cta, "extra_ctas": list(k.extra_ctas)}
            if k else {"label": o.offering_type, "flow": "enquiry", "cta": "Enquire", "extra_ctas": []},
            "attributes": {key: val for key, val in attrs.items() if key in public_keys},
            "labels": {f.key: f.label for f in k.fields} if k else {},
            "units": {f.key: f.unit for f in k.fields if f.unit} if k else {},
            "option_groups": list(o.option_groups or []),
            "packs": packs,
            "variants": variants.get(str(o.id), []),
        }
        if o.offering_type == "cause":
            item["raised_amount"] = float(raised.get(str(o.id), Decimal(0)))
        if o.preorder:
            item["preorder"] = await _preorder_public(session, business_id, o)
        if (o.price_formula or {}).get("last"):
            # OK-15: the customer sees how today's price is made up (weight × today's rate + making).
            from platform_core.pricing.formula import basis_words

            last = o.price_formula["last"]
            item["price_basis"] = {"words": basis_words(last), "rate_at": last.get("rate_at")}
        out[str(o.id)] = item
    return out


async def _preorder_public(session: AsyncSession, business_id: uuid.UUID, o: Offering) -> dict[str, Any]:
    """What a customer should know before ordering ahead: whether a day is
    needed, the earliest it can be ready, the advance and the cancel window."""
    from platform_core.models import BusinessLocation
    from platform_core.orders import preorder as po

    rules = po.Rules.of(o.preorder)
    if rules is None:
        return {}
    location = (await session.execute(select(BusinessLocation).where(
        BusinessLocation.business_id == business_id, BusinessLocation.status == "active")
        .order_by(BusinessLocation.is_primary.desc(), BusinessLocation.created_at).limit(1))).scalars().first()
    zone = po.zone_of(location)
    price = Decimal(str(o.price_amount or 0))
    plan = await po.plan(session, business_id=business_id, location=location,
                         lines=[po.Line(o, rules, 1, price)], require=False, days=1)
    adv = rules.advance
    return {
        "needed": rules.mode == "required", "lead_hours": rules.lead_hours,
        "earliest_words": po.when_words(plan.earliest, zone) if plan.earliest else None,
        "advance": ({"type": adv["type"], "value": float(adv["value"])} if adv else None),
        "cancel_hours": rules.cancel_hours,
        "window": {"order_until": rules.order_until.isoformat() if rules.order_until else None,
                   "ready_from": rules.ready_from.isoformat() if rules.ready_from else None,
                   "ready_until": rules.ready_until.isoformat() if rules.ready_until else None},
    }
