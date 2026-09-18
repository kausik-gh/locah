from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Float, ForeignKey, Integer, Numeric, Text, Time, text
from sqlalchemy.dialects.postgresql import (
    ARRAY,
    INET,
    JSONB,
    TSTZRANGE,
    TSVECTOR,
    UUID as PG_UUID,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class PlatformIdentity(Base):
    __tablename__ = "platform_identities"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    supabase_user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), unique=True, nullable=False
    )
    email: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone_verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    email_verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MediaAsset(Base):
    """Uploaded media (Doc 12 §15.2). Domain rows store the asset id, never a
    provider URL — `public_url` here is the only place a storage URL lives."""

    __tablename__ = "media_assets"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    business_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("businesses.id"), nullable=True
    )
    uploader_identity_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("platform_identities.id"), nullable=True
    )
    original_filename: Mapped[str | None] = mapped_column(Text, nullable=True)
    mime_type: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    bucket: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'media'"))
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    public_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    alt_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    purpose: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'pending'"))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ConsumerProfile(Base):
    __tablename__ = "consumer_profiles"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    identity_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("platform_identities.id"), unique=True
    )
    preferences: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PlatformAdminGrant(Base):
    __tablename__ = "platform_admin_grants"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    identity_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("platform_identities.id")
    )
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    granted_by: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("platform_identities.id")
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)


class Business(Base):
    __tablename__ = "businesses"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    slug: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'draft'"))
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'in_good_standing'")
    )
    visibility: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'private'"))
    primary_owner_identity_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("platform_identities.id")
    )
    business_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    characteristics: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    settings: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))


class BusinessProfile(Base):
    __tablename__ = "business_profiles"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    business_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("businesses.id"), unique=True, nullable=False
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    tagline: Mapped[str | None] = mapped_column(Text, nullable=True)
    logo_asset_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    cover_asset_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    contact: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    website_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    social_links: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    completeness_score: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WebsiteSectionType(Base):
    __tablename__ = "website_section_types"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_schema: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    allowed_variants: Mapped[list[Any]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'")
    )
    contributing_module: Mapped[str | None] = mapped_column(Text, nullable=True)
    requires_module: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Website(Base):
    __tablename__ = "websites"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    business_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("businesses.id"), unique=True, nullable=False
    )
    published_version_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    custom_domain: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'draft'"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WebsiteVersion(Base):
    __tablename__ = "website_versions"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    website_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("websites.id"))
    business_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"))
    version_type: Mapped[str] = mapped_column(Text, nullable=False)
    navigation: Mapped[list[Any] | dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    theme: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    generated_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    generation_job_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # AUD-08: set when a newer draft soft-replaces this one. Exactly one draft
    # row per website has superseded_at IS NULL (enforced by a partial unique
    # index) — that is "the current draft", no created_at ordering needed.
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WebsitePage(Base):
    __tablename__ = "website_pages"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    website_version_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("website_versions.id")
    )
    business_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"))
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    page_type: Mapped[str] = mapped_column(Text, nullable=False)
    seo_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    seo_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    og_image_asset_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WebsiteSection(Base):
    __tablename__ = "website_sections"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    page_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("website_pages.id"))
    business_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"))
    section_type_id: Mapped[str] = mapped_column(Text, ForeignKey("website_section_types.id"))
    layout_variant: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    module_binding: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    is_visible: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WebsiteGenerationJob(Base):
    __tablename__ = "website_generation_jobs"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    business_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"))
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'pending'"))
    ai_provider: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_version: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'v1'"))
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    fallback_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    intake: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    result_version_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    triggered_by: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("platform_identities.id")
    )
    provider_usage: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MarketplaceBusinessProjection(Base):
    __tablename__ = "marketplace_business_projections"

    business_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("businesses.id"), primary_key=True
    )
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    business_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    characteristics: Mapped[list[Any]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'")
    )
    primary_category: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list[Any]] = mapped_column(ARRAY(Text), nullable=False, server_default=text("'{}'"))
    primary_location_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    city: Mapped[str | None] = mapped_column(Text, nullable=True)
    lat: Mapped[float | None] = mapped_column(Numeric(10, 7), nullable=True)
    lng: Mapped[float | None] = mapped_column(Numeric(10, 7), nullable=True)
    is_discoverable: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    logo_asset_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    website_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    capability_flags: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    indexed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    search_vector: Mapped[Any | None] = mapped_column(TSVECTOR, nullable=True)


