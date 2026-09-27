import re
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.business_types import (
    DEFAULT_BUSINESS_TYPE,
    DEFAULT_TIMEZONE,
    RESERVED_SLUGS,
)
from platform_core.context import EntitlementSet
from platform_core.exceptions import ConflictError, MembershipRequired, ResourceNotFound, ValidationError
from platform_core.gates import assert_business_switchable
from platform_core.models import (
    Business,
    BusinessLocation,
    BusinessMembership,
    BusinessModuleState,
    BusinessProfile,
    CommercialEntitlement,
)
from platform_core.catalog.modules import storefront_modules
from platform_core.permissions import ALL_PERMISSIONS, PLATFORM_CORE_MODULE_IDS, ROLE_PRIMARY_OWNER
from platform_core.services.audit import AuditService
from platform_core.services.entitlement import EntitlementService, ModuleService
from platform_core.services.identity import IdentityService
from platform_core.services.outbox import OutboxService
from platform_core.services.team import TeamService
from platform_core.validation.business_creation import (
    BusinessCreationInput,
    validate_business_creation_payload,
)


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "business"


def _default_settings(input_data: BusinessCreationInput) -> dict[str, Any]:
    return {
        "timezone": input_data.timezone,
        "currency": input_data.currency,
        "country": input_data.country,
        "language": input_data.language,
        "locale": f"{input_data.language}-{input_data.country}",
        "notifications": {
            "transactional_email": True,
            "transactional_in_app": True,
            "marketing_email": False,
        },
    }


def _default_metadata(input_data: BusinessCreationInput) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "creation": {
            "source": "platform_create_business",
            "business_type": input_data.business_type,
        }
    }
    if input_data.classification:
        # Read by the interview as a seed (BusinessInterviewService.read). The
        # P1 migration moves this to category_key / subcategory_key columns.
        metadata["classification"] = dict(input_data.classification)
    return metadata


