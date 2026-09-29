"""Commercial facts a quote carries besides its totals.

Quantity breaks, a minimum order, lead time, a bill-of-quantities section and
a size matrix live on the line. A payment plan and the token (the deposit
already stored on the quote) are what Payments is handed after acceptance.
The conversion payload is the contract Orders, Projects and Invoicing read.
This module does not create an order, a project, an invoice or a payment.
"""

from __future__ import annotations

import hashlib
import secrets
from decimal import Decimal
from typing import Any

from platform_core.exceptions import ValidationError
from platform_core.services.order_calculation import _money

LINE_KINDS = frozenset({"item", "boq", "size_matrix"})
DUE_RULES = frozenset({"on_acceptance", "net_days", "milestone"})
CONVERSION_TARGETS = frozenset({"order", "project", "invoice"})
RFQ_CHANNELS = frozenset({"website", "whatsapp"})
DEFAULT_VALID_DAYS = 7
DEFAULT_DISCOUNT_LIMIT = Decimal("5")
OTP_TTL_MINUTES = 10
OTP_MAX_ATTEMPTS = 5


def _dec(value: Any, default: str = "0") -> Decimal:
    if value is None or value == "":
        return Decimal(default)
    return Decimal(str(value))


def money_str(value: Any) -> str:
    return str(_money(_dec(value)))


