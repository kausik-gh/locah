"""The one billing engine's arithmetic (Capability Universe §14, §14.4, §14.6).

Pure and deterministic: the same lines and context always give the same bill,
so an order priced at checkout and the invoice issued for it agree to the
paisa. It computes; it never decides a rate — rates arrive as data the owner
or their CA entered, and a missing rate is reported, never assumed.

Rules implemented here, each one an acceptance test in §14.6:

* Regular scheme, same state (place of supply = seller's state): CGST and SGST
  at half the rate each. Other state: IGST at the full rate.
* Composition scheme and unregistered sellers charge no tax at all: no tax is
  computed, so none can be printed.
* Round-off rounds the payable total to the rupee and is its own figure; it is
  applied after tax, so it never changes the tax.

Prices may include GST (tax is extracted, so the customer pays exactly the
shelf price) or exclude it (tax is added). Discounts come off before tax.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

ZERO = Decimal("0")
SCHEMES = ("regular", "composition", "unregistered")
DOC_KIND_FOR_SCHEME = {"regular": "tax_invoice", "composition": "bill_of_supply", "unregistered": "bill"}


def money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def dec(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value if value is not None else 0))


@dataclass(frozen=True)
class TaxContext:
    scheme: str  # regular | composition | unregistered
    inclusive: bool  # catalogue prices include GST
    intra_state: bool  # place of supply is the seller's state
    round_off: bool = False
    reverse_charge: bool = False

    @property
    def charges_tax(self) -> bool:
        return self.scheme == "regular"


@dataclass(frozen=True)
class LineIn:
    quantity: Decimal
    unit_price: Decimal
    rate: Decimal | None
    discount: Decimal = ZERO  # in the same terms as the price (incl./excl. tax)


@dataclass(frozen=True)
class LineOut:
    gross: Decimal
    discount: Decimal
    taxable: Decimal
    rate: Decimal | None
    cgst: Decimal
    sgst: Decimal
    igst: Decimal
    total: Decimal
    rate_missing: bool = False

    @property
    def tax(self) -> Decimal:
        return self.cgst + self.sgst + self.igst


@dataclass
class Bill:
    lines: list[LineOut] = field(default_factory=list)
    taxable: Decimal = ZERO
    cgst: Decimal = ZERO
    sgst: Decimal = ZERO
    igst: Decimal = ZERO
    round_off: Decimal = ZERO
    grand_total: Decimal = ZERO
    amount_due: Decimal = ZERO
    discount: Decimal = ZERO

    @property
    def tax(self) -> Decimal:
        return self.cgst + self.sgst + self.igst

    @property
    def missing_rates(self) -> list[int]:
        return [i for i, line in enumerate(self.lines) if line.rate_missing]


def _apportion(amounts: list[Decimal], discount: Decimal) -> list[Decimal]:
    """Share a bill-level discount across lines in proportion to their value;
    the last line takes the rounding remainder so the shares sum exactly."""
    base = sum(amounts, ZERO)
    if discount <= 0 or base <= 0:
        return [ZERO for _ in amounts]
    discount = min(discount, base)
    shares: list[Decimal] = []
    running = ZERO
    for i, amount in enumerate(amounts):
        share = discount - running if i == len(amounts) - 1 else money(discount * amount / base)
        shares.append(share)
        running += share
    return shares


def compute_line(line: LineIn, ctx: TaxContext, extra_discount: Decimal = ZERO) -> LineOut:
    gross = money(dec(line.quantity) * dec(line.unit_price))
    discount = min(money(dec(line.discount) + extra_discount), gross)
    amount = gross - discount
    if not ctx.charges_tax:
        return LineOut(gross, discount, amount, None, ZERO, ZERO, ZERO, amount)
    if line.rate is None:
        # Unknown rate: nothing is assumed. Callers decide (an order may still
        # be taken; an invoice may not be issued).
        return LineOut(gross, discount, amount, None, ZERO, ZERO, ZERO, amount, rate_missing=True)
    rate = dec(line.rate)
    if ctx.inclusive:
        if ctx.intra_state:
            half = money(amount * rate / (2 * (100 + rate)))
            return LineOut(gross, discount, amount - 2 * half, rate, half, half, ZERO, amount)
        igst = money(amount * rate / (100 + rate))
        return LineOut(gross, discount, amount - igst, rate, ZERO, ZERO, igst, amount)
    if ctx.intra_state:
        half = money(amount * rate / 200)
        return LineOut(gross, discount, amount, rate, half, half, ZERO, amount + 2 * half)
    igst = money(amount * rate / 100)
    return LineOut(gross, discount, amount, rate, ZERO, ZERO, igst, amount + igst)


def compute(lines: list[LineIn], ctx: TaxContext, *, bill_discount: Any = ZERO) -> Bill:
    grosses = [money(dec(x.quantity) * dec(x.unit_price)) - dec(x.discount) for x in lines]
    shares = _apportion(grosses, money(dec(bill_discount)))
    out = [compute_line(x, ctx, share) for x, share in zip(lines, shares)]
    bill = Bill(lines=out)
    bill.discount = sum((x.discount for x in out), ZERO)
    bill.taxable = sum((x.taxable for x in out), ZERO)
    bill.cgst = sum((x.cgst for x in out), ZERO)
    bill.sgst = sum((x.sgst for x in out), ZERO)
    bill.igst = sum((x.igst for x in out), ZERO)
    if ctx.reverse_charge and ctx.charges_tax:
        # The recipient pays the tax to the government themselves: it is
        # shown, not collected. Round-off applies to what is collected.
        payable = bill.taxable
        bill.grand_total = bill.taxable + bill.tax
    else:
        payable = bill.taxable + bill.tax
        bill.grand_total = payable
    due = payable.quantize(Decimal("1"), rounding=ROUND_HALF_UP) if ctx.round_off else payable
    bill.round_off = due - payable
    if not ctx.reverse_charge:
        bill.grand_total = due
    bill.amount_due = due
    return bill
