"""AI model provider abstraction (Doc 12 §12.2).

`get_ai_provider()` returns the live Gemini provider when `GEMINI_API_KEY` is
set, and `UnavailableAIProvider` otherwise. Callers always keep the
deterministic fallback path (Doc 12 §12.1) regardless.

FL-DEC-015 (initial provider, budget, and fallback policy) remains formally
open — the Gemini key currently in use is a temporary founder-authorised one
pending its closure. See memory `gemini-key-needs-rotation`.
"""

from __future__ import annotations

import json
import os
from typing import Any, Protocol, runtime_checkable

from platform_core.logging import get_logger

_log = get_logger("website.ai_provider")

# Content generation only — never platform mechanics (Doc 12 §12.6).
# `gemini-flash-latest` is the never-retiring alias but has been flaky under
# load (503s); `gemini-3.6-flash` is the current concrete recommendation and
# the retry loop + deterministic fallback cover a model going away again.
_DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")


@runtime_checkable
class AIModelProvider(Protocol):
    async def generate_structured(
        self,
        prompt: str,
        schema: dict[str, Any],
        model_config: dict[str, Any],
        timeout_seconds: int,
    ) -> dict[str, Any]: ...


class UnavailableAIProvider:
    """Default provider when no API key is configured — always fails fast."""

    async def generate_structured(
        self,
        prompt: str,
        schema: dict[str, Any],
        model_config: dict[str, Any],
        timeout_seconds: int,
    ) -> dict[str, Any]:
        raise RuntimeError(
            "AI provider not configured (no GEMINI_API_KEY); use deterministic fallback"
        )


class GeminiProvider:
    """Google Gemini via the `google-genai` SDK.

    Structured output is requested with `response_mime_type=application/json`
    and the target schema is embedded in the prompt. The hard guarantee is the
    caller's `validate_generation_payload` — this provider only needs to return
    parseable JSON.
    """

    def __init__(self, api_key: str, model: str = _DEFAULT_MODEL) -> None:
        self._api_key = api_key
        self._model = model

    async def generate_structured(
        self,
        prompt: str,
        schema: dict[str, Any],
        model_config: dict[str, Any],
        timeout_seconds: int,
    ) -> dict[str, Any]:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=self._api_key)
        full_prompt = (
            f"{prompt}\n\n"
            "Return ONLY a JSON object that conforms to this JSON Schema. "
            "Do not include markdown fences or commentary.\n\n"
            f"JSON Schema:\n{json.dumps(schema)}"
        )
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=float(model_config.get("temperature", 0.6)),
            max_output_tokens=int(model_config.get("max_output_tokens", 8192)),
            http_options=types.HttpOptions(timeout=timeout_seconds * 1000),
        )
        try:
            response = await client.aio.models.generate_content(
                model=model_config.get("model", self._model),
                contents=full_prompt,
                config=config,
            )
        except Exception as exc:  # noqa: BLE001 — surface as a ret/fallback trigger
            _log.warning(
                "website.ai_provider.call_failed",
                provider="gemini",
                model=self._model,
                purpose=model_config.get("purpose"),
                error=str(exc),
            )
            raise

        text = (response.text or "").strip()
        if text.startswith("```"):
            text = text.strip("`")
            text = text[text.index("{") :] if "{" in text else text
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            _log.warning(
                "website.ai_provider.unparseable_response",
                provider="gemini",
                model=self._model,
                error=str(exc),
            )
            raise RuntimeError("Gemini returned non-JSON output") from exc
        if not isinstance(parsed, dict):
            raise RuntimeError("Gemini returned a non-object JSON value")
        return parsed


def get_ai_provider() -> AIModelProvider:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if api_key:
        return GeminiProvider(api_key)
    return UnavailableAIProvider()
