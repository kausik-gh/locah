"""Stage 6 — Leads Kernel tests (Doc 11 §10.2)."""

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
from platform_core.models import PlatformAuditEvent, PlatformOutboxEvent
from platform_testing.db_helpers import ensure_auth_user
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

TEST_JWT_SECRET = "super-secret-jwt-token-with-at-least-32-characters-long"


def _token(sub: uuid.UUID, email: str) -> str:
    return jwt.encode(
        {"sub": str(sub), "email": email, "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        TEST_JWT_SECRET,
        algorithm="HS256",
    )


def _headers(user_id: uuid.UUID, email: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {_token(user_id, email)}"}


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
def owner(monkeypatch: Any) -> tuple[dict[str, str], uuid.UUID]:
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    user_id = uuid.uuid4()
    email = f"{user_id}@example.com"
    _seed(user_id, email)
    return _headers(user_id, email), user_id


def _create_business(client: TestClient, headers: dict[str, str]) -> str:
    resp = client.post(
        "/v1/platform/businesses",
        json={"display_name": f"Leads Co {uuid.uuid4().hex[:8]}", "business_type": "professional_service"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    business_id = cast(str, resp.json()["data"]["business"]["id"])
    for module_id in ("leads", "customer-relationships"):
        enabled = client.post(
            f"/v1/b/{business_id}/modules/{module_id}/enable", headers=headers
        )
        assert enabled.status_code == 200, enabled.text
    return business_id


def _create_lead(client: TestClient, headers: dict[str, str], business_id: str, **over: Any) -> dict[str, Any]:
    body = {
        "display_name": f"Prospect {uuid.uuid4().hex[:6]}",
        "email": f"{uuid.uuid4().hex[:8]}@example.com",
        "message": "Interested in your services",
        "source": "website_enquiry",
        **over,
    }
    resp = client.post(
        f"/v1/platform/businesses/{business_id}/leads", json=body, headers=headers
    )
    assert resp.status_code == 200, resp.text
    return cast(dict[str, Any], resp.json()["data"])


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_lead_capture_pipeline_and_notes(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    client = TestClient(app)
    bid = _create_business(client, headers)

    lead = _create_lead(client, headers, bid, offering_id=None)
    assert lead["status"] == "new"
    assert lead["source"] == "website_enquiry"
    lead_id = lead["id"]

    # New → Contacted → Qualified
    for target in ("contacted", "qualified"):
        moved = client.post(
            f"/v1/platform/businesses/{bid}/leads/{lead_id}/move-stage",
            json={"status": target},
            headers=headers,
        )
        assert moved.status_code == 200, moved.text
        assert moved.json()["data"]["status"] == target

    # A note
    note = client.post(
        f"/v1/platform/businesses/{bid}/leads/{lead_id}/notes",
        json={"body": "Left a voicemail"},
        headers=headers,
    )
    assert note.status_code == 200, note.text

    detail = client.get(
        f"/v1/platform/businesses/{bid}/leads/{lead_id}", headers=headers
    )
    assert detail.status_code == 200
    data = detail.json()["data"]
    assert len(data["status_history"]) == 3  # new + contacted + qualified
    assert len(data["notes"]) == 1

    pipeline = client.get(
        f"/v1/platform/businesses/{bid}/leads", headers=headers
    ).json()["meta"]["pipeline"]
    assert pipeline["qualified"] == 1


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_lead_won_creates_customer_contact(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    client = TestClient(app)
    bid = _create_business(client, headers)
    lead = _create_lead(client, headers, bid)
    lead_id = lead["id"]
    lead_email = lead["email"]

    won = client.post(
        f"/v1/platform/businesses/{bid}/leads/{lead_id}/move-stage",
        json={"status": "won"},
        headers=headers,
    )
    assert won.status_code == 200, won.text
    contact_id = won.json()["data"]["customer_contact_id"]
    assert contact_id is not None

    # The lead is retained (still visible), and the contact exists with the lead email.
    still_there = client.get(
        f"/v1/platform/businesses/{bid}/leads/{lead_id}", headers=headers
    )
    assert still_there.status_code == 200
    assert still_there.json()["data"]["status"] == "won"

    contacts = client.get(
        f"/v1/platform/businesses/{bid}/customers", headers=headers
    ).json()["data"]
    assert any(c["id"] == contact_id and c["email"] == lead_email for c in contacts)

    # A won lead is terminal — no further transitions.
    reopen = client.post(
        f"/v1/platform/businesses/{bid}/leads/{lead_id}/move-stage",
        json={"status": "contacted"},
        headers=headers,
    )
    assert reopen.status_code == 409, reopen.text


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_lead_lost_requires_reason_and_can_reopen(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    client = TestClient(app)
    bid = _create_business(client, headers)
    lead_id = _create_lead(client, headers, bid)["id"]

    no_reason = client.post(
        f"/v1/platform/businesses/{bid}/leads/{lead_id}/move-stage",
        json={"status": "lost"},
        headers=headers,
    )
    assert no_reason.status_code == 422, no_reason.text

    lost = client.post(
        f"/v1/platform/businesses/{bid}/leads/{lead_id}/move-stage",
        json={"status": "lost", "reason": "Budget mismatch"},
        headers=headers,
    )
    assert lost.status_code == 200, lost.text
    assert lost.json()["data"]["lost_reason"] == "Budget mismatch"

    reopen = client.post(
        f"/v1/platform/businesses/{bid}/leads/{lead_id}/move-stage",
        json={"status": "contacted"},
        headers=headers,
    )
    assert reopen.status_code == 200, reopen.text


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_lead_assign_and_filter(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, owner_id = owner
    client = TestClient(app)
    bid = _create_business(client, headers)
    a = _create_lead(client, headers, bid)["id"]
    _create_lead(client, headers, bid)

    assigned = client.post(
        f"/v1/platform/businesses/{bid}/leads/{a}/assign",
        json={"assignee_identity_id": str(owner_id)},
        headers=headers,
    )
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["data"]["assignee_identity_id"] == str(owner_id)

    mine = client.get(
        f"/v1/platform/businesses/{bid}/leads?assignee_identity_id={owner_id}",
        headers=headers,
    )
    assert mine.status_code == 200
    assert {row["id"] for row in mine.json()["data"]} == {a}


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_leads_module_gate_and_isolation(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    client = TestClient(app)

    # A business with leads not enabled is gated.
    ungated = client.post(
        "/v1/platform/businesses",
        json={"display_name": f"NoLeads {uuid.uuid4().hex[:6]}", "business_type": "retail"},
        headers=headers,
    ).json()["data"]["business"]["id"]
    blocked = client.get(f"/v1/platform/businesses/{ungated}/leads", headers=headers)
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "MODULE_NOT_ACTIVE"

    # Cross-tenant read is refused.
    other_id = uuid.uuid4()
    other_email = f"{other_id}@example.com"
    _seed(other_id, other_email)
    other_headers = _headers(other_id, other_email)
    bid = _create_business(client, headers)
    lead_id = _create_lead(client, headers, bid)["id"]
    leaked = client.get(
        f"/v1/platform/businesses/{bid}/leads/{lead_id}", headers=other_headers
    )
    assert leaked.status_code in (403, 404)


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_lead_audit_and_outbox(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    headers, _ = owner
    client = TestClient(app)
    bid = _create_business(client, headers)
    lead_id = _create_lead(client, headers, bid)["id"]
    client.post(
        f"/v1/platform/businesses/{bid}/leads/{lead_id}/move-stage",
        json={"status": "contacted"},
        headers=headers,
    )

    async def _check() -> tuple[int, int]:
        url = get_database_url()
        assert url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(url, echo=False, poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            audits = (
                await session.execute(
                    select(PlatformAuditEvent).where(
                        PlatformAuditEvent.business_id == uuid.UUID(bid),
                        PlatformAuditEvent.resource_type == "lead",
                    )
                )
            ).scalars().all()
            outbox = (
                await session.execute(
                    select(PlatformOutboxEvent).where(
                        PlatformOutboxEvent.business_id == uuid.UUID(bid),
                        PlatformOutboxEvent.event_type.like("lead.%"),
                    )
                )
            ).scalars().all()
        await engine.dispose()
        return len(audits), len(outbox)

    n_audit, n_outbox = asyncio.run(_check())
    assert n_audit >= 2  # create + contacted
    assert n_outbox >= 2
