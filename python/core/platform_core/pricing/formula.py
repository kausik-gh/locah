"""Formula-priced offerings and the rate board (P1-10D2b; MD §21.2, PDF p.22).

A jeweller's chain: *today's 22K rate × 10.000 g + 12% making + ₹500 stones*.
The same rule serves silver articles, metals or any commodity sold by a rate
the owner enters each day. The owner's numbers are data — nothing here assumes
a metal, a making charge or a tax rate (GST comes from the item's HSN / rate,
IV-06, and is added by the billing engine like any other item).

When the owner enters a rate, every item priced from it gets its new price
(``offerings.price_amount``) with the inputs kept in ``price_formula.last``;
the website, WhatsApp, the counter and checkout keep reading one catalogue
price. Order lines copy ``last`` at confirmation and bill lines keep it as
``price_basis`` — a later rate never changes a sale already made.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.exceptions import ConflictError, ResourceNotFound, ValidationError
from platform_core.models import Offering, PricingRate, PricingRateValue
from platform_core.services.audit import AuditService
from platform_core.services.outbox import OutboxService

MAKING = ("percent", "per_unit", "flat")
UNITS = {"g": "g", "kg": "kg", "ml": "ml", "l": "litre", "piece": "piece", "carat": "carat"}


def _bad(fld: str, message: str) -> ValidationError:
    return ValidationError(message, details={"field": fld, "errors": [{"field": fld, "message": message}]})


def _dec(value: Any, fld: str, places: str = "0.01") -> Decimal:
    try:
        return Decimal(str(value).replace(",", "").replace("₹", "").strip()).quantize(Decimal(places))
    except (InvalidOperation, ValueError):
        raise _bad(fld, "Enter a number") from None


def clean_formula(flow: str, raw: Any) -> dict[str, Any] | None:
    """Validate an item's price formula (structure only; the rate must exist — checked by the service)."""
    if raw in (None, "", {}) or (isinstance(raw, dict) and not raw.get("rate_key")):
        return None
    if flow != "cart":
        raise _bad("price_formula", "Only items sold through a basket or at the counter can be priced from a rate")
    if not isinstance(raw, dict):
        raise _bad("price_formula", "The price formula must be a set of fields")
    qty = _dec(raw.get("quantity"), "price_formula.quantity", "0.001")
    if qty <= 0 or qty > Decimal("1000000"):
        raise _bad("price_formula.quantity", "Enter how much of the rate one piece uses, for example 10.5 g")
    making = None
    m = raw.get("making") or {}
    if m.get("type") not in (None, "", "none"):
        if m.get("type") not in MAKING:
            raise _bad("price_formula.making", "Making charge is a %, an amount per unit or a flat amount")
        value = _dec(m.get("value"), "price_formula.making")
        if value < 0 or (m["type"] == "percent" and value > 500):
            raise _bad("price_formula.making", "Enter a making charge of 0 or more (up to 500%)")
        making = {"type": m["type"], "value": str(value)}
    extra = _dec(raw.get("extra") or 0, "price_formula.extra")
    if extra < 0:
        raise _bad("price_formula.extra", "Extras cannot be negative")
    rounding = raw.get("round") or "rupee"
    if rounding not in ("rupee", "paise"):
        raise _bad("price_formula.round", "Round to the rupee or to the paisa")
    return {"rate_key": str(raw["rate_key"]).strip().lower()[:40], "quantity": str(qty), "making": making,
            "extra": str(extra), "extra_label": (str(raw.get("extra_label") or "").strip()[:40] or None),
            "round": rounding}


def compute(formula: dict[str, Any], rate: Decimal, *, label: str = "", unit: str = "g",
            rate_at: datetime | None = None, rate_value_id: Any = None) -> tuple[Decimal, dict[str, Any]]:
    """Price = rate × quantity + making + extras, rounded as the owner chose. Pure."""
    qty = Decimal(formula["quantity"])
    base = rate * qty
    making = Decimal("0")
    rule = formula.get("making")
    if rule:
        v = Decimal(rule["value"])
        making = base * v / Decimal(100) if rule["type"] == "percent" else v * qty if rule["type"] == "per_unit" else v
    extra = Decimal(formula.get("extra") or "0")
    raw = base + making + extra
    price = raw.quantize(Decimal("1") if formula.get("round", "rupee") == "rupee" else Decimal("0.01"), ROUND_HALF_UP)
    basis = {
        "rate_key": formula["rate_key"], "rate_label": label, "unit": unit, "rate": str(rate),
        "rate_at": rate_at.isoformat() if rate_at else None,
        "rate_value_id": str(rate_value_id) if rate_value_id else None,
        "quantity": formula["quantity"], "base": str(base.quantize(Decimal("0.01"))),
        "making": str(making.quantize(Decimal("0.01"))), "making_rule": rule,
        "extra": str(extra), "extra_label": formula.get("extra_label"), "price": str(price),
    }
    return price, basis


