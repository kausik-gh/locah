"""Documents acceptance on a disposable local PostgreSQL database, never hosted."""

from __future__ import annotations

import os
import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator
from urllib.parse import urlparse

# The request-context binder uses API_DATABASE_URL to enable platform_api RLS.
os.environ.setdefault("API_DATABASE_URL", os.environ.get("DATABASE_URL", ""))

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from platform_core.exceptions import ConflictError, ResourceNotFound, ValidationError
from platform_core.services.document_workflows import DocumentWorkflows


def _url() -> str:
    url = os.environ.get("DATABASE_URL", "")
    if not url or urlparse(url.replace("postgresql+asyncpg://", "postgresql://")).hostname not in {
        "localhost", "127.0.0.1"
    }:
        pytest.fail("Documents tests require disposable local PostgreSQL DATABASE_URL")
    return url.replace("postgresql://", "postgresql+asyncpg://", 1)


@asynccontextmanager
async def _case() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(_url(), poolclass=NullPool)
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False)
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()
    await engine.dispose()


async def _identity(session: AsyncSession) -> uuid.UUID:
    identity = uuid.uuid4()
    await session.execute(text("INSERT INTO auth.users (id,email) VALUES (:id,:email)"),
                          {"id": identity, "email": f"docs-{identity}@example.test"})
    return identity


async def _business(session: AsyncSession, owner: uuid.UUID) -> tuple[uuid.UUID, str]:
    business = uuid.uuid4()
    slug = f"docs-{business.hex}"
    await session.execute(text("""INSERT INTO businesses
        (id,slug,display_name,primary_owner_identity_id,state)
        VALUES (:id,:slug,'Documents fixture',:owner,'active')"""),
        {"id": business, "slug": slug, "owner": owner})
    return business, slug


async def _merchant(session: AsyncSession, business: uuid.UUID, identity: uuid.UUID) -> None:
    await session.execute(text("SET LOCAL ROLE platform_api"))
    await session.execute(text("SELECT set_config('app.current_business_id',:bid,true)"),
                          {"bid": str(business)})
    await session.execute(text("SELECT set_config('app.current_identity_id',:id,true)"),
                          {"id": str(identity)})


def _fields() -> list[dict[str, object]]:
    return [
        {"key": "full_name", "type": "text", "label": "Full name", "required": True},
        {"key": "age", "type": "number", "label": "Age", "required": True},
        {"key": "consent", "type": "consent", "label": "I consent", "required": True},
        {"key": "signature", "type": "signature", "label": "Signature", "required": True},
    ]


@pytest.mark.asyncio
async def test_template_form_version_submission_signature_and_rls() -> None:
    async with _case() as session:
        owner = await _identity(session)
        business, slug = await _business(session, owner)
        other, _ = await _business(session, owner)
        await _merchant(session, business, owner)
        correlation = str(uuid.uuid4())
        template = await DocumentWorkflows.create_template(session, business_id=business,
            kind="consent", title="Safety consent", description="For studio visits", traits={"minor": True},
            content={"sections": [{"heading": "Terms", "body": "I understand the activity."}]},
            actor_id=owner, correlation_id=correlation)
        assert template["kind"] == "consent"
        assert len(await DocumentWorkflows.list_templates(session, business)) == 1
        form = await DocumentWorkflows.create_form(session, business_id=business,
            title="Studio intake", kind="intake", fields=_fields(),
            consent_text="I agree to the terms", guardian_required=True,
            actor_id=owner, correlation_id=correlation)
        request = await DocumentWorkflows.create_request(session, business_id=business,
            request_type="form", title="Please complete intake", form_id=uuid.UUID(form["id"]),
            related_type="general", related_id=None, customer_contact_id=None, days_valid=7,
            actor_id=owner, correlation_id=correlation)
        assert request["token"] not in str(await DocumentWorkflows.list_requests(session, business))
        newer = await DocumentWorkflows.version_form(session, business_id=business,
            form_id=uuid.UUID(form["id"]), fields=_fields() + [
                {"key": "colour", "type": "select", "label": "Colour", "options": ["Blue", "Green"]}],
            consent_text="New wording", guardian_required=False,
            actor_id=owner, correlation_id=correlation)
        assert newer["version"] == 2
        public = await DocumentWorkflows.public_view(session, slug, request["token"])
        assert public["form"]["version"] == 1
        assert len(public["form"]["fields"]) == 4
        with pytest.raises(ValidationError):
            await DocumentWorkflows.submit(session, slug=slug, token=request["token"],
                answers={"full_name": "Asha", "age": 17}, signer_name="Asha",
                signature={"kind": "typed", "value": "Asha"}, age_confirmed=True,
                guardian_relationship="Mother", ip="127.0.0.1", user_agent="test")
        submitted = await DocumentWorkflows.submit(session, slug=slug, token=request["token"],
            answers={"full_name": "Asha", "age": 17, "consent": True},
            signer_name="Asha", signature={"kind": "typed", "value": "Asha"},
            age_confirmed=True, guardian_relationship="Mother",
            ip="127.0.0.1", user_agent="test")
        assert submitted["form_version_id"] == form["version"]["id"]
        # Public token cannot view any other tenant's template or submission.
        assert await session.scalar(text("SELECT count(*) FROM document_templates")) == 0
        assert await session.scalar(text("SELECT count(*) FROM document_submissions")) == 1
        with pytest.raises(ConflictError):
            await DocumentWorkflows.submit(session, slug=slug, token=request["token"],
                answers={}, signer_name="Asha", signature=None, age_confirmed=True,
                guardian_relationship="Mother", ip=None, user_agent=None)
        await _merchant(session, business, owner)
        record = await DocumentWorkflows.submission(session, business, uuid.UUID(submitted["id"]))
        assert record["signature_kind"] == "typed"
        assert record["declared_guardian_relationship"] == "Mother"
        assert record["form_version"] == 1
        assert await session.scalar(text("SELECT has_table_privilege('authenticated','document_submissions','SELECT')")) is False
        # Immutable: platform_api has no UPDATE on signed content.
        with pytest.raises(Exception, match="permission denied"):
            async with session.begin_nested():
                await session.execute(text("UPDATE document_submissions SET signer_name='changed' WHERE id=:id"),
                                      {"id": uuid.UUID(submitted["id"])})
        await session.execute(text("SELECT set_config('app.current_business_id',:bid,true)"),
                              {"bid": str(other)})
        assert await session.scalar(text("SELECT count(*) FROM document_templates")) == 0
        assert await session.scalar(text("SELECT count(*) FROM document_submissions")) == 0


