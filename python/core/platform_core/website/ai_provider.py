"""AI model provider abstraction (Doc 12 §12.2).

`get_ai_provider()` returns the live xAI Grok provider when `XAI_API_KEY` is set
and `AI_PROVIDER` is `xai` (default), otherwise `UnavailableAIProvider`.
Callers always keep the deterministic fallback path (Doc 12 §12.1) regardless.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Protocol, runtime_checkable

import httpx

from platform_core.logging import get_logger

_log = get_logger("website.ai_provider")

# Content generation only — never platform mechanics (Doc 12 §12.6).
# Default is a fast Grok model suited to large structured website drafts; override
# with XAI_MODEL for staging/production tuning.
_DEFAULT_MODEL = os.getenv("XAI_MODEL", "grok-3-mini")
_XAI_CHAT_COMPLETIONS_URL = "https://api.x.ai/v1/chat/completions"


@runtime_checkable
class AIModelProvider(Protocol):
    provider_name: str

    @property
    def model_name(self) -> str: ...

    async def generate_structured(
        self,
        prompt: str,
        schema: dict[str, Any],
        model_config: dict[str, Any],
        timeout_seconds: int,
    ) -> dict[str, Any]: ...


class AIProviderPermanentError(RuntimeError):
    """The provider refused in a way that retrying cannot fix.

    A rejected key, a revoked key or an unknown model fails identically on every
    attempt, so retrying only delays the deterministic fallback — and the owner
    is sitting in onboarding watching it. Retry the transient cases only.
    """


class UnavailableAIProvider:
    """Default provider when no API key is configured — always fails fast."""

    provider_name = "unavailable"

    @property
    def model_name(self) -> str:
        return "unavailable"

    async def generate_structured(
        self,
        prompt: str,
        schema: dict[str, Any],
        model_config: dict[str, Any],
        timeout_seconds: int,
    ) -> dict[str, Any]:
        raise RuntimeError(
            "AI provider not configured (no XAI_API_KEY); use deterministic fallback"
        )


class GrokProvider:
    """xAI Grok via the OpenAI-compatible Chat Completions API.

    Structured output uses native `response_format.type=json_schema`. Section
    content objects stay schema-loose (`strict=False`) because each SectionType
    carries a different content shape; the hard guarantee remains the caller's
    `validate_generation_payload`.
    """

    provider_name = "xai"

    def __init__(self, api_key: str, model: str = _DEFAULT_MODEL) -> None:
        self._api_key = api_key
        self._model = model

    @property
    def model_name(self) -> str:
        return self._model

    async def generate_structured(
        self,
        prompt: str,
        schema: dict[str, Any],
        model_config: dict[str, Any],
        timeout_seconds: int,
    ) -> dict[str, Any]:
        model = str(model_config.get("model", self._model))
        purpose = model_config.get("purpose")
        body = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You generate structured multi-page business website drafts. "
                        "Return JSON only that matches the supplied schema. "
                        "Do not include markdown fences or commentary."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": str(model_config.get("schema_name", "website_generation")),
                    "schema": schema,
                    # Section `content` objects vary by SectionType — strict mode
                    # would reject the envelope schema the platform already validates.
                    "strict": False,
                },
            },
            "temperature": float(model_config.get("temperature", 0.6)),
            "max_tokens": int(model_config.get("max_output_tokens", 8192)),
        }
        started = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                response = await client.post(
                    _XAI_CHAT_COMPLETIONS_URL,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json=body,
                )
            latency_ms = int((time.monotonic() - started) * 1000)
            if response.status_code >= 400:
                _log.warning(
                    "website.ai_provider.call_failed",
                    provider=self.provider_name,
                    model=model,
                    purpose=purpose,
                    status_code=response.status_code,
                    latency_ms=latency_ms,
                    error=response.text[:500],
                )
                # 401/403 are unambiguous. xAI also answers a bad key with 400
                # + code "invalid-argument", so match on the code rather than
                # the status alone; a genuinely malformed request is equally
                # not worth three attempts.
                detail = response.text[:300]
                if response.status_code in (401, 403) or (
                    response.status_code == 400 and "invalid-argument" in detail
                ):
                    raise AIProviderPermanentError(
                        f"{self.provider_name} rejected the request "
                        f"({response.status_code}): {detail}"
                    )
                response.raise_for_status()

            data = response.json()
            usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
            _log.info(
                "website.ai_provider.completed",
                provider=self.provider_name,
                model=model,
                purpose=purpose,
                latency_ms=latency_ms,
                prompt_tokens=usage.get("prompt_tokens"),
                completion_tokens=usage.get("completion_tokens"),
            )
            text = self._extract_message_content(data)
        except Exception as exc:  # noqa: BLE001 — surface as a retry/fallback trigger
            _log.warning(
                "website.ai_provider.call_failed",
                provider=self.provider_name,
                model=model,
                purpose=purpose,
                error=str(exc),
            )
            raise

        if text.startswith("```"):
            text = text.strip("`")
            text = text[text.index("{") :] if "{" in text else text
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            _log.warning(
                "website.ai_provider.unparseable_response",
                provider=self.provider_name,
                model=model,
                error=str(exc),
            )
            raise RuntimeError("Grok returned non-JSON output") from exc
        if not isinstance(parsed, dict):
            raise RuntimeError("Grok returned a non-object JSON value")
        return parsed

    @staticmethod
    def _extract_message_content(data: dict[str, Any]) -> str:
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise RuntimeError("Grok returned no choices")
        message = choices[0].get("message")
        if not isinstance(message, dict):
            raise RuntimeError("Grok returned an invalid message envelope")
        content = message.get("content")
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts: list[str] = []
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    text = part.get("text")
                    if isinstance(text, str):
                        parts.append(text)
            if parts:
                return "".join(parts).strip()
        raise RuntimeError("Grok returned empty content")


def get_ai_provider() -> AIModelProvider:
    provider_choice = os.getenv("AI_PROVIDER", "xai").strip().lower()
    if provider_choice in {"xai", "grok"}:
        api_key = os.getenv("XAI_API_KEY", "").strip()
        if api_key:
            model = os.getenv("XAI_MODEL", _DEFAULT_MODEL).strip() or _DEFAULT_MODEL
            return GrokProvider(api_key, model)
    return UnavailableAIProvider()
