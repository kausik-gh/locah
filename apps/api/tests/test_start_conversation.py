"""POST /v1/platform/businesses/start — Create Business by talking, against a real database.

The owner can start before the business has a name. What must hold:

* an owner who opens "Talk to LOCAH" twice and says nothing gets the SAME
  draft back — no trail of empty businesses;
* the placeholder address follows the real name once the owner says it;
* the kind of business the conversation settles is kept on the Business.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

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


@pytest.fixture
def owner(monkeypatch: Any) -> dict[str, str]:
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    user_id = uuid.uuid4()
    email = f"{user_id}@example.com"

    async def seed() -> None:
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

    asyncio.run(seed())
    token = jwt.encode({"sub": str(user_id), "email": email,
                        "exp": datetime.now(timezone.utc) + timedelta(hours=1)}, TEST_JWT_SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


def turn(client: TestClient, headers: dict[str, str], business_id: str, revision: int, text: str,
         via: str = "text") -> dict[str, Any]:
    res = client.post(f"/v1/b/{business_id}/interview", headers=headers, json={
        "revision": revision, "request_id": str(uuid.uuid4()), "action": "turn", "text": text, "via": via})
    assert res.status_code == 200, res.text
    data: dict[str, Any] = res.json()["data"]
    return data


def test_talking_first_reuses_the_untouched_draft_and_the_address_follows_the_name(owner) -> None:
    with TestClient(app) as client:
        first = client.post("/v1/platform/businesses/start", headers=owner, json={})
        assert first.status_code == 200, first.text
        started = first.json()["data"]
        assert started["created"] is True and started["business"]["slug"].startswith("draft-")
        business_id = started["business"]["id"]

        # Opened again without saying anything: the same draft, not a new one.
        again = client.post("/v1/platform/businesses/start", headers=owner, json={})
        assert again.json()["data"]["created"] is False
        assert again.json()["data"]["business"]["id"] == business_id

        headers = {**owner, "X-Business-Id": business_id, "X-Operating-Context": "business"}
        interview = client.get(f"/v1/b/{business_id}/interview", headers=headers).json()["data"]
        assert interview["blueprint"]["name_pending"] is True
        assert interview["understanding"]["business"]["name_pending"] is True
        assert interview["blueprint"]["messages"][0]["text"].startswith("Tell me about your business")

        # Spoken first answer: the name and the kind are read from it (no model).
        data = turn(client, headers, business_id, interview["blueprint"]["revision"],
                    "Grit Barbell Club is a strength gym in Velachery — powerlifting, strength classes "
                    "and personal training.", via="voice")
        assert data["blueprint"]["name_pending"] is False
        assert data["understanding"]["business"]["name"] == "Grit Barbell Club"
        assert data["understanding"]["business"]["category"]
        assert data["blueprint"]["messages"][-2]["via"] == "voice"

        listed = client.get("/v1/platform/businesses", headers=owner).json()["data"]
        mine = next(b for b in listed if b["id"] == business_id)
        assert mine["display_name"] == "Grit Barbell Club"
        assert mine["slug"].startswith("grit-barbell-club")

        # Now that something was said, "Talk to LOCAH" starts a new business.
        fresh = client.post("/v1/platform/businesses/start", headers=owner, json={})
        assert fresh.json()["data"]["created"] is True
        assert fresh.json()["data"]["business"]["id"] != business_id


def test_category_first_seeds_the_opening(owner) -> None:
    with TestClient(app) as client:
        res = client.post("/v1/platform/businesses/start", headers=owner, json={
            "category_key": "fresh_grocery", "subcategory_key": "meat_shop"})
        business_id = res.json()["data"]["business"]["id"]
        headers = {**owner, "X-Business-Id": business_id, "X-Operating-Context": "business"}
        interview = client.get(f"/v1/b/{business_id}/interview", headers=headers).json()["data"]
        assert interview["blueprint"]["messages"][0]["text"].startswith("Got it — a meat shop.")
        assert interview["understanding"]["business"]["category"] == "Meat shop"
        assert interview["understanding"]["business"]["category_source"] == "owner_picked"
