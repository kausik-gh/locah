"""The Gemini adapter's one second chance: a different Gemini model, never another provider.

No network — each test scripts the answers Google gave during the live run:
503 "high demand", a replica's misleading 400, a 429 quota, a rejected key.
"""

from __future__ import annotations

import json

import httpx
import pytest

from platform_core.website import ai_provider
from platform_core.website.ai_provider import AIProviderPermanentError, GeminiProvider

OK = {
    "candidates": [{"content": {"parts": [{"text": json.dumps({"ok": True})}]}}],
    "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 3},
}


def _error(status: int, message: str) -> httpx.Response:
    return httpx.Response(status, json={"error": {"code": status, "message": message}})


class Script:
    def __init__(self, *responses: httpx.Response) -> None:
        self.responses = list(responses)
        self.urls: list[str] = []

    def client(self, *args, **kwargs):  # noqa: ANN002, ANN003
        script = self

        class _Client:
            async def __aenter__(self):  # noqa: ANN204
                return self

            async def __aexit__(self, *exc):  # noqa: ANN002, ANN204
                return False

            async def post(self, url, headers, json):  # noqa: ANN001, ANN201, A002
                script.urls.append(url)
                return script.responses.pop(0)

        return _Client()


def _models(script: Script) -> list[str]:
    return [url.split("/models/")[1].split(":")[0] for url in script.urls]


@pytest.fixture(autouse=True)
def _no_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("GEMINI_FALLBACK_MODEL", "GEMINI_INTERVIEW_MODEL", "GEMINI_WEBSITE_MODEL"):
        monkeypatch.delenv(name, raising=False)


@pytest.mark.parametrize(
    "first",
    [
        _error(503, "This model is currently experiencing high demand."),
        _error(400, "Request contains an invalid argument."),
        _error(429, "You exceeded your current quota."),
    ],
)
async def test_a_busy_model_falls_back_to_another_gemini_model(monkeypatch, first):
    script = Script(first, httpx.Response(200, json=OK))
    monkeypatch.setattr(ai_provider.httpx, "AsyncClient", script.client)
    provider = GeminiProvider("k", model="gemini-3.8-flash")
    result = await provider.generate_structured("p", {"type": "object"}, {"purpose": "business.interview"}, 12)
    assert result == {"ok": True}
    assert _models(script) == ["gemini-3.8-flash", "gemini-3.5-flash"]
    assert provider.model_name == "gemini-3.5-flash"  # recorded honestly


async def test_a_rejected_key_is_not_retried_on_another_model(monkeypatch):
    script = Script(_error(403, "API key not valid."))
    monkeypatch.setattr(ai_provider.httpx, "AsyncClient", script.client)
    with pytest.raises(AIProviderPermanentError):
        await GeminiProvider("k").generate_structured("p", {"type": "object"}, {}, 12)
    assert len(script.urls) == 1


async def test_when_every_model_fails_the_caller_gets_the_last_error(monkeypatch):
    script = Script(_error(503, "busy"), _error(503, "busy too"), _error(503, "still busy"))
    monkeypatch.setattr(ai_provider.httpx, "AsyncClient", script.client)
    with pytest.raises(RuntimeError, match="still busy"):
        await GeminiProvider("k").generate_structured("p", {"type": "object"}, {}, 30)
    assert _models(script) == ["gemini-3.8-flash", "gemini-3.5-flash", "gemini-3.1-flash-lite"]
    assert all("x.ai" not in url for url in script.urls)


async def test_no_second_attempt_without_time_for_it(monkeypatch):
    # A two-second budget leaves no room for a fallback that needs three.
    script = Script(_error(503, "busy"))
    monkeypatch.setattr(ai_provider.httpx, "AsyncClient", script.client)
    with pytest.raises(RuntimeError):
        await GeminiProvider("k").generate_structured("p", {"type": "object"}, {}, 2)
    assert len(script.urls) == 1


# ------------------------------------------------------ long string limits


def test_only_the_portable_schema_core_is_sent():
    from platform_core.interview.models import Extraction
    from platform_core.website.ai_provider import _gemini_schema

    sent = json.dumps(_gemini_schema(Extraction.model_json_schema()))
    # These keywords made live requests fail on one Gemini model or another.
    for keyword in ("maxLength", "minLength", "maxItems", "additionalProperties", "$defs", "$ref"):
        assert f'"{keyword}"' not in sent
    # The limits still reach the model, as guidance it can read.
    assert "At most 4000 characters." in sent and "At most 20 items." in sent
    assert '"enum"' in sent and '"required"' in sent


def test_the_answer_is_held_to_every_limit_the_model_was_only_told():
    from platform_core.interview.models import Extraction
    from platform_core.website.ai_provider import _fit, _inline_schema

    schema = _inline_schema(Extraction.model_json_schema())
    raw = {
        "facts": [{"field": "offerings", "quote": "sofas"}]
        + [{"field": "description", "quote": ""}]  # empty quote: dropped, not fatal
        + [{"quote": "no field"}]  # missing a required field: dropped
        + [{"field": "phone", "quote": str(n), "confidence": "high"} for n in range(30)],
        "surprise": "a key the schema never declared",
    }
    fitted = _fit(raw, schema)
    assert "surprise" not in fitted
    assert len(fitted["facts"]) == 20 and fitted["facts"][0]["quote"] == "sofas"
    assert all("confidence" not in fact for fact in fitted["facts"])
    Extraction.model_validate(fitted)


async def test_an_overlong_answer_is_trimmed_to_the_declared_limit(monkeypatch):
    long_quote = "q" * 5000
    body = {"candidates": [{"content": {"parts": [{"text": json.dumps(
        {"facts": [{"field": "description", "quote": long_quote}]})}]}}]}
    script = Script(httpx.Response(200, json=body))
    monkeypatch.setattr(ai_provider.httpx, "AsyncClient", script.client)
    from platform_core.interview.models import Extraction

    raw = await GeminiProvider("k").generate_structured(
        "p", Extraction.model_json_schema(), {"purpose": "business.interview"}, 12)
    assert len(raw["facts"][0]["quote"]) == 4000
    Extraction.model_validate(raw)  # the platform's own validation still passes


def test_a_field_named_like_a_keyword_is_kept():
    """Live 400: "features.items requires unspecified property 'title'"."""
    from platform_core.interview.design_strategy import WebsitePlan
    from platform_core.website.ai_provider import _gemini_schema

    def check(node):
        if isinstance(node, dict):
            props = node.get("properties") or {}
            for name in node.get("required") or []:
                assert name in props, name
            for value in node.values():
                check(value)
        elif isinstance(node, list):
            for item in node:
                check(item)

    schema = _gemini_schema(WebsitePlan.model_json_schema())
    check(schema)
    feature = schema["properties"]["copy"]["properties"]["features"]["items"]
    assert "title" in feature["properties"]
