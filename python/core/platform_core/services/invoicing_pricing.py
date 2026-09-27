"""Orders priced by the billing engine (Capability Universe §14: one billing
engine for counter, website, WhatsApp and B2B).

Before a business has told LOCAH how it bills, orders keep their original
arithmetic (the item's rate added on top). Once a tax profile exists, every
order is priced exactly as its bill will be: GST extracted from or added to
the price as the owner chose, no tax at all for composition or unregistered
sellers, CGST + SGST or IGST from the place of supply, and the round-off line.
So the bill issued later equals what the customer was charged.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.invoicing.states import STATES
from platform_core.invoicing.tax_engine import LineIn, TaxContext, compute, dec
from platform_core.models import (
    BusinessLocation,
    InvoicingRegistration,
    InvoicingTaxProfile,
    Offering,
    OrderLineItem,
    SalesOrder,
)
from platform_core.services.invoicing_setup import InvoicingSetupService, TaxRateService, local_today


async def _registration_for(session: AsyncSession, business_id: uuid.UUID,
                            location_id: uuid.UUID) -> InvoicingRegistration | None:
    register = await InvoicingSetupService.register_for_location(session, business_id, location_id)
    if register is not None:
        return await session.get(InvoicingRegistration, register.registration_id)
    regs = [r for r in await InvoicingSetupService.registrations(session, business_id) if r.status == "active"]
    return regs[0] if len(regs) == 1 else None


async def price_order(
    session: AsyncSession, *, business_id: uuid.UUID, order: SalesOrder, lines: list[OrderLineItem],
    discount: Decimal, place_of_supply: str | None,
) -> bool:
    """Price `order` with the engine. Returns False (legacy pricing applies)
    when the business has not set up billing yet."""
    profile = await session.get(InvoicingTaxProfile, business_id)
    if profile is None:
        return False
    reg = await _registration_for(session, business_id, order.location_id)
    if reg is None:
        return False
    location = await session.get(BusinessLocation, order.location_id)
    today = local_today(location.timezone if location else None)
    offerings = {o.id: o for o in (await session.execute(
        select(Offering).where(Offering.id.in_([x.offering_id for x in lines]))
    )).scalars()}
    rates = await TaxRateService.resolve(
        session, business_id,
        [(x.offering_id, offerings[x.offering_id].hsn_sac if x.offering_id in offerings else None,
          offerings[x.offering_id].tax_rate if x.offering_id in offerings else None) for x in lines],
        today,
    )
    pos = place_of_supply if place_of_supply in STATES else reg.state_code
    if reg.scheme == "unregistered":
        pos = None
    intra = pos is None or pos == reg.state_code
    ctx = TaxContext(reg.scheme, profile.prices_include_tax, intra, profile.round_off)
    bill = compute([LineIn(Decimal(x.quantity), dec(x.unit_price), r) for x, r in zip(lines, rates)], ctx,
                   bill_discount=discount)
    for item, out in zip(lines, bill.lines):
        item.tax_rate = float(out.rate) if out.rate is not None else None
        item.line_subtotal = float(out.taxable)
        item.line_tax = float(out.tax)
        item.line_total = float(out.total)
    order.subtotal = float(bill.taxable + bill.discount)
    order.tax_amount = float(bill.tax)
    order.discount_amount = float(bill.discount)
    order.round_off = float(bill.round_off)
    order.total_amount = float(bill.amount_due)
    basis: dict[str, Any] = {
        "engine": "gst-v1", "scheme": reg.scheme, "inclusive": profile.prices_include_tax,
        "round_off": profile.round_off, "place_of_supply": pos, "intra_state": intra,
        "registration_id": str(reg.id), "rates_missing": [lines[i].title for i in bill.missing_rates],
    }
    order.tax_basis = basis
    return True
