"""Test-suite wiring for LOCAH_TEST_NO_EXTERNAL_AI.

`enable_no_external_ai(environ)` turns the switch on for the whole session and
installs the httpx backstop. The two fixtures below are registered by each
suite's conftest:

* `no_paid_ai_calls` (autouse) fails any test that attempted a paid AI call —
  the call itself was already refused before it left the process;
* `stubbed_ai_transport` is for the few unit tests that replace a provider's
  HTTP client with a stub to check how requests are built and replies parsed.
"""

from __future__ import annotations

from collections.abc import Iterator, MutableMapping

import pytest

from platform_core.ai_guard import (
    ENV,
    blocked_calls,
    install_transport_guard,
    reset_blocked_calls,
    stubbed_transport_only,
)


def enable_no_external_ai(environ: MutableMapping[str, str]) -> None:
    environ[ENV] = "1"
    install_transport_guard()


@pytest.fixture(autouse=True)
def no_paid_ai_calls() -> Iterator[None]:
    reset_blocked_calls()
    yield
    attempts = blocked_calls()
    reset_blocked_calls()
    if attempts:
        listed = ", ".join(f"{a.kind} via {a.provider} ({a.purpose or '-'})" for a in attempts)
        pytest.fail(
            f"{len(attempts)} paid AI call(s) attempted and blocked by {ENV}: {listed}. "
            "Stub the provider (or use the stubbed_ai_transport fixture with a stub client).",
            pytrace=False,
        )


@pytest.fixture
def stubbed_ai_transport() -> Iterator[None]:
    with stubbed_transport_only():
        yield