@pytest.mark.asyncio
async def test_drawn_signature_and_token_cannot_open_another_request() -> None:
    async with _case() as session:
        owner = await _identity(session)
        business, slug = await _business(session, owner)
        await _merchant(session, business, owner)
        correlation = str(uuid.uuid4())
        form = await DocumentWorkflows.create_form(session, business_id=business,
            title="Waiver", kind="consent", fields=_fields(), consent_text="Agreement",
            guardian_required=False, actor_id=owner, correlation_id=correlation)
        first = await DocumentWorkflows.create_request(session, business_id=business,
            request_type="form", title="First waiver", form_id=uuid.UUID(form["id"]),
            related_type="general", related_id=None, customer_contact_id=None, days_valid=1,
            actor_id=owner, correlation_id=correlation)
        second = await DocumentWorkflows.create_request(session, business_id=business,
            request_type="form", title="Second waiver", form_id=uuid.UUID(form["id"]),
            related_type="general", related_id=None, customer_contact_id=None, days_valid=1,
            actor_id=owner, correlation_id=correlation)
        result = await DocumentWorkflows.submit(session, slug=slug, token=first["token"],
            answers={"full_name": "Bharat", "age": 28, "consent": True}, signer_name="Bharat",
            signature={"kind": "drawn", "value": [[[0.1, 0.2], [0.4, 0.8], [0.9, 0.2]]]},
            age_confirmed=False, guardian_relationship=None, ip="127.0.0.1", user_agent="test")
        assert result["content_sha256"]
        assert (await DocumentWorkflows.public_view(session, slug, second["token"]))["status"] == "open"
        with pytest.raises(ResourceNotFound):
            await DocumentWorkflows.public_view(session, "wrong-slug", first["token"])
        await _merchant(session, business, owner)
        assert (await DocumentWorkflows.submission(session, business,
                uuid.UUID(result["id"])))["signature_kind"] == "drawn"


@pytest.mark.asyncio
async def test_upload_fulfilment_private_access_hash_and_replay() -> None:
    async with _case() as session:
        owner = await _identity(session)
        business, slug = await _business(session, owner)
        await _merchant(session, business, owner)
        request = await DocumentWorkflows.create_request(session, business_id=business,
            request_type="upload", title="Upload ID", form_id=None,
            related_type="general", related_id=None, customer_contact_id=None,
            days_valid=7, actor_id=owner, correlation_id=str(uuid.uuid4()))
        content = b"%PDF-1.4\nprivate fixture\n%%EOF"
        file = await DocumentWorkflows.upload(session, slug=slug, token=request["token"],
            field_key="requested_file", filename="passport.pdf", content_type="application/pdf",
            content=content, ip="127.0.0.1", user_agent="test")
        assert (await DocumentWorkflows.public_view(session, slug, request["token"]))["status"] == "fulfilled"
        with pytest.raises(ConflictError):
            await DocumentWorkflows.upload(session, slug=slug, token=request["token"],
                field_key="requested_file", filename="passport.pdf", content_type="application/pdf",
                content=content, ip=None, user_agent=None)
        await _merchant(session, business, owner)
        link = await DocumentWorkflows.create_access_link(session, business_id=business,
            file_id=uuid.UUID(file["id"]), actor_id=owner)
        fetched, meta = await DocumentWorkflows.download(session, link["token"])
        assert fetched == content
        assert meta["sha256"] == file["sha256"]
        await session.execute(text("SELECT set_config('app.document_access_token_hash','',true)"))
        await session.execute(text("SELECT set_config('app.document_request_token_hash','',true)"))
        assert await session.scalar(text("SELECT count(*) FROM document_files")) == 0
