"""Order total calculation helpers (Stage 6)."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_line(
    *,
    unit_price: Decimal,
    quantity: int,
    tax_rate: Decimal | None,
) -> dict[str, Decimal]:
    line_subtotal = _money(unit_price * quantity)
    rate = tax_rate or Decimal("0")
    line_tax = _money(line_subtotal * rate / Decimal("100"))
    line_total = _money(line_subtotal + line_tax)
    return {
        "line_subtotal": line_subtotal,
        "line_tax": line_tax,
        "line_total": line_total,
    }


def calculate_order_totals(
    lines: list[dict[str, Any]],
    *,
    discount_amount: Decimal,
) -> dict[str, Decimal]:
    subtotal = Decimal("0")
    tax_amount = Decimal("0")
    for line in lines:
        subtotal += Decimal(str(line["line_subtotal"]))
        tax_amount += Decimal(str(line["line_tax"]))
    subtotal = _money(subtotal)
    tax_amount = _money(tax_amount)
    discount = _money(max(discount_amount, Decimal("0")))
    total = _money(subtotal + tax_amount - discount)
    if total < 0:
        total = Decimal("0")
    return {
        "subtotal": subtotal,
        "tax_amount": tax_amount,
        "discount_amount": discount,
        "total_amount": total,
    }