class MarketplaceOfferingProjection(Base):
    __tablename__ = "marketplace_offering_projections"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    business_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"))
    offering_type: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price_from: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list[Any]] = mapped_column(ARRAY(Text), nullable=False, server_default=text("'{}'"))
    location_ids: Mapped[list[UUID]] = mapped_column(
        ARRAY(PG_UUID(as_uuid=True)), nullable=False, server_default=text("'{}'")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    indexed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    search_vector: Mapped[Any | None] = mapped_column(TSVECTOR, nullable=True)


class MarketplaceIndexHealth(Base):
    __tablename__ = "marketplace_index_health"

    business_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("businesses.id"), primary_key=True
    )
    last_indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'never'"))
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    discoverability_consented_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    consented_by: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BusinessLocation(Base):
    __tablename__ = "business_locations"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    business_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"))
    name: Mapped[str] = mapped_column(Text, nullable=False)
    address: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    timezone: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'UTC'"))
    hours: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'active'"))
    internal_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone: Mapped[str | None] = mapped_column(Text, nullable=True)
    email: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))


class BusinessEmployee(Base):
    __tablename__ = "business_employees"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    business_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"))
    identity_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("platform_identities.id"), nullable=True
    )
    membership_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("business_memberships.id"), nullable=True
    )
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone: Mapped[str | None] = mapped_column(Text, nullable=True)
    designation: Mapped[str | None] = mapped_column(Text, nullable=True)
    internal_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'active'"))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))


class BusinessEmployeeLocationAssignment(Base):
    __tablename__ = "business_employee_location_assignments"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    business_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"))
    employee_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("business_employees.id")
    )
    location_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("business_locations.id")
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    assigned_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("platform_identities.id"), nullable=True
    )


class CustomerContact(Base):
    __tablename__ = "customer_relationships_contacts"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    business_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"))
    identity_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("platform_identities.id"), nullable=True
    )
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    phone: Mapped[str | None] = mapped_column(Text, nullable=True)
    email: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'active'"))
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'")
    )
    preferred_location_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("business_locations.id"), nullable=True
    )
    customer_since: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_interaction_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))


class CustomerNote(Base):
    __tablename__ = "customer_relationships_notes"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    business_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"))
    contact_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("customer_relationships_contacts.id")
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    author_identity_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("platform_identities.id")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))


class CustomerTimelineEntry(Base):
    __tablename__ = "customer_relationships_timeline_entries"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    business_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"))
    contact_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("customer_relationships_contacts.id")
    )
    activity_type: Mapped[str] = mapped_column(Text, nullable=False)
    resource_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    resource_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    location_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("business_locations.id"), nullable=True
    )
    summary: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    source_event_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OfferingCategory(Base):
    __tablename__ = "offerings_catalog_categories"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    business_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"))
    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    parent_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("offerings_catalog_categories.id"), nullable=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'active'"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))


class Offering(Base):
    __tablename__ = "offerings_catalog_offerings"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    business_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"))
    category_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("offerings_catalog_categories.id"), nullable=True
    )
    offering_type: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'product'"))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sku: Mapped[str | None] = mapped_column(Text, nullable=True)
    barcode: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'draft'"))
    price_type: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'fixed'"))
    price_amount: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'INR'"))
    unit_of_measure: Mapped[str | None] = mapped_column(Text, nullable=True)
    tax_rate: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    track_inventory: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    low_stock_threshold: Mapped[int | None] = mapped_column(Integer, nullable=True)
    visibility: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'public'"))
    image_asset_ids: Mapped[list[UUID]] = mapped_column(
        ARRAY(PG_UUID(as_uuid=True)), nullable=False, server_default=text("'{}'")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))


class OfferingVariant(Base):
    __tablename__ = "offerings_catalog_variants"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    business_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"))
    offering_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("offerings_catalog_offerings.id")
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    sku: Mapped[str | None] = mapped_column(Text, nullable=True)
    barcode: Mapped[str | None] = mapped_column(Text, nullable=True)
    price_amount: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'active'"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))


