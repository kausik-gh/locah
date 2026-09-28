"""Offerings catalog validation (Stage 5)."""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any
from uuid import UUID

from platform_core.catalog.offering_kinds import (
    KINDS,
    STOCK_UNITS,
    clean_attributes,
    clean_option_groups,
    clean_packs,
    clean_tax_code,
    clean_variant_options,
    gtin_ok,
    kind,
)
from platform_core.exceptions import ValidationError

TITLE_MIN = 1
TITLE_MAX = 200
SKU_MAX = 64
BARCODE_MAX = 64
DESCRIPTION_MAX = 5000
SLUG_MAX = 120

OFFERING_TYPES = frozenset(KINDS)
KIND_FIELDS = ("attributes", "option_groups", "sell_units", "variant_options", "hsn_sac", "stock_unit")
OFFERING_STATUSES = frozenset({"draft", "active", "archived"})
PRICE_TYPES = frozenset({"fixed", "starting_from", "variable", "free", "enquiry"})
VISIBILITY = frozenset({"public", "private"})
CATEGORY_STATUSES = frozenset({"active", "archived"})

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _field_error(field: str, message: str) -> dict[str, str]:
    return {"field": field, "message": message}


def slugify(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return base[:SLUG_MAX] or "item"


def validate_title(title: str | None) -> str:
    if title is None or not str(title).strip():
        raise ValidationError(
            "Title is required",
            details={"errors": [_field_error("title", "Title is required")]},
        )
    normalized = str(title).strip()
    if len(normalized) > TITLE_MAX:
        raise ValidationError(
            "Title too long",
            details={"errors": [_field_error("title", f"Max {TITLE_MAX} characters")]},
        )
    return normalized


def validate_sku(sku: str | None) -> str | None:
    if sku is None:
        return None
    normalized = str(sku).strip()
    if not normalized:
        return None
    if len(normalized) > SKU_MAX:
        raise ValidationError(
            "SKU too long",
            details={"errors": [_field_error("sku", f"Max {SKU_MAX} characters")]},
        )
    return normalized


def validate_optional_uuid(value: Any, *, field: str) -> UUID | None:
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except ValueError as exc:
        raise ValidationError(
            f"Invalid UUID for {field}",
            details={"errors": [_field_error(field, "Must be a valid UUID")]},
        ) from exc


def validate_category_create_payload(raw: dict[str, Any]) -> dict[str, Any]:
    name = validate_title(raw.get("name"))
    slug = raw.get("slug")
    normalized_slug = slugify(str(slug)) if slug else slugify(name)
    if not _SLUG_RE.match(normalized_slug):
        normalized_slug = slugify(name)
    return {
        "name": name,
        "slug": normalized_slug,
        "parent_id": validate_optional_uuid(raw.get("parent_id"), field="parent_id"),
        "sort_order": int(raw.get("sort_order") or 0),
    }


def validate_category_patch_payload(raw: dict[str, Any]) -> dict[str, Any]:
    patch: dict[str, Any] = {}
    if "name" in raw:
        patch["name"] = validate_title(raw["name"])
    if "slug" in raw and raw["slug"]:
        patch["slug"] = slugify(str(raw["slug"]))
    if "parent_id" in raw:
        patch["parent_id"] = validate_optional_uuid(raw["parent_id"], field="parent_id")
    if "sort_order" in raw:
        patch["sort_order"] = int(raw["sort_order"])
    if "status" in raw:
        status = str(raw["status"]).strip().lower()
        if status not in CATEGORY_STATUSES:
            raise ValidationError(
                "Invalid category status",
                details={"errors": [_field_error("status", "Invalid status")]},
            )
        patch["status"] = status
    return patch


def validate_product_create_payload(raw: dict[str, Any]) -> dict[str, Any]:
    offering_type = str(raw.get("offering_type") or "product").strip().lower()
    if offering_type not in OFFERING_TYPES:
        raise ValidationError(
            "Invalid offering type",
            details={"errors": [_field_error("offering_type", "Unsupported type")]},
        )
    price_type = str(raw.get("price_type") or "fixed").strip().lower()
    if price_type not in PRICE_TYPES:
        raise ValidationError(
            "Invalid price type",
            details={"errors": [_field_error("price_type", "Unsupported price type")]},
        )
    price_amount = raw.get("price_amount")
    parsed_price: Decimal | None = None
    if price_amount is not None:
        parsed_price = Decimal(str(price_amount))
        if parsed_price < 0:
            raise ValidationError(
                "Invalid price",
                details={"errors": [_field_error("price_amount", "Must be non-negative")]},
            )
    visibility = str(raw.get("visibility") or "public").strip().lower()
    if visibility not in VISIBILITY:
        raise ValidationError(
            "Invalid visibility",
            details={"errors": [_field_error("visibility", "Invalid visibility")]},
        )
    description = raw.get("description")
    if description is not None:
        description = str(description).strip() or None
        if description and len(description) > DESCRIPTION_MAX:
            raise ValidationError(
                "Description too long",
                details={"errors": [_field_error("description", "Too long")]},
            )
    threshold = raw.get("low_stock_threshold")
    parsed_threshold: int | None = None
    if threshold is not None:
        parsed_threshold = int(threshold)
        if parsed_threshold < 0:
            raise ValidationError(
                "Invalid threshold",
                details={"errors": [_field_error("low_stock_threshold", "Must be >= 0")]},
            )
    k = kind(offering_type)
    if k.flow == "give":  # a cause takes what the giver chooses, above its smallest gift
        price_type, parsed_price = "variable", None
    kind_fields = clean_kind_fields(offering_type, raw, current=None)
    barcode = validate_barcode(raw.get("barcode"))
    return {
        **kind_fields,
        "offering_type": offering_type,
        "title": validate_title(raw.get("title")),
        "description": description,
        "category_id": validate_optional_uuid(raw.get("category_id"), field="category_id"),
        "sku": validate_sku(raw.get("sku")),
        "barcode": barcode,
        "status": str(raw.get("status") or "draft").strip().lower(),
        "price_type": price_type,
        "price_amount": parsed_price,
        "currency": str(raw.get("currency") or "INR").strip().upper(),
        "unit_of_measure": (str(raw["unit_of_measure"]).strip() if raw.get("unit_of_measure") else None),
        "tax_rate": Decimal(str(raw["tax_rate"])) if raw.get("tax_rate") is not None else None,
        "track_inventory": bool(raw.get("track_inventory", False)),
        "low_stock_threshold": parsed_threshold,
        "visibility": visibility,
        "image_asset_ids": raw.get("image_asset_ids") or [],
    }


def validate_product_patch_payload(raw: dict[str, Any]) -> dict[str, Any]:
    patch: dict[str, Any] = {}
    if "title" in raw:
        patch["title"] = validate_title(raw["title"])
    if "description" in raw:
        desc = raw["description"]
        patch["description"] = str(desc).strip() if desc else None
    if "category_id" in raw:
        patch["category_id"] = validate_optional_uuid(raw["category_id"], field="category_id")
    if "sku" in raw:
        patch["sku"] = validate_sku(raw["sku"])
    if "barcode" in raw:
        patch["barcode"] = validate_barcode(raw.get("barcode"))
    for key in KIND_FIELDS:  # cleaned by the service against the offering's kind
        if key in raw:
            patch[key] = raw[key]
    if "price_type" in raw:
        pt = str(raw["price_type"]).strip().lower()
        if pt not in PRICE_TYPES:
            raise ValidationError("Invalid price type", details={"errors": [_field_error("price_type", "Invalid")]})
        patch["price_type"] = pt
    if "price_amount" in raw:
        patch["price_amount"] = Decimal(str(raw["price_amount"])) if raw["price_amount"] is not None else None
    if "currency" in raw:
        patch["currency"] = str(raw["currency"]).strip().upper()
    if "unit_of_measure" in raw:
        patch["unit_of_measure"] = str(raw["unit_of_measure"]).strip() if raw.get("unit_of_measure") else None
    if "tax_rate" in raw:
        patch["tax_rate"] = Decimal(str(raw["tax_rate"])) if raw["tax_rate"] is not None else None
    if "track_inventory" in raw:
        patch["track_inventory"] = bool(raw["track_inventory"])
    if "low_stock_threshold" in raw:
        patch["low_stock_threshold"] = int(raw["low_stock_threshold"]) if raw["low_stock_threshold"] is not None else None
    if "visibility" in raw:
        vis = str(raw["visibility"]).strip().lower()
        if vis not in VISIBILITY:
            raise ValidationError("Invalid visibility", details={"errors": [_field_error("visibility", "Invalid")]})
        patch["visibility"] = vis
    if "status" in raw:
        st = str(raw["status"]).strip().lower()
        if st not in OFFERING_STATUSES:
            raise ValidationError("Invalid status", details={"errors": [_field_error("status", "Invalid")]})
        patch["status"] = st
    if "image_asset_ids" in raw:
        patch["image_asset_ids"] = raw["image_asset_ids"] or []
    return patch


def validate_barcode(value: Any) -> str | None:
    """Any shop code is allowed; a GTIN-shaped one must have a valid check digit."""
    if not value:
        return None
    code = str(value).strip()
    if len(code) > BARCODE_MAX:
        raise ValidationError("Barcode too long", details={"errors": [_field_error("barcode", "Too long")]})
    if code.isdigit() and len(code) in (8, 12, 13, 14) and not gtin_ok(code):
        raise ValidationError(
            "That barcode's last digit does not match — check it was typed or scanned correctly",
            details={"errors": [_field_error("barcode", "GTIN check digit mismatch")]},
        )
    return code


def clean_kind_fields(offering_type: str, raw: dict[str, Any], current: dict[str, Any] | None) -> dict[str, Any]:
    """Kind fields (Capability Universe §6.3) for a create, or the changed ones
    for an update, validated against the offering's kind."""
    k = kind(offering_type)
    cur = current or {}
    out: dict[str, Any] = {}
    stock_unit = str(raw.get("stock_unit") or cur.get("stock_unit") or ("g" if k.packs else "piece"))
    if stock_unit not in STOCK_UNITS:
        raise ValidationError("Unknown stock unit", details={"errors": [_field_error("stock_unit", "Invalid")]})
    if current is None or "stock_unit" in raw:
        out["stock_unit"] = stock_unit
    if current is None or "attributes" in raw:
        out["attributes"] = clean_attributes(k, raw.get("attributes"))
    if current is None or "option_groups" in raw:
        out["option_groups"] = clean_option_groups(k, raw.get("option_groups"))
    if current is None or "sell_units" in raw or "stock_unit" in raw:
        out["sell_units"] = clean_packs(k, raw.get("sell_units", cur.get("sell_units")), stock_unit)
    if current is None or "variant_options" in raw:
        out["variant_options"] = clean_variant_options(k, raw.get("variant_options"))
    if current is None or "hsn_sac" in raw:
        out["hsn_sac"] = clean_tax_code(raw.get("hsn_sac"), k)
    return out
