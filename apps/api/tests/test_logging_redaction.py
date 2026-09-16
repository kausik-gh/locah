"""AUD-11 — structured logging redaction filter.

The redaction processor must scrub credential- and payment-sensitive values
out of every log line *before* any renderer runs. These tests exercise the
processor directly (no DB, no app) and assert nothing sensitive survives.
"""

from __future__ import annotations

import json

from platform_core.logging import _redact, _redact_value, configure, get_logger


def _run(event_dict: dict) -> dict:
    return _redact(None, "info", event_dict)


def test_credential_keys_are_redacted() -> None:
    out = _run(
        {
            "event": "x",
            "authorization": "Bearer abc.def.ghi",
            "password": "hunter2",
            "jwt_secret": "s3cr3t",
            "webhook_signature": "t=1,v1=deadbeef",
            "api_key": "sk-live-xxx",
            "safe": "keep-me",
        }
    )
    assert out["authorization"] == "***redacted***"
    assert out["password"] == "***redacted***"
    assert out["jwt_secret"] == "***redacted***"
    assert out["webhook_signature"] == "***redacted***"
    assert out["api_key"] == "***redacted***"
    assert out["safe"] == "keep-me"


def test_gemini_api_key_is_redacted() -> None:
    out = _run(
        {
            "event": "website.generate",
            "GEMINI_API_KEY": "AIzaSyEXAMPLE",
            "gemini_api_key": "AIzaSyEXAMPLE",
            "model_config": {"gemini": "AIzaSyEXAMPLE", "purpose": "website.generate"},
        }
    )
    assert out["GEMINI_API_KEY"] == "***redacted***"
    assert out["gemini_api_key"] == "***redacted***"
    assert out["model_config"]["gemini"] == "***redacted***"
    assert out["model_config"]["purpose"] == "website.generate"


def test_supabase_service_role_key_is_redacted() -> None:
    out = _run(
        {
            "event": "config",
            "SUPABASE_SERVICE_ROLE_KEY": "eyJ...service_role...",
            "service_role_key": "eyJ...",
            "service_key": "abc",
            "supabase_anon_key": "eyJ...anon...",  # public — must NOT be touched
        }
    )
    assert out["SUPABASE_SERVICE_ROLE_KEY"] == "***redacted***"
    assert out["service_role_key"] == "***redacted***"
    assert out["service_key"] == "***redacted***"
    assert out["supabase_anon_key"] == "eyJ...anon..."


def test_redaction_is_recursive_through_dicts_and_lists() -> None:
    out = _run(
        {
            "event": "webhook",
            "raw_payload": {"amount": 500},
            "body": {"card": {"pan": "4111111111111111"}, "amount": 500},
            "items": [{"token": "abc"}, {"qty": 2}],
        }
    )
    assert out["raw_payload"] == "***redacted***"  # whole subtree gone by key
    assert out["body"]["card"] == "***redacted***"  # nested credential key
    assert out["body"]["amount"] == 500
    assert out["items"][0]["token"] == "***redacted***"
    assert out["items"][1]["qty"] == 2


def test_nested_secret_under_safe_parent_still_redacted() -> None:
    out = _run({"event": "x", "context": {"access_token": "abc", "user": "u1"}})
    assert out["context"]["access_token"] == "***redacted***"
    assert out["context"]["user"] == "u1"


def test_value_helper_passes_through_non_sensitive() -> None:
    assert _redact_value("count", 3) == 3
    assert _redact_value("business_id", "uuid-here") == "uuid-here"


def test_redaction_processor_runs_before_the_renderer() -> None:
    """`_redact` must sit ahead of any renderer in the configured chain, so a
    sensitive value can never reach stdout."""
    import structlog

    configure()
    processors = structlog.get_config()["processors"]
    names = [getattr(p, "__name__", type(p).__name__) for p in processors]
    assert "_redact" in names
    # the renderer is the last processor; redaction is strictly before it
    assert names.index("_redact") < len(names) - 1
    assert names[-1] in {"JSONRenderer", "ConsoleRenderer"}


def test_full_chain_serializes_with_secrets_scrubbed() -> None:
    import structlog

    configure()
    chain = structlog.get_config()["processors"]
    event_dict: dict = {
        "event": "payment_webhook.signature_rejected",
        "provider": "stripe",
        "signature": "v1=abcd",
        "level": "warning",
    }
    for proc in chain:
        event_dict = proc(get_logger("t"), "warning", event_dict)
    parsed = json.loads(event_dict) if isinstance(event_dict, str) else event_dict
    assert parsed["provider"] == "stripe"
    assert parsed["signature"] == "***redacted***"
