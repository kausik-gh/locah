"""Fulfilment validation (Doc 11 §10.4)."""

from __future__ import annotations

import math
from decimal import Decimal, InvalidOperation
from typing import Any

from platform_core.exceptions import ValidationError

FULFILMENT_MODES = frozenset({"pickup", "delivery"})
ZONE_MATCH_TYPES = frozenset({"city", "radius", "postal_prefix"})

JOB_TRANSITIONS: dict[str, frozenset[str]] = {
    "pending": frozenset({"preparing", "cancelled", "failed"}),
    "preparing": frozenset({"ready", "cancelled", "failed"}),
    "ready": frozenset({"out_for_delivery", "delivered", "cancelled", "failed"}),
    "out_for_delivery": frozenset({"delivered", "failed", "cancelled"}),
    "delivered": frozenset(),
    "failed": frozenset(),
    "cancelled": frozenset(),
}

CUSTOMER_FACING_STATUS = {
    "pending": "received",
    "preparing": "preparing",
    "ready": "ready",
    "out_for_delivery": "out_for_delivery",
    "delivered": "delivered",
    "failed": "failed",
    "cancelled": "cancelled",
}


def _field_error(field: str, message: str) -> dict[str, str]:
    return {"field": field, "message": message}


def validate_zone_payload(raw: dict[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    name = str(raw.get("name") or "").strip()
    if not name:
        errors.append(_field_error("name", "Required"))
    match_type = str(raw.get("match_type") or "city").strip()
    if match_type not in ZONE_MATCH_TYPES:
        errors.append(_field_error("match_type", f"Must be one of {sorted(ZONE_MATCH_TYPES)}"))
    try:
        charge = Decimal(str(raw.get("charge_amount") if raw.get("charge_amount") is not None else 0))
        if charge < 0:
            raise InvalidOperation()
    except (InvalidOperation, ValueError):
        errors.append(_field_error("charge_amount", "Must be a non-negative number"))
        charge = Decimal("0")
    city = (str(raw.get("city")).strip() if raw.get("city") is not None else None) or None
    postal_prefix = (
        str(raw.get("postal_prefix")).strip() if raw.get("postal_prefix") is not None else None
    ) or None
    if match_type == "city" and not city:
        errors.append(_field_error("city", "Required for city match"))
    if match_type == "postal_prefix" and not postal_prefix:
        errors.append(_field_error("postal_prefix", "Required for postal_prefix match"))
    center_lat = raw.get("center_lat")
    center_lng = raw.get("center_lng")
    radius_km = raw.get("radius_km")
    if match_type == "radius":
        if center_lat is None or center_lng is None or radius_km is None:
            errors.append(_field_error("radius_km", "center_lat, center_lng, radius_km required"))
    if errors:
        raise ValidationError("Invalid fulfilment zone", details={"errors": errors})
    return {
        "name": name,
        "match_type": match_type,
        "city": city,
        "postal_prefix": postal_prefix,
        "center_lat": float(center_lat) if center_lat is not None else None,
        "center_lng": float(center_lng) if center_lng is not None else None,
        "radius_km": float(radius_km) if radius_km is not None else None,
        "charge_amount": charge,
        "currency": str(raw.get("currency") or "INR"),
        "location_id": raw.get("location_id"),
        "is_active": bool(raw.get("is_active", True)),
    }


def validate_settings_payload(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "pickup_enabled": bool(raw.get("pickup_enabled", True)),
        "delivery_enabled": bool(raw.get("delivery_enabled", False)),
    }


def validate_job_status_payload(raw: dict[str, Any], *, current: str) -> dict[str, Any]:
    status = str(raw.get("status") or "").strip()
    allowed = JOB_TRANSITIONS.get(current, frozenset())
    if status not in allowed:
        raise ValidationError(
            "Invalid fulfilment status transition",
            details={"from": current, "to": status, "allowed": sorted(allowed)},
        )
    reason = (str(raw.get("reason")).strip() if raw.get("reason") is not None else None) or None
    if status in {"failed", "cancelled"} and not reason:
        raise ValidationError(
            "Reason required for failure/cancellation",
            details={"field": "reason"},
        )
    # ready → delivered only for pickup; ready → out_for_delivery for delivery
    return {"status": status, "reason": reason}


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))
