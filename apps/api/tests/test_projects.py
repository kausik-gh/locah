"""Projects and work orders.

The behaviour worth holding still is not "a row can be written" — it is that a
project is the same thing whatever trade runs it, that its lifecycle cannot be
walked backwards, and that converting an accepted quote twice does not produce
two jobs.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, cast

import jwt
import pytest
from fastapi.testclient import TestClient
from platform_api.main import app
from platform_core.db import get_database_url
from platform_testing.db_helpers import ensure_auth_user
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

TEST_JWT_SECRET = "super-secret-jwt-token-with-at-least-32-characters-long"
pytestmark = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")


def _headers(user_id: uuid.UUID, email: str) -> dict[str, str]:
    token = jwt.encode(
        {
            "sub": str(user_id),
            "email": email,
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
        TEST_JWT_SECRET,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def _seed(user_id: uuid.UUID, email: str) -> None:
    async def _run() -> None:
        url = get_database_url()
        assert url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(url, echo=False, poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            await ensure_auth_user(session, user_id, email)
            await session.commit()
        await engine.dispose()

    asyncio.run(_run())


@pytest.fixture
def owner(monkeypatch: Any) -> dict[str, str]:
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    user_id = uuid.uuid4()
    email = f"{user_id}@example.com"
    _seed(user_id, email)
    return _headers(user_id, email)


@pytest.fixture
def stranger(monkeypatch: Any) -> dict[str, str]:
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    user_id = uuid.uuid4()
    email = f"{user_id}@example.com"
    _seed(user_id, email)
    return _headers(user_id, email)


def _business(
    client: TestClient, headers: dict[str, str], business_type: str = "professional_service"
) -> str:
    resp = client.post(
        "/v1/platform/businesses",
        json={
            "display_name": f"ProjectCo {uuid.uuid4().hex[:8]}",
            "business_type": business_type,
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    business_id = cast(str, resp.json()["data"]["business"]["id"])
    for mid in ("projects", "quotes", "customer-relationships", "workforce"):
        enabled = client.post(f"/v1/b/{business_id}/modules/{mid}/enable", headers=headers)
        assert enabled.status_code == 200, f"{mid}: {enabled.text}"
    return business_id


def _project(
    client: TestClient, headers: dict[str, str], business_id: str, **over: Any
) -> dict[str, Any]:
    body: dict[str, Any] = {"title": "Ground floor refit"}
    body.update(over)
    resp = client.post(
        f"/v1/platform/businesses/{business_id}/projects", json=body, headers=headers
    )
    assert resp.status_code == 200, resp.text
    return cast(dict[str, Any], resp.json()["data"])


# ------------------------------------------------------------ business type


def test_starting_stages_come_from_the_business_type(owner: dict[str, str]) -> None:
    """A clinic opens a case at Assessment; a studio opens a project at Brief.

    The service never branches on business type — this is the profile reaching
    the data, and it is the whole reason Projects is one capability rather than
    one per trade.
    """
    client = TestClient(app)

    clinic = _business(client, owner, business_type="clinic")
    case = _project(client, owner, clinic, title="Root canal — Mr Raman")
    assert [p["name"] for p in case["phases"]] == ["Assessment", "Treatment", "Review"]

    studio = _business(client, owner, business_type="studio")
    shoot = _project(client, owner, studio, title="Autumn lookbook")
    assert [p["name"] for p in shoot["phases"]] == ["Brief", "Shoot", "Edit", "Delivery"]

    listing = client.get(f"/v1/platform/businesses/{clinic}/projects", headers=owner)
    assert listing.status_code == 200
    assert listing.json()["data"]["semantics"]["noun"] == "Case"


def test_an_explicit_empty_phase_list_means_no_stages(owner: dict[str, str]) -> None:
    """A one-visit job is a real shape, not a project missing its stages."""
    client = TestClient(app)
    business_id = _business(client, owner)
    project = _project(client, owner, business_id, phases=[])
    assert project["phases"] == []


# ---------------------------------------------------------------- lifecycle


def test_a_project_walks_forward_only(owner: dict[str, str]) -> None:
    client = TestClient(app)
    business_id = _business(client, owner)
    project = _project(client, owner, business_id)
    base = f"/v1/platform/businesses/{business_id}/projects/{project['id']}"

    assert project["status"] == "draft"
    assert project["reference"].startswith("P-")

    for target in ("active", "on_hold", "active", "completed"):
        resp = client.post(f"{base}/status", json={"status": target}, headers=owner)
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["status"] == target

    body = client.get(base, headers=owner).json()["data"]
    assert body["completed_at"]
    assert body["is_open"] is False

    # Nothing comes back from completed.
    for target in ("active", "draft", "on_hold"):
        resp = client.post(f"{base}/status", json={"status": target}, headers=owner)
        assert resp.status_code == 422, f"{target}: {resp.text}"
        assert resp.json()["error"]["details"]["code"] == "invalid_transition"


def test_a_closed_project_cannot_be_edited_or_restaffed(owner: dict[str, str]) -> None:
    """A finished project is a record of what happened, not a working document."""
    client = TestClient(app)
    business_id = _business(client, owner)
    project = _project(client, owner, business_id)
    base = f"/v1/platform/businesses/{business_id}/projects/{project['id']}"

    client.post(f"{base}/status", json={"status": "active"}, headers=owner)
    client.post(f"{base}/tasks", json={"title": "Strip the old units"}, headers=owner)
    client.post(f"{base}/status", json={"status": "completed"}, headers=owner)

    edited = client.patch(base, json={"title": "Something else"}, headers=owner)
    assert edited.status_code == 422
    assert edited.json()["error"]["details"]["code"] == "project_closed"

    task_added = client.post(f"{base}/tasks", json={"title": "One more thing"}, headers=owner)
    assert task_added.status_code == 422
    assert task_added.json()["error"]["details"]["code"] == "project_closed"


def test_cancelling_records_the_reason(owner: dict[str, str]) -> None:
    client = TestClient(app)
    business_id = _business(client, owner)
    project = _project(client, owner, business_id)
    base = f"/v1/platform/businesses/{business_id}/projects/{project['id']}"
    resp = client.post(
        f"{base}/status",
        json={"status": "cancelled", "reason": "Customer went elsewhere"},
        headers=owner,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["status"] == "cancelled"
    assert data["cancellation_reason"] == "Customer went elsewhere"
    assert data["cancelled_at"]


# --------------------------------------------------------- tasks and phases


def test_progress_counts_finished_work_and_ignores_cancelled(owner: dict[str, str]) -> None:
    """An empty project is not finished, and a cancelled task is not work."""
    client = TestClient(app)
    business_id = _business(client, owner)
    project = _project(client, owner, business_id)
    base = f"/v1/platform/businesses/{business_id}/projects/{project['id']}"

    assert project["progress_percent"] is None

    for title in ("Strip out", "First fix", "Second fix", "Snagging"):
        assert (
            client.post(f"{base}/tasks", json={"title": title}, headers=owner).status_code == 200
        )
    detail = client.get(base, headers=owner).json()["data"]
    assert detail["task_count"] == 4
    assert detail["progress_percent"] == 0

    tasks = detail["tasks"]
    client.patch(f"{base}/tasks/{tasks[0]['id']}", json={"status": "done"}, headers=owner)
    client.patch(f"{base}/tasks/{tasks[1]['id']}", json={"status": "cancelled"}, headers=owner)

    detail = client.get(base, headers=owner).json()["data"]
    # Three tasks count; one is done.
    assert detail["task_count"] == 3
    assert detail["tasks_done"] == 1
    assert detail["progress_percent"] == 33

    listing = client.get(
        f"/v1/platform/businesses/{business_id}/projects", headers=owner
    ).json()["data"]["projects"]
    row = next(p for p in listing if p["id"] == project["id"])
    assert row["progress_percent"] == 33


def test_a_task_cannot_be_assigned_to_another_business_workforce(
    owner: dict[str, str], stranger: dict[str, str]
) -> None:
    """Assignment reuses the workforce module, and tenancy still holds."""
    client = TestClient(app)
    mine = _business(client, owner)
    theirs = _business(client, stranger)

    member = client.post(
        f"/v1/platform/businesses/{theirs}/workforce/members",
        json={"display_name": "Someone Else"},
        headers=stranger,
    )
    assert member.status_code == 200, member.text
    foreign_member_id = member.json()["data"]["id"]

    project = _project(client, owner, mine)
    resp = client.post(
        f"/v1/platform/businesses/{mine}/projects/{project['id']}/tasks",
        json={"title": "Wire the kitchen", "assignee_member_id": foreign_member_id},
        headers=owner,
    )
    assert resp.status_code == 404, resp.text


def test_completing_a_phase_is_recorded_once(owner: dict[str, str]) -> None:
    client = TestClient(app)
    business_id = _business(client, owner)
    project = _project(client, owner, business_id)
    base = f"/v1/platform/businesses/{business_id}/projects/{project['id']}"
    phase_id = project["phases"][0]["id"]

    done = client.patch(f"{base}/phases/{phase_id}", json={"status": "done"}, headers=owner)
    assert done.status_code == 200, done.text
    phase = next(p for p in done.json()["data"]["phases"] if p["id"] == phase_id)
    assert phase["status"] == "done"
    assert phase["completed_at"]

    # Reopening clears the completion rather than leaving a stale timestamp.
    reopened = client.patch(
        f"{base}/phases/{phase_id}", json={"status": "in_progress"}, headers=owner
    )
    phase = next(p for p in reopened.json()["data"]["phases"] if p["id"] == phase_id)
    assert phase["completed_at"] is None


def test_a_stale_task_edit_is_refused(owner: dict[str, str]) -> None:
    client = TestClient(app)
    business_id = _business(client, owner)
    project = _project(client, owner, business_id)
    base = f"/v1/platform/businesses/{business_id}/projects/{project['id']}"

    created = client.post(f"{base}/tasks", json={"title": "Measure up"}, headers=owner)
    task = created.json()["data"]["tasks"][0]
    assert task["version"] == 1

    first = client.patch(
        f"{base}/tasks/{task['id']}", json={"status": "in_progress", "version": 1}, headers=owner
    )
    assert first.status_code == 200, first.text

    stale = client.patch(
        f"{base}/tasks/{task['id']}", json={"status": "done", "version": 1}, headers=owner
    )
    assert stale.status_code == 409, stale.text


# ------------------------------------------------------------- conversion


def _accepted_quote(client: TestClient, headers: dict[str, str], business_id: str) -> dict[str, Any]:
    quote = client.post(
        f"/v1/platform/businesses/{business_id}/quotes",
        json={
            "title": "Kitchen refit",
            "items": [{"title": "Labour", "quantity": 1, "unit_price": 50000, "tax_rate": 18}],
        },
        headers=headers,
    ).json()["data"]
    client.post(
        f"/v1/platform/businesses/{business_id}/quotes/{quote['id']}/issue",
        json={},
        headers=headers,
    )
    decided = client.post(
        f"/v1/platform/businesses/{business_id}/quotes/{quote['id']}/decision",
        json={"decision": "accepted"},
        headers=headers,
    )
    assert decided.status_code == 200, decided.text
    return cast(dict[str, Any], decided.json()["data"])


def test_an_accepted_quote_becomes_a_project_once(owner: dict[str, str]) -> None:
    """Converting twice returns the same project — the button is safe to hit."""
    client = TestClient(app)
    business_id = _business(client, owner)
    quote = _accepted_quote(client, owner, business_id)
    url = f"/v1/platform/businesses/{business_id}/quotes/{quote['id']}/convert-to-project"

    first = client.post(url, json={}, headers=owner)
    assert first.status_code == 200, first.text
    project = first.json()["data"]
    assert project["source_quote_id"] == quote["id"]
    # A reporting snapshot of what was agreed; the quote stays authoritative.
    assert project["agreed_value"] == quote["total"]
    assert project["title"] == "Kitchen refit"

    second = client.post(url, json={}, headers=owner)
    assert second.status_code == 200, second.text
    assert second.json()["data"]["id"] == project["id"]

    listing = client.get(
        f"/v1/platform/businesses/{business_id}/projects", headers=owner
    ).json()["data"]["projects"]
    assert len([p for p in listing if p["source_quote_id"] == quote["id"]]) == 1

    # And the quote now knows what became of it.
    back = client.get(
        f"/v1/platform/businesses/{business_id}/quotes/{quote['id']}", headers=owner
    ).json()["data"]
    assert back["converted_to_type"] == "project"
    assert back["converted_to_id"] == project["id"]


def test_only_an_accepted_quote_converts(owner: dict[str, str]) -> None:
    client = TestClient(app)
    business_id = _business(client, owner)
    draft = client.post(
        f"/v1/platform/businesses/{business_id}/quotes",
        json={"title": "Maybe", "items": [{"title": "Work", "quantity": 1, "unit_price": 100}]},
        headers=owner,
    ).json()["data"]

    resp = client.post(
        f"/v1/platform/businesses/{business_id}/quotes/{draft['id']}/convert-to-project",
        json={},
        headers=owner,
    )
    assert resp.status_code == 422, resp.text
    assert resp.json()["error"]["details"]["code"] == "quote_not_accepted"


# ---------------------------------------------------- isolation and access


def test_projects_are_tenant_isolated(owner: dict[str, str], stranger: dict[str, str]) -> None:
    client = TestClient(app)
    mine = _business(client, owner)
    project = _project(client, owner, mine)

    seen = client.get(
        f"/v1/platform/businesses/{mine}/projects/{project['id']}", headers=stranger
    )
    assert seen.status_code in (403, 404), seen.text

    listed = client.get(f"/v1/platform/businesses/{mine}/projects", headers=stranger)
    assert listed.status_code in (403, 404), listed.text


def test_project_endpoints_require_authentication(owner: dict[str, str]) -> None:
    client = TestClient(app)
    business_id = _business(client, owner)
    project = _project(client, owner, business_id)
    assert client.get(f"/v1/platform/businesses/{business_id}/projects").status_code == 401
    assert (
        client.get(
            f"/v1/platform/businesses/{business_id}/projects/{project['id']}"
        ).status_code
        == 401
    )


def test_projects_are_gated_on_the_module(owner: dict[str, str]) -> None:
    """A business that has not enabled Projects gets the module gate, not a list."""
    client = TestClient(app)
    resp = client.post(
        "/v1/platform/businesses",
        json={"display_name": f"NoProjects {uuid.uuid4().hex[:8]}", "business_type": "retail"},
        headers=owner,
    )
    business_id = resp.json()["data"]["business"]["id"]

    listed = client.get(f"/v1/platform/businesses/{business_id}/projects", headers=owner)
    assert listed.status_code in (403, 422), listed.text
    assert listed.json()["error"]["code"] in ("MODULE_NOT_ACTIVE", "ENTITLEMENT_REQUIRED")
