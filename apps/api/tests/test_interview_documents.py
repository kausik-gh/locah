"""The owner's own menu / catalogue — read once, confirmed by the owner, never invented.

Pure tests cover governance (a price needs a number; unclear lines are
flagged, not guessed) and applying accepted lines. The database test runs the
real interview actions and the real worker function, with only the file
download and the model stubbed at their boundary (a replay recording keyed
by the file's sha256).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import uuid
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from platform_api.main import app
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from platform_core.interview import documents
from platform_core.interview.models import BusinessBlueprint, TurnIntelligence
from platform_core.website.replay_provider import ReplayProvider
from platform_testing.phase_b import db_url, sql
from test_start_conversation import owner  # noqa: F401 — the signed-in owner fixture
from test_website_conversation import Talk

MENU = {
    "kind": "menu",
    "groups": [
        {"name": "Tiffin", "items": [
            {"name": "Idli", "price": "40", "unit": "2 pcs", "attributes": "veg"},
            {"name": "Idli", "price": "40"},  # printed twice: one line
            {"name": "Ghee Roast Dosa", "price": "₹ ??", "confidence": "high"},  # unreadable price
            {"name": "Kothu Parotta", "price": "90", "confidence": "low"},
        ]},
        {"name": "Podi & Pickles", "items": [{"name": "Idli Podi", "price": "120", "unit": "200 g"}]},
    ],
    "phone": "98401 23456",
    "hours": "7 am – 10 pm",
}
FILE = b"%PDF-1.4 a home kitchen's menu"


def _read() -> tuple[str, list[Any], dict[str, str]]:
    return asyncio.run(_read_async())


async def _read_async() -> tuple[str, list[Any], dict[str, str]]:
    result: tuple[str, list[Any], dict[str, str]] = await documents.read(
        FILE, "application/pdf", provider=_replay())
    return result


def _replay(tmp: Path | None = None) -> ReplayProvider:
    path = (tmp or Path(os.getenv("TMPDIR", "/tmp"))) / f"menu-{uuid.uuid4().hex}.json"
    path.write_text(json.dumps({"document:" + hashlib.sha256(FILE).hexdigest(): MENU}), encoding="utf-8")
    return ReplayProvider(str(path))


def test_nothing_is_invented_and_unclear_lines_are_flagged() -> None:
    kind, groups, facts = _read()
    assert kind == "menu"
    tiffin = {i.name: i for i in groups[0].items}
    assert list(tiffin) == ["Idli", "Ghee Roast Dosa", "Kothu Parotta"]
    assert tiffin["Idli"].price == "40" and tiffin["Idli"].confidence == "high"
    # A price that was printed but unreadable is dropped and the line flagged — never guessed.
    assert tiffin["Ghee Roast Dosa"].price == "" and tiffin["Ghee Roast Dosa"].confidence == "low"
    assert tiffin["Kothu Parotta"].confidence == "low"
    assert facts == {"phone": "98401 23456", "hours": "7 am – 10 pm"}


def test_only_accepted_lines_reach_the_catalogue() -> None:
    bp = BusinessBlueprint(business_id=uuid.uuid4())
    doc_id = uuid.uuid4()
    with pytest.raises(ValueError):
        documents.apply(bp, doc_id, [])  # never read
    assert documents.begin(bp, doc_id) and not documents.begin(bp, doc_id)  # idempotent
    _, groups, facts = _read()
    bp.documents[0].status, bp.documents[0].groups, bp.documents[0].facts = "ready", groups, facts
    touched = documents.apply(bp, doc_id, [documents.line_key("Tiffin", "Idli"),
                                           documents.line_key("Podi & Pickles", "Idli Podi")])
    assert touched == ["Tiffin", "Podi & Pickles"]
    items = {i.name: i for g in bp.taxonomy.groups for i in g.items}
    assert set(items) == {"Idli", "Idli Podi"}  # the unticked low-confidence lines stay out
    assert items["Idli Podi"].price == "120" and items["Idli Podi"].unit == "200 g"
    assert items["Idli"].source == "document" and items["Idli"].attributes == "veg"
    assert bp.documents[0].status == "applied"
    # The phone printed on the menu is shown to confirm — never applied silently.
    assert "phone" not in bp.known_facts


def test_saying_i_have_a_menu_asks_for_the_file() -> None:
    from platform_core.interview.orchestrator import _contextual_signals, _record_media_intent

    bp = BusinessBlueprint(business_id=uuid.uuid4())
    ti = TurnIntelligence()
    _contextual_signals(bp, ti, "Yes, we have a printed menu with all our prices")
    assert ti.media_intent == "will_upload_catalogue"
    assert "📎" in _record_media_intent(bp, ti.media_intent, True)


# ------------------------------------------------------------ the owner path

pytestmark_db = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL required")


def _upload(business_id: str, owner_id: str | None = None) -> str:
    asset = str(uuid.uuid4())
    sql("insert into media_assets (id, business_id, mime_type, bucket, storage_key, purpose, status, size_bytes) "
        "values (:id, :b, 'application/pdf', 'owner-documents', :k, 'document', 'ready', 20)",
        id=asset, b=business_id, k=f"{owner_id or 'someone'}/{business_id}/{asset}.pdf")
    return asset


def _worker(business_id: str, asset_id: str) -> str:
    async def _go() -> str:
        engine = create_async_engine(db_url(), echo=False, poolclass=NullPool)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        try:
            async with factory() as session:
                async def fetch(key: str) -> bytes:
                    assert key.endswith(f"{asset_id}.pdf")
                    return FILE

                outcome: str = await documents.read_owner_document(
                    session, business_id=uuid.UUID(business_id), asset_id=uuid.UUID(asset_id),
                    fetch=fetch, provider=_replay())
                await session.commit()
                return outcome
        finally:
            await engine.dispose()

    return asyncio.run(_go())


@pytestmark_db
def test_the_owner_attaches_a_menu_checks_it_and_it_becomes_their_catalogue(owner) -> None:  # noqa: F811
    with TestClient(app) as client:
        started = client.post("/v1/platform/businesses/start", headers=owner, json={
            "category_key": "home_food", "subcategory_key": "home_bakery"}).json()["data"]
        business_id = started["business"]["id"]
        headers = {**owner, "X-Business-Id": business_id, "X-Operating-Context": "business"}
        talk = Talk(client, headers, business_id)
        asset = _upload(business_id)

        data = talk.send("document", document_id=asset)
        assert data["blueprint"]["documents"][0]["status"] == "reading"
        jobs = sql("select count(*) from platform_async_jobs where job_type = 'interview.read_document' "
                   "and business_id = :b", b=business_id)[0][0]
        assert jobs == 1
        talk.send("document", document_id=asset)  # sent twice: read once
        assert sql("select count(*) from platform_async_jobs where job_type = 'interview.read_document' "
                   "and business_id = :b", b=business_id)[0][0] == 1

        assert _worker(business_id, asset) == "ready"
        doc = client.get(f"/v1/b/{business_id}/interview", headers=headers).json()["data"]["blueprint"][
            "documents"][0]
        assert doc["status"] == "ready" and doc["groups"][0]["name"] == "Tiffin"

        talk.revision = client.get(f"/v1/b/{business_id}/interview", headers=headers).json()["data"][
            "blueprint"]["revision"]
        data = talk.send("document_apply", document_id=asset, accept=["Tiffin::Idli", "Podi & Pickles::Idli Podi"])
        items = {i["name"]: i for g in data["blueprint"]["taxonomy"]["groups"] for i in g["items"]}
        assert items["Idli Podi"]["price"] == "120" and items["Idli"]["source"] == "document"
        assert "Kothu Parotta" not in items


@pytestmark_db
def test_another_business_cannot_have_this_file_read(owner) -> None:  # noqa: F811
    with TestClient(app) as client:
        ids = []
        for _ in range(2):
            started = client.post("/v1/platform/businesses/start", headers=owner, json={
                "category_key": "home_food", "subcategory_key": "home_bakery"}).json()["data"]
            ids.append(started["business"]["id"])
            # An untouched draft is reused by /start: say something so the next one is new.
            Talk(client, {**owner, "X-Business-Id": ids[-1], "X-Operating-Context": "business"}, ids[-1]).say(
                "We bake cakes and cookies at home.")
        assert ids[0] != ids[1]
        theirs = _upload(ids[0])
        headers = {**owner, "X-Business-Id": ids[1], "X-Operating-Context": "business"}
        talk = Talk(client, headers, ids[1])
        res = client.post(f"/v1/b/{ids[1]}/interview", headers=headers, json={
            "revision": talk.revision, "request_id": str(uuid.uuid4()), "action": "document",
            "document_id": theirs})
        assert res.status_code in {400, 404, 422}, res.text
        # A plain website picture is not a document either.
        picture = str(uuid.uuid4())
        sql("insert into media_assets (id, business_id, mime_type, bucket, storage_key, purpose, status) "
            "values (:id, :b, 'image/png', 'media', :k, 'website', 'ready')", id=picture, b=ids[1], k=f"x/{picture}")
        res = client.post(f"/v1/b/{ids[1]}/interview", headers=headers, json={
            "revision": talk.revision, "request_id": str(uuid.uuid4()), "action": "document",
            "document_id": picture})
        assert res.status_code in {400, 422}, res.text
