"""WhatsApp Cloud API webhook payloads, built the way Meta delivers them.

Used by the sandbox's "a customer writes" endpoint on test stacks and by the
provider-contract tests (§27: recorded webhook payloads, zero live calls), so a
simulated message goes through exactly the code path a real one does.
"""

from __future__ import annotations

import time
import uuid
from typing import Any


def webhook_payload(phone_number_id: str, display_phone: str, m: dict[str, Any]) -> dict[str, Any]:
    """One delivery: an inbound message, or (echo=True) the owner's reply from
    the WhatsApp Business app on the same number (coexistence)."""
    sender = "".join(ch for ch in str(m.get("from_phone") or "") if ch.isdigit())
    message_id = m.get("message_id") or f"wamid.sandbox.{uuid.uuid4().hex}"
    stamp = str(int(time.time()))
    body: dict[str, Any] = {"id": message_id, "timestamp": stamp}
    if m.get("button_id"):
        kind = "list_reply" if m.get("list_reply") else "button_reply"
        body |= {"type": "interactive", "interactive": {"type": kind, kind: {
            "id": m["button_id"], "title": m.get("button_title") or m["button_id"]}}}
    elif m.get("latitude") is not None and m.get("longitude") is not None:
        body |= {"type": "location", "location": {"latitude": m["latitude"], "longitude": m["longitude"],
                                                  "name": m.get("text") or None}}
    else:
        body |= {"type": "text", "text": {"body": m.get("text") or ""}}
    metadata = {"display_phone_number": display_phone.lstrip("+"), "phone_number_id": phone_number_id}
    if m.get("echo"):
        value: dict[str, Any] = {"messaging_product": "whatsapp", "metadata": metadata,
                                 "message_echoes": [{"from": metadata["display_phone_number"], "to": sender, **body}]}
        field = "smb_message_echoes"
    else:
        value = {"messaging_product": "whatsapp", "metadata": metadata,
                 "contacts": [{"profile": {"name": m.get("name") or ""}, "wa_id": sender}],
                 "messages": [{"from": sender, **body}]}
        field = "messages"
    return {"object": "whatsapp_business_account",
            "entry": [{"id": "sandbox-waba", "changes": [{"field": field, "value": value}]}]}


def status_payload(phone_number_id: str, message_id: str, status: str, recipient: str,
                   error: str | None = None) -> dict[str, Any]:
    st: dict[str, Any] = {"id": message_id, "status": status, "timestamp": str(int(time.time())),
                          "recipient_id": recipient}
    if error:
        st["errors"] = [{"code": 131026, "title": error}]
    return {"object": "whatsapp_business_account", "entry": [{"id": "sandbox-waba", "changes": [{
        "field": "messages", "value": {"messaging_product": "whatsapp",
                                       "metadata": {"phone_number_id": phone_number_id},
                                       "statuses": [st]}}]}]}
