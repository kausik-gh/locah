from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


def now() -> datetime:
    return datetime.now(timezone.utc)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


FactKey = Literal[
    "description", "classification", "operating_model", "locations", "offerings",
    "customer_actions", "operational_characteristics", "brand", "tone", "colours",
    "opening_hours", "phone", "email", "website_priorities",
]


class Fact(StrictModel):
    value: str = Field(max_length=4000)
    source: Literal["USER_STATEMENT", "PLATFORM", "AI_EXTRACTION"]
    confirmation: Literal["confirmed", "unconfirmed"] = "unconfirmed"
    evidence: str = Field(default="", max_length=4000)
    updated_at: datetime = Field(default_factory=now)


class Question(StrictModel):
    field: FactKey
    text: str
    reason: str


class MediaReference(StrictModel):
    asset_id: UUID
    role: Literal["logo", "hero", "business", "offering", "gallery"]
    label: str = Field(default="", max_length=120)
    source: Literal["USER_UPLOAD", "AI_GENERATED"] = "USER_UPLOAD"


class MediaGenerationRequest(StrictModel):
    role: Literal["hero", "logo"]
    status: Literal["requested", "unavailable", "queued", "ready", "failed"]
    reason: str | None = None
    asset_id: UUID | None = None


class CapabilityIntent(StrictModel):
    intent: str = Field(max_length=120)
    original_request: str = Field(max_length=4000)


class CapabilityGapProposal(StrictModel):
    original_request: str
    normalized_intent: str
    business_classification: str
    closest_supported_capabilities: list[str] = Field(default_factory=list)
    why_unsupported: str
    required_mechanics: list[str] = Field(default_factory=list)
    session_reference: UUID


class ModuleRecommendation(StrictModel):
    module_id: str
    label: str
    reason: str
    capability_ids: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    status: Literal[
        "SUPPORTED", "SUPPORTED_REQUIRES_CONFIGURATION", "SUPPORTED_NOT_ENABLED",
        "NOT_CURRENTLY_AVAILABLE",
    ]
    availability_reason: str
    choice: Literal["pending", "approved", "declined"] = "pending"


class CreativeCopy(StrictModel):
    text: str = Field(max_length=300)
    source: Literal["AI_SUGGESTION"] = "AI_SUGGESTION"
    confirmation: Literal["unconfirmed", "confirmed"] = "unconfirmed"


class TemplatePreferences(StrictModel):
    template_id: str | None = None
    source: Literal["PLATFORM", "USER_STATEMENT"] = "PLATFORM"


class CompletionState(StrictModel):
    status: Literal["collecting", "review", "ready", "built"] = "collecting"
    sufficient: bool = False
    confirmed: bool = False
    completed_at: datetime | None = None
    first_preview_at: datetime | None = None
    generation_job_id: UUID | None = None


class Message(StrictModel):
    role: Literal["user", "assistant"]
    text: str
    at: datetime = Field(default_factory=now)


class TurnTelemetry(StrictModel):
    provider: str
    model: str
    latency_ms: int
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost: float | None = None
    retries: int = 0
    fallback_reason: str | None = None


class BusinessBlueprint(StrictModel):
    schema_version: Literal[1] = 1
    business_id: UUID
    session_id: UUID = Field(default_factory=uuid4)
    revision: int = 0
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)
    transport: Literal["chat", "voice"] = "chat"
    turn_count: int = 0
    identity: dict[str, Fact] = Field(default_factory=dict)
    business_classification: Fact | None = None
    operating_model: Fact | None = None
    locations: Fact | None = None
    offerings: Fact | None = None
    customer_actions: Fact | None = None
    operational_characteristics: Fact | None = None
    brand: Fact | None = None
    tone: Fact | None = None
    colours: Fact | None = None
    logo_state: Literal["not_supplied", "uploaded", "generation_requested"] = "not_supplied"
    media_assets: list[MediaReference] = Field(default_factory=list)
    media_generation_requests: list[MediaGenerationRequest] = Field(default_factory=list)
    requested_capabilities: list[CapabilityIntent] = Field(default_factory=list)
    recommended_modules: list[ModuleRecommendation] = Field(default_factory=list)
    declined_modules: list[str] = Field(default_factory=list)
    approved_modules: list[str] = Field(default_factory=list)
    website_content: dict[str, Fact] = Field(default_factory=dict)
    website_priorities: Fact | None = None
    template_preferences: TemplatePreferences = Field(default_factory=TemplatePreferences)
    known_facts: dict[str, Fact] = Field(default_factory=dict)
    suggested_content: dict[str, CreativeCopy] = Field(default_factory=dict)
    unconfirmed_facts: dict[str, Fact] = Field(default_factory=dict)
    unsupported_requests: list[CapabilityGapProposal] = Field(default_factory=list)
    remaining_questions: list[Question] = Field(default_factory=list)
    completion_state: CompletionState = Field(default_factory=CompletionState)
    messages: list[Message] = Field(default_factory=list)
    last_turn: TurnTelemetry | None = None
    # Bounded idempotency window. Revision checking also rejects old replays.
    applied_requests: list[UUID] = Field(default_factory=list)


class ExtractedFact(StrictModel):
    field: FactKey
    # Exact quotation, not a paraphrase. Negation/ambiguity still needs owner review.
    quote: str = Field(min_length=1, max_length=4000)


class Extraction(StrictModel):
    off_topic: bool = False
    facts: list[ExtractedFact] = Field(default_factory=list, max_length=20)
    intents: list[CapabilityIntent] = Field(default_factory=list, max_length=12)


class InterviewCommand(StrictModel):
    revision: int = Field(ge=0)
    request_id: UUID
    action: Literal["turn", "confirm", "choices", "template", "media", "image", "build"]
    text: str = Field(default="", max_length=4000)
    # Explicit correction also works without an AI provider.
    field: FactKey | None = None
    choices: dict[str, Literal["approved", "declined"]] = Field(default_factory=dict)
    template_id: str | None = Field(default=None, max_length=80)
    media: MediaReference | None = None
