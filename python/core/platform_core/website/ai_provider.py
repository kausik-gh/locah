"""AI model provider abstraction (Doc 12 §12.2).

`get_ai_provider()` returns the one provider `AI_PROVIDER` names — Gemini by
default, xAI Grok as an explicit alternative — or `UnavailableAIProvider` when
that provider has no key. Callers describe a *purpose*; each provider maps the
purpose to its own model, so no vendor model name leaks into business logic.
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
#
# Must be an id xAI currently serves. `grok-3-mini` was the previous default and
# is no longer in /v1/models — xAI still answers for it by aliasing to a current
# model, so the substitution is silent and the configured id is not what runs.
# Pin the real one instead of relying on an alias that can be withdrawn.
_DEFAULT_MODEL = os.getenv("XAI_MODEL", "grok-4.3")
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
            "AI provider not configured (no key for AI_PROVIDER); use deterministic fallback"
        )


class GrokProvider:
    """xAI Grok via the OpenAI-compatible Chat Completions API.

    Structured output uses native `response_format.type=json_schema`. Section
    content objects stay schema-loose (`strict=False`) because each SectionType
    carries a different content shape; the hard guarantee remains the caller's
    `validate_generation_payload`.
    """

    provider_name = "xai"

    # Extraction is quotation, not reasoning. Measured on the real interview
    # payload: grok-4.3 8.6-10.2s per turn, the non-reasoning model 1.5-2.3s and
    # more accurate. Owned here so callers never name a vendor's model.
    _PURPOSE_MODELS = {"business.interview": "grok-4.20-0309-non-reasoning"}

    def __init__(self, api_key: str, model: str = _DEFAULT_MODEL) -> None:
        self._api_key = api_key
        self._model = model
        self.last_usage: dict[str, Any] | None = None

    @property
    def model_name(self) -> str:
        return self._model

    def model_for(self, purpose: str | None) -> str:
        return self._PURPOSE_MODELS.get(str(purpose or ""), self._model)

    async def generate_structured(
        self,
        prompt: str,
        schema: dict[str, Any],
        model_config: dict[str, Any],
        timeout_seconds: int,
    ) -> dict[str, Any]:
        purpose = model_config.get("purpose")
        model = str(model_config.get("model") or self.model_for(purpose))
        body = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": model_config.get("system_prompt") or (
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
            self.last_usage = {
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
                "total_tokens": usage.get("total_tokens"),
                "latency_ms": latency_ms,
                "model": model,
            }
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


# ---------------------------------------------------------------- Gemini

_GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"
GEMINI_DEFAULT_MODEL = "gemini-3.8-flash"

# One fast model everywhere by default; the purposes differ in how much the
# model is allowed to think. Routine extraction is quotation and must answer
# while the owner is waiting, so it thinks least. Website strategy and copy are
# the one place where a little more deliberation visibly changes the result.
_GEMINI_THINKING = {
    "business.interview": "low",
    "website.design_strategy": "medium",
    "website.personalization": "medium",
    "website.generate": "medium",
}

# Keywords JSON Schema allows but Gemini's structured-output subset rejects or
# ignores. Pydantic emits them; they carry no constraint the platform relies
# on, because every response is re-validated by the same Pydantic model.
_UNSUPPORTED_SCHEMA_KEYS = {"title", "default", "$schema", "examples", "discriminator"}


# Gemini's structured output accepts a narrower JSON Schema than Pydantic
# writes, and the subset differs by model. Live, with the interview schema:
# `maxLength: 4000` failed on gemini-3.8-flash ("400 invalid argument", or a 503
# "high demand" from the grammar build), and on gemini-3.5-flash the remaining
# constraint keywords failed too — while the same schema with only type,
# properties, items, enum, required and description was accepted by both.
# So only that core is sent. Every limit still reaches the model as guidance
# in the description, and `_fit` enforces all of them on the answer before
# the caller's own Pydantic validation runs.
_GEMINI_KEEP = {"type", "properties", "items", "enum", "required", "description", "anyOf", "nullable"}


def _gemini_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """The schema as Gemini will accept it: references inlined, constraints as guidance."""

    def relax(node: Any) -> Any:
        if isinstance(node, list):
            return [relax(item) for item in node]
        if not isinstance(node, dict):
            return node
        out: dict[str, Any] = {}
        for key, value in node.items():
            if key == "properties" and isinstance(value, dict):
                out[key] = {name: relax(sub) for name, sub in value.items()}
            elif key in _GEMINI_KEEP:
                out[key] = relax(value)
        if "const" in node and "enum" not in out:
            # A single allowed value is still a constraint worth decoding.
            out["enum"] = [node["const"]]
        hints = []
        if isinstance(node.get("minimum"), (int, float)) or isinstance(node.get("maximum"), (int, float)):
            hints.append(f"Between {node.get('minimum', '-inf')} and {node.get('maximum', 'inf')}.")
        if isinstance(node.get("maxLength"), int):
            hints.append(f"At most {node['maxLength']} characters.")
        if isinstance(node.get("maxItems"), int):
            hints.append(f"At most {node['maxItems']} items.")
        if hints:
            out["description"] = " ".join([str(out.get("description", ""))] + hints).strip()
        return out

    relaxed = relax(_inline_schema(schema))
    return relaxed if isinstance(relaxed, dict) else {}


def _fit(value: Any, schema: Any) -> Any:
    """Hold an answer to the limits Gemini was only told about.

    Strings are trimmed to maxLength, lists capped at maxItems, list items that
    break minLength or miss a required field are dropped, and keys a closed
    object does not declare are removed — the smallest repair that lets one
    over-eager field survive instead of failing the whole answer.
    """
    if not isinstance(schema, dict):
        return value
    if isinstance(value, str):
        limit = schema.get("maxLength")
        return value[:limit] if isinstance(limit, int) else value
    if isinstance(value, list):
        item_schema = schema.get("items")
        kept = [_fit(item, item_schema) for item in value]
        kept = [item for item in kept if _acceptable(item, item_schema)]
        limit = schema.get("maxItems")
        return kept[:limit] if isinstance(limit, int) else kept
    if isinstance(value, dict):
        props = schema.get("properties") or {}
        closed = schema.get("additionalProperties") is False
        return {k: _fit(v, props.get(k)) for k, v in value.items() if not closed or k in props}
    return value


def _acceptable(item: Any, schema: Any) -> bool:
    if not isinstance(schema, dict):
        return True
    if isinstance(item, str):
        return len(item) >= int(schema.get("minLength") or 0)
    if isinstance(item, dict):
        props = schema.get("properties") or {}
        for name in schema.get("required") or []:
            if name not in item:
                return False
            sub = props.get(name)
            if isinstance(item[name], str) and isinstance(sub, dict):
                if len(item[name]) < int(sub.get("minLength") or 0):
                    return False
    return True


def _inline_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Inline `$defs` references and drop keywords Gemini does not accept."""
    defs = schema.get("$defs") or schema.get("definitions") or {}

    def resolve(node: Any, depth: int = 0) -> Any:
        if depth > 24:
            return {}
        if isinstance(node, dict):
            ref = node.get("$ref")
            if isinstance(ref, str) and ref.startswith("#/"):
                target = defs.get(ref.rsplit("/", 1)[-1], {})
                merged = {**target, **{k: v for k, v in node.items() if k != "$ref"}}
                return resolve(merged, depth + 1)
            out: dict[str, Any] = {}
            for key, value in node.items():
                if key == "properties" and isinstance(value, dict):
                    # Property *names* are data, not keywords: a field called
                    # "title" was being stripped as if it were the keyword, and
                    # Gemini rightly refused a schema requiring a missing field.
                    out[key] = {name: resolve(sub, depth + 1) for name, sub in value.items()}
                elif key not in _UNSUPPORTED_SCHEMA_KEYS and key not in {"$defs", "definitions"}:
                    out[key] = resolve(value, depth + 1)
            return out
        if isinstance(node, list):
            return [resolve(item, depth + 1) for item in node]
        return node

    resolved = resolve(schema)
    return resolved if isinstance(resolved, dict) else {}


