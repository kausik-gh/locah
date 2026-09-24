"""Doc 12 §15 — media upload foundation.

Covers the pure validation/permission surface plus one end-to-end request that
stubs Supabase Storage. No test ever makes a live storage call.
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
from platform_core.exceptions import ValidationError
from platform_core.models import MediaAsset
from platform_core.permissions import BUSINESS_UPDATE, OFFERINGS_UPDATE, WEBSITE_EDIT
from platform_core.services.media import PURPOSE_PERMISSIONS, MediaService
from platform_testing.db_helpers import ensure_auth_user
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

TEST_JWT_SECRET = "super-secret-jwt-token-with-at-least-32-characters-long"


def _token(sub: uuid.UUID, email: str) -> str:
    return jwt.encode(
        {
            "sub": str(sub),
            "email": email,
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
        TEST_JWT_SECRET,
        algorithm="HS256",
    )


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
    return {"Authorization": f"Bearer {_token(user_id, email)}"}, user_id


def _create_business(client: TestClient, headers: dict[str, str]) -> str:
    resp = client.post(
        "/v1/platform/businesses",
        json={"display_name": f"Media Co {uuid.uuid4().hex[:8]}", "business_type": "cafe"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    return cast(str, resp.json()["data"]["business"]["id"])


# --------------------------------------------------------------- pure surface


def test_purpose_maps_to_existing_canonical_permissions() -> None:
    """No `media.*` identifier is invented — every purpose reuses a permission
    that already exists in the Doc 12 §8.2 catalogue."""
    assert PURPOSE_PERMISSIONS == {
        "website": WEBSITE_EDIT,
        "brand": BUSINESS_UPDATE,
        "profile": BUSINESS_UPDATE,
        "offering": OFFERINGS_UPDATE,
    }
    assert MediaService.permission_for("website") == WEBSITE_EDIT
    assert MediaService.permission_for("offering") == OFFERINGS_UPDATE


def test_unknown_purpose_is_rejected_not_defaulted() -> None:
    with pytest.raises(ValidationError):
        MediaService.permission_for("anything_else")


@pytest.mark.asyncio
async def test_disallowed_mime_types_rejected() -> None:
    # SVG is excluded on purpose (XSS), PDF is deferred — Doc 12 §15.4.
    for bad in ("image/svg+xml", "application/pdf", "text/html", ""):
        with pytest.raises(ValidationError):
            await MediaService.request_upload(
                cast(Any, None),
                business_id=uuid.uuid4(),
                identity_id=uuid.uuid4(),
                supabase_user_id=uuid.uuid4(),
                user_jwt="x",
                purpose="website",
                mime_type=bad,
            )


@pytest.mark.asyncio
async def test_oversized_file_rejected() -> None:
    with pytest.raises(ValidationError):
        await MediaService.request_upload(
            cast(Any, None),
            business_id=uuid.uuid4(),
            identity_id=uuid.uuid4(),
            supabase_user_id=uuid.uuid4(),
            user_jwt="x",
            purpose="website",
            mime_type="image/png",
            size_bytes=10 * 1024 * 1024 + 1,
        )


# ----------------------------------------------------------- url resolution


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_asset_urls_attach_beside_content_never_inside_it(
    owner: tuple[dict[str, str], uuid.UUID],
) -> None:
    """`content` is schema-validated on write, so a resolved URL must not be
    injected into it — otherwise the next PATCH round-trip fails."""
    headers, _ = owner
    client = TestClient(app)
    business_id = uuid.UUID(_create_business(client, headers))

    async def _run() -> list[dict[str, Any]]:
        url = get_database_url()
        assert url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(url, echo=False, poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            ready = MediaAsset(
                business_id=business_id,
                mime_type="image/png",
                bucket="media",
                storage_key=f"{uuid.uuid4()}/{uuid.uuid4()}.png",
                public_url="https://example.supabase.co/storage/v1/object/public/media/x.png",
                alt_text="A cup of coffee",
                purpose="website",
                status="ready",
            )
            pending = MediaAsset(
                business_id=business_id,
                mime_type="image/png",
                bucket="media",
                storage_key=f"{uuid.uuid4()}/{uuid.uuid4()}.png",
                public_url="https://example.supabase.co/storage/v1/object/public/media/y.png",
                purpose="website",
                status="pending",
            )
            session.add_all([ready, pending])
            await session.flush()
            await session.commit()

            sections = [
                {"id": "s1", "content": {"headline": "Hi", "image_asset_id": str(ready.id)}},
                {"id": "s2", "content": {"headline": "Nope", "image_asset_id": str(pending.id)}},
                {"id": "s3", "content": {"headline": "No image"}},
            ]
            await MediaService.attach_section_asset_urls(
                session, sections, business_id=business_id
            )
        await engine.dispose()
        return sections

    sections = asyncio.run(_run())

    resolved = sections[0]
    assert resolved["assets"]["image_asset_id"]["url"].endswith("/x.png")
    assert resolved["assets"]["image_asset_id"]["alt_text"] == "A cup of coffee"
    # the critical invariant
    assert "image_url" not in resolved["content"]
    assert set(resolved["content"]) == {"headline", "image_asset_id"}

    # a pending (not yet confirmed) upload must not surface
    assert "assets" not in sections[1]
    assert "assets" not in sections[2]


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_asset_resolution_is_tenant_scoped(owner: tuple[dict[str, str], uuid.UUID]) -> None:
    """One Business must not surface another's asset by writing its id into a
    section's content."""
    headers, _ = owner
    client = TestClient(app)
    mine = uuid.UUID(_create_business(client, headers))
    theirs = uuid.UUID(_create_business(client, headers))

    async def _run() -> list[dict[str, Any]]:
        url = get_database_url()
        assert url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(url, echo=False, poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            foreign = MediaAsset(
                business_id=theirs,
                mime_type="image/png",
                bucket="media",
                storage_key=f"{uuid.uuid4()}/{uuid.uuid4()}.png",
                public_url="https://example.supabase.co/storage/v1/object/public/media/z.png",
                purpose="website",
                status="ready",
            )
            session.add(foreign)
            await session.flush()
            await session.commit()

            sections = [{"id": "s1", "content": {"image_asset_id": str(foreign.id)}}]
            await MediaService.attach_section_asset_urls(session, sections, business_id=mine)
        await engine.dispose()
        return sections

    sections = asyncio.run(_run())
    assert "assets" not in sections[0]


# ------------------------------------------------------------- API surface


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_upload_url_endpoint_returns_signed_url_and_pending_asset(
    owner: tuple[dict[str, str], uuid.UUID], monkeypatch: Any
) -> None:
    import platform_core.services.media as media_mod

    async def _fake_sign(**kwargs: Any) -> dict[str, Any]:
        return {
            "upload_url": "https://example.supabase.co/storage/v1/object/upload/sign/media/k",
            "storage_key": kwargs["storage_key"],
            "bucket": kwargs["bucket"],
        }

    monkeypatch.setattr(media_mod, "create_signed_upload_url", _fake_sign)

    headers, _ = owner
    client = TestClient(app)
    business_id = _create_business(client, headers)

    resp = client.post(
        f"/v1/b/{business_id}/media/upload-url",
        json={"purpose": "website", "mime_type": "image/png", "size_bytes": 1234},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["asset"]["status"] == "pending"
    assert data["asset"]["purpose"] == "website"
    assert data["upload"]["upload_url"].startswith("https://")
    # path is scoped to the caller's own uid prefix, which storage RLS enforces
    assert data["upload"]["storage_key"].endswith(".png")


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_upload_url_rejects_svg_at_the_api_boundary(
    owner: tuple[dict[str, str], uuid.UUID],
) -> None:
    headers, _ = owner
    client = TestClient(app)
    business_id = _create_business(client, headers)

    resp = client.post(
        f"/v1/b/{business_id}/media/upload-url",
        json={"purpose": "website", "mime_type": "image/svg+xml"},
        headers=headers,
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_complete_marks_failed_when_object_absent(
    owner: tuple[dict[str, str], uuid.UUID], monkeypatch: Any
) -> None:
    import platform_core.services.media as media_mod

    async def _fake_sign(**kwargs: Any) -> dict[str, Any]:
        return {"upload_url": "https://x/y", "storage_key": kwargs["storage_key"], "bucket": "media"}

    async def _absent(**_: Any) -> int | None:
        return None

    monkeypatch.setattr(media_mod, "create_signed_upload_url", _fake_sign)
    monkeypatch.setattr(media_mod, "object_exists", _absent)

    headers, _ = owner
    client = TestClient(app)
    business_id = _create_business(client, headers)

    started = client.post(
        f"/v1/b/{business_id}/media/upload-url",
        json={"purpose": "website", "mime_type": "image/png"},
        headers=headers,
    )
    assert started.status_code == 200, started.text
    asset_id = started.json()["data"]["asset"]["id"]

    done = client.post(
        f"/v1/b/{business_id}/media/{asset_id}/complete", headers=headers
    )
    assert done.status_code == 422, done.text

    async def _status() -> str:
        url = get_database_url()
        assert url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(url, echo=False, poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            row = await session.execute(
                select(MediaAsset).where(MediaAsset.id == uuid.UUID(asset_id))
            )
            asset = row.scalars().first()
            assert asset is not None
            value = asset.status
        await engine.dispose()
        return str(value)

    assert asyncio.run(_status()) == "failed"


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")
def test_upload_denied_without_the_purpose_permission(
    owner: tuple[dict[str, str], uuid.UUID],
) -> None:
    """A member of another Business must not be able to upload here — the gate
    is the same `resolve_business_actor` chain every other route uses."""
    headers, _ = owner
    client = TestClient(app)
    business_id = _create_business(client, headers)

    stranger_id = uuid.uuid4()
    stranger_email = f"{stranger_id}@example.com"
    _seed(stranger_id, stranger_email)
    stranger_headers = {"Authorization": f"Bearer {_token(stranger_id, stranger_email)}"}

    resp = client.post(
        f"/v1/b/{business_id}/media/upload-url",
        json={"purpose": "website", "mime_type": "image/png"},
        headers=stranger_headers,
    )
    assert resp.status_code in (403, 404), resp.text
