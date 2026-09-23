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


# How the owner talks. Used to answer in the same register — a Chennai owner
# who writes "WhatsApp pannitu showroom-ku varuvanga" should not be answered in
# formal English. Stored facts stay in the owner's own words either way.
LanguageStyle = Literal["en", "ta", "ta_en", "hi", "hi_en", "other"]

# Advisory business characteristics. They steer which question is worth asking
# and how the website is composed; they never enable, grant or configure
# anything, and every one must be backed by an exact quotation.
OperatingPattern = Literal[
    "b2c", "b2b", "b2b2c", "service_led", "retail", "wholesale", "appointment_led",
    "quote_led", "lead_generation", "catalogue_led", "order_led", "membership_led",
    "subscription_like", "multi_location", "provider_based", "project_based",
    "made_to_order", "delivery", "walk_in", "online_first",
]

# Optional things worth asking about once, after the essentials. None of them
# blocks completion.
OptionalAsk = Literal["locations", "phone", "logo"]


class PatternEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pattern: OperatingPattern
    quote: str = Field(min_length=1, max_length=600)


class Highlight(BaseModel):
    """A number the owner actually said, fit for a stats strip.

    `value` must occur inside `quote`, and `quote` inside the owner's message.
    Nothing here is ever computed, rounded or rated by the model.
    """

    model_config = ConfigDict(extra="forbid")
    value: str = Field(min_length=1, max_length=24)
    label: str = Field(min_length=1, max_length=40)
    quote: str = Field(min_length=1, max_length=600)


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
    # Customer-facing tools are shown first; back-office ones stay out of the way.
    group: Literal["customer", "operations"] = "customer"


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
    logo_state: Literal["not_supplied", "uploaded", "generation_requested", "generated"] = (
        "not_supplied"
    )
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
    language_style: LanguageStyle = "en"
    operating_patterns: list[PatternEvidence] = Field(default_factory=list)
    highlights: list[Highlight] = Field(default_factory=list)
    # Optional asks already made once. Asking again is the questionnaire feel
    # this whole conversation exists to avoid.
    asked_optional: list[OptionalAsk] = Field(default_factory=list)


class ExtractedFact(StrictModel):
    field: FactKey
    # Exact quotation, not a paraphrase. Negation/ambiguity still needs owner review.
    quote: str = Field(min_length=1, max_length=4000)
    # "add" extends what is known ("we also do office lunch subscriptions");
    # "replace" is a correction ("actually wardrobes are the main thing").
    mode: Literal["add", "replace"] = "replace"


class Extraction(StrictModel):
    off_topic: bool = False
    language: LanguageStyle = "en"
    facts: list[ExtractedFact] = Field(default_factory=list, max_length=20)
    intents: list[CapabilityIntent] = Field(default_factory=list, max_length=12)
    operating_patterns: list[PatternEvidence] = Field(default_factory=list, max_length=10)
    highlights: list[Highlight] = Field(default_factory=list, max_length=8)
    # Conversational glue in the owner's register. Governed: short, no numbers
    # the owner did not say, no promises about what the platform will do.
    acknowledgement: str = Field(default="", max_length=120)
    # A phrasing for the one field Locah will ask about next. Locah decides the
    # field; this is only how to say it, and it is discarded if it targets
    # anything else.
    next_question_field: str = Field(default="", max_length=40)
    next_question: str = Field(default="", max_length=260)
    # The owner explicitly asking Locah to draw something for them.
    asset_request: Literal["none", "generate_logo", "generate_hero"] = "none"


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
    # For action="image": what the owner asked Locah to draw.
    image_role: Literal["hero", "logo"] = "hero"