# Tried in order after the purpose's own model. In the live run each one was
# busy at some moment (3.5-flash: a 503 after 31 s) and another answered.
GEMINI_FALLBACK_MODEL = "gemini-3.5-flash,gemini-3.1-flash-lite"


class _GeminiRejected(Exception):
    """A non-2xx answer: the status, and the error callers should finally see."""

    def __init__(self, status: int, error: Exception) -> None:
        super().__init__(str(error))
        self.status = status
        self.error = error


class GeminiProvider:
    """Google Gemini `generateContent` with native JSON-schema structured output.

    Schema compliance is a convenience, not a guarantee the platform trusts:
    every caller re-validates with its own Pydantic model and deterministic
    rules, exactly as it does for Grok. A quota or credential failure is
    permanent for the request — retrying a 429 on a free tier only spends the
    remaining allowance faster.
    """

    provider_name = "gemini"

    def __init__(self, api_key: str, model: str = GEMINI_DEFAULT_MODEL) -> None:
        self._api_key = api_key
        self._model = model
        self._model_used: str | None = None
        self.last_usage: dict[str, Any] | None = None

    @property
    def model_name(self) -> str:
        """The model that actually answered last — the fallback, when it did."""
        return self._model_used or self._model

    def model_for(self, purpose: str | None) -> str:
        key = str(purpose or "")
        if key == "business.interview":
            return os.getenv("GEMINI_INTERVIEW_MODEL", "").strip() or self._model
        if key.startswith("website."):
            return os.getenv("GEMINI_WEBSITE_MODEL", "").strip() or self._model
        return self._model

    def build_body(self, prompt: str, schema: dict[str, Any], model_config: dict[str, Any]) -> dict[str, Any]:
        purpose = model_config.get("purpose")
        generation: dict[str, Any] = {
            "responseMimeType": "application/json",
            "responseJsonSchema": _gemini_schema(schema),
            "maxOutputTokens": int(model_config.get("max_output_tokens", 8192)),
        }
        if "temperature" in model_config:
            generation["temperature"] = float(model_config["temperature"])
        thinking = model_config.get("thinking_level") or _GEMINI_THINKING.get(str(purpose or ""))
        if thinking:
            generation["thinkingConfig"] = {"thinkingLevel": thinking}
        body: dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": generation,
        }
        system_prompt = model_config.get("system_prompt")
        if system_prompt:
            body["systemInstruction"] = {"parts": [{"text": str(system_prompt)}]}
        return body

    async def generate_structured(
        self,
        prompt: str,
        schema: dict[str, Any],
        model_config: dict[str, Any],
        timeout_seconds: int,
    ) -> dict[str, Any]:
        """One structured answer, from the purpose's model or — once — the fallback.

        A busy Gemini model answers 503, and on the free tier its overloaded
        replicas also answer `400 invalid argument` for a request that another
        replica accepts unchanged. Quotas are per model, so the fallback model
        (GEMINI_FALLBACK_MODEL, a comma-separated list) are real further chances
        at no second provider.
        Only a credential failure skips it: another model cannot fix a bad key.
        """
        purpose = model_config.get("purpose")
        primary = str(model_config.get("model") or self.model_for(purpose))
        fallbacks = (os.getenv("GEMINI_FALLBACK_MODEL") or GEMINI_FALLBACK_MODEL).split(",")
        models = [primary] + [m.strip() for m in fallbacks if m.strip() and m.strip() != primary]
        body = self.build_body(prompt, schema, model_config)
        started = time.monotonic()
        failure: Exception | None = None
        for attempt, model in enumerate(models):
            remaining = timeout_seconds - (time.monotonic() - started)
            if attempt and remaining < 3:
                break
            try:
                data = await self._post(model, body, purpose, max(remaining, 1.0))
            except _GeminiRejected as exc:
                failure = exc.error
                if exc.status in (401, 403):
                    break
                continue
            parsed = self._parse(data, model, purpose, started)
            clipped = _fit(parsed, _inline_schema(schema))
            return clipped if isinstance(clipped, dict) else parsed
        assert failure is not None
        raise failure

    async def _post(
        self, model: str, body: dict[str, Any], purpose: Any, timeout: float
    ) -> dict[str, Any]:
        started = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    f"{_GEMINI_BASE}/models/{model}:generateContent",
                    headers={"x-goog-api-key": self._api_key, "Content-Type": "application/json"},
                    json=body,
                )
        except Exception as exc:  # noqa: BLE001
            _log.warning("ai.gemini.call_failed", model=model, purpose=purpose, error=type(exc).__name__)
            raise
        latency_ms = int((time.monotonic() - started) * 1000)
        if response.status_code >= 400:
            # Google's own message ("high demand", "quota exceeded") carries no
            # key and no owner text, and without it a 400 is undiagnosable.
            try:
                reason = str((response.json().get("error") or {}).get("message", ""))[:200]
            except ValueError:
                reason = response.text[:200]
            _log.warning(
                "ai.gemini.call_failed", model=model, purpose=purpose,
                status_code=response.status_code, latency_ms=latency_ms, reason=reason,
            )
            error: Exception = (
                AIProviderPermanentError(f"gemini rejected the request ({response.status_code}): {reason}")
                if response.status_code in (400, 401, 403, 404, 429)
                else RuntimeError(f"gemini unavailable ({response.status_code}): {reason}")
            )
            raise _GeminiRejected(response.status_code, error)
        data = response.json()
        return data if isinstance(data, dict) else {}

    def _parse(
        self, data: dict[str, Any], model: str, purpose: Any, started: float
    ) -> dict[str, Any]:
        latency_ms = int((time.monotonic() - started) * 1000)
        self._model_used = model
        raw_usage = data.get("usageMetadata")
        usage: dict[str, Any] = raw_usage if isinstance(raw_usage, dict) else {}
        self.last_usage = {
            "prompt_tokens": usage.get("promptTokenCount"),
            "completion_tokens": usage.get("candidatesTokenCount"),
            "thinking_tokens": usage.get("thoughtsTokenCount"),
            "total_tokens": usage.get("totalTokenCount"),
            "latency_ms": latency_ms,
            "model": model,
        }
        # Keys avoid the word "token": the log redactor masks anything named
        # like a credential, and usage is the one thing these lines are for.
        _log.info(
            "ai.gemini.completed", model=model, purpose=purpose, latency_ms=latency_ms,
            prompt_units=usage.get("promptTokenCount"),
            output_units=usage.get("candidatesTokenCount"),
            thinking_units=usage.get("thoughtsTokenCount"),
        )
        text = self.extract_text(data)
        if text.startswith("```"):
            text = text.strip("`")
            text = text[text.index("{"):] if "{" in text else text
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Gemini returned non-JSON output") from exc
        if not isinstance(parsed, dict):
            raise RuntimeError("Gemini returned a non-object JSON value")
        return parsed

    @staticmethod
    def extract_text(data: dict[str, Any]) -> str:
        candidates = data.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            feedback = data.get("promptFeedback") or {}
            raise RuntimeError(f"Gemini returned no candidates ({feedback.get('blockReason', 'unknown')})")
        first = candidates[0] if isinstance(candidates[0], dict) else {}
        parts = ((first.get("content") or {}).get("parts")) or []
        # Thought summaries are not the answer and must never be parsed as one.
        text = "".join(
            str(part.get("text", ""))
            for part in parts
            if isinstance(part, dict) and not part.get("thought")
        ).strip()
        if not text:
            raise RuntimeError(f"Gemini returned empty content ({first.get('finishReason', 'unknown')})")
        return text


def configured_provider_name() -> str:
    """Which provider is configured, without revealing anything about its key."""
    return os.getenv("AI_PROVIDER", "gemini").strip().lower() or "gemini"


def get_ai_provider() -> AIModelProvider:
    """The one configured provider, or none at all.

    There is deliberately no automatic cross-provider fallback: silently calling
    a second paid provider whenever the first returns an error is how a bad
    afternoon becomes an unexpected bill. Switching is an explicit
    configuration change. When the configured provider has no key, callers get
    `UnavailableAIProvider` and take their existing deterministic path.
    """
    choice = configured_provider_name()
    if choice == "gemini":
        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        if api_key:
            model = os.getenv("GEMINI_MODEL", GEMINI_DEFAULT_MODEL).strip() or GEMINI_DEFAULT_MODEL
            return GeminiProvider(api_key, model)
        return UnavailableAIProvider()
    if choice in {"xai", "grok"}:
        api_key = os.getenv("XAI_API_KEY", "").strip()
        if api_key:
            model = os.getenv("XAI_MODEL", _DEFAULT_MODEL).strip() or _DEFAULT_MODEL
            return GrokProvider(api_key, model)
    return UnavailableAIProvider()