def qty_str(value: Any) -> str:
    """A quantity as plain digits. Decimal.normalize() would print 10 as 1E+1."""
    rendered = format(_dec(value), "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered or "0"


def hash_acceptance_code(quote_id: Any, code: str) -> str:
    raw = f"{quote_id}:{code}".encode()
    return hashlib.sha256(raw).hexdigest()


def new_acceptance_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def normalize_breaks(raw: Any) -> list[dict[str, str]]:
    """Highest min_qty at or below the ordered quantity sets the rate."""
    if not raw:
        return []
    if not isinstance(raw, list):
        raise ValidationError("Quantity breaks must be a list")
    cleaned: list[tuple[Decimal, Decimal]] = []
    for row in raw:
        if not isinstance(row, dict):
            raise ValidationError("Each quantity break needs a minimum and a price")
        minimum = _dec(row.get("min_qty"))
        price = _dec(row.get("unit_price"))
        if minimum <= 0:
            raise ValidationError("A quantity break needs a minimum above zero")
        if price < 0:
            raise ValidationError("A quantity break cannot have a negative price")
        cleaned.append((minimum, price))
    cleaned.sort(key=lambda pair: pair[0])
    return [{"min_qty": qty_str(q), "unit_price": money_str(p)} for q, p in cleaned]


def price_from_breaks(quantity: Decimal, breaks: list[dict[str, str]], fallback: Decimal) -> Decimal:
    chosen = fallback
    for row in breaks:
        if quantity >= _dec(row["min_qty"]):
            chosen = _dec(row["unit_price"])
    return chosen


def normalize_sizes(raw: Any) -> list[dict[str, str]]:
    if not raw:
        return []
    if not isinstance(raw, list):
        raise ValidationError("A size matrix must be a list")
    sizes: list[dict[str, str]] = []
    for row in raw:
        if not isinstance(row, dict):
            raise ValidationError("Each size needs a label and a quantity")
        label = str(row.get("size") or "").strip()
        qty = _dec(row.get("quantity"))
        if not label:
            raise ValidationError("Each size needs a label")
        if qty < 0:
            raise ValidationError("A size quantity cannot be negative")
        if qty == 0:
            continue
        sizes.append({"size": label[:40], "quantity": qty_str(qty)})
    return sizes


def prepare_line(raw: dict[str, Any]) -> dict[str, Any]:
    """Turn one incoming line into the snapshot fields stored on the row.

    A size matrix's quantity is the sum of its sizes. Quantity breaks replace
    the typed rate when the quantity reaches a break. A quantity under the
    MOQ is refused before any total is computed.
    """
    kind = str(raw.get("line_kind") or "item")
    if kind not in LINE_KINDS:
        raise ValidationError("A line is an item, a BOQ line, or a size matrix")

    sizes = normalize_sizes(raw.get("size_matrix"))
    if kind == "size_matrix":
        if not sizes:
            raise ValidationError("A size matrix needs at least one size")
        quantity = sum((_dec(row["quantity"]) for row in sizes), Decimal("0"))
    else:
        quantity = _dec(raw.get("quantity") if raw.get("quantity") is not None else 1)
        sizes = []

    if quantity <= 0:
        raise ValidationError("Quantity must be greater than zero")

    moq_raw = raw.get("moq")
    moq = _dec(moq_raw) if moq_raw not in (None, "") else None
    if moq is not None and moq <= 0:
        raise ValidationError("Minimum order quantity must be above zero")
    if moq is not None and quantity < moq:
        raise ValidationError(
            f"Quantity is below the minimum of {moq.normalize()}",
            details={"code": "below_moq", "moq": str(moq.normalize())},
        )

    breaks = normalize_breaks(raw.get("quantity_breaks"))
    typed = raw.get("unit_price")
    fallback = _dec(typed) if typed is not None else Decimal("0")
    unit_price = price_from_breaks(quantity, breaks, fallback) if breaks else fallback

    lead_raw = raw.get("lead_time_days")
    lead_time = None
    if lead_raw not in (None, ""):
        lead_time = int(lead_raw)
        if lead_time < 0:
            raise ValidationError("Lead time cannot be negative")

    section = str(raw.get("boq_section") or "").strip()[:120] or None
    if kind != "boq":
        section = None

    return {
        "line_kind": kind,
        "quantity": quantity,
        "unit_price": unit_price,
        "moq": moq,
        "lead_time_days": lead_time,
        "quantity_breaks": breaks,
        "boq_section": section,
        "size_matrix": sizes,
    }


def normalize_plan(raw: Any) -> list[dict[str, Any]]:
    if not raw:
        return []
    if not isinstance(raw, list):
        raise ValidationError("A payment plan is a list of stages")
    if len(raw) > 24:
        raise ValidationError("A payment plan can have at most 24 stages")
    stages: list[dict[str, Any]] = []
    for index, row in enumerate(raw):
        if not isinstance(row, dict):
            raise ValidationError("Each payment stage needs a label and an amount")
        label = str(row.get("label") or "").strip()[:120]
        if not label:
            raise ValidationError("Each payment stage needs a label")
        amount_type = str(row.get("amount_type") or "amount")
        if amount_type not in {"amount", "percent"}:
            raise ValidationError("A payment stage is an amount or a percent")
        value = _dec(row.get("amount_value"))
        if value < 0:
            raise ValidationError("A payment stage cannot be negative")
        if amount_type == "percent" and value > 100:
            raise ValidationError("A payment stage percent cannot exceed 100")
        due_rule = str(row.get("due_rule") or "on_acceptance")
        if due_rule not in DUE_RULES:
            raise ValidationError("A payment stage is due on acceptance, after a number of days, or at a milestone")
        due_days = row.get("due_days")
        days = None
        if due_days not in (None, ""):
            days = int(due_days)
            if days < 0:
                raise ValidationError("Due days cannot be negative")
        stages.append(
            {
                "label": label,
                "amount_type": amount_type,
                "amount_value": value,
                "due_rule": due_rule,
                "due_days": days,
                "sort_order": index,
            }
        )
    return stages


def resolve_plan_amounts(stages: list[dict[str, Any]], total: Any) -> list[dict[str, str]]:
    """Percents become money against the locked total. Payments does not re-price."""
    base = _dec(total)
    resolved: list[dict[str, str]] = []
    for stage in stages:
        if stage["amount_type"] == "percent":
            amount = _money(base * _dec(stage["amount_value"]) / Decimal("100"))
        else:
            amount = _money(_dec(stage["amount_value"]))
        resolved.append(
            {
                "label": stage["label"],
                "amount": money_str(amount),
                "due_rule": stage["due_rule"],
                "due_days": "" if stage["due_days"] is None else str(stage["due_days"]),
            }
        )
    return resolved


def discount_percent(subtotal: Any, discount_amount: Any) -> Decimal:
    base = _dec(subtotal)
    if base <= 0:
        return Decimal("0.00")
    return (_dec(discount_amount) / base * Decimal("100")).quantize(Decimal("0.01"))


def conversion_contract(
    *,
    quote: dict[str, Any],
    plan: list[dict[str, str]],
    target: str,
) -> dict[str, Any]:
    """The frozen commercial snapshot another module is allowed to consume.

    `target` names who should act. This payload does not insert that record.
    """
    if target not in CONVERSION_TARGETS:
        raise ValidationError("A quote converts toward an order, a project, or an invoice")
    return {
        "contract": "locah.quote.conversion.v1",
        "target": target,
        "business_id": quote["business_id"],
        "quote_id": quote["id"],
        "quote_number": quote["quote_number"],
        "revision": quote["revision"],
        "customer_contact_id": quote.get("customer_contact_id"),
        "currency": quote.get("currency") or "INR",
        "price_locked_at": quote.get("price_locked_at"),
        "totals": {
            "subtotal": quote["subtotal"],
            "discount_amount": quote["discount_amount"],
            "charges_amount": quote["charges_amount"],
            "tax_amount": quote["tax_amount"],
            "total": quote["total"],
            "deposit_amount": quote["deposit_amount"],
        },
        "lines": quote.get("items") or [],
        "charges": quote.get("charges") or [],
        "payment_plan": plan,
        "token_amount": quote["deposit_amount"],
    }


def payment_handoff(
    *,
    quote: dict[str, Any],
    plan: list[dict[str, str]],
) -> dict[str, Any]:
    """Token plus the plan, for Payments to collect. No payment row is written here."""
    return {
        "contract": "locah.quote.payment_handoff.v1",
        "business_id": quote["business_id"],
        "quote_id": quote["id"],
        "quote_number": quote["quote_number"],
        "revision": quote["revision"],
        "customer_contact_id": quote.get("customer_contact_id"),
        "currency": quote.get("currency") or "INR",
        "token_amount": quote["deposit_amount"],
        "total": quote["total"],
        "plan": plan,
    }
