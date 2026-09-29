"""P5 job-card persistence; separate from Projects' coordination record."""
# mypy: allow-subclassing-any

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import ARRAY, DateTime, ForeignKey, Integer, Text, func, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from platform_core.models import Base


class JobCard(Base):
    __tablename__ = "jobs_job_cards"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    business_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"))
    location_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("business_locations.id"))
    customer_contact_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("customer_relationships_contacts.id"))
    project_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("projects_projects.id"))
    source_quote_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("quotes_quotes.id"))
    source_type: Mapped[str] = mapped_column(Text, server_default=text("'manual'"))
    source_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    reference: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    problem: Mapped[str | None] = mapped_column(Text)
    asset_description: Mapped[str | None] = mapped_column(Text)
    asset_serial: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(Text, server_default=text("'normal'"))
    status: Mapped[str] = mapped_column(Text, server_default=text("'new'"))
    stage: Mapped[str | None] = mapped_column(Text)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    assigned_member_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("workforce_members.id"))
    work_performed: Mapped[str | None] = mapped_column(Text)
    approval_note: Mapped[str | None] = mapped_column(Text)
    approval_recorded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completion_note: Mapped[str | None] = mapped_column(Text)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    invoice_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"))
    created_by: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("platform_identities.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class JobPart(Base):
    __tablename__ = "jobs_parts"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    business_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"))
    job_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("jobs_job_cards.id"))
    inventory_movement_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("inventory_movements.id"))
    offering_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("offerings_catalog_offerings.id"))
    quantity: Mapped[int] = mapped_column(Integer)
    serials: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    idempotency_key: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
