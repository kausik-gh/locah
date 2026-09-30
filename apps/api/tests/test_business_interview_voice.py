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
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from platform_core.exceptions import PermissionDenied, ServiceUnavailable
from platform_core.interview import voice
from platform_core.interview.models import TargetState, Message
from platform_core.interview.models import BusinessBlueprint, Fact
from platform_core.interview.orchestrator import BusinessInterviewOrchestrator as Engine
from platform_core.interview.orchestrator import QUESTIONS


# Credential minting runs against a stub HTTP client; the backstop stays on.
pytestmark = pytest.mark.usefixtures("stubbed_ai_transport")


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

    def __init__(self, *, status: int = 200, payload: dict[str, Any] | None = None, raises=None):
        self.status = status
        self.payload = payload or {}
        self.raises = raises
        self.sent: dict[str, Any] = {}

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


def test_an_old_xai_voice_setting_gives_no_voice(monkeypatch):
    """Gemini Live is the only voice: a leftover VOICE_PROVIDER=xai is simply off."""
    monkeypatch.setenv("VOICE_PROVIDER", "xai")
    monkeypatch.setenv("XAI_API_KEY", "old")
    monkeypatch.setenv("GEMINI_API_KEY", "g")
    assert voice.is_configured() is False


@pytest.mark.asyncio
async def test_an_unsupported_provider_is_a_voice_failure(monkeypatch):
    monkeypatch.setenv("VOICE_PROVIDER", "xai")
    with pytest.raises(voice.VoiceSessionError):
        await voice.create_voice_session(blueprint())




















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
    monkeypatch.setenv("VOICE_PROVIDER", "gemini")
    monkeypatch.setattr(
        routes.voice_module,
        "mint_gemini_token",
        AsyncMock(side_effect=voice.VoiceSessionError("down")),
    )
    with pytest.raises(ServiceUnavailable):
        await routes.create_voice_session(
            uuid4(), SimpleNamespace(identity_id=uuid4(), correlation_id="c"), AsyncMock()
        )


# ---------------------------------------------------- one interview, two doors


def test_the_session_is_built_from_the_existing_blueprint():
    bp = blueprint(description="We are a 120-bed hospital", offerings="Cardiology and scans")
    instructions = voice.gemini_setup(bp)["systemInstruction"]["parts"][0]["text"]
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
    bp.messages = [Message(role="assistant", text="Which pieces should customers see first?")]
    Engine.project(bp)
    # The voice repeats Locah's own question; it never chooses one.
    assert "Which pieces should customers see first?" in voice.build_session_instructions(bp)


def test_completion_tells_the_voice_to_stop_interviewing():
    bp = blueprint(
        description="We make furniture", offerings="Sofas, wardrobes and dining tables",
        customer_actions="Send an enquiry", locations="Jaipur", phone="94140 55678",
    )
    bp.discovery["brand.story"] = TargetState(status="answered", summary="Made to last.")
    bp.discovery["media.logo"] = TargetState(status="declined", asked=1)
    bp.discovery["media.photos"] = TargetState(status="declined", asked=1)
    # Readiness is judged per business now (a furniture maker is still worth one
    # question about custom work); what matters here is that once there is
    # enough, the voice stops interviewing — and "enough" never goes away.
    from platform_core.interview.models import now

    bp.completion_state.ready_at = now()
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








# ------------------------------------------------------------------- Gemini Live

GEMINI_KEY = "gemini-account-key-that-must-never-be-served"