class InventoryRecord(Base):
    __tablename__ = "inventory_records"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    business_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"))
    offering_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("offerings_catalog_offerings.id")
    )
    variant_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("offerings_catalog_variants.id"), nullable=True
    )
    location_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("business_locations.id")
    )
    quantity_on_hand: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    quantity_reserved: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    low_stock_threshold: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))


class InventoryMovement(Base):
    __tablename__ = "inventory_movements"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    business_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"))
    offering_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("offerings_catalog_offerings.id")
    )
    variant_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("offerings_catalog_variants.id"), nullable=True
    )
    location_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("business_locations.id")
    )
    inventory_record_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("inventory_records.id")
    )
    movement_type: Mapped[str] = mapped_column(Text, nullable=False)
    quantity_delta: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_after: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor_identity_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("platform_identities.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SalesOrder(Base):
    __tablename__ = "orders_orders"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    business_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"))
    location_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("business_locations.id")
    )
    customer_contact_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("customer_relationships_contacts.id"), nullable=True
    )
    order_number: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'pending'"))
    payment_method: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'cod'"))
    payment_status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'pending'"))
    currency: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'INR'"))
    subtotal: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, server_default=text("0"))
    tax_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, server_default=text("0"))
    discount_amount: Mapped[float] = mapped_column(
        Numeric(12, 2), nullable=False, server_default=text("0")
    )
    total_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, server_default=text("0"))
    internal_reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancelled_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("platform_identities.id"), nullable=True
    )
    idempotency_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))


class OrderLineItem(Base):
    __tablename__ = "orders_order_line_items"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    business_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"))
    order_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("orders_orders.id")
    )
    offering_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("offerings_catalog_offerings.id")
    )
    variant_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("offerings_catalog_variants.id"), nullable=True
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    sku: Mapped[str | None] = mapped_column(Text, nullable=True)
    unit_price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    tax_rate: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    line_subtotal: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    line_tax: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, server_default=text("0"))
    line_total: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    track_inventory: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    quantity_reserved: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    quantity_deducted: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OrderStatusHistory(Base):
    __tablename__ = "orders_order_status_history"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    business_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"))
    order_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("orders_orders.id")
    )
    from_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    to_status: Mapped[str] = mapped_column(Text, nullable=False)
    actor_identity_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("platform_identities.id"), nullable=True
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OrderNote(Base):
    __tablename__ = "orders_order_notes"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    business_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"))
    order_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("orders_orders.id")
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    author_identity_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("platform_identities.id")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))


class FulfilmentSettings(Base):
    __tablename__ = "fulfilment_settings"

    business_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("businesses.id"), primary_key=True
    )
    pickup_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    delivery_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    delivery_fee_offering_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("offerings_catalog_offerings.id"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))


class FulfilmentZone(Base):
    __tablename__ = "fulfilment_zones"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    business_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"))
    location_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("business_locations.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    match_type: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'city'"))
    city: Mapped[str | None] = mapped_column(Text, nullable=True)
    postal_prefix: Mapped[str | None] = mapped_column(Text, nullable=True)
    center_lat: Mapped[float | None] = mapped_column(Numeric(10, 7), nullable=True)
    center_lng: Mapped[float | None] = mapped_column(Numeric(10, 7), nullable=True)
    radius_km: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    charge_amount: Mapped[float] = mapped_column(
        Numeric(12, 2), nullable=False, server_default=text("0")
    )
    currency: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'INR'"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))


class FulfilmentJob(Base):
    __tablename__ = "fulfilment_jobs"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    business_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"))
    order_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("orders_orders.id"), unique=True
    )
    location_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("business_locations.id")
    )
    mode: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'pending'"))
    zone_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("fulfilment_zones.id"), nullable=True
    )
    delivery_address: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    delivery_charge: Mapped[float] = mapped_column(
        Numeric(12, 2), nullable=False, server_default=text("0")
    )
    currency: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'INR'"))
    tracking_token: Mapped[str] = mapped_column(Text, nullable=False)
    tracking_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    outcome_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("platform_identities.id"), nullable=True
    )
    updated_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("platform_identities.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))


class WorkforceMember(Base):
    __tablename__ = "workforce_members"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    business_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"))
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone: Mapped[str | None] = mapped_column(Text, nullable=True)
    designation: Mapped[str | None] = mapped_column(Text, nullable=True)
    identity_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("platform_identities.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'active'"))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))


