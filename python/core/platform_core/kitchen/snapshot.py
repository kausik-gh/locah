"""Copy what the pass needs from an order, and nothing commercial.

Prices, phone numbers and customer names stay on the order. The ticket keeps
the channel, how it will be served, the table or handoff label, and the
choices the kitchen has to cook.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any

# A run of digits long enough to be a phone. Names and table numbers stay.
_PHONE = re.compile(r"(?:\+?\d[\d\s().-]{8,}\d)")

# Catalogue kinds that are prepared even before anyone assigns a station.
# This is the offering kind, not a business type — a retail product is not one.
PREPARED_KINDS = frozenset({"menu_item"})

# Station keys a business may turn on. A business can also name its own.
# None of these are created until that business asks for them, except General,
# which is the fallback so an unrouted prepared item still reaches the pass.
STATION_KINDS: tuple[tuple[str, str], ...] = (
    ("grill", "Grill"),
    ("fryer", "Fryer"),
    ("beverages", "Beverages"),
    ("bakery", "Bakery"),
    ("general", "General"),
)

CHANNEL_WORDS = {
    "web": "Website",
    "whatsapp": "WhatsApp",
    "pos": "Counter",
    "phone": "Phone",
    "workspace": "Workspace",
    "marketplace": "Marketplace",
    "chitbridge": "Trade",
}

MODE_WORDS = {
    "dine_in": "Dine-in",
    "takeaway": "Takeaway",
    "pickup": "Pickup",
    "delivery": "Delivery",
    "counter": "Counter",
}

# Shown on the card when the order moves after cooking has started.
VISIBLE_EVENT_KINDS = frozenset({
    "cancel_after_start",
    "quantity_changed",
    "modifier_changed",
    "line_added",
    "line_removed",
})

OPEN_ORDER_STATUSES = frozenset({"accepted", "preparing", "ready"})


def redact(value: str | None) -> str:
    """Drop phone-shaped numbers. Table labels and short notes stay."""
    if not value:
        return ""
    return _PHONE.sub("", value).strip()


def modifier_snapshot(options: dict[str, Any] | None) -> tuple[dict[str, Any], list[str]]:
    """Choices and written notes only. Price deltas are not preparation facts."""
    raw = options or {}
    choices: dict[Any, Any] = raw["choices"] if isinstance(raw.get("choices"), dict) else {}
    notes: dict[Any, Any] = raw["notes"] if isinstance(raw.get("notes"), dict) else {}
    record_choices: dict[str, list[str]] = {}
    record_notes: dict[str, str] = {}
    lines: list[str] = []
    for group, labels in choices.items():
        picked = [str(x) for x in (labels if isinstance(labels, list) else [labels]) if str(x).strip()]
        if not picked:
            continue
        record_choices[str(group)] = picked
        lines.append(f"{group}: {', '.join(picked)}")
    for group, note in notes.items():
        cleaned = redact(str(note))
        if not cleaned:
            continue
        record_notes[str(group)] = cleaned[:200]
        lines.append(f"{group}: {record_notes[str(group)]}")
    record: dict[str, Any] = {}
    if record_choices:
        record["choices"] = record_choices
    if record_notes:
        record["notes"] = record_notes
    return record, lines


def modifiers_match(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return json.dumps(left, sort_keys=True) == json.dumps(right, sort_keys=True)


def service_snapshot(
    *,
    channel: str | None,
    internal_reference: str | None,
    due_at: datetime | None,
    fulfilment_mode: str | None,
    delivery_address: dict[str, Any] | None,
) -> dict[str, str]:
    """How the pass should call the ticket: channel, mode, and a place label."""
    ref = redact(internal_reference)[:80]
    mode = (fulfilment_mode or "").strip().lower()
    if ref and re.search(r"\btable\b", ref, re.IGNORECASE):
        service_mode, label = "dine_in", ref
    elif mode == "delivery":
        city = ""
        if isinstance(delivery_address, dict):
            city = redact(str(delivery_address.get("city") or delivery_address.get("area") or ""))
        service_mode, label = "delivery", (city[:80] or "Delivery")
    elif mode == "pickup":
        service_mode, label = "pickup", ref or "Pickup"
    elif mode in {"takeaway", "shipping"}:
        service_mode, label = "takeaway", ref or "Takeaway"
    else:
        service_mode, label = "counter", ref or "Counter"

    priority = "normal"
    if due_at is not None:
        moment = due_at if due_at.tzinfo else due_at.replace(tzinfo=timezone.utc)
        if moment <= datetime.now(timezone.utc) + timedelta(minutes=15):
            priority = "rush"

    return {
        "channel": channel if channel in CHANNEL_WORDS else (channel or "workspace"),
        "service_mode": service_mode,
        "service_label": label,
        "priority": priority,
    }


def channel_words(channel: str) -> str:
    return CHANNEL_WORDS.get(channel, channel.replace("_", " ").title())


def mode_words(mode: str) -> str:
    return MODE_WORDS.get(mode, mode.replace("_", " ").title())
