"""Quote arithmetic — deterministic, and reproducible years later.

Shares `_money` with order_calculation so a quote and the order it converts into
round the same way. What it adds is the parts an order does not have: per-line
discounts, a quote-level discount that has to be apportioned, itemised charges,
and a deposit.

Ordering is the whole design here. Discounts come off before tax, because tax is
owed on what is actually charged; a quote-level discount is apportioned across
lines in proportion to their post-line-discount subtotal, so the tax on each line
still reflects that line's real price. Taking the discount off the final total
instead would tax the customer on money they never paid, and would give a
different answer depending on the mix of tax rates.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from platform_core.services.order_calculation import _money


def _as_decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value if value is not None else 0))


def resolve_discount(
    base: Decimal, discount_type: str | None, discount_value: Any
) -> Decimal:
    """A percent or an amount, resolved to money and capped at the base.

    Capping matters: a 120% discount or a flat discount larger than the line is
    a data-entry slip, and letting it through produces a negative total that
    every downstream total then has to defend against.
    """
    if not discount_type or discount_value is None:
        return Decimal("0")
    value = _as_decimal(discount_value)
    if value <= 0:
        return Decimal("0")
    if discount_type == "percent":
        # Percentages above 100 are meaningless rather than free money.
        pct = min(value, Decimal("100"))
        return Decimal(_money(base * pct / Decimal("100")))
    return Decimal(_money(min(value, base)))


def calculate_line(
    *,
    quantity: Any,
    unit_price: Any,
    tax_rate: Any,
    discount_type: str | None = None,
    discount_value: Any = None,
) -> dict[str, Decimal]:
    """One line, before any quote-level discount is apportioned."""
    qty = _as_decimal(quantity)
    price = _as_decimal(unit_price)
    gross = _money(qty * price)
    discount = resolve_discount(gross, discount_type, discount_value)
    net = gross - discount
    tax = _money(net * _as_decimal(tax_rate) / Decimal("100"))
    return {
        "line_subtotal": gross,
        "line_discount": discount,
        "line_tax": tax,
        "line_total": _money(net + tax),
    }


def calculate_quote(
    *,
    lines: list[dict[str, Any]],
    charges: list[dict[str, Any]] | None = None,
    discount_type: str | None = None,
    discount_value: Any = None,
    deposit_type: str | None = None,
    deposit_value: Any = None,
) -> dict[str, Any]:
    """Recompute a whole quote from its lines, charges and discounts.

    Returns the per-line numbers alongside the totals so both can be stored.
    Storing them is deliberate: a document reprinted in two years must show the
    same figures even if this function is later improved.
    """
    charges = charges or []

    priced: list[dict[str, Decimal]] = []
    for line in lines:
        priced.append(
            calculate_line(
                quantity=line.get("quantity", 1),
                unit_price=line.get("unit_price", 0),
                tax_rate=line.get("tax_rate", 0),
                discount_type=line.get("discount_type"),
                discount_value=line.get("discount_value"),
            )
        )

    gross_subtotal = sum((p["line_subtotal"] for p in priced), Decimal("0"))
    line_discounts = sum((p["line_discount"] for p in priced), Decimal("0"))
    net_subtotal = gross_subtotal - line_discounts

    quote_discount = resolve_discount(net_subtotal, discount_type, discount_value)

    # Apportion the quote-level discount across lines so tax stays correct per
    # line. The last line absorbs the rounding remainder rather than letting the
    # apportioned parts silently fail to sum to the whole.
    apportioned: list[Decimal] = []
    if quote_discount > 0 and net_subtotal > 0:
        running = Decimal("0")
        for index, price in enumerate(priced):
            line_net = price["line_subtotal"] - price["line_discount"]
            if index == len(priced) - 1:
                share = quote_discount - running
            else:
                share = _money(quote_discount * line_net / net_subtotal)
                running += share
            apportioned.append(share)
    else:
        apportioned = [Decimal("0")] * len(priced)

    tax_total = Decimal("0")
    for line, price, share in zip(lines, priced, apportioned, strict=False):
        line_net = price["line_subtotal"] - price["line_discount"] - share
        if line_net < 0:
            line_net = Decimal("0")
        line_tax = _money(line_net * _as_decimal(line.get("tax_rate", 0)) / Decimal("100"))
        price["line_tax"] = line_tax
        price["line_total"] = _money(line_net + line_tax)
        tax_total += line_tax

    charges_total = Decimal("0")
    for charge in charges:
        amount = _money(_as_decimal(charge.get("amount", 0)))
        charges_total += amount
        if charge.get("taxable"):
            tax_total += _money(amount * _as_decimal(charge.get("tax_rate", 0)) / Decimal("100"))

    tax_total = _money(tax_total)
    total = _money(net_subtotal - quote_discount + charges_total + tax_total)
    if total < 0:
        total = Decimal("0")

    deposit = resolve_discount(total, deposit_type, deposit_value)

    return {
        "lines": priced,
        "subtotal": _money(gross_subtotal),
        # Everything the customer was given off, in one number for the document.
        "discount_amount": _money(line_discounts + quote_discount),
        "quote_discount_amount": quote_discount,
        "charges_amount": _money(charges_total),
        "tax_amount": tax_total,
        "total": total,
        "deposit_amount": deposit,
    }