class WorkforceLocationAssignment(Base):
    __tablename__ = "workforce_location_assignments"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    business_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"))
    member_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("workforce_members.id")
    )
    location_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("business_locations.id")
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    assigned_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("platform_identities.id"), nullable=True
    )


class WorkforceServiceAssociation(Base):
    __tablename__ = "workforce_service_associations"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    business_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"))
    member_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("workforce_members.id")
    )
    offering_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("offerings_catalog_offerings.id")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("platform_identities.id"), nullable=True
    )


class WorkforceAvailability(Base):
    __tablename__ = "workforce_availability"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    business_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"))
    member_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("workforce_members.id")
    )
    location_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("business_locations.id"), nullable=True
    )
    weekday: Mapped[int | None] = mapped_column(Integer, nullable=True)
    exception_date: Mapped[Any | None] = mapped_column(Date, nullable=True)
    start_time: Mapped[Any] = mapped_column(Time, nullable=False)
    end_time: Mapped[Any] = mapped_column(Time, nullable=False)
    is_available: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BookingsPolicy(Base):
    __tablename__ = "bookings_policies"

    business_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("businesses.id"), primary_key=True
    )
    require_deposit: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    deposit_amount: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    deposit_percent: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    cancel_window_hours: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("24")
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))


class ConsumerActivityProjection(Base):
    __tablename__ = "consumer_activity_projections"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    identity_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("platform_identities.id")
    )
    business_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"))
    activity_type: Mapped[str] = mapped_column(Text, nullable=False)
    resource_type: Mapped[str] = mapped_column(Text, nullable=False)
    resource_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    summary: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Booking(Base):
    __tablename__ = "bookings_bookings"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    business_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"))
    location_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("business_locations.id")
    )
    customer_contact_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("customer_relationships_contacts.id"), nullable=True
    )
    offering_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    provider_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("workforce_members.id"), nullable=True
    )
    booking_number: Mapped[str] = mapped_column(Text, nullable=False)
    reservation_mode: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'pending'"))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    party_size: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    guest_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payment_method: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'cod'"))
    payment_status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'pending'"))
    deposit_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    deposit_amount: Mapped[float] = mapped_column(
        Numeric(12, 2), nullable=False, server_default=text("0")
    )
    management_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    management_token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    internal_reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancelled_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("platform_identities.id"), nullable=True
    )
    idempotency_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))


class BookingStatusHistory(Base):
    __tablename__ = "bookings_booking_status_history"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    business_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"))
    booking_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("bookings_bookings.id")
    )
    from_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    to_status: Mapped[str] = mapped_column(Text, nullable=False)
    actor_identity_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("platform_identities.id"), nullable=True
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BookingResource(Base):
    """A bookable asset — a room, table, court, vehicle, or a pool of seats.

    Deliberately not a person. A workforce member has employment, skills and
    pay; the two meet only in an allocation, which is the thing that collides.
    """

    __tablename__ = "bookings_resources"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    business_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"))
    location_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("business_locations.id")
    )
    resource_type: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    code: Mapped[str | None] = mapped_column(Text, nullable=True)
    allocation_mode: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'exclusive'")
    )
    capacity: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    min_party_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_party_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    buffer_before_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    buffer_after_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    granularity: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'slot'"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    resource_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))


class BookingAllocation(Base):
    """One claim on one subject for one interval — the only thing that collides.

    `occupies` is half-open and already includes the resource's buffers, so
    turnaround and the difference between nights and slots both fall out of
    range arithmetic rather than needing their own branches.
    """

    __tablename__ = "bookings_booking_allocations"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    business_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"))
    kind: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'booking'"))
    booking_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("bookings_bookings.id", ondelete="CASCADE"), nullable=True
    )
    resource_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("bookings_resources.id"), nullable=True
    )
    provider_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("workforce_members.id"), nullable=True
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    is_exclusive: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    occupies: Mapped[Any] = mapped_column(TSTZRANGE, nullable=False)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BookingNote(Base):
    __tablename__ = "bookings_booking_notes"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    business_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"))
    booking_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("bookings_bookings.id")
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    author_identity_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("platform_identities.id")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))


