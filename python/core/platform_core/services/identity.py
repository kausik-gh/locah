import uuid
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.models import ConsumerProfile, PlatformAdminGrant, PlatformIdentity


class IdentityService:
    @staticmethod
    async def get_by_supabase_id(
        session: AsyncSession, supabase_user_id: uuid.UUID
    ) -> Optional[PlatformIdentity]:
        result = await session.execute(
            select(PlatformIdentity).where(PlatformIdentity.supabase_user_id == supabase_user_id)
        )
        return result.scalars().first()

    @staticmethod
    async def get_by_id(
        session: AsyncSession, identity_id: uuid.UUID
    ) -> Optional[PlatformIdentity]:
        result = await session.execute(
            select(PlatformIdentity).where(PlatformIdentity.id == identity_id)
        )
        return result.scalars().first()

    @staticmethod
    async def get_by_email(session: AsyncSession, email: str) -> Optional[PlatformIdentity]:
        normalized = email.strip().lower()
        result = await session.execute(
            select(PlatformIdentity).where(PlatformIdentity.email.ilike(normalized))
        )
        return result.scalars().first()

    @staticmethod
    async def bootstrap_identity(
        session: AsyncSession,
        supabase_user_id: uuid.UUID,
        email: str,
        display_name: str | None = None,
    ) -> PlatformIdentity:
        existing = await IdentityService.get_by_supabase_id(session, supabase_user_id)
        if existing:
            return existing

        name = display_name or email.split("@")[0]
        identity = PlatformIdentity(
            id=supabase_user_id,
            supabase_user_id=supabase_user_id,
            email=email,
            display_name=name,
        )
        session.add(identity)
        await session.flush()

        consumer = ConsumerProfile(identity_id=identity.id)
        session.add(consumer)
        await session.flush()
        return identity

    @staticmethod
    async def update_profile(
        session: AsyncSession,
        supabase_user_id: uuid.UUID,
        display_name: Optional[str] = None,
        avatar_url: Optional[str] = None,
    ) -> Optional[PlatformIdentity]:
        identity = await IdentityService.get_by_supabase_id(session, supabase_user_id)
        if not identity:
            return None
        if display_name is not None:
            identity.display_name = display_name
        if avatar_url is not None:
            identity.avatar_url = avatar_url
        await session.flush()
        return identity

    @staticmethod
    async def is_super_admin(session: AsyncSession, identity_id: uuid.UUID) -> bool:
        result = await session.execute(
            select(PlatformAdminGrant).where(
                PlatformAdminGrant.identity_id == identity_id,
                PlatformAdminGrant.revoked_at.is_(None),
            )
        )
        return result.scalars().first() is not None

    @staticmethod
    async def get_consumer_preferences(
        session: AsyncSession, identity_id: uuid.UUID
    ) -> dict[str, Any]:
        result = await session.execute(
            select(ConsumerProfile).where(ConsumerProfile.identity_id == identity_id)
        )
        profile = result.scalars().first()
        if profile is None:
            return {}
        return dict(profile.preferences or {})

    @staticmethod
    async def _ensure_consumer_profile(
        session: AsyncSession, identity_id: uuid.UUID
    ) -> ConsumerProfile:
        result = await session.execute(
            select(ConsumerProfile).where(ConsumerProfile.identity_id == identity_id)
        )
        profile = result.scalars().first()
        if profile is None:
            profile = ConsumerProfile(identity_id=identity_id, preferences={})
            session.add(profile)
            await session.flush()
        return profile

    @staticmethod
    def _parse_pref_uuid(prefs: dict[str, Any], key: str) -> uuid.UUID | None:
        value = prefs.get(key)
        if not value:
            return None
        try:
            return uuid.UUID(str(value))
        except ValueError:
            return None

    @staticmethod
    async def get_default_business_id(
        session: AsyncSession, identity_id: uuid.UUID
    ) -> uuid.UUID | None:
        prefs = await IdentityService.get_consumer_preferences(session, identity_id)
        return IdentityService._parse_pref_uuid(prefs, "default_business_id")

    @staticmethod
    async def get_last_business_id(
        session: AsyncSession, identity_id: uuid.UUID
    ) -> uuid.UUID | None:
        prefs = await IdentityService.get_consumer_preferences(session, identity_id)
        return IdentityService._parse_pref_uuid(prefs, "last_business_id")

    @staticmethod
    async def get_primary_business_id(
        session: AsyncSession, identity_id: uuid.UUID
    ) -> uuid.UUID | None:
        prefs = await IdentityService.get_consumer_preferences(session, identity_id)
        return IdentityService._parse_pref_uuid(prefs, "primary_business_id")

    @staticmethod
    async def get_remembered_business_id(
        session: AsyncSession, identity_id: uuid.UUID
    ) -> uuid.UUID | None:
        """Restore order for Business context: default → last → none (Doc 05 / Stage 2B)."""
        default_id = await IdentityService.get_default_business_id(session, identity_id)
        if default_id is not None:
            return default_id
        return await IdentityService.get_last_business_id(session, identity_id)

    @staticmethod
    async def update_business_context_preferences(
        session: AsyncSession,
        *,
        identity_id: uuid.UUID,
        last_business_id: uuid.UUID | None = None,
        default_business_id: uuid.UUID | None = None,
        set_primary_if_absent: bool = False,
        primary_business_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        """
        Update remembered Business preferences.

        primary_business_id is immutable once set unless set_primary_if_absent
        and no primary exists yet (first Business creation).
        """
        profile = await IdentityService._ensure_consumer_profile(session, identity_id)
        prefs = dict(profile.preferences or {})
        if last_business_id is not None:
            prefs["last_business_id"] = str(last_business_id)
        if default_business_id is not None:
            prefs["default_business_id"] = str(default_business_id)
        if set_primary_if_absent and primary_business_id is not None:
            if not prefs.get("primary_business_id"):
                prefs["primary_business_id"] = str(primary_business_id)
        profile.preferences = prefs
        await session.flush()
        return prefs

    # Legacy aliases for Stage 1C /me routes
    get_profile_by_auth_user_id = get_by_supabase_id

    @staticmethod
    async def create_profile(
        session: AsyncSession, auth_user_id: uuid.UUID, email: str, display_name: str
    ) -> PlatformIdentity:
        return await IdentityService.bootstrap_identity(session, auth_user_id, email, display_name)
