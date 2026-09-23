"""Fail-closed database selection for integration tests.

The application legitimately uses ``DATABASE_URL`` in deployed environments.
Tests must not interpret that deployment variable as permission to write to the
same database.  A remote integration database therefore has to be named
explicitly with ``TEST_DATABASE_URL``.
"""

from __future__ import annotations

from collections.abc import MutableMapping
import re
from urllib.parse import urlsplit


_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "postgres", "db"}


def _host(url: str) -> str | None:
    normalized = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return urlsplit(normalized).hostname


def _is_local(url: str) -> bool:
    return _host(url) in _LOCAL_HOSTS


def _identity(url: str) -> tuple[str | None, int, str, str | None]:
    normalized = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    parsed = urlsplit(normalized)
    return parsed.hostname, parsed.port or 5432, parsed.path.rstrip("/"), parsed.username


def _supabase_project_ref(url: str) -> str | None:
    normalized = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    parsed = urlsplit(normalized)
    host_match = re.fullmatch(r"db\.([a-z0-9]+)\.supabase\.co", parsed.hostname or "")
    if host_match:
        return host_match.group(1)
    if parsed.username and "." in parsed.username:
        role, project_ref = parsed.username.rsplit(".", 1)
        if role and re.fullmatch(r"[a-z0-9]+", project_ref):
            return project_ref
    return None


def _same_database(left: str, right: str) -> bool:
    left_ref = _supabase_project_ref(left)
    right_ref = _supabase_project_ref(right)
    if left_ref and right_ref:
        return left_ref == right_ref
    return _identity(left) == _identity(right)


def configure_test_database(environ: MutableMapping[str, str]) -> None:
    """Select an explicit test DB and reject generic remote deployment URLs."""

    test_url = environ.get("TEST_DATABASE_URL", "").strip()
    runtime_url = environ.get("DATABASE_URL", "").strip()

    if test_url:
        if runtime_url and _same_database(test_url, runtime_url) and not _is_local(test_url):
            raise RuntimeError(
                "TEST_DATABASE_URL is identical to the remote DATABASE_URL. "
                "Refusing to run tests against the deployed database."
            )
        environ["DATABASE_URL"] = test_url

        test_api_url = environ.get("TEST_API_DATABASE_URL", "").strip()
        if test_api_url:
            runtime_api_url = environ.get("API_DATABASE_URL", "").strip()
            if (
                runtime_api_url
                and _same_database(test_api_url, runtime_api_url)
                and not _is_local(test_api_url)
            ):
                raise RuntimeError(
                    "TEST_API_DATABASE_URL identifies the deployed API database. "
                    "Refusing to run tests against it."
                )
            environ["API_DATABASE_URL"] = test_api_url
        elif not _is_local(test_url):
            # Never leave a deployed API_DATABASE_URL paired with a dedicated
            # test service connection.
            environ.pop("API_DATABASE_URL", None)
        return

    if runtime_url and not _is_local(runtime_url):
        raise RuntimeError(
            "Refusing to run database-writing tests with a remote DATABASE_URL. "
            "Set TEST_DATABASE_URL to a dedicated test database."
        )

    api_url = environ.get("API_DATABASE_URL", "").strip()
    if api_url and not _is_local(api_url):
        raise RuntimeError(
            "Refusing to run tests with a remote API_DATABASE_URL. "
            "Set TEST_API_DATABASE_URL together with TEST_DATABASE_URL."
        )
