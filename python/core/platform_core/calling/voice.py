"""The phone-line (PSTN / SIP) boundary - provider-neutral on purpose.

No telephony vendor has been chosen for LOCAH (the sources name none), so
nothing here commits the product to one. A vendor adapter implements
`VoiceProvider` and is selected by TELEPHONY_PROVIDER; until then phone calls
are ACTIVATION_REQUIRED and every operation says so instead of pretending.
The fixture provider exists for tests and local stacks only.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

from platform_core.exceptions import ServiceUnavailable
from platform_core.secrets import is_development


@dataclass(frozen=True)
class CallEvent:
    """What a provider tells LOCAH about a call, whatever its wire format."""

    external_call_id: str
    event: str  # ringing | answered | ended | failed
    direction: str  # inbound | outbound
    from_number: str | None = None
    to_number: str | None = None
    at: datetime | None = None
    duration_seconds: int | None = None
    status: str | None = None
    digits: str | None = None  # DTMF, when the provider reports it
    recording_ref: str | None = None  # a reference only - never the audio


class VoiceProvider(Protocol):
    name: str

    async def place_call(self, *, to: str, caller_id: str, reference: str) -> str: ...

    async def answer(self, external_call_id: str, *, route_to: str) -> None: ...

    async def transfer(self, external_call_id: str, *, to: str) -> None: ...

    async def hangup(self, external_call_id: str) -> None: ...

    def parse_webhook(self, headers: dict[str, str], body: bytes) -> list[CallEvent]: ...


def _activation_required() -> ServiceUnavailable:
    return ServiceUnavailable("Phone calls are not switched on for LOCAH yet: no telephony provider is connected",
                              details={"service": "telephony", "activation_required": True})


class UnconfiguredVoiceProvider:
    name = "none"

    async def place_call(self, *, to: str, caller_id: str, reference: str) -> str:
        raise _activation_required()

    async def answer(self, external_call_id: str, *, route_to: str) -> None:
        raise _activation_required()

    async def transfer(self, external_call_id: str, *, to: str) -> None:
        raise _activation_required()

    async def hangup(self, external_call_id: str) -> None:
        raise _activation_required()

    def parse_webhook(self, headers: dict[str, str], body: bytes) -> list[CallEvent]:
        raise _activation_required()


@dataclass
class FixtureVoiceProvider:
    """Records what would have happened. Test and local stacks only."""

    name: str = "fixture"
    log: list[dict[str, Any]] = field(default_factory=list)

    async def place_call(self, *, to: str, caller_id: str, reference: str) -> str:
        call_id = f"fixture-{uuid.uuid4().hex[:12]}"
        self.log.append({"op": "place_call", "to": to, "caller_id": caller_id, "reference": reference, "id": call_id})
        return call_id

    async def answer(self, external_call_id: str, *, route_to: str) -> None:
        self.log.append({"op": "answer", "id": external_call_id, "route_to": route_to})

    async def transfer(self, external_call_id: str, *, to: str) -> None:
        self.log.append({"op": "transfer", "id": external_call_id, "to": to})

    async def hangup(self, external_call_id: str) -> None:
        self.log.append({"op": "hangup", "id": external_call_id})

    def parse_webhook(self, headers: dict[str, str], body: bytes) -> list[CallEvent]:
        import json

        data = json.loads(body or b"{}")
        return [CallEvent(external_call_id=str(e["id"]), event=str(e["event"]), direction=str(e.get("direction",
                          "inbound")), from_number=e.get("from"), to_number=e.get("to"),
                          duration_seconds=e.get("duration"), status=e.get("status")) for e in data.get("events", [])]


def telephony_provider() -> VoiceProvider:
    kind = os.getenv("TELEPHONY_PROVIDER", "").strip().lower()
    if kind == "fixture" and is_development():
        return FixtureVoiceProvider()
    return UnconfiguredVoiceProvider()


def telephony_state() -> dict[str, Any]:
    kind = os.getenv("TELEPHONY_PROVIDER", "").strip().lower()
    if kind == "fixture" and is_development():
        return {"state": "TEST", "provider": "fixture", "reason": "A test line on this stack; no real calls"}
    return {"state": "ACTIVATION_REQUIRED", "provider": None,
            "reason": "No telephony provider is connected. Choosing one (and a number) is a founder decision."}
