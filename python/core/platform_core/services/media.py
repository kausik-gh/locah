"""Media asset service (Doc 12 §15).

Two-step upload, so the API never touches binary content:

    request_upload()  -> validates, pre-creates a `pending` media_assets row,
                         returns a signed upload URL
    (client PUTs the bytes straight to Supabase Storage)
    complete_upload() -> verifies the object landed, flips the row to `ready`
                         and records its public URL

**Permission model.** There is no `media.*` permission in the canonical First
Launch catalogue (Doc 12 §8.2), and inventing one would be a registry change.
Instead an upload declares a `purpose`, and each purpose maps to the permission
that already governs the thing the asset is for — the same shape as the AUD-10
payment-source fix. Adding a purpose without a permission raises, rather than
silently falling open.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.exceptions import ResourceNotFound, ValidationError
from platform_core.media.supabase_storage import (
    ALLOWED_MIME_TYPES,
    EXTENSION_BY_MIME,
    MAX_FILE_BYTES,
    create_signed_upload_url,
    object_exists,
    public_url,
)
from platform_core.models import MediaAsset
from platform_core.permissions import BUSINESS_UPDATE, OFFERINGS_UPDATE, WEBSITE_EDIT
from platform_core.services.audit import AuditService

# purpose -> the existing canonical permission that already governs it
PURPOSE_PERMISSIONS: dict[str, str] = {
    "website": WEBSITE_EDIT,
    "brand": BUSINESS_UPDATE,
    "profile": BUSINESS_UPDATE,
    "offering": OFFERINGS_UPDATE,
}
PURPOSES = frozenset(PURPOSE_PERMISSIONS)


def _field_error(field: str, message: str) -> dict[str, str]:
    return {"field": field, "message": message}


class MediaService:
    @staticmethod
    def permission_for(purpose: str) -> str:
        permission = PURPOSE_PERMISSIONS.get(purpose)
        if permission is None:
            raise ValidationError(
                "Unknown upload purpose",
                details={"errors": [_field_error("purpose", "Not a supported purpose")]},
            )
        return permission

    @staticmethod
    async def request_upload(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        identity_id: uuid.UUID,
        supabase_user_id: uuid.UUID,
        user_jwt: str,
        purpose: str,
        mime_type: str,
        size_bytes: int | None = None,
        original_filename: str | None = None,
        alt_text: str | None = None,
    ) -> dict[str, Any]:
        MediaService.permission_for(purpose)

        normalized_mime = (mime_type or "").strip().lower()
        if normalized_mime not in ALLOWED_MIME_TYPES:
            raise ValidationError(
                "Unsupported file type",
                details={
                    "errors": [
                        _field_error(
                            "mime_type", "Only JPEG, PNG, WebP and GIF images are accepted"
                        )
                    ]
                },
            )
        if size_bytes is not None and size_bytes > MAX_FILE_BYTES:
            raise ValidationError(
                "File is too large",
                details={"errors": [_field_error("size_bytes", "Maximum size is 10MB")]},
            )

        asset_id = uuid.uuid4()
        extension = EXTENSION_BY_MIME[normalized_mime]
        # Storage RLS scopes writes to the caller's own uid prefix.
        storage_key = f"{supabase_user_id}/{asset_id}.{extension}"

        asset = MediaAsset(
            id=asset_id,
            business_id=business_id,
            uploader_identity_id=identity_id,
            original_filename=(original_filename or None),
            mime_type=normalized_mime,
            size_bytes=size_bytes,
            bucket="media",
            storage_key=storage_key,
            alt_text=(alt_text or None),
            purpose=purpose,
            status="pending",
        )
        session.add(asset)
        await session.flush()

        signed = await create_signed_upload_url(
            user_jwt=user_jwt, bucket="media", storage_key=storage_key
        )
        return {"asset": MediaService.serialize(asset), "upload": signed}

    @staticmethod
    async def complete_upload(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        asset_id: uuid.UUID,
        actor_id: uuid.UUID,
    ) -> dict[str, Any]:
        asset = await MediaService._get(session, business_id=business_id, asset_id=asset_id)
        if asset.status == "ready":
            return MediaService.serialize(asset)

        size = await object_exists(bucket=asset.bucket, storage_key=asset.storage_key)
        if size is None:
            # Commit before raising: the router commits *after* a successful
            # call, so without this the rollback would leave the asset stuck
            # on `pending` forever. `failed` is not terminal — asking again
            # after a genuine upload re-checks and can still succeed.
            asset.status = "failed"
            await session.commit()
            raise ValidationError(
                "Upload did not complete",
                details={"errors": [_field_error("asset_id", "No stored object for this asset")]},
            )

        asset.status = "ready"
        asset.size_bytes = size or asset.size_bytes
        asset.public_url = public_url(asset.bucket, asset.storage_key)
        asset.updated_at = datetime.now(timezone.utc)
        await session.flush()

        await AuditService.record(
            session,
            event_type="media.asset_uploaded",
            actor_identity_id=actor_id,
            actor_context="business",
            business_id=business_id,
            resource_type="media_asset",
            resource_id=asset.id,
            action="upload",
            after_state={
                "purpose": asset.purpose,
                "mime_type": asset.mime_type,
                "size_bytes": asset.size_bytes,
            },
        )
        return MediaService.serialize(asset)

    @staticmethod
    async def _get(
        session: AsyncSession, *, business_id: uuid.UUID, asset_id: uuid.UUID
    ) -> MediaAsset:
        result = await session.execute(
            select(MediaAsset).where(
                MediaAsset.id == asset_id,
                MediaAsset.business_id == business_id,
                MediaAsset.deleted_at.is_(None),
            )
        )
        asset = result.scalars().first()
        if asset is None:
            raise ResourceNotFound("Media asset")
        return asset

    @staticmethod
    async def get(
        session: AsyncSession, *, business_id: uuid.UUID, asset_id: uuid.UUID
    ) -> dict[str, Any]:
        return MediaService.serialize(
            await MediaService._get(session, business_id=business_id, asset_id=asset_id)
        )

    @staticmethod
    async def list_for_business(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        purpose: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        stmt = select(MediaAsset).where(
            MediaAsset.business_id == business_id,
            MediaAsset.deleted_at.is_(None),
            MediaAsset.status == "ready",
        )
        if purpose:
            stmt = stmt.where(MediaAsset.purpose == purpose)
        stmt = stmt.order_by(MediaAsset.created_at.desc()).limit(min(limit, 200))
        result = await session.execute(stmt)
        return [MediaService.serialize(a) for a in result.scalars().all()]

    # Asset ids in section content resolve to URLs OUTSIDE `content`. Injecting
    # a url into content would break the next PATCH round-trip, because
    # validate_section_content rejects fields absent from the SectionType schema.
    ASSET_CONTENT_KEYS = ("image_asset_id", "og_image_asset_id", "logo_asset_id")

    @staticmethod
    async def attach_section_asset_urls(
        session: AsyncSession,
        sections: list[dict[str, Any]],
        *,
        business_id: uuid.UUID | None = None,
    ) -> list[dict[str, Any]]:
        """Add `section["assets"] = {content_key: url}` for any asset id present.

        `business_id` scopes resolution so one Business cannot surface another's
        asset by writing its id into a section.
        """
        wanted: set[uuid.UUID] = set()
        for section in sections:
            content = section.get("content") or {}
            for key in MediaService.ASSET_CONTENT_KEYS:
                raw = content.get(key)
                if not raw:
                    continue
                try:
                    wanted.add(uuid.UUID(str(raw)))
                except ValueError:
                    continue
        if not wanted:
            return sections

        stmt = select(MediaAsset).where(
            MediaAsset.id.in_(wanted),
            MediaAsset.status == "ready",
            MediaAsset.deleted_at.is_(None),
        )
        if business_id is not None:
            # A section may only resolve its own Business's assets.
            stmt = stmt.where(MediaAsset.business_id == business_id)
        result = await session.execute(stmt)
        by_id = {str(a.id): a for a in result.scalars().all()}
        for section in sections:
            content = section.get("content") or {}
            resolved: dict[str, Any] = {}
            for key in MediaService.ASSET_CONTENT_KEYS:
                asset = by_id.get(str(content.get(key) or ""))
                if asset is not None and asset.public_url:
                    resolved[key] = {"url": asset.public_url, "alt_text": asset.alt_text}
            if resolved:
                section["assets"] = resolved
        return sections

    @staticmethod
    def serialize(asset: MediaAsset) -> dict[str, Any]:
        return {
            "id": str(asset.id),
            "business_id": str(asset.business_id) if asset.business_id else None,
            "purpose": asset.purpose,
            "mime_type": asset.mime_type,
            "size_bytes": asset.size_bytes,
            "alt_text": asset.alt_text,
            "width": asset.width,
            "height": asset.height,
            "status": asset.status,
            "url": asset.public_url,
            "created_at": asset.created_at.isoformat() if asset.created_at else None,
        }
