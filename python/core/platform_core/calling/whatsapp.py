"""WhatsApp Business Calling API - the wire contract (Meta docs checked 2026-09-30).

Signalling is Graph API + the `calls` webhook field; media is WebRTC
(ICE + DTLS-SRTP, OPUS) between Meta and whatever answers the call. This module
only speaks the signalling: turning calling on for a number (with its hours),
the call actions (pre_accept / accept / reject / terminate), and the
customer's call permission. Answering needs a media runtime LOCAH does not
have yet, so accept() is only called once one exists (calling_runtime()).

Request bodies are built by pure functions so the tests can hold them to
Meta's documented shapes; the sandbox records instead of calling Meta.
"""

from __future__ import annotations

import os
from datetime import time
from typing import Any

from platform_core.exceptions import ServiceUnavailable

DAYS = {"mon": "MONDAY", "tue": "TUESDAY", "wed": "WEDNESDAY", "thu": "THURSDAY", "fri": "FRIDAY",
        "sat": "SATURDAY", "sun": "SUNDAY"}


def call_hours(location_hours: dict[str, Any] | None, timezone_id: str) -> dict[str, Any] | None:
    """The location's opening hours in Meta's call_hours shape (at most two
    spans a day, "HHMM"). None when the business saved no hours."""
    if not location_hours:
        return None
    weekly = []
    for key, day in DAYS.items():
        for span in (location_hours.get(key) or [])[:2]:
            try:
                start, end = time.fromisoformat(span[0]), time.fromisoformat(span[1])
            except (ValueError, TypeError, IndexError):
                continue
            weekly.append({"day_of_week": day, "open_time": start.strftime("%H%M"), "close_time": end.strftime("%H%M")})
    if not weekly:
        return None
    return {"status": "ENABLED", "timezone_id": timezone_id, "weekly_operating_hours": weekly}


def settings_body(enabled: bool, hours: dict[str, Any] | None) -> dict[str, Any]:
    calling: dict[str, Any] = {"status": "ENABLED" if enabled else "DISABLED"}
    if enabled:
        calling["call_icon_visibility"] = "DEFAULT"
        # A customer who calls may be called back (Meta grants a temporary permission).
        calling["callback_permission_status"] = "ENABLED"
        if hours:
            calling["call_hours"] = hours
    return {"calling": calling}


def action_body(call_id: str, action: str, sdp_answer: str | None = None) -> dict[str, Any]:
    if action not in ("pre_accept", "accept", "reject", "terminate"):
        raise ValueError(f"unknown call action {action}")
    body: dict[str, Any] = {"messaging_product": "whatsapp", "call_id": call_id, "action": action}
    if action in ("pre_accept", "accept"):
        if not sdp_answer:
            raise ValueError("pre_accept/accept need the SDP answer from the media runtime")
        body["session"] = {"sdp_type": "answer", "sdp": sdp_answer}
    return body


def permission_request_interactive(text: str) -> dict[str, Any]:
    """The free-form request, allowed only inside the customer's 24-hour window."""
    return {"type": "call_permission_request", "action": {"name": "call_permission_request"},
            "body": {"text": text[:1024]}}


class WhatsAppCalling:
    """Graph calls for one number. `transport` lets tests capture requests."""

    def __init__(self, provider: str, *, transport: Any = None) -> None:
        self.provider = provider
        self.transport = transport
        self.recorded: list[tuple[str, str, dict[str, Any] | None]] = []

    async def _request(self, method: str, token: str | None, path: str,
                       body: dict[str, Any] | None = None) -> dict[str, Any]:
        if self.provider == "sandbox":
            self.recorded.append((method, path, body))
            return {"success": True}
        version = os.getenv("META_GRAPH_VERSION", "").strip()
        if not version or not token:
            raise ServiceUnavailable("WhatsApp calling needs LOCAH's Meta app and this number's access",
                                     details={"service": "whatsapp_calling", "activation_required": True})
        import httpx

        async with httpx.AsyncClient(timeout=15, transport=self.transport) as client:
            res = await client.request(method, f"https://graph.facebook.com/{version}/{path}", json=body,
                                       headers={"Authorization": f"Bearer {token}"})
        data: dict[str, Any] = res.json() if res.content else {}
        if res.status_code >= 400:
            err = (data.get("error") or {}) if isinstance(data, dict) else {}
            raise ServiceUnavailable(f"WhatsApp refused: {err.get('message') or res.status_code}",
                                     details={"service": "whatsapp_calling"})
        return data

    async def set_calling(self, token: str | None, phone_number_id: str, *, enabled: bool,
                          hours: dict[str, Any] | None) -> dict[str, Any]:
        return await self._request("POST", token, f"{phone_number_id}/settings", settings_body(enabled, hours))

    async def act(self, token: str | None, phone_number_id: str, call_id: str, action: str,
                  sdp_answer: str | None = None) -> dict[str, Any]:
        return await self._request("POST", token, f"{phone_number_id}/calls", action_body(call_id, action, sdp_answer))

    async def permission(self, token: str | None, phone_number_id: str, wa_id: str) -> dict[str, Any]:
        return await self._request("GET", token, f"{phone_number_id}/call_permissions?user_wa_id={wa_id}")
