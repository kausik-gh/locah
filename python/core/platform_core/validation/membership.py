"""Membership domain validation (Stage 6 — Doc 11 §9.5).

Fixed-duration plans and explicit manual renewal only. `recurring` billing is
reserved for FL-DEC-005 and is rejected at write time until that decision closes.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from platform_core.exceptions import ResourceStateDenied, ValidationError

NAME_MIN = 1
NAME_MAX = 160
DESC_MAX = 2000
REASON_MAX = 500
DURATION_MAX_DAYS = 3650

PLAN_STATUSES = frozenset({"draft", "active", "archived"})
PLAN_VISIBILITY = frozenset({"public", "private"})
BILLING_MODELS = frozenset({"fixed_duration", "recurring"})
LAUNCH_BILLING_MODELS = frozenset({"fixed_duration"})  # FL-DEC-005 gate

ENROLMENT_STATUSES = frozenset(
    {"pending", "active", "paused", "expired", "cancelled", "completed"}
)
ENROLMENT_TERMINAL = frozenset({"expired", "cancelled", "completed"})
PAYMENT_METHODS = frozenset({"cod", "online", "pay_at_business", "pay_later"})

# Manual lifecycle. Expiry is service/scheduler-driven from `ends_at`.
# Manual transitions an owner may make. Everything else (active, grace,
# expired, paused by a freeze) is recalculated from what happened (P2-02).
ALLOWED_ENROLMENT_TRANSITIONS: dict[str, frozenset[str]] = {
    "pending": frozenset({"active", "cancelled"}),
    "active": frozenset({"paused", "cancelled", "expired", "completed"}),
    "paused": frozenset({"active", "cancelled", "expired"}),
    "grace": frozenset({"cancelled"}),
    "expired": frozenset({"cancelled"}),
    "cancelled": frozenset(),
    "completed": frozenset(),
}

PLAN_KINDS = frozenset({"access", "session_pack", "recurring_delivery", "service_contract", "fee_plan",
                        "member_dues"})
CONSUME_ON = frozenset({"booked", "completed", "checkin"})
SOURCE_REF_TYPES = frozenset({"academic_enrolment", "customer_asset"})

ENROLMENT_STATUS_EVENT_MAP: dict[str, str] = {
    "active": "membership.enrolment.activated",
    "paused": "membership.enrolment.paused",
    "expired": "membership.enrolment.expired",
    "cancelled": "membership.enrolment.cancelled",
    "completed": "membership.enrolment.completed",
}


def _field_error(field: str, message: str) -> dict[str, str]:
    return {"field": field, "message": message}


def validate_uuid(value: Any, *, field: str) -> UUID:
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (ValueError, TypeError) as exc:
        raise ValidationError(
            f"Invalid UUID for {field}",
            details={"errors": [_field_error(field, "Must be a valid UUID")]},
        ) from exc


def validate_optional_uuid(value: Any, *, field: str) -> UUID | None:
    if value is None:
        return None
    return validate_uuid(value, field=field)


def validate_name(name: Any) -> str:
    if name is None or not str(name).strip():
        raise ValidationError(
            "Plan name is required",
            details={"errors": [_field_error("name", "Plan name is required")]},
        )
    normalized = str(name).strip()
    if not (NAME_MIN <= len(normalized) <= NAME_MAX):
        raise ValidationError(
            "Invalid plan name length",
            details={"errors": [_field_error("name", f"Name must be 1–{NAME_MAX} characters")]},
        )
    return normalized


def validate_description(value: Any) -> str | None:
    if value is None or not str(value).strip():
        return None
    normalized = str(value).strip()
    if len(normalized) > DESC_MAX:
        raise ValidationError(
            "Description too long",
            details={"errors": [_field_error("description", f"At most {DESC_MAX} characters")]},
        )
    return normalized


def validate_amount(value: Any, *, field: str = "price_amount") -> float:
    if value is None:
        return 0.0
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError) as exc:
        raise ValidationError(
            "Invalid amount",
            details={"errors": [_field_error(field, "Must be a number")]},
        ) from exc
    if amount < 0:
        raise ValidationError(
            "Amount cannot be negative",
            details={"errors": [_field_error(field, "Must be zero or positive")]},
        )
    return float(amount)


def validate_currency(value: Any) -> str:
    return str(value or "INR").strip().upper()


def validate_billing_model(value: Any) -> str:
    normalized = str(value or "fixed_duration").strip().lower()
    if normalized not in BILLING_MODELS:
        raise ValidationError(
            "Invalid billing model",
            details={
                "errors": [
                    _field_error(
                        "billing_model",
                        f"Must be one of: {', '.join(sorted(BILLING_MODELS))}",
                    )
                ]
            },
        )
    if normalized not in LAUNCH_BILLING_MODELS:
        raise ValidationError(
            "Recurring membership billing is not available at First Launch",
            details={
                "errors": [
                    _field_error(
                        "billing_model",
                        "Only fixed_duration plans can be created (FL-DEC-005 pending)",
                    )
                ]
            },
        )
    return normalized


def validate_duration_days(value: Any, *, required: bool = True) -> int | None:
    if value is None:
        if required:
            raise ValidationError(
                "Plan duration is required",
                details={
                    "errors": [_field_error("duration_days", "duration_days is required")]
                },
            )
        return None
    try:
        days = int(value)
    except (ValueError, TypeError) as exc:
        raise ValidationError(
            "Invalid duration",
            details={"errors": [_field_error("duration_days", "Must be a whole number of days")]},
        ) from exc
    if not (1 <= days <= DURATION_MAX_DAYS):
        raise ValidationError(
            "Duration out of range",
            details={
                "errors": [
                    _field_error("duration_days", f"Must be between 1 and {DURATION_MAX_DAYS} days")
                ]
            },
        )
    return days


def validate_plan_status(value: Any) -> str:
    normalized = str(value or "draft").strip().lower()
    if normalized not in PLAN_STATUSES:
        raise ValidationError(
            "Invalid plan status",
            details={
                "errors": [
                    _field_error("status", f"Must be one of: {', '.join(sorted(PLAN_STATUSES))}")
                ]
            },
        )
    return normalized


def validate_visibility(value: Any) -> str:
    normalized = str(value or "private").strip().lower()
    if normalized not in PLAN_VISIBILITY:
        raise ValidationError(
            "Invalid visibility",
            details={
                "errors": [
                    _field_error("visibility", f"Must be one of: {', '.join(sorted(PLAN_VISIBILITY))}")
                ]
            },
        )
    return normalized


def validate_reason(value: Any, *, field: str = "reason") -> str | None:
    if value is None or not str(value).strip():
        return None
    normalized = str(value).strip()
    if len(normalized) > REASON_MAX:
        raise ValidationError(
            "Reason too long",
            details={"errors": [_field_error(field, f"At most {REASON_MAX} characters")]},
        )
    return normalized


def validate_datetime(value: Any, *, field: str) -> datetime:
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError) as exc:
        raise ValidationError(
            f"Invalid timestamp for {field}",
            details={"errors": [_field_error(field, "Must be an ISO-8601 datetime")]},
        ) from exc


# ---------------------------------------------------------------------------
# Payloads
# ---------------------------------------------------------------------------
def validate_plan_create_payload(raw: dict[str, Any]) -> dict[str, Any]:
    kind = _kind(raw.get("plan_kind"))
    timing = _timing(raw.get("billing_timing"))
    ongoing = kind == "recurring_delivery" and timing == "postpaid"
    out = {
        "name": validate_name(raw.get("name")),
        "description": validate_description(raw.get("description")),
        "offering_id": validate_optional_uuid(raw.get("offering_id"), field="offering_id"),
        "price_amount": validate_amount(raw.get("price_amount")),
        "currency": validate_currency(raw.get("currency")),
        "billing_model": validate_billing_model(raw.get("billing_model")),
        "duration_days": validate_duration_days(raw.get("duration_days"), required=not ongoing),
        "status": validate_plan_status(raw.get("status")),
        "visibility": validate_visibility(raw.get("visibility")),
        "offering_access": _validate_offering_access(raw.get("offering_access")),
        "plan_kind": kind,
        "billing_timing": timing,
        **validate_plan_rules(raw, kind=kind),
    }
    _require_kind_fields(out)
    return out


def _kind(value: Any) -> str:
    kind = str(value or "access").strip().lower()
    if kind not in PLAN_KINDS:
        raise ValidationError("Unknown kind of plan", details={"errors": [_field_error(
            "plan_kind", "Membership, session pack, subscription, service contract, fee plan or dues")]})
    return kind


def _timing(value: Any) -> str:
    timing = str(value or "prepaid").strip().lower()
    if timing not in ("prepaid", "postpaid"):
        raise ValidationError("Prepaid or postpaid", details={"errors": [_field_error("billing_timing", "prepaid|postpaid")]})
    return timing


def _int(raw: dict[str, Any], field: str, lo: int, hi: int) -> int | None:
    if raw.get(field) in (None, ""):
        return None
    try:
        v = int(raw[field])
    except (TypeError, ValueError):
        raise ValidationError("Whole number", details={"errors": [_field_error(field, "Must be a whole number")]}) from None
    if not lo <= v <= hi:
        raise ValidationError("Out of range", details={"errors": [_field_error(field, f"Between {lo} and {hi}")]})
    return v


def validate_plan_rules(raw: dict[str, Any], *, kind: str | None) -> dict[str, Any]:
    """The rules a plan kind carries: grace, freezes, sessions, delivery,
    instalments, visits. Only keys present in `raw` are returned for patches."""
    out: dict[str, Any] = {}
    if "grace_days" in raw or kind is not None:
        out["grace_days"] = _int(raw, "grace_days", 0, 90) or 0
    for flag in ("grace_allows_entry", "freeze_allowed", "no_show_consumes"):
        if flag in raw or kind is not None:
            out[flag] = bool(raw.get(flag, flag == "no_show_consumes"))
    if "max_freeze_days" in raw or kind is not None:
        out["max_freeze_days"] = _int(raw, "max_freeze_days", 1, 365)
    if "sessions_included" in raw or kind is not None:
        out["sessions_included"] = _int(raw, "sessions_included", 1, 1000)
    if "consume_on" in raw or kind is not None:
        consume = str(raw.get("consume_on") or "completed")
        if consume not in CONSUME_ON:
            raise ValidationError("When a session counts", details={"errors": [_field_error(
                "consume_on", "booked, completed or checkin")]})
        out["consume_on"] = consume
    if "delivery" in raw or kind is not None:
        out["delivery"] = dict(raw["delivery"]) if isinstance(raw.get("delivery"), dict) else None
    if "instalment_template" in raw or kind is not None:
        rows = raw.get("instalment_template")
        if rows is not None and not isinstance(rows, list):
            raise ValidationError("Instalments are a list", details={"errors": [_field_error(
                "instalment_template", "A list of {label, amount, due_after_days}")]})
        clean = []
        for i, row in enumerate(rows or []):
            amount = validate_amount(row.get("amount"), field=f"instalment_template[{i}].amount")
            if amount <= 0:
                raise ValidationError("Instalment amount", details={"errors": [_field_error(
                    f"instalment_template[{i}].amount", "Must be more than zero")]})
            clean.append({"label": str(row.get("label") or f"Instalment {i + 1}")[:80], "amount": amount,
                          "due_after_days": _int(row, "due_after_days", 0, 3650) or 0})
        out["instalment_template"] = clean or None
    if "visits_included" in raw or kind is not None:
        out["visits_included"] = _int(raw, "visits_included", 1, 365)
    if "visit_every_days" in raw or kind is not None:
        out["visit_every_days"] = _int(raw, "visit_every_days", 1, 366)
    return out


def _require_kind_fields(v: dict[str, Any]) -> None:
    kind = v["plan_kind"]
    if kind == "session_pack" and not v.get("sessions_included"):
        raise ValidationError("How many sessions", details={"errors": [_field_error(
            "sessions_included", "A session pack needs the number of sessions")]})
    if kind == "recurring_delivery" and not (v.get("delivery") or {}).get("offering_id"):
        raise ValidationError("What is delivered", details={"errors": [_field_error(
            "delivery", "A subscription needs the item delivered (delivery.offering_id)")]})
    if kind == "fee_plan" and not v.get("instalment_template"):
        raise ValidationError("Fee instalments", details={"errors": [_field_error(
            "instalment_template", "A fee plan needs its instalments")]})


def validate_plan_patch_payload(raw: dict[str, Any]) -> dict[str, Any]:
    patch: dict[str, Any] = {}
    if "name" in raw:
        patch["name"] = validate_name(raw["name"])
    if "description" in raw:
        patch["description"] = validate_description(raw["description"])
    if "offering_id" in raw:
        patch["offering_id"] = validate_optional_uuid(raw["offering_id"], field="offering_id")
    if "price_amount" in raw:
        patch["price_amount"] = validate_amount(raw["price_amount"])
    if "currency" in raw:
        patch["currency"] = validate_currency(raw["currency"])
    if "duration_days" in raw:
        patch["duration_days"] = validate_duration_days(raw["duration_days"], required=False)
    if "status" in raw:
        patch["status"] = validate_plan_status(raw["status"])
    if "visibility" in raw:
        patch["visibility"] = validate_visibility(raw["visibility"])
    if "offering_access" in raw:
        patch["offering_access"] = _validate_offering_access(raw["offering_access"])
    patch.update(validate_plan_rules(raw, kind=None))
    if "billing_timing" in raw:
        patch["billing_timing"] = _timing(raw["billing_timing"])
    if not patch:
        raise ValidationError("No plan fields to update")
    return patch


def _validate_offering_access(value: Any) -> list[UUID]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValidationError(
            "offering_access must be a list of offering ids",
            details={"errors": [_field_error("offering_access", "Must be a list of UUIDs")]},
        )
    return [validate_uuid(v, field=f"offering_access[{i}]") for i, v in enumerate(value)]


def validate_enrolment_create_payload(raw: dict[str, Any]) -> dict[str, Any]:
    method = str(raw.get("payment_method") or "cod").strip().lower()
    if method not in PAYMENT_METHODS:
        raise ValidationError(
            "Invalid payment method",
            details={
                "errors": [
                    _field_error(
                        "payment_method", f"Must be one of: {', '.join(sorted(PAYMENT_METHODS))}"
                    )
                ]
            },
        )
    starts_at = (
        validate_datetime(raw["starts_at"], field="starts_at") if raw.get("starts_at") else None
    )
    return {
        "plan_id": validate_uuid(raw.get("plan_id"), field="plan_id"),
        "customer_contact_id": validate_uuid(
            raw.get("customer_contact_id"), field="customer_contact_id"
        ),
        "starts_at": starts_at,
        "payment_method": method,
        "auto_renew": bool(raw.get("auto_renew", False)),
        "idempotency_key": (str(raw["idempotency_key"]) if raw.get("idempotency_key") else None),
        "location_id": validate_optional_uuid(raw.get("location_id"), field="location_id"),
        "payer_contact_id": validate_optional_uuid(raw.get("payer_contact_id"), field="payer_contact_id"),
        "source_ref_type": _source_ref_type(raw.get("source_ref_type")),
        "source_ref_id": validate_optional_uuid(raw.get("source_ref_id"), field="source_ref_id"),
        "delivery": dict(raw["delivery"]) if isinstance(raw.get("delivery"), dict) else None,
        "instalments": _instalments(raw.get("instalments")),
        "channel": str(raw.get("channel") or "workspace")[:20],
    }


def _source_ref_type(value: Any) -> str | None:
    if value in (None, ""):
        return None
    if value not in SOURCE_REF_TYPES:
        raise ValidationError("Unknown reference", details={"errors": [_field_error(
            "source_ref_type", "academic_enrolment or customer_asset")]})
    return str(value)


def _instalments(value: Any) -> list[dict[str, Any]] | None:
    """Explicit instalments for one student (overrides the plan's template)."""
    from datetime import date as _date

    if value in (None, []):
        return None
    if not isinstance(value, list):
        raise ValidationError("Instalments are a list", details={"errors": [_field_error("instalments", "List")]})
    out = []
    for i, row in enumerate(value):
        amount = validate_amount(row.get("amount"), field=f"instalments[{i}].amount")
        if amount <= 0:
            raise ValidationError("Instalment amount", details={"errors": [_field_error(
                f"instalments[{i}].amount", "Must be more than zero")]})
        try:
            due = _date.fromisoformat(str(row.get("due_on")))
        except ValueError:
            raise ValidationError("Due date", details={"errors": [_field_error(
                f"instalments[{i}].due_on", "A date like 2026-11-01")]}) from None
        out.append({"label": str(row.get("label") or f"Instalment {i + 1}")[:80], "amount": amount, "due_on": due})
    return out


def assert_enrolment_transition_allowed(
    current: str, target: str, *, action: str = "update enrolment"
) -> None:
    allowed = ALLOWED_ENROLMENT_TRANSITIONS.get(current, frozenset())
    if target not in allowed:
        raise ResourceStateDenied(
            "membership_enrolment",
            current,
            action=action,
            allowed_states=sorted(allowed),
        )
