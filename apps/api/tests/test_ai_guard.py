"""LOCAH_TEST_NO_EXTERNAL_AI: every paid AI path refuses before it leaves the process.

The suite runs with the switch on (conftest). Each test here points a real
provider at a stub HTTP client that records whether it was reached, and checks
the call was refused first — so the proof holds even though no network exists.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from uuid import uuid4

import httpx
import pytest

from platform_core import ai_guard
from platform_core.ai_guard import ExternalAICallBlocked, blocked_calls, reset_blocked_calls
from platform_core.interview import voice
from platform_core.interview.models import BusinessBlueprint, Fact
from platform_core.interview.orchestrator import BusinessInterviewOrchestrator as Engine
from platform_core.website import ai_provider, image_generation
from platform_core.website.ai_provider import GeminiProvider, GrokProvider


class Reached:
    """An HTTP client stand-in that only records that it was used."""

    def __init__(self) -> None:
        self.used = False

    def client(self, *args: Any, **kwargs: Any) -> Any:
        recorder = self

        class _Client:
            async def __aenter__(self) -> Any:
                recorder.used = True
                return self

            async def __aexit__(self, *exc: Any) -> bool:
                return False

            async def post(self, *a: Any, **k: Any) -> Any:
                raise AssertionError("a paid host was reached")

        return _Client()


@pytest.fixture
def reached(monkeypatch: pytest.MonkeyPatch) -> Iterator[Reached]:
    stub = Reached()
    for module in (ai_provider, image_generation, voice):
        monkeypatch.setattr(module.httpx, "AsyncClient", stub.client)
    yield stub
    # These tests attempt paid calls on purpose; the autouse check would fail
    # them for it, so each one consumes its own record.
    reset_blocked_calls()


def test_the_suite_runs_with_the_switch_on() -> None:
    assert ai_guard.external_ai_disabled()


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", [GeminiProvider("k"), GrokProvider("k")], ids=["gemini", "xai"])
async def test_text_providers_refuse_before_any_request(provider: Any, reached: Reached) -> None:
    with pytest.raises(ExternalAICallBlocked):
        await provider.generate_structured("p", {"type": "object"}, {"purpose": "business.interview"}, 5)
    assert not reached.used
    assert [(c.kind, c.provider) for c in blocked_calls()] == [("text", provider.provider_name)]


@pytest.mark.asyncio
async def test_gemini_images_refuse_loudly_not_as_a_failed_picture(
    monkeypatch: pytest.MonkeyPatch, reached: Reached
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "g-present")
    monkeypatch.setenv("IMAGE_PROVIDER", "gemini")
    with pytest.raises(ExternalAICallBlocked):
        await image_generation.generate_image("draw", aspect_ratio="1:1")
    assert not reached.used


@pytest.mark.asyncio
async def test_xai_images_refuse(monkeypatch: pytest.MonkeyPatch, reached: Reached) -> None:
    monkeypatch.setenv("XAI_API_KEY", "x-present")
    monkeypatch.setenv("IMAGE_PROVIDER", "xai")
    with pytest.raises(ExternalAICallBlocked):
        await image_generation.generate_image_bytes("draw")
    assert not reached.used


@pytest.mark.asyncio
async def test_voice_credentials_refuse_for_both_providers(
    monkeypatch: pytest.MonkeyPatch, reached: Reached
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "g-present")
    monkeypatch.setenv("XAI_API_KEY", "x-present")
    bp = BusinessBlueprint(business_id=uuid4())
    with pytest.raises(ExternalAICallBlocked):
        await voice.mint_gemini_token(bp)
    with pytest.raises(ExternalAICallBlocked):
        await voice.mint_client_secret()
    assert not reached.used
    assert {c.provider for c in blocked_calls()} == {"gemini", "xai"}


@pytest.mark.asyncio
async def test_the_backstop_refuses_an_unguarded_request_to_an_ai_host() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, json={})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        # A path written tomorrow, without its own guard, still cannot spend.
        with pytest.raises(ExternalAICallBlocked):
            await client.post("https://api.openai.com/v1/responses", json={})
        # Everything that is not an AI host is untouched.
        assert (await client.get("https://storage.example.test/object")).status_code == 200
    assert seen == ["https://storage.example.test/object"]
    assert [c.kind for c in blocked_calls()] == ["http"]
    reset_blocked_calls()


@pytest.mark.asyncio
async def test_a_stubbed_transport_still_cannot_reach_a_paid_host() -> None:
    with ai_guard.stubbed_transport_only():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200))) as client:
            with pytest.raises(ExternalAICallBlocked):
                await client.post("https://generativelanguage.googleapis.com/v1beta/models/x", json={})
    reset_blocked_calls()


@pytest.mark.asyncio
async def test_an_interview_turn_on_a_real_provider_degrades_and_is_recorded(reached: Reached) -> None:
    bp = BusinessBlueprint(
        business_id=uuid4(),
        identity={"display_name": Fact(value="Ishant Proteins", source="PLATFORM", confirmation="confirmed")},
    )
    after = await Engine.turn(bp, "We sell chicken and mutton.", provider=GeminiProvider("k"))
    assert not reached.used
    assert after.last_turn is not None and after.last_turn.fallback_reason == "ExternalAICallBlocked"
    assert [c.purpose for c in blocked_calls()] == ["business.interview"]
