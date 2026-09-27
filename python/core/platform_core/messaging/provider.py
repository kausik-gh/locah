"""WhatsApp providers (Capability Universe §9.1).

`MetaCloudProvider` speaks Meta's WhatsApp Cloud API (LOCAH as a Tech Provider;
Embedded Signup per business). It needs LOCAH's own Meta app — app id, app
secret, the Embedded Signup configuration and the Graph API version — set in
the environment; until then the real connection is *activation required* and
nothing calls Meta. It has not been exercised against Meta from this
repository: every test uses the sandbox or recorded webhook payloads.

`SandboxProvider` stands in on local and test stacks only (MESSAGING_SANDBOX=1
outside production). It records what would have been sent and never leaves
the machine, so a whole flow — connect, receive, reply, notify — can be seen
end to end without a Meta number.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from typing import Any, Protocol

from platform_core.exceptions import ServiceUnavailable
from platform_core.messaging.templates import LIBRARY, META_LANGUAGE
from platform_core.secrets import is_development

_META_ENV = ("META_APP_ID", "META_APP_SECRET", "META_GRAPH_VERSION", "META_ES_CONFIG_ID")


def _unavailable(message: str) -> ServiceUnavailable:
    return ServiceUnavailable(message, details={"service": "whatsapp", "activation_required": not meta_configured()})


def meta_configured() -> bool:
    """LOCAH's Meta app is set up, so owners can connect real numbers."""
    return all(os.getenv(k, "").strip() for k in _META_ENV)


def sandbox_enabled() -> bool:
    return os.getenv("MESSAGING_SANDBOX", "").strip() in ("1", "true") and is_development()


def meta_public_config() -> dict[str, str] | None:
    """What the Workspace needs to open Embedded Signup (no secrets)."""
    if not meta_configured():
        return None
    return {"app_id": os.environ["META_APP_ID"], "config_id": os.environ["META_ES_CONFIG_ID"],
            "graph_version": os.environ["META_GRAPH_VERSION"]}


@dataclass(frozen=True)
class Sent:
    provider_message_id: str


@dataclass(frozen=True)
class SignupResult:
    token: str
    waba_id: str
    phone_number_id: str
    display_phone: str | None
    display_name: str | None
    quality_rating: str | None


class Provider(Protocol):
    name: str

    async def send_template(self, token: str | None, phone_number_id: str | None, to: str, key: str, language: str,
                            params: list[str]) -> Sent: ...

    async def send_text(self, token: str | None, phone_number_id: str | None, to: str, body: str) -> Sent: ...

    async def send_interactive(self, token: str | None, phone_number_id: str | None, to: str,
                               interactive: dict[str, Any]) -> Sent: ...

    async def submit_template(self, token: str | None, waba_id: str | None, key: str,
                              language: str) -> tuple[str, str | None]: ...


class SandboxProvider:
    name = "sandbox"

    async def send_template(self, token: str | None, phone_number_id: str | None, to: str, key: str, language: str,
                            params: list[str]) -> Sent:
        return Sent(f"sandbox.{uuid.uuid4().hex}")

    async def send_text(self, token: str | None, phone_number_id: str | None, to: str, body: str) -> Sent:
        return Sent(f"sandbox.{uuid.uuid4().hex}")

    async def send_interactive(self, token: str | None, phone_number_id: str | None, to: str,
                               interactive: dict[str, Any]) -> Sent:
        return Sent(f"sandbox.{uuid.uuid4().hex}")

    async def submit_template(self, token: str | None, waba_id: str | None, key: str,
                              language: str) -> tuple[str, str | None]:
        # The sandbox approves at once; Meta reviews each template (usually minutes to a day).
        return "approved", f"sandbox-{key}-{language}"


