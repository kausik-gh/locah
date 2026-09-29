"""Unit tests for the AI provider boundary: Gemini is LOCAH's only provider."""

from __future__ import annotations

from typing import Any

import pytest
from platform_core.website.ai_provider import (
    GeminiProvider,
    UnavailableAIProvider,
    get_ai_provider,
)

pytestmark = pytest.mark.usefixtures("stubbed_ai_transport")


def test_without_a_key_there_is_no_model(monkeypatch: Any) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("AI_PROVIDER", "gemini")
    assert isinstance(get_ai_provider(), UnavailableAIProvider)


def test_gemini_with_a_key(monkeypatch: Any) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("AI_PROVIDER", "gemini")
    provider = get_ai_provider()
    assert isinstance(provider, GeminiProvider) and provider.provider_name == "gemini"


@pytest.mark.parametrize("leftover", ["xai", "grok", "openai"])
def test_a_leftover_provider_setting_never_reaches_another_vendor(monkeypatch: Any, leftover: str) -> None:
    """Grok was removed: an old AI_PROVIDER=xai means no model, not a second vendor."""
    monkeypatch.setenv("AI_PROVIDER", leftover)
    monkeypatch.setenv("XAI_API_KEY", "old-key")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    assert isinstance(get_ai_provider(), UnavailableAIProvider)


def test_there_is_no_grok_code_left() -> None:
    import platform_core.interview.voice as voice
    import platform_core.website.ai_provider as ai
    import platform_core.website.image_generation as images

    assert not hasattr(ai, "GrokProvider")
    assert not hasattr(voice, "mint_client_secret")
    for module in (ai, images, voice):
        source = open(module.__file__ or "", encoding="utf-8").read()
        assert "api.x.ai" not in source, module.__name__


@pytest.mark.asyncio
async def test_unavailable_provider_fails_fast() -> None:
    with pytest.raises(RuntimeError):
        await UnavailableAIProvider().generate_structured("x", {}, {}, timeout_seconds=1)