class MerchantConnection(Base):
    __tablename__ = "payments_merchant_connections"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    business_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"))
    provider: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'stub'"))
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'not_connected'"))
    provider_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    # Fernet ciphertext of the owner's provider API credentials (Razorpay
    # {key_id, key_secret}). Never plaintext, never serialized to a client.
    encrypted_credentials: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    verification_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))


class PaymentAttempt(Base):
    __tablename__ = "payments_payment_attempts"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    business_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"))
    customer_contact_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("customer_relationships_contacts.id"), nullable=True
    )
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    source_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'INR'"))
    payment_method: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'pending'"))
    provider: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'stub'"))
    provider_reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    refunded_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, server_default=text("0"))
    failure_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))


class PaymentRefund(Base):
    __tablename__ = "payments_refunds"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    business_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"))
    payment_attempt_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("payments_payment_attempts.id")
    )
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'pending'"))
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))


class PaymentWebhookReceipt(Base):
    __tablename__ = "payments_webhook_receipts"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    provider_event_id: Mapped[str] = mapped_column(Text, nullable=False)
    payment_attempt_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("payments_payment_attempts.id"), nullable=True
    )
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'received'"))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BusinessMembership(Base):
    __tablename__ = "business_memberships"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    business_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"))
    identity_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("platform_identities.id")
    )
    role: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'pending'"))
    location_scope: Mapped[list[UUID] | None] = mapped_column(
        ARRAY(PG_UUID(as_uuid=True)), nullable=True
    )
    invited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))


class BusinessInvitation(Base):
    __tablename__ = "business_invitations"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    business_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"))
    invited_email: Mapped[str] = mapped_column(Text, nullable=False)
    invited_identity_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("platform_identities.id"), nullable=True
    )
    invited_role: Mapped[str] = mapped_column(Text, nullable=False)
    location_scope: Mapped[list[UUID] | None] = mapped_column(
        ARRAY(PG_UUID(as_uuid=True)), nullable=True
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'pending'"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    invited_by: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("platform_identities.id")
    )
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    declined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    membership_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("business_memberships.id"), nullable=True
    )
    last_resent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resend_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))


class MembershipPermissionGrant(Base):
    __tablename__ = "business_membership_permission_grants"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    business_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"))
    membership_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("business_memberships.id")
    )
    permission: Mapped[str] = mapped_column(Text, nullable=False)
    location_ids: Mapped[list[UUID] | None] = mapped_column(
        ARRAY(PG_UUID(as_uuid=True)), nullable=True
    )
    granted_by: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("platform_identities.id")
    )
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MembershipPermissionDenial(Base):
    __tablename__ = "business_membership_permission_denials"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    business_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"))
    membership_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("business_memberships.id")
    )
    permission: Mapped[str] = mapped_column(Text, nullable=False)
    denied_by: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("platform_identities.id")
    )
    denied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MembershipAppliedTemplate(Base):
    __tablename__ = "business_membership_applied_templates"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    membership_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("business_memberships.id")
    )
    template_id: Mapped[str] = mapped_column(Text, nullable=False)
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    applied_by: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("platform_identities.id")
    )
    customized: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))


class CommercialEntitlement(Base):
    __tablename__ = "commercial_entitlements"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    business_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"))
    subject_type: Mapped[str] = mapped_column(Text, nullable=False)
    subject_id: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'active'"))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    quantity_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    granted_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("platform_identities.id")
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ModuleDefinition(Base):
    __tablename__ = "module_definitions"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    module_class: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    dependencies: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'")
    )
    config_schema: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    is_available: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BusinessModuleState(Base):
    __tablename__ = "business_module_states"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    business_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"))
    module_id: Mapped[str] = mapped_column(Text, ForeignKey("module_definitions.id"))
    activation_state: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'not_enabled'")
    )
    configuration: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    enabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deactivated_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))