class MetaCloudProvider:
    """WhatsApp Cloud API over Graph. Activation required: see module docstring."""

    name = "meta_cloud"

    def __init__(self) -> None:
        if not meta_configured():
            raise _unavailable("WhatsApp through Meta is not switched on for LOCAH yet")
        self.version = os.environ["META_GRAPH_VERSION"]
        self.base = f"https://graph.facebook.com/{self.version}"

    async def _post(self, token: str | None, path: str, body: dict[str, Any]) -> dict[str, Any]:
        import httpx

        if not token:
            raise _unavailable("This WhatsApp number has no access token; connect it again")
        async with httpx.AsyncClient(timeout=15) as client:
            res = await client.post(f"{self.base}/{path}", json=body, headers={"Authorization": f"Bearer {token}"})
        data: dict[str, Any] = res.json() if res.content else {}
        if res.status_code >= 400:
            err = (data.get("error") or {}) if isinstance(data, dict) else {}
            raise _unavailable(f"WhatsApp refused: {err.get('message') or res.status_code}")
        return data

    async def _send(self, token: str | None, phone_number_id: str | None, body: dict[str, Any]) -> Sent:
        if not phone_number_id:
            raise _unavailable("This WhatsApp number is not fully connected")
        data = await self._post(token, f"{phone_number_id}/messages", {"messaging_product": "whatsapp", **body})
        return Sent(str((data.get("messages") or [{}])[0].get("id") or ""))

    async def send_template(self, token: str | None, phone_number_id: str | None, to: str, key: str, language: str,
                            params: list[str]) -> Sent:
        return await self._send(token, phone_number_id, {
            "to": to, "type": "template",
            "template": {"name": key, "language": {"code": META_LANGUAGE[language]},
                         "components": [{"type": "body",
                                         "parameters": [{"type": "text", "text": p} for p in params]}]}})

    async def send_text(self, token: str | None, phone_number_id: str | None, to: str, body: str) -> Sent:
        return await self._send(token, phone_number_id, {
            "recipient_type": "individual", "to": to, "type": "text", "text": {"preview_url": True, "body": body}})

    async def send_interactive(self, token: str | None, phone_number_id: str | None, to: str,
                               interactive: dict[str, Any]) -> Sent:
        return await self._send(token, phone_number_id, {
            "recipient_type": "individual", "to": to, "type": "interactive", "interactive": interactive})

    async def submit_template(self, token: str | None, waba_id: str | None, key: str,
                              language: str) -> tuple[str, str | None]:
        t = LIBRARY[key]
        body = t.bodies[language]
        examples = [f"<{p}>" for p in t.params]
        data = await self._post(token, f"{waba_id}/message_templates", {
            "name": key, "language": META_LANGUAGE[language], "category": t.category.upper(),
            "components": [{"type": "BODY", "text": body, "example": {"body_text": [examples]}}]})
        status = str(data.get("status") or "PENDING").lower()
        return ("approved" if status == "approved" else "rejected" if status == "rejected" else "submitted",
                str(data.get("id") or "") or None)

    async def complete_signup(self, code: str, waba_id: str, phone_number_id: str) -> SignupResult:
        """Embedded Signup's last step: exchange the code for the business's token,
        subscribe LOCAH's app to its WhatsApp Business Account, read the number."""
        import httpx

        async with httpx.AsyncClient(timeout=15) as client:
            res = await client.get(f"{self.base}/oauth/access_token", params={
                "client_id": os.environ["META_APP_ID"], "client_secret": os.environ["META_APP_SECRET"],
                "code": code})
            if res.status_code >= 400:
                raise _unavailable("Meta did not accept the sign-up; try connecting again")
            token = str(res.json().get("access_token") or "")
            await self._post(token, f"{waba_id}/subscribed_apps", {})
            info = await client.get(f"{self.base}/{phone_number_id}", headers={"Authorization": f"Bearer {token}"},
                                    params={"fields": "display_phone_number,verified_name,quality_rating"})
            details: dict[str, Any] = info.json() if info.status_code < 400 else {}
        return SignupResult(token, waba_id, phone_number_id, details.get("display_phone_number"),
                            details.get("verified_name"), details.get("quality_rating"))


def provider_for(kind: str) -> Provider:
    if kind == "sandbox":
        if not sandbox_enabled():
            raise _unavailable("The WhatsApp sandbox is only available on test stacks")
        return SandboxProvider()
    return MetaCloudProvider()
