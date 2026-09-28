"""Money as integer minor units + ISO 4217 currency (Capability Universe §24 #6).

LOCAH stores new money as `*_minor BIGINT` + `currency` — paise for INR —
matching ChitBridge's stamped `{amount, currency}`. Arithmetic never touches a
float. First Launch tables keep their exact NUMERIC(12,2) columns; `Money`
converts those without loss (`from_decimal`), so both meet at one type.

Rounding is half-up to the minor unit, the convention Indian invoices use for
tax lines. Splitting a sum (tax components, instalments) uses `allocate`, which
never loses or invents a paisa.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

# Minor units per currency (ISO 4217 exponent). Only what LOCAH handles.
EXPONENT: dict[str, int] = {"INR": 2, "USD": 2, "EUR": 2, "GBP": 2, "AED": 2, "SGD": 2, "AUD": 2, "JPY": 0}
SYMBOL: dict[str, str] = {"INR": "₹", "USD": "$", "EUR": "€", "GBP": "£", "AED": "AED ", "SGD": "S$",
                          "AUD": "A$", "JPY": "¥"}


class CurrencyMismatch(ValueError):
    pass


def _exp(currency: str) -> int:
    try:
        return EXPONENT[currency]
    except KeyError as exc:
        raise ValueError(f"unsupported currency {currency!r}") from exc


@dataclass(frozen=True, order=True)
class Money:
    minor: int
    currency: str = "INR"

    def __post_init__(self) -> None:
        if not isinstance(self.minor, int) or isinstance(self.minor, bool):
            raise TypeError("Money.minor must be an int (minor units), never a float")
        _exp(self.currency)

    # ------------------------------------------------------------ construct
    @staticmethod
    def zero(currency: str = "INR") -> Money:
        return Money(0, currency)

    @staticmethod
    def from_decimal(value: Decimal | str | int, currency: str = "INR") -> Money:
        """Exact from a decimal amount in major units (never pass a float)."""
        if isinstance(value, float):
            raise TypeError("pass a Decimal or string, never a float")
        q = Decimal(10) ** -_exp(currency)
        major = Decimal(str(value)).quantize(q, rounding=ROUND_HALF_UP)
        return Money(int(major.scaleb(_exp(currency))), currency)

    # ------------------------------------------------------------ read
    def to_decimal(self) -> Decimal:
        return Decimal(self.minor).scaleb(-_exp(self.currency))

    def stamped(self) -> dict[str, Any]:
        """ChitBridge-style stamped money."""
        return {"amount_minor": self.minor, "currency": self.currency}

    def format(self) -> str:
        """Indian digit grouping for INR (₹1,23,456.50); western otherwise."""
        sign = "-" if self.minor < 0 else ""
        d = abs(self.to_decimal())
        exp = _exp(self.currency)
        whole, _, frac = f"{d:.{exp}f}".partition(".")
        if self.currency == "INR" and len(whole) > 3:
            head, tail = whole[:-3], whole[-3:]
            groups: list[str] = []
            while len(head) > 2:
                groups.insert(0, head[-2:])
                head = head[:-2]
            if head:
                groups.insert(0, head)
            whole = ",".join(groups + [tail])
        elif len(whole) > 3:
            whole = f"{int(whole):,}"
        return f"{sign}{SYMBOL.get(self.currency, self.currency + ' ')}{whole}{'.' + frac if exp else ''}"

    # ------------------------------------------------------------ arithmetic
    def _same(self, other: Money) -> None:
        if other.currency != self.currency:
            raise CurrencyMismatch(f"{self.currency} vs {other.currency}")

    def __add__(self, other: Money) -> Money:
        self._same(other)
        return Money(self.minor + other.minor, self.currency)

    def __sub__(self, other: Money) -> Money:
        self._same(other)
        return Money(self.minor - other.minor, self.currency)

    def __neg__(self) -> Money:
        return Money(-self.minor, self.currency)

    def times(self, quantity: Decimal | int | str) -> Money:
        """Price × quantity (quantity may be fractional: 0.75 kg), rounded half-up."""
        raw = Decimal(self.minor) * Decimal(str(quantity))
        return Money(int(raw.quantize(Decimal(1), rounding=ROUND_HALF_UP)), self.currency)

    def percent(self, rate: Decimal | int | str) -> Money:
        """This amount × rate% (e.g. 9 for 9 %), rounded half-up to the minor unit."""
        raw = Decimal(self.minor) * Decimal(str(rate)) / Decimal(100)
        return Money(int(raw.quantize(Decimal(1), rounding=ROUND_HALF_UP)), self.currency)

    def allocate(self, ratios: list[int | Decimal]) -> list[Money]:
        """Split without losing a paisa: remainders go to the largest shares first."""
        if not ratios or any(Decimal(str(r)) < 0 for r in ratios):
            raise ValueError("ratios must be non-negative and non-empty")
        total = sum(Decimal(str(r)) for r in ratios)
        if total == 0:
            raise ValueError("ratios sum to zero")
        exact = [Decimal(self.minor) * Decimal(str(r)) / total for r in ratios]
        floors = [int(e.to_integral_value(rounding="ROUND_FLOOR")) for e in exact]
        left = self.minor - sum(floors)
        order = sorted(range(len(ratios)), key=lambda i: (exact[i] - floors[i], exact[i]), reverse=True)
        for i in order[:left]:
            floors[i] += 1
        return [Money(v, self.currency) for v in floors]

    def is_zero(self) -> bool:
        return self.minor == 0


def total(items: list[Money], currency: str = "INR") -> Money:
    acc = Money.zero(currency)
    for m in items:
        acc = acc + m
    return acc