class PlatformOutboxEvent(Base):
    __tablename__ = "platform_outbox_events"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    business_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    event_version: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'1.0'"))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    correlation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    causation_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'pending'"))
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("5"))
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    leased_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    leased_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PlatformEventDelivery(Base):
    """One subscriber's delivery of one outbox event.

    Delivery state lives here rather than on the event so that a subscriber can
    fail and retry without re-running the subscribers that already succeeded.
    """

    __tablename__ = "platform_event_deliveries"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    event_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("platform_outbox_events.id", ondelete="CASCADE")
    )
    subscriber_id: Mapped[str] = mapped_column(Text, nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    business_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'pending'"))
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("5"))
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    leased_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    leased_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PlatformAuditEvent(Base):
    __tablename__ = "platform_audit_events"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    actor_identity_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("platform_identities.id")
    )
    actor_context: Mapped[str] = mapped_column(Text, nullable=False)
    business_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    resource_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    resource_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    before_state: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    after_state: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(INET, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ============================================================
# Stage 6 - Leads (module: leads)
# ============================================================
class Lead(Base):
    __tablename__ = "leads_leads"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    business_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"))
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone: Mapped[str | None] = mapped_column(Text, nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'manual'"))
    origin_context: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    offering_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'new'"))
    lost_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    assignee_identity_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("platform_identities.id"), nullable=True
    )
    next_follow_up_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    customer_contact_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("customer_relationships_contacts.id"), nullable=True
    )
    created_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("platform_identities.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))


class LeadStatusHistory(Base):
    __tablename__ = "leads_lead_status_history"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    business_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"))
    lead_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("leads_leads.id"))
    from_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    to_status: Mapped[str] = mapped_column(Text, nullable=False)
    actor_identity_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("platform_identities.id"), nullable=True
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LeadNote(Base):
    __tablename__ = "leads_lead_notes"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    business_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"))
    lead_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("leads_leads.id"))
    body: Mapped[str] = mapped_column(Text, nullable=False)
    author_identity_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("platform_identities.id")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))


# ============================================================
# Stage 6 - Memberships (module: memberships)
# ============================================================
class MembershipPlan(Base):
    __tablename__ = "memberships_plans"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    business_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"))
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    offering_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    price_amount: Mapped[float] = mapped_column(
        Numeric(12, 2), nullable=False, server_default=text("0")
    )
    currency: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'INR'"))
    billing_model: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'fixed_duration'")
    )
    duration_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'draft'"))
    visibility: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'private'"))
    created_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("platform_identities.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))


class MembershipPlanOfferingAccess(Base):
    __tablename__ = "memberships_plan_offering_access"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    business_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"))
    plan_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("memberships_plans.id")
    )
    offering_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MembershipEnrolment(Base):
    __tablename__ = "memberships_enrolments"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    business_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"))
    plan_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("memberships_plans.id")
    )
    customer_contact_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("customer_relationships_contacts.id")
    )
    identity_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("platform_identities.id"), nullable=True
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'pending'"))
    payment_attempt_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    payment_status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'pending'")
    )
    auto_renew: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("platform_identities.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))


class MembershipEnrolmentStatusHistory(Base):
    __tablename__ = "memberships_enrolment_status_history"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    business_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"))
    enrolment_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("memberships_enrolments.id")
    )
    from_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    to_status: Mapped[str] = mapped_column(Text, nullable=False)
    actor_identity_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("platform_identities.id"), nullable=True
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# Backward-compatible alias during transition
class PlatformNotification(Base):
    __tablename__ = "platform_notifications"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    business_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"))
    recipient_identity_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("platform_identities.id")
    )
    notification_type: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'operational'")
    )
    severity: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'info'"))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    resource_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    resource_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    location_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("business_locations.id"), nullable=True
    )
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))


class PlatformNotificationPreference(Base):
    __tablename__ = "platform_notification_preferences"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    business_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"))
    identity_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("platform_identities.id")
    )
    category: Mapped[str] = mapped_column(Text, nullable=False)
    in_app_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))


PlatformProfile = PlatformIdentity