def test_gemini_is_the_default_voice_provider(monkeypatch):
    monkeypatch.delenv("VOICE_PROVIDER", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", GEMINI_KEY)
    assert voice.voice_provider() == "gemini"
    assert voice.is_configured() is True
    monkeypatch.delenv("GEMINI_API_KEY")
    assert voice.is_configured() is False


def test_gemini_detects_turns_so_the_owner_can_interrupt():
    detection = voice.gemini_setup(blueprint())["realtimeInputConfig"]["automaticActivityDetection"]
    assert detection["startOfSpeechSensitivity"] == "START_SENSITIVITY_HIGH"


def test_the_gemini_setup_locks_one_narrow_tool_and_the_instructions():
    bp = blueprint(description="Furniture kadai in Chennai")
    setup = voice.gemini_setup(bp)
    declarations = setup["tools"][0]["functionDeclarations"]
    assert [d["name"] for d in declarations] == ["process_business_interview_turn"]
    assert set(declarations[0]["parameters"]["properties"]) == {"transcript"}
    text = setup["systemInstruction"]["parts"][0]["text"]
    assert "Furniture kadai in Chennai" in text
    assert "WhatsApp pannitu" in text  # code-switching is expected, not tolerated
    assert "Do not ask anything before the tool answers" in " ".join(text.split())
    # gemini-3.8-live takes no thinking configuration.
    assert "thinkingConfig" not in setup["generationConfig"]
    assert setup["generationConfig"]["responseModalities"] == ["AUDIO"]
    assert setup["inputAudioTranscription"] == {} and setup["outputAudioTranscription"] == {}


@pytest.mark.asyncio
async def test_a_gemini_token_is_one_use_short_lived_and_locked(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", GEMINI_KEY)
    client = _Client(payload={"name": "auth_tokens/abc123"})
    monkeypatch.setattr(voice.httpx, "AsyncClient", lambda **_: client)

    minted = await voice.mint_gemini_token(blueprint(description="A clinic"))
    assert minted["token"] == "auth_tokens/abc123"
    assert GEMINI_KEY not in json.dumps(minted)
    sent = client.sent["json"]
    assert sent["uses"] == 1
    # The instructions and tools are locked into the token itself.
    assert sent["bidiGenerateContentSetup"]["tools"][0]["functionDeclarations"][0]["name"] == (
        "process_business_interview_turn"
    )
    # The browser only names the model; it cannot resend its own instructions.
    assert set(minted["setup"]) == {"model"}
    assert client.sent["headers"]["x-goog-api-key"] == GEMINI_KEY


@pytest.mark.asyncio
async def test_a_refused_gemini_token_is_a_voice_failure_not_a_crash(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", GEMINI_KEY)
    monkeypatch.setattr(voice.httpx, "AsyncClient", lambda **_: _Client(status=429))
    with pytest.raises(voice.VoiceSessionError):
        await voice.mint_gemini_token(blueprint())


@pytest.mark.asyncio
async def test_the_owner_gets_a_gemini_session_and_never_the_account_key(monkeypatch):
    import platform_api.routers.v1_business_interview as routes
    from platform_core.services.business_interview import BusinessInterviewService

    monkeypatch.setenv("GEMINI_API_KEY", GEMINI_KEY)
    monkeypatch.setenv("VOICE_PROVIDER", "gemini")
    bp = blueprint(description="We are a hospital")
    monkeypatch.setattr(routes, "resolve_business_actor", AsyncMock(return_value=SimpleNamespace(
        actor_membership=SimpleNamespace(role="primary_owner"),
        request=SimpleNamespace(effective_permissions={"website.edit", "business.update"}))))
    monkeypatch.setattr(BusinessInterviewService, "load_business", AsyncMock(return_value=MagicMock()))
    monkeypatch.setattr(BusinessInterviewService, "read", MagicMock(return_value=bp))
    monkeypatch.setattr(voice.httpx, "AsyncClient", lambda **_: _Client(payload={"name": "auth_tokens/t1"}))

    result = await routes.create_voice_session(
        bp.business_id, SimpleNamespace(identity_id=uuid4(), correlation_id="c"), AsyncMock()
    )
    assert GEMINI_KEY not in json.dumps(result)
    assert result["data"]["provider"] == "gemini"
    assert result["data"]["url"].startswith("wss://generativelanguage.googleapis.com/")
    assert "Constrained" in result["data"]["url"]