def basis_words(basis: dict[str, Any] | None) -> str | None:
    """"10.000 g × ₹6,450 (22K gold) + making ₹7,740 + stones ₹500" — for bills and cards."""
    if not basis:
        return None
    unit = UNITS.get(str(basis.get("unit")), str(basis.get("unit")))
    qty = Decimal(str(basis["quantity"])).normalize()
    parts = [f"{qty:f} {unit} × ₹{Decimal(str(basis['rate'])).normalize():,f}"
             + (f" ({basis['rate_label']})" if basis.get("rate_label") else "")]
    if Decimal(str(basis.get("making") or 0)) > 0:
        rule = basis.get("making_rule") or {}
        how = f" ({Decimal(rule['value']).normalize():f}%)" if rule.get("type") == "percent" else ""
        parts.append(f"making ₹{Decimal(str(basis['making'])):,.2f}{how}".replace(".00", ""))
    if Decimal(str(basis.get("extra") or 0)) > 0:
        parts.append(f"{basis.get('extra_label') or 'extras'} ₹{Decimal(str(basis['extra'])):,.2f}".replace(".00", ""))
    return " + ".join(parts)


class RateService:
    @staticmethod
    async def _rate(session: AsyncSession, business_id: uuid.UUID, *, key: str | None = None,
                    rate_id: uuid.UUID | None = None) -> PricingRate:
        q = select(PricingRate).where(PricingRate.business_id == business_id, PricingRate.archived_at.is_(None))
        q = q.where(PricingRate.key == key) if key is not None else q.where(PricingRate.id == rate_id)
        rate = (await session.execute(q)).scalars().first()
        if rate is None:
            raise ResourceNotFound("Rate")
        return rate

    @staticmethod
    async def current(session: AsyncSession, rate: PricingRate, at: datetime | None = None) -> PricingRateValue | None:
        q = select(PricingRateValue).where(PricingRateValue.rate_id == rate.id)
        if at is not None:
            q = q.where(PricingRateValue.effective_from <= at)
        return (await session.execute(q.order_by(PricingRateValue.effective_from.desc(),
                                                 PricingRateValue.created_at.desc()).limit(1))).scalars().first()

    @staticmethod
    async def create(session: AsyncSession, business_id: uuid.UUID, actor_id: uuid.UUID, *, label: str,
                     unit: str, key: str | None = None) -> PricingRate:
        label = " ".join(str(label or "").split())[:60]
        if not label:
            raise _bad("label", "Name the rate, for example 22K gold")
        if unit not in UNITS:
            raise _bad("unit", "Choose what the rate is per")
        slug = key or "".join(ch if ch.isalnum() else "_" for ch in label.lower()).strip("_")[:40] or "rate"
        exists = (await session.execute(select(PricingRate).where(
            PricingRate.business_id == business_id, PricingRate.key == slug))).scalars().first()
        if exists is not None:
            raise ConflictError(f"You already have a rate called {exists.label}")
        rate = PricingRate(business_id=business_id, key=slug, label=label, unit=unit, created_by=actor_id)
        session.add(rate)
        await session.flush()
        await AuditService.record(session, event_type="pricing.rate.created", actor_identity_id=actor_id,
                                  actor_context="business", action="create", business_id=business_id,
                                  resource_type="pricing_rate", resource_id=rate.id,
                                  after_state={"key": slug, "label": label, "unit": unit})
        return rate

    @staticmethod
    async def set_value(session: AsyncSession, business_id: uuid.UUID, actor_id: uuid.UUID, rate_id: uuid.UUID, *,
                        value: Any, note: str | None, correlation_id: str) -> dict[str, Any]:
        """Today's rate: kept in the history, and every item priced from it re-priced."""
        rate = await RateService._rate(session, business_id, rate_id=rate_id)
        amount = _dec(value, "value", "0.0001")
        if amount <= 0:
            raise _bad("value", "Enter today's rate")
        row = PricingRateValue(business_id=business_id, rate_id=rate.id, value=amount,
                               effective_from=datetime.now(timezone.utc), note=(note or "").strip()[:200] or None,
                               entered_by=actor_id)
        session.add(row)
        await session.flush()
        changed = await RateService.reprice(session, business_id, rate, row, correlation_id=correlation_id)
        await AuditService.record(session, event_type="pricing.rate.value_set", actor_identity_id=actor_id,
                                  actor_context="business", action="update", business_id=business_id,
                                  resource_type="pricing_rate", resource_id=rate.id,
                                  after_state={"value": str(amount), "items": len(changed)})
        await OutboxService.publish(session, event_type="pricing.rate.updated", business_id=business_id,
                                    payload={"rate_id": str(rate.id), "key": rate.key, "value": str(amount),
                                             "offerings": changed}, correlation_id=correlation_id)
        return {"rate": RateService.serialize(rate, row), "repriced": changed}

    @staticmethod
    async def reprice(session: AsyncSession, business_id: uuid.UUID, rate: PricingRate,
                      value: PricingRateValue | None, *, correlation_id: str) -> list[str]:
        items = (await session.execute(select(Offering).where(
            Offering.business_id == business_id, Offering.deleted_at.is_(None),
            Offering.price_formula["rate_key"].astext == rate.key))).scalars().all()
        changed = []
        for o in items:
            RateService.price_into(o, rate, value)
            changed.append(str(o.id))
            await OutboxService.publish(session, event_type="offering.updated", business_id=business_id,
                                        payload={"business_id": str(business_id), "offering_id": str(o.id),
                                                 "reason": "rate"}, correlation_id=correlation_id)
        return changed

    @staticmethod
    def price_into(o: Offering, rate: PricingRate, value: PricingRateValue | None, *, bump: bool = True) -> None:
        """Set an item's price from the rate (no rate yet → no price: it cannot be sold)."""
        formula = dict(o.price_formula or {})
        formula.pop("last", None)
        if value is None:
            o.price_amount = None
            o.price_formula = formula
        else:
            price, basis = compute(formula, Decimal(str(value.value)), label=rate.label, unit=rate.unit,
                                   rate_at=value.effective_from, rate_value_id=value.id)
            o.price_amount = float(price)
            o.price_type = "fixed"
            o.price_formula = {**formula, "last": basis}
        if bump:  # a re-price from the rate board is its own change to the item
            o.updated_at = datetime.now(timezone.utc)
            o.version += 1

    @staticmethod
    async def apply_to(session: AsyncSession, business_id: uuid.UUID, offering: Offering) -> None:
        """After an item's formula is set or changed: price it from today's rate."""
        if not offering.price_formula:
            return
        try:
            rate = await RateService._rate(session, business_id, key=str(offering.price_formula.get("rate_key")))
        except ResourceNotFound:
            raise _bad("price_formula.rate_key", "Add that rate to your rate board first") from None
        RateService.price_into(offering, rate, await RateService.current(session, rate), bump=False)

    @staticmethod
    def serialize(rate: PricingRate, value: PricingRateValue | None) -> dict[str, Any]:
        return {"id": str(rate.id), "key": rate.key, "label": rate.label, "unit": rate.unit,
                "unit_label": UNITS.get(rate.unit, rate.unit),
                "value": float(value.value) if value is not None else None,
                "effective_from": value.effective_from.isoformat() if value is not None else None}

    @staticmethod
    async def board(session: AsyncSession, business_id: uuid.UUID) -> list[dict[str, Any]]:
        rates = (await session.execute(select(PricingRate).where(
            PricingRate.business_id == business_id, PricingRate.archived_at.is_(None))
            .order_by(PricingRate.created_at))).scalars().all()
        out = []
        for r in rates:
            history = (await session.execute(select(PricingRateValue).where(PricingRateValue.rate_id == r.id)
                                             .order_by(PricingRateValue.effective_from.desc()).limit(10))).scalars().all()
            items = (await session.execute(select(Offering).where(
                Offering.business_id == business_id, Offering.deleted_at.is_(None),
                Offering.price_formula["rate_key"].astext == r.key).order_by(Offering.title))).scalars().all()
            out.append({**RateService.serialize(r, history[0] if history else None),
                        "history": [{"value": float(h.value), "effective_from": h.effective_from.isoformat(),
                                     "note": h.note} for h in history],
                        "items": [{"id": str(o.id), "title": o.title, "status": o.status,
                                   "price_amount": float(o.price_amount) if o.price_amount is not None else None,
                                   "basis": basis_words((o.price_formula or {}).get("last"))} for o in items]})
        return out

    @staticmethod
    async def not_entered_since(session: AsyncSession, business_id: uuid.UUID, since: datetime) -> list[str]:
        """Rates that price a live item but have no value entered since ``since``
        (the start of the owner's day): what Home asks the owner to enter."""
        rates = (await session.execute(select(PricingRate).where(
            PricingRate.business_id == business_id, PricingRate.archived_at.is_(None)))).scalars().all()
        out = []
        for r in rates:
            used = (await session.execute(select(Offering.id).where(
                Offering.business_id == business_id, Offering.deleted_at.is_(None), Offering.status == "active",
                Offering.price_formula["rate_key"].astext == r.key).limit(1))).first()
            if used is None:
                continue
            latest = await RateService.current(session, r)
            if latest is None or latest.effective_from < since:
                out.append(r.label)
        return out