class BusinessService:
    @staticmethod
    async def get_by_id(session: AsyncSession, business_id: uuid.UUID) -> Business | None:
        result = await session.execute(
            select(Business).where(Business.id == business_id, Business.deleted_at.is_(None))
        )
        return result.scalars().first()

    @staticmethod
    async def get_profile(
        session: AsyncSession, business_id: uuid.UUID
    ) -> BusinessProfile | None:
        result = await session.execute(
            select(BusinessProfile).where(BusinessProfile.business_id == business_id)
        )
        return result.scalars().first()

    @staticmethod
    async def list_for_identity(session: AsyncSession, identity_id: uuid.UUID) -> list[Business]:
        result = await session.execute(
            select(Business)
            .join(BusinessMembership, BusinessMembership.business_id == Business.id)
            .where(
                BusinessMembership.identity_id == identity_id,
                BusinessMembership.status == "active",
                BusinessMembership.deleted_at.is_(None),
                Business.deleted_at.is_(None),
            )
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_by_slug(session: AsyncSession, slug: str) -> Business | None:
        result = await session.execute(
            select(Business).where(Business.slug == slug, Business.deleted_at.is_(None))
        )
        return result.scalars().first()

    @staticmethod
    async def _allocate_slug(
        session: AsyncSession,
        *,
        display_name: str,
        requested_slug: str | None,
    ) -> str:
        if requested_slug is not None:
            if requested_slug in RESERVED_SLUGS:
                raise ValidationError(
                    "Slug is reserved",
                    details={
                        "errors": [
                            {
                                "field": "slug",
                                "message": f"slug '{requested_slug}' is reserved",
                            }
                        ]
                    },
                )
            if await BusinessService.get_by_slug(session, requested_slug):
                raise ConflictError(
                    "Slug already in use",
                    details={"field": "slug", "slug": requested_slug},
                )
            return requested_slug

        base_slug = slugify(display_name)
        if base_slug in RESERVED_SLUGS:
            base_slug = f"biz-{base_slug}"
        slug = base_slug
        suffix = 1
        while await BusinessService.get_by_slug(session, slug) or slug in RESERVED_SLUGS:
            slug = f"{base_slug}-{suffix}"
            suffix += 1
            if suffix > 1000:
                raise ConflictError("Unable to allocate a unique slug")
        return slug

    @staticmethod
    async def _set_identity_default_business(
        session: AsyncSession,
        *,
        identity_id: uuid.UUID,
        business_id: uuid.UUID,
    ) -> None:
        # First Business: set default + last + primary-if-absent.
        # Subsequent creates: update last + default, never overwrite primary.
        await IdentityService.update_business_context_preferences(
            session,
            identity_id=identity_id,
            last_business_id=business_id,
            default_business_id=business_id,
            set_primary_if_absent=True,
            primary_business_id=business_id,
        )
    @staticmethod
    async def create_business(
        session: AsyncSession,
        *,
        identity_id: uuid.UUID,
        display_name: str | None = None,
        business_type: str | None = None,
        correlation_id: str,
        payload: dict[str, Any] | None = None,
    ) -> tuple[Business, BusinessLocation, BusinessMembership, BusinessProfile]:
        raw: dict[str, Any] = dict(payload or {})
        if display_name is not None and "display_name" not in raw:
            raw["display_name"] = display_name
        if business_type is not None and "business_type" not in raw:
            raw["business_type"] = business_type
        if "business_type" not in raw:
            raw["business_type"] = DEFAULT_BUSINESS_TYPE

        input_data = validate_business_creation_payload(raw)
        slug = await BusinessService._allocate_slug(
            session,
            display_name=input_data.display_name,
            requested_slug=input_data.slug,
        )

        if input_data.logo_asset_id is not None:
            media = await session.execute(
                text("SELECT id FROM media_assets WHERE id = :id AND status <> 'deleted'"),
                {"id": str(input_data.logo_asset_id)},
            )
            if media.first() is None:
                raise ValidationError(
                    "logo_asset_id does not reference an available media asset",
                    details={
                        "errors": [
                            {
                                "field": "logo_asset_id",
                                "message": "logo_asset_id not found",
                            }
                        ]
                    },
                )

        now = datetime.now(timezone.utc)
        settings = _default_settings(input_data)
        metadata = _default_metadata(input_data)

        # The slug check above runs under the owner's row-level security and
        # cannot see anyone else's business, so two owners who both call theirs
        # "Ishant Proteins" used to end in a 500 on the unique index. The index
        # is the authority: on a collision, take the next free address.
        base_slug = slug
        for attempt in range(1, 26):
            business = Business(
                slug=slug,
                display_name=input_data.display_name,
                state="draft",
                primary_owner_identity_id=identity_id,
                business_type=input_data.business_type,
                settings=settings,
                metadata_=metadata,
            )
            try:
                async with session.begin_nested():
                    session.add(business)
                    await session.flush()
                break
            except IntegrityError as exc:
                if "businesses_slug_active_key" not in str(exc.orig):
                    raise
                if input_data.slug is not None:
                    raise ConflictError(
                        "Slug already in use", details={"field": "slug", "slug": input_data.slug}
                    ) from exc
                slug = f"{base_slug}-{attempt}" if attempt < 6 else f"{base_slug}-{uuid.uuid4().hex[:4]}"
        else:
            raise ConflictError("Unable to allocate a unique slug")

        # RLS (AUD-02): bind the tenant GUC now, before creating the child rows
        # (location, membership, profile, modules, website, ...). Their write
        # policies check `business_id = current_business_id()`; without this the
        # INSERTs fail the WITH CHECK. Safe to bind here — the row exists and
        # `primary_owner_identity_id = identity_id`, so the creator owns it.
        from platform_core.context_resolver import bind_session_context

        await bind_session_context(session, identity_id, business.id)

        location = BusinessLocation(
            business_id=business.id,
            name="Primary Location",
            is_primary=True,
            status="active",
            timezone=input_data.timezone or DEFAULT_TIMEZONE,
            address={"country": input_data.country},
        )
        session.add(location)
        await session.flush()

        membership = BusinessMembership(
            business_id=business.id,
            identity_id=identity_id,
            role=ROLE_PRIMARY_OWNER,
            status="active",
            activated_at=now,
        )
        session.add(membership)
        await session.flush()

        profile = BusinessProfile(
            business_id=business.id,
            logo_asset_id=input_data.logo_asset_id,
            contact={},
            social_links={},
            completeness_score=10 if input_data.logo_asset_id else 0,
        )
        session.add(profile)
        await session.flush()

        for module_id in PLATFORM_CORE_MODULE_IDS:
            session.add(
                CommercialEntitlement(
                    business_id=business.id,
                    subject_type="module",
                    subject_id=module_id,
                    source="platform_core",
                    status="active",
                    granted_by=identity_id,
                    reason="Platform Core auto-grant",
                )
            )
            session.add(
                BusinessModuleState(
                    business_id=business.id,
                    module_id=module_id,
                    activation_state="active",
                    enabled_at=now,
                    activated_at=now,
                )
            )
        # Capability Universe §6.1: "Storefront is always on" — every built
        # Storefront module starts active (unbuilt ones join when they ship).
        for module_id in storefront_modules():
            session.add(
                BusinessModuleState(
                    business_id=business.id,
                    module_id=module_id,
                    activation_state="active",
                    enabled_at=now,
                    activated_at=now,
                )
            )
        await session.flush()

        await BusinessService._set_identity_default_business(
            session, identity_id=identity_id, business_id=business.id
        )

        # Capability Universe §4.4: the picked kind is a column, and its default
        # operating traits are seeded (never a module grant).
        picked = input_data.classification or {}
        if picked.get("category_key"):
            from platform_core.catalog.taxonomy import resolve
            from platform_core.services.business_classification import (
                BusinessClassificationService,
            )

            if resolve(picked.get("category_key"), picked.get("subcategory_key") or None):
                await BusinessClassificationService.set_classification(
                    session, business, category_key=picked["category_key"],
                    subcategory_key=picked.get("subcategory_key") or None,
                    actor_id=None, audit=False,
                )

        await OutboxService.publish(
            session,
            event_type="business.created",
            payload={
                "business_id": str(business.id),
                "slug": business.slug,
                "business_type": business.business_type,
                "owner_id": str(identity_id),
            },
            business_id=business.id,
            correlation_id=correlation_id,
        )
        await OutboxService.publish(
            session,
            event_type="membership.created",
            payload={
                "business_id": str(business.id),
                "membership_id": str(membership.id),
                "identity_id": str(identity_id),
                "role": ROLE_PRIMARY_OWNER,
                "status": "active",
            },
            business_id=business.id,
            correlation_id=correlation_id,
        )
        await OutboxService.publish(
            session,
            event_type="business.initialized",
            payload={
                "business_id": str(business.id),
                "primary_location_id": str(location.id),
                "settings": settings,
            },
            business_id=business.id,
            correlation_id=correlation_id,
        )

        await AuditService.record(
            session,
            event_type="business.created",
            actor_identity_id=identity_id,
            actor_context="personal",
            business_id=business.id,
            resource_type="business",
            resource_id=business.id,
            action="create",
            after_state={
                "display_name": input_data.display_name,
                "slug": slug,
                "business_type": input_data.business_type,
            },
        )
        await AuditService.record(
            session,
            event_type="membership.owner_assigned",
            actor_identity_id=identity_id,
            actor_context="personal",
            business_id=business.id,
            resource_type="membership",
            resource_id=membership.id,
            action="assign_owner",
            after_state={
                "role": ROLE_PRIMARY_OWNER,
                "status": "active",
                "identity_id": str(identity_id),
            },
        )
        await AuditService.record(
            session,
            event_type="business.configuration_initialized",
            actor_identity_id=identity_id,
            actor_context="personal",
            business_id=business.id,
            resource_type="business",
            resource_id=business.id,
            action="initialize_defaults",
            after_state={"settings": settings},
        )

        # core-website: provision only the editable shell; no generation or paid calls.
        # Doc 08 §6.4 / Doc 11 §17.2 / Doc 12 §12.1
        from platform_core.services.website import WebsiteService

        await WebsiteService.provision_for_business(
            session, business_id=business.id, actor_id=identity_id
        )
        # Interview/build is an explicit owner action, never a creation side effect.

        return business, location, membership, profile

    @staticmethod
    async def switch_business(
        session: AsyncSession,
        *,
        identity_id: uuid.UUID,
        business_id: uuid.UUID,
        correlation_id: str,
        set_as_default: bool = False,
    ) -> dict[str, Any]:
        business = await BusinessService.get_by_id(session, business_id)
        if not business:
            raise ResourceNotFound("Business")

        # Closed / non-operable states are distinct resource-gate failures.
        assert_business_switchable(business.state)

        membership = await TeamService.get_membership(session, identity_id, business_id)
        if membership is None:
            raise MembershipRequired()
        if membership.status != "active":
            raise MembershipRequired()

        # RLS (AUD-02): membership is confirmed active — bind the tenant GUC
        # before the entitlement / module-state / location reads below, which
        # are all row-level scoped by `business_id = current_business_id()`.
        from platform_core.context_resolver import bind_session_context

        await bind_session_context(session, identity_id, business_id)

        permissions = await TeamService.resolve_permissions(session, membership)
        entitlements = await EntitlementService.get_effective(session, business_id)
        module_states = await ModuleService.get_states(session, business_id)
        location = await BusinessService.get_primary_location(session, business_id)

        prefs_before = await IdentityService.get_consumer_preferences(session, identity_id)
        previous_last = prefs_before.get("last_business_id")
        previous_default = prefs_before.get("default_business_id")

        await IdentityService.update_business_context_preferences(
            session,
            identity_id=identity_id,
            last_business_id=business_id,
            default_business_id=business_id if set_as_default else None,
        )
        prefs_after = await IdentityService.get_consumer_preferences(session, identity_id)

        await OutboxService.publish(
            session,
            event_type="business.context_switched",
            payload={
                "business_id": str(business_id),
                "identity_id": str(identity_id),
                "set_as_default": set_as_default,
                "previous_last_business_id": previous_last,
            },
            business_id=business_id,
            correlation_id=correlation_id,
        )
        await AuditService.record(
            session,
            event_type="business.context_switched",
            actor_identity_id=identity_id,
            actor_context="business",
            business_id=business_id,
            resource_type="business",
            resource_id=business_id,
            action="switch_context",
            before_state={"last_business_id": previous_last},
            after_state={
                "last_business_id": str(business_id),
                "set_as_default": set_as_default,
            },
        )
        if set_as_default and previous_default != str(business_id):
            await AuditService.record(
                session,
                event_type="default_business_changed",
                actor_identity_id=identity_id,
                actor_context="business",
                business_id=business_id,
                resource_type="identity_preferences",
                resource_id=identity_id,
                action="set_default_business",
                before_state={"default_business_id": previous_default},
                after_state={"default_business_id": str(business_id)},
            )


        return BusinessService.hydrate_switch_response(
            business=business,
            membership=membership,
            location=location,
            permissions=permissions,
            entitlements=entitlements,
            module_states=module_states,
            preferences=prefs_after,
            correlation_id=correlation_id,
        )

    @staticmethod
    async def get_primary_location(
        session: AsyncSession, business_id: uuid.UUID
    ) -> BusinessLocation | None:
        result = await session.execute(
            select(BusinessLocation).where(
                BusinessLocation.business_id == business_id,
                BusinessLocation.deleted_at.is_(None),
                BusinessLocation.is_primary.is_(True),
            )
        )
        location = result.scalars().first()
        if location:
            return location
        result = await session.execute(
            select(BusinessLocation).where(
                BusinessLocation.business_id == business_id,
                BusinessLocation.deleted_at.is_(None),
            )
        )
        return result.scalars().first()

    @staticmethod
    def hydrate_create_response(
        *,
        business: Business,
        location: BusinessLocation,
        membership: BusinessMembership,
        profile: BusinessProfile,
        correlation_id: str,
        preferences: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        permissions = sorted(ALL_PERMISSIONS)
        prefs = preferences or {}
        business_id = str(business.id)
        return {
            "data": {
                "business": {
                    "id": business_id,
                    "slug": business.slug,
                    "display_name": business.display_name,
                    "state": business.state,
                    "visibility": business.visibility,
                    "business_type": business.business_type,
                    "settings": business.settings,
                    "primary_location": {
                        "id": str(location.id),
                        "name": location.name,
                        "timezone": location.timezone,
                        "is_primary": location.is_primary,
                        "country": (location.address or {}).get("country"),
                    },
                    "profile": {
                        "id": str(profile.id),
                        "logo_asset_id": (
                            str(profile.logo_asset_id) if profile.logo_asset_id else None
                        ),
                        "completeness_score": profile.completeness_score,
                    },
                },
                "membership": {
                    "id": str(membership.id),
                    "role": membership.role,
                    "status": membership.status,
                    "identity_id": str(membership.identity_id),
                },
                "context": {
                    "active_context": "business",
                    "business_id": business_id,
                    "location_id": str(location.id),
                    "role": membership.role,
                    "permissions": permissions,
                    "location_scope": None,
                    "module_states": {},
                    "entitled_modules": sorted(PLATFORM_CORE_MODULE_IDS),
                    "is_default_business": prefs.get("default_business_id", business_id)
                    == business_id,
                    "is_primary_business": prefs.get("primary_business_id", business_id)
                    == business_id,
                    "is_current_business": True,
                    "default_business_id": prefs.get("default_business_id", business_id),
                    "last_business_id": prefs.get("last_business_id", business_id),
                    "primary_business_id": prefs.get("primary_business_id", business_id),
                },
            },
            "meta": {"correlation_id": correlation_id},
        }

    @staticmethod
    def hydrate_switch_response(
        *,
        business: Business,
        membership: BusinessMembership,
        location: BusinessLocation | None,
        permissions: frozenset[str],
        entitlements: EntitlementSet,
        module_states: dict[str, BusinessModuleState],
        preferences: dict[str, Any],
        correlation_id: str,
    ) -> dict[str, Any]:
        business_id = str(business.id)
        location_scope = (
            [str(lid) for lid in membership.location_scope]
            if membership.location_scope is not None
            else None
        )
        return {
            "data": {
                "business": {
                    "id": business_id,
                    "slug": business.slug,
                    "display_name": business.display_name,
                    "state": business.state,
                    "visibility": business.visibility,
                    "business_type": business.business_type,
                    "settings": business.settings,
                    "primary_location": (
                        {
                            "id": str(location.id),
                            "name": location.name,
                            "timezone": location.timezone,
                            "is_primary": location.is_primary,
                        }
                        if location
                        else None
                    ),
                },
                "membership": {
                    "id": str(membership.id),
                    "role": membership.role,
                    "status": membership.status,
                    "identity_id": str(membership.identity_id),
                    "location_scope": location_scope,
                },
                "context": {
                    "active_context": "business",
                    "business_id": business_id,
                    "location_id": str(location.id) if location else None,
                    "role": membership.role,
                    "permissions": sorted(permissions),
                    "location_scope": location_scope,
                    "module_states": {
                        mid: state.activation_state for mid, state in module_states.items()
                    },
                    "entitled_modules": sorted(entitlements.modules),
                    "is_current_business": True,
                    "is_default_business": preferences.get("default_business_id") == business_id,
                    "is_primary_business": preferences.get("primary_business_id") == business_id,
                    "default_business_id": preferences.get("default_business_id"),
                    "last_business_id": preferences.get("last_business_id"),
                    "primary_business_id": preferences.get("primary_business_id"),
                },
            },
            "meta": {"correlation_id": correlation_id},
        }

    @staticmethod
    async def start_conversation(
        session: AsyncSession,
        *,
        identity_id: uuid.UUID,
        correlation_id: str,
        display_name: str | None = None,
        category_key: str | None = None,
        subcategory_key: str | None = None,
    ) -> tuple[Business, bool]:
        """A Business to talk to LOCAH about — before it has to have a name.

        "Talk to LOCAH" needs a Business (the conversation is its Blueprint), but
        an owner who opens the page and leaves must not leave a trail of empty
        businesses behind. So an untouched draft this owner already started
        (no name yet, nothing said yet) is reused; only otherwise is a new one
        created, with a placeholder address that follows the real name later.
        Returns (business, created).
        """
        name = " ".join((display_name or "").split())[:200]
        classification = (
            {"category_key": category_key, "subcategory_key": subcategory_key or ""}
            if category_key else None
        )
        for existing in await BusinessService.list_for_identity(session, identity_id):
            meta = existing.metadata_ or {}
            interview = meta.get("interview") or {}
            untouched = not any(m.get("role") == "user" for m in interview.get("messages") or [])
            if (existing.primary_owner_identity_id == identity_id and existing.state == "draft"
                    and meta.get("name_pending") and untouched):
                updated = dict(meta)
                updated.pop("interview", None)  # re-opened with this category / name
                if classification:
                    updated["classification"] = classification
                existing.metadata_ = updated
                if name:
                    await BusinessService.adopt_name(session, existing, name)
                await session.flush()
                return existing, False
        payload: dict[str, Any] = {"display_name": name or "New business"}
        if classification:
            payload.update({k: v for k, v in classification.items() if v})
        if not name:
            payload["slug"] = f"draft-{uuid.uuid4().hex[:10]}"
        business, *_ = await BusinessService.create_business(
            session, identity_id=identity_id, correlation_id=correlation_id, payload=payload,
        )
        if not name:
            business.metadata_ = {**(business.metadata_ or {}), "name_pending": True}
            await session.flush()
        return business, True

    @staticmethod
    async def adopt_name(session: AsyncSession, business: Business, name: str) -> None:
        """The owner said what the business is called.

        While the name was pending, the public address was a placeholder; it
        now follows the real name. After that, the address never changes on
        its own — a later rename is the owner's settings change, not this.
        """
        name = " ".join(name.split())[:200]
        if not name:
            return
        meta = dict(business.metadata_ or {})
        business.display_name = name
        if meta.get("name_pending"):
            base = slugify(name)
            if base in RESERVED_SLUGS:
                base = f"biz-{base}"
            candidate = await BusinessService._allocate_slug(session, display_name=name, requested_slug=None)
            for attempt in range(1, 26):
                try:
                    async with session.begin_nested():
                        business.slug = candidate
                        await session.flush()
                    break
                except IntegrityError as exc:
                    if "businesses_slug_active_key" not in str(exc.orig):
                        raise
                    candidate = f"{base}-{attempt}" if attempt < 6 else f"{base}-{uuid.uuid4().hex[:4]}"
            meta["name_pending"] = False
            business.metadata_ = meta
        await session.flush()

    @staticmethod
    async def update_business(
        session: AsyncSession,
        business: Business,
        *,
        display_name: str | None = None,
        visibility: str | None = None,
    ) -> Business:
        from platform_core.gates import assert_business_mutable

        # Distinct resource-state gate (Doc 11 §17.1 / Doc 12 §8.9 gate [9]).
        assert_business_mutable(business.state, action="update")
        if display_name is not None:
            business.display_name = display_name
        if visibility is not None:
            business.visibility = visibility
        await session.flush()
        return business
