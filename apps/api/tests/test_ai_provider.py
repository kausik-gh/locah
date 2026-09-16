"""Unit tests for the website AI provider abstraction."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from platform_core.website.ai_provider import (
    GrokProvider,
    UnavailableAIProvider,
    get_ai_provider,
)


def test_get_ai_provider_without_key_returns_unavailable(monkeypatch: Any) -> None:
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.setenv("AI_PROVIDER", "xai")
    provider = get_ai_provider()
    assert isinstance(provider, UnavailableAIProvider)


def test_get_ai_provider_with_key_returns_grok(monkeypatch: Any) -> None:
    monkeypatch.setenv("XAI_API_KEY", "test-key")
    monkeypatch.setenv("AI_PROVIDER", "xai")
    monkeypatch.setenv("XAI_MODEL", "grok-test")
    provider = get_ai_provider()
    assert isinstance(provider, GrokProvider)
    assert provider.provider_name == "xai"
    assert provider.model_name == "grok-test"


@pytest.mark.asyncio
async def test_grok_provider_parses_structured_response() -> None:
    payload = {
        "pages": [{"slug": "home", "title": "Home", "page_type": "home", "sections": []}],
        "navigation": [{"label": "Home", "path": "/"}],
        "theme_hints": {"primary_color": "#112233"},
    }
    response = MagicMock()
    response.status_code = 200
    response.text = ""
    response.json.return_value = {
        "choices": [{"message": {"content": json.dumps(payload)}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20},
    }
    response.raise_for_status = MagicMock()
    client = AsyncMock()
    client.post = AsyncMock(return_value=response)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)

    provider = GrokProvider("test-key", "grok-test")
    with patch("platform_core.website.ai_provider.httpx.AsyncClient", return_value=client):
        parsed = await provider.generate_structured(
            "prompt",
            {"type": "object"},
            {"purpose": "website.generate"},
            30,
        )
    assert parsed == payload
    sent = client.post.await_args.kwargs["json"]
    assert sent["response_format"]["type"] == "json_schema"
    assert sent["model"] == "grok-test"


@pytest.mark.asyncio
async def test_grok_provider_rejects_non_json() -> None:
    response = MagicMock()
    response.status_code = 200
    response.text = ""
    response.json.return_value = {"choices": [{"message": {"content": "not json"}}]}
    response.raise_for_status = MagicMock()
    client = AsyncMock()
    client.post = AsyncMock(return_value=response)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)

    provider = GrokProvider("test-key", "grok-test")
    with patch("platform_core.website.ai_provider.httpx.AsyncClient", return_value=client):
        with pytest.raises(RuntimeError, match="non-JSON"):
            await provider.generate_structured("prompt", {"type": "object"}, {}, 30)
