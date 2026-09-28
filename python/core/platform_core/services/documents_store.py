"""Stored rendered documents, each with its SHA-256 (Capability Universe §24 #7).

Rendering the same spec twice yields the same bytes, so storing is idempotent:
a new version is written only when the content actually changed (for example
an invoice that was later cancelled gains a CANCELLED banner).
"""

from __future__ import annotations

import hashlib
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.documents.renderer import DocSpec, render_pdf
from platform_core.exceptions import ResourceNotFound


class DocumentStore:
    @staticmethod
    async def store(
        session: AsyncSession,
        business_id: uuid.UUID,
        *,
        doc_type: str,
        source_type: str,
        source_id: uuid.UUID,
        spec: DocSpec,
        layout: str = "a4",
        actor_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        content = render_pdf(spec, layout)
        digest = hashlib.sha256(content).hexdigest()
        latest = (await session.execute(
            text("""
                SELECT id, version, sha256 FROM rendered_documents
                WHERE business_id = :b AND source_type = :st AND source_id = :sid AND doc_type = :dt
                  AND layout = :l
                ORDER BY version DESC LIMIT 1
            """),
            {"b": str(business_id), "st": source_type, "sid": str(source_id), "dt": doc_type, "l": layout},
        )).first()
        if latest is not None and latest[2] == digest:
            return {"id": str(latest[0]), "version": int(latest[1]), "sha256": digest, "created": False}
        version = (int(latest[1]) + 1) if latest else 1
        new_id = uuid.uuid4()
        await session.execute(
            text("""
                INSERT INTO rendered_documents (id, business_id, doc_type, source_type, source_id, version, layout,
                                                sha256, size_bytes, content, created_by)
                VALUES (:id, :b, :dt, :st, :sid, :v, :l, :h, :n, :c, :u)
            """),
            {"id": str(new_id), "b": str(business_id), "dt": doc_type, "st": source_type, "sid": str(source_id),
             "v": version, "l": layout, "h": digest, "n": len(content), "c": content,
             "u": str(actor_id) if actor_id else None},
        )
        return {"id": str(new_id), "version": version, "sha256": digest, "created": True}

    @staticmethod
    async def fetch(session: AsyncSession, business_id: uuid.UUID, document_id: uuid.UUID) -> tuple[bytes, dict[str, Any]]:
        row = (await session.execute(
            text("""SELECT content, doc_type, source_type, source_id, version, sha256, layout, media_type
                    FROM rendered_documents WHERE business_id = :b AND id = :id"""),
            {"b": str(business_id), "id": str(document_id)},
        )).first()
        if row is None:
            raise ResourceNotFound("Document")
        return bytes(row[0]), {"doc_type": row[1], "source_type": row[2], "source_id": str(row[3]),
                               "version": row[4], "sha256": row[5], "layout": row[6], "media_type": row[7]}

    @staticmethod
    async def latest_for(
        session: AsyncSession, business_id: uuid.UUID, *, source_type: str, source_id: uuid.UUID,
    ) -> list[dict[str, Any]]:
        rows = (await session.execute(
            text("""
                SELECT DISTINCT ON (doc_type, layout) id, doc_type, layout, version, sha256, size_bytes, created_at
                FROM rendered_documents WHERE business_id = :b AND source_type = :st AND source_id = :sid
                ORDER BY doc_type, layout, version DESC
            """),
            {"b": str(business_id), "st": source_type, "sid": str(source_id)},
        )).all()
        return [{"id": str(r[0]), "doc_type": r[1], "layout": r[2], "version": r[3], "sha256": r[4],
                 "size_bytes": r[5], "created_at": r[6].isoformat()} for r in rows]
