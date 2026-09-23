from __future__ import annotations

import pytest

from platform_testing.database_guard import configure_test_database


REMOTE = "postgresql://postgres:secret@db.example.test:5432/postgres"
TEST_REMOTE = "postgresql://postgres:secret@test-db.example.test:5432/postgres"


def test_remote_runtime_database_is_rejected() -> None:
    with pytest.raises(RuntimeError, match="TEST_DATABASE_URL"):
        configure_test_database({"DATABASE_URL": REMOTE})


def test_remote_test_database_must_not_equal_runtime_database() -> None:
    with pytest.raises(RuntimeError, match="identical"):
        configure_test_database({"DATABASE_URL": REMOTE, "TEST_DATABASE_URL": REMOTE})


def test_equivalent_async_driver_url_is_still_rejected() -> None:
    async_url = REMOTE.replace("postgresql://", "postgresql+asyncpg://")
    with pytest.raises(RuntimeError, match="identical"):
        configure_test_database({"DATABASE_URL": REMOTE, "TEST_DATABASE_URL": async_url})


def test_same_supabase_project_is_rejected_across_direct_and_pooler_urls() -> None:
    direct = "postgresql://postgres:secret@db.projectref.supabase.co:5432/postgres"
    pooler = (
        "postgresql://postgres.projectref:secret@aws-0-ap-south-1.pooler.supabase.com:6543/"
        "postgres"
    )
    with pytest.raises(RuntimeError, match="identical"):
        configure_test_database({"DATABASE_URL": direct, "TEST_DATABASE_URL": pooler})


def test_explicit_remote_test_database_replaces_runtime_database() -> None:
    environ = {
        "DATABASE_URL": REMOTE,
        "API_DATABASE_URL": REMOTE,
        "TEST_DATABASE_URL": TEST_REMOTE,
    }

    configure_test_database(environ)

    assert environ["DATABASE_URL"] == TEST_REMOTE
    assert "API_DATABASE_URL" not in environ


def test_local_database_remains_available_without_test_alias() -> None:
    environ = {"DATABASE_URL": "postgresql://postgres:postgres@127.0.0.1:54322/postgres"}

    configure_test_database(environ)

    assert environ["DATABASE_URL"].endswith("/postgres")
