"""Realtime voice: transport only, over the interview that already exists.

The claims worth testing here are not "audio plays". They are that the account
key never leaves the server, that talking is authorized exactly like typing,
that voice reuses the one Blueprint and the one orchestrator rather than
growing a parallel set, and that when the voice provider is missing or broken
onboarding carries on in chat with nothing lost.
"""

from __future__ import annotations

import inspect
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from platform_core.exceptions import PermissionDenied, ServiceUnavailable
from platform_core.interview import voice
from platform_core.interview.models import BusinessBlueprint, Fact
from platform_core.interview.orchestrator import BusinessInterviewOrchestrator as Engine
from platform_core.interview.orchestrator import QUESTIONS

KEY = "xai-secret-key-that-must-never-be-served"


def blueprint(**facts: str) -> BusinessBlueprint:
    bp = BusinessBlueprint(
        business_id=uuid4(),
        identity={
            "display_name": Fact(
                value="Riverside Hospital", source="PLATFORM", confirmation="confirmed"
            )
        },
        remaining_questions=list(QUESTIONS),
    )
    bp.known_facts = {
        k: Fact(value=v, source="USER_STATEMENT", confirmation="confirmed")
        for k, v in facts.items()
    }
    return bp


class _Client:
    """Minimal httpx.AsyncClient stand-in. No network in the suite."""

    def __init__(self, *, status: int = 200, payload: dict | None = None, raises=None):
        self.status = status
        self.payload = payload or {}
        self.raises = raises
        self.sent: dict = {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False

    async def post(self, url, headers=None, json=None, **_):
        if self.raises:
            raise self.raises
        self.sent = {"url": url, "headers": headers, "json": json}
        return SimpleNamespace(status_code=self.status, json=lambda: self.payload, text="")


# ------------------------------------------------------------- configuration


def test_voice_is_unavailable_without_a_key(monkeypatch):
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    assert voice.is_configured() is False


def test_voice_is_available_with_a_key(monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", KEY)
    monkeypatch.setenv("AI_PROVIDER", "xai")
    assert voice.is_configured() is True


@pytest.mark.asyncio
async def test_missing_key_fails_safely_rather_than_calling_out(monkeypatch):
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    with pytest.raises(voice.VoiceSessionError):
        await voice.mint_client_secret()


@pytest.mark.asyncio
async def test_a_revoked_credential_fails_safely(monkeypatch):
    """A deleted key must degrade to "carry on in chat", not to a stack trace."""
    monkeypatch.setenv("XAI_API_KEY", "xai-revoked")
    monkeypatch.setattr(voice.httpx, "AsyncClient", lambda **_: _Client(status=401))
    with pytest.raises(voice.VoiceSessionError):
        await voice.mint_client_secret()


@pytest.mark.asyncio
async def test_provider_outage_fails_safely(monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", KEY)
    monkeypatch.setattr(voice.httpx, "AsyncClient", lambda **_: _Client(raises=TimeoutError()))
    with pytest.raises(voice.VoiceSessionError):
        await voice.mint_client_secret()


@pytest.mark.asyncio
async def test_only_the_ephemeral_secret_is_returned(monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", KEY)
    client = _Client(payload={"value": "xai-realtime-client-secret-max-EPH", "expires_at": 123})
    monkeypatch.setattr(voice.httpx, "AsyncClient", lambda **_: client)

    minted = await voice.mint_client_secret()
    assert minted["client_secret"] == "xai-realtime-client-secret-max-EPH"
    assert KEY not in json.dumps(minted)
    # The permanent key is used to ask, and only to ask.
    assert client.sent["headers"]["Authorization"] == f"Bearer {KEY}"
    # A short life, so a leaked secret is worth very little.
    assert client.sent["json"]["expires_after"]["seconds"] == voice.SECRET_TTL_SECONDS
    assert voice.SECRET_TTL_SECONDS <= 300


# ------------------------------------------------------------- authorization


@pytest.mark.asyncio
async def test_a_member_who_is_not_the_owner_cannot_mint_a_voice_token(monkeypatch):
    import platform_api.routers.v1_business_interview as routes

    monkeypatch.setattr(
        routes,
        "resolve_business_actor",
        AsyncMock(
            return_value=SimpleNamespace(
                actor_membership=SimpleNamespace(role="staff"),
                request=SimpleNamespace(effective_permissions={"website.edit"}),
            )
        ),
    )
    with pytest.raises(PermissionDenied):
        await routes.create_voice_session(uuid4(), MagicMock(), AsyncMock())


@pytest.mark.asyncio
async def test_the_owner_gets_a_session_and_never_the_account_key(monkeypatch):
    import platform_api.routers.v1_business_interview as routes
    from platform_core.services.business_interview import BusinessInterviewService

    monkeypatch.setenv("XAI_API_KEY", KEY)
    bp = blueprint(description="We are a hospital", offerings="Cardiology")
    monkeypatch.setattr(
        routes,
        "resolve_business_actor",
        AsyncMock(
            return_value=SimpleNamespace(
                actor_membership=SimpleNamespace(role="primary_owner"),
                request=SimpleNamespace(
                    effective_permissions={"website.edit", "business.update"}
                ),
            )
        ),
    )
    monkeypatch.setattr(BusinessInterviewService, "load_business", AsyncMock(return_value=MagicMock()))
    monkeypatch.setattr(BusinessInterviewService, "read", MagicMock(return_value=bp))
    monkeypatch.setattr(
        routes.voice_module,
        "mint_client_secret",
        AsyncMock(return_value={"client_secret": "eph-abc", "expires_at": 9}),
    )

    result = await routes.create_voice_session(
        bp.business_id, SimpleNamespace(identity_id=uuid4(), correlation_id="c"), AsyncMock()
    )
    assert KEY not in json.dumps(result), "the permanent key must never reach the browser"
    assert result["data"]["client_secret"] == "eph-abc"
    assert result["data"]["url"].startswith("wss://")
    assert result["data"]["model"] == voice.VOICE_MODEL


@pytest.mark.asyncio
async def test_a_voice_outage_is_a_service_unavailable_not_a_crash(monkeypatch):
    import platform_api.routers.v1_business_interview as routes
    from platform_core.services.business_interview import BusinessInterviewService

    monkeypatch.setattr(
        routes,
        "resolve_business_actor",
        AsyncMock(
            return_value=SimpleNamespace(
                actor_membership=SimpleNamespace(role="primary_owner"),
                request=SimpleNamespace(
                    effective_permissions={"website.edit", "business.update"}
                ),
            )
        ),
    )
    monkeypatch.setattr(BusinessInterviewService, "load_business", AsyncMock(return_value=MagicMock()))
    monkeypatch.setattr(BusinessInterviewService, "read", MagicMock(return_value=blueprint()))
    monkeypatch.setattr(
        routes.voice_module,
        "mint_client_secret",
        AsyncMock(side_effect=voice.VoiceSessionError("down")),
    )
    with pytest.raises(ServiceUnavailable):
        await routes.create_voice_session(
            uuid4(), SimpleNamespace(identity_id=uuid4(), correlation_id="c"), AsyncMock()
        )


# ---------------------------------------------------- one interview, two doors


def test_the_session_is_built_from_the_existing_blueprint():
    bp = blueprint(description="We are a 120-bed hospital", offerings="Cardiology and scans")
    instructions = voice.session_config(bp)["instructions"]
    assert "Riverside Hospital" in instructions
    assert "120-bed hospital" in instructions
    assert "Cardiology and scans" in instructions


def test_known_facts_are_marked_never_to_be_asked_again():
    bp = blueprint(description="We make furniture")
    instructions = voice.build_session_instructions(bp)
    assert "never ask about these again" in instructions.lower()
    assert "We make furniture" in instructions


def test_the_next_question_comes_from_the_interview_not_the_model():
    bp = blueprint(description="We make furniture")
    Engine.project(bp)
    assert bp.remaining_questions[0].text in voice.build_session_instructions(bp)


def test_completion_tells_the_voice_to_stop_interviewing():
    bp = blueprint(
        description="We make furniture", offerings="Sofas", customer_actions="Send an enquiry"
    )
    Engine.project(bp)
    assert bp.completion_state.sufficient
    instructions = voice.build_session_instructions(bp)
    assert "Stop interviewing" in instructions
    assert "ENOUGH INFORMATION" in instructions


def test_the_prompt_stays_compact_and_carries_no_platform_internals():
    bp = blueprint(description="We are a hospital", offerings="Cardiology")
    instructions = voice.build_session_instructions(bp)
    # No registry dump, no schema, no module ids — Locah decides those, not Grok.
    for leak in ("offerings-catalog", "section_type", "website_section_types", "module_id"):
        assert leak not in instructions
    assert len(instructions) < 4000


def test_off_topic_and_unsupported_behaviour_are_instructed():
    instructions = voice.build_session_instructions(blueprint())
    assert "do not answer it" in instructions.lower()
    assert "not supported" in instructions.lower() or "cannot do that" in instructions.lower()


def test_voice_exposes_exactly_one_narrow_tool():
    assert [tool["name"] for tool in voice.VOICE_TOOLS] == ["process_business_interview_turn"]
    tool = voice.VOICE_TOOLS[0]
    assert set(tool["parameters"]["properties"]) == {"transcript"}
    # The model may report what was said. It may not name a module, enable one,
    # pick a template or build anything.
    params = json.dumps(tool["parameters"])
    for forbidden in ("module", "template", "enable", "build", "capability"):
        assert forbidden not in params


def test_there_is_no_parallel_voice_blueprint_or_orchestrator():
    """Voice is a transport. If it ever grows its own state, this should fail."""
    for banned in ("VoiceBusinessBlueprint", "VoiceInterviewOrchestrator", "VoiceCapabilities"):
        assert banned not in dir(voice)
    source = inspect.getsource(voice)
    # No extraction, completion or capability logic may live in the voice layer.
    for banned in ("known_facts[", "resolve_recommendations", "completion_state.sufficient ="):
        assert banned not in source


def test_server_vad_and_transcription_are_on_so_the_owner_can_interrupt():
    config = voice.session_config(blueprint())
    assert config["turn_detection"]["type"] == "server_vad"
    assert config["audio"]["input"]["transcription"]["model"] == "grok-transcribe"
    assert config["audio"]["input"]["format"] == {"type": "audio/pcm", "rate": 24000}
    assert config["audio"]["output"]["format"] == {"type": "audio/pcm", "rate": 24000}
    assert "audio" in config["modalities"] and "text" in config["modalities"]


def test_voice_uses_the_fast_model_not_a_reasoning_one():
    assert "fast" in voice.VOICE_MODEL
