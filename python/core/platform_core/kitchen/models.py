"""Kitchen tables. Preparation truth, separate from the sales order."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from platform_core.models import Base


class KitchenStation(Base):
    __tablename__ = "kitchen_stations"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    business_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"))
    location_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("business_locations.id"), nullable=True)
    key: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class KitchenStationRoute(Base):
    __tablename__ = "kitchen_station_routes"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    business_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"))
    offering_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("offerings_catalog_offerings.id"))
    station_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("kitchen_stations.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class KitchenCounter(Base):
    __tablename__ = "kitchen_counters"

    business_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"), primary_key=True)
    next_number: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))


class KitchenTicket(Base):
    __tablename__ = "kitchen_tickets"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    business_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"))
    location_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("business_locations.id"))
    order_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("orders_orders.id"))
    ticket_number: Mapped[str] = mapped_column(Text, nullable=False)
    channel: Mapped[str] = mapped_column(Text, nullable=False)
    service_mode: Mapped[str] = mapped_column(Text, nullable=False)
    service_label: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'normal'"))
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'new'"))
    attention: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    entered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consumption_published: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class KitchenTicketLine(Base):
    __tablename__ = "kitchen_ticket_lines"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    business_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"))
    location_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("business_locations.id"))
    ticket_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("kitchen_tickets.id"))
    order_line_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    station_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("kitchen_stations.id"))
    offering_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    variant_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    modifiers: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    modifier_lines: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default=text("'{}'"))
    prep_status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'new'"))
    origin: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'original'"))
    attention: Mapped[str | None] = mapped_column(Text, nullable=True)
    entered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class KitchenLineEvent(Base):
    __tablename__ = "kitchen_line_events"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    business_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"))
    location_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("business_locations.id"))
    ticket_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("kitchen_tickets.id"))
    line_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("kitchen_ticket_lines.id"), nullable=True)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    detail: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class KitchenIntake(Base):
    """One applied outbox event. The primary key is the event id, so a replay inserts nothing."""

    __tablename__ = "kitchen_intakes"

    event_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    business_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("businesses.id"))
    order_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
