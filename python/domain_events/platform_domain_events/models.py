from datetime import datetime, timezone
from uuid import UUID, uuid4
from pydantic import BaseModel, Field


class DomainEvent(BaseModel):
    event_type: str
    event_version: str = "1.0"
    event_id: UUID = Field(default_factory=uuid4)
    correlation_id: UUID | None = None
    causation_id: UUID | None = None
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    business_id: UUID | None = None
