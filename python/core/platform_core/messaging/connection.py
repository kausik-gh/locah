"""The honest state of a business's WhatsApp connection (and its calling).

Derived, never stored: every value comes from something true right now -
whether LOCAH's own Meta app is configured and approved, the channel row, the
templates Meta has decided on, the last errors. A sandbox number is always
labelled as a test number; nothing here says "connected" because a fixture
transport works.

Messaging states (continuation brief §12):
  ACTIVATION_REQUIRED       LOCAH's Meta app is not configured (and no sandbox)
  META_REVIEW_REQUIRED      the app is configured but not yet approved by Meta
                            for other businesses (advanced access); only the
                            app's own test users can connect
  NOT_CONNECTED             nothing connected; the owner can connect
  SETUP_REQUIRED            sign-up started but not finished
  PHONE_VERIFICATION_REQUIRED  signed up; the number is not registered for
                            Cloud API yet (two-step PIN)
  TEMPLATE_SETUP_REQUIRED   connected, but no approved utility template yet,
                            so nothing can be sent outside a customer's
                            24-hour window
  ACTIVE                    connected, registered, templates approved
  DEGRADED                  connected but the last send failed or Meta flags
                            the number's quality
  DISCONNECTED              the owner disconnected the number

Calling states (§21): CALLING_NOT_AVAILABLE, CALLING_ACTIVATION_REQUIRED,
CALLING_ELIGIBLE, CALLING_SETUP_REQUIRED, CALLING_ACTIVE, CALLING_DEGRADED.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from platform_core.models import MessagingChannel

# Meta's Calling API needs a daily messaging limit of at least 2,000 unique
# recipients in production (checked 2026-09-30); tiers below that do not qualify.
CALLING_TOO_LOW_TIERS = frozenset({"TIER_50", "TIER_250", "TIER_1K"})
BAD_QUALITY = frozenset({"RED", "FLAGGED"})


def meta_advanced_access() -> bool:
    """LOCAH's Meta app has advanced access for the WhatsApp permissions, so
    businesses other than the app's own test users can be onboarded. Set by
    whoever operates LOCAH once Meta approves App Review (no secret)."""
    return os.getenv("META_ADVANCED_ACCESS", "").strip() in ("1", "true")


def calling_runtime() -> str | None:
    """The media runtime that can answer a WhatsApp call (WebRTC: a staff
    softphone or an AI voice runtime). None configured means LOCAH cannot pick
    up a call, whatever Meta allows."""
    value = os.getenv("WHATSAPP_CALLING_RUNTIME", "").strip()
    return value or None


@dataclass(frozen=True)
class Step:
    key: str
    label: str
    done: bool

    def view(self) -> dict[str, Any]:
        return {"key": self.key, "label": self.label, "done": self.done}


def messaging_state(
    *, channel: MessagingChannel | None, was_disconnected: bool, meta_ready: bool, sandbox_available: bool,
    approved_utility: int, awaiting_review: int,
) -> dict[str, Any]:
    sandbox = channel is not None and channel.provider == "sandbox"
    steps = [
        # What is true of LOCAH's Meta app, even on a sandbox stack (a test
        # number working proves nothing about production).
        Step("meta_app", "LOCAH's WhatsApp partnership with Meta is switched on", meta_ready),
        Step("meta_review", "Meta has approved LOCAH to connect businesses", meta_ready and meta_advanced_access()),
        Step("signup", "Your number is connected through Meta", channel is not None and channel.status != "disconnected"),
        Step("registered", "Your number is registered for sending",
             channel is not None and channel.phone_registered_at is not None),
        Step("templates", "WhatsApp has approved your message templates", approved_utility > 0),
    ]
    reason = None
    if channel is None or channel.status == "disconnected":
        if not meta_ready and not sandbox_available:
            state = "ACTIVATION_REQUIRED"
            reason = "LOCAH's Meta app is not configured on this deployment"
        elif was_disconnected:
            state = "DISCONNECTED"
        elif meta_ready and not meta_advanced_access() and not sandbox_available:
            state = "META_REVIEW_REQUIRED"
            reason = "Meta has not yet approved LOCAH to onboard other businesses"
        else:
            state = "NOT_CONNECTED"
    elif channel.status == "pending":
        if channel.phone_registered_at is None and not channel.coexistence:
            state = "PHONE_VERIFICATION_REQUIRED"
            reason = channel.registration_error
        else:
            state = "SETUP_REQUIRED"
    elif approved_utility == 0:
        state = "TEMPLATE_SETUP_REQUIRED"
        reason = "Waiting for WhatsApp to review your templates" if awaiting_review else "No approved templates yet"
    elif channel.last_error or (channel.quality_rating or "").upper() in BAD_QUALITY:
        state = "DEGRADED"
        reason = channel.last_error or f"WhatsApp rates this number's quality {channel.quality_rating}"
    else:
        state = "ACTIVE"
    return {
        "state": state,
        "reason": reason,
        "environment": "sandbox" if sandbox else ("production" if channel is not None else None),
        "label": "TEST / SANDBOX" if sandbox else None,
        "steps": [s.view() for s in steps],
    }


def calling_state(channel: MessagingChannel | None, messaging: dict[str, Any]) -> dict[str, Any]:
    """Whether WhatsApp calls can reach this business through LOCAH.

    Never inferred from messaging alone: a number can message and still not
    be able to take calls (tier, Meta settings, and a media runtime LOCAH must
    run to answer)."""
    if channel is None or messaging["state"] not in ("ACTIVE", "DEGRADED", "TEMPLATE_SETUP_REQUIRED"):
        return {"state": "CALLING_NOT_AVAILABLE", "reason": "Connect WhatsApp first", "messaging_active": False}
    base = {"messaging_active": True}
    if calling_runtime() is None:
        return {**base, "state": "CALLING_ACTIVATION_REQUIRED",
                "reason": "LOCAH has no call runtime yet to answer WhatsApp calls (WebRTC media for a person or "
                          "an AI receptionist). Calls are recorded but not answered by LOCAH."}
    if channel.provider != "sandbox" and (channel.messaging_limit or "").upper() in CALLING_TOO_LOW_TIERS:
        return {**base, "state": "CALLING_NOT_AVAILABLE",
                "reason": f"WhatsApp calling needs a daily limit of 2,000 or more (this number: "
                          f"{channel.messaging_limit})"}
    if channel.calling_status != "enabled":
        return {**base, "state": "CALLING_ELIGIBLE", "reason": "Calling can be switched on for this number"}
    if channel.calling_error:
        return {**base, "state": "CALLING_DEGRADED", "reason": channel.calling_error}
    if channel.calling_checked_at is None:
        return {**base, "state": "CALLING_SETUP_REQUIRED", "reason": "Waiting for WhatsApp to confirm the settings"}
    return {**base, "state": "CALLING_ACTIVE", "reason": None}
