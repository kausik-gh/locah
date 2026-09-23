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
    # Added with the discovery planner. Each maps onto a Document 07 §11.1
    # operating characteristic in `discovery.CHARACTERISTICS_BY_PATTERN`.
    "product_led", "local_delivery", "pickup", "shipping", "stock_based", "has_team",
    "runs_classes", "hybrid", "custom_made",
]

# What Locah still wants to understand about a business. A target is a concept,
# not a question: "offerings.units" is asked once, in whatever words fit this
# business, and never again once it is known. See `discovery.TARGETS`.
DiscoveryTargetId = Literal[
    "business.identity", "offerings.main", "offerings.structure", "offerings.units", "offerings.pricing",
    "offerings.customisation", "services.providers", "commerce.action", "commerce.payment",
    "fulfilment.mode", "fulfilment.area", "fulfilment.operator", "operations.stock",
    "operations.hours", "operations.team", "b2b.customers", "b2b.process",
    "bookings.format", "memberships.plans", "contact.location", "contact.phone",
    "brand.story", "brand.feel", "media.logo", "media.photos",
]
TargetStatus = Literal["open", "asked", "partial", "answered", "declined", "deferred"]

# How the owner reacted to the last question. "redundant" is the one that
# matters most: it means Locah asked something it already knew.
OwnerSignal = Literal["none", "redundant", "correction", "wants_to_finish", "annoyed"]
MediaIntent = Literal[
    "none", "generate_logo", "generate_hero", "will_upload_logo", "no_logo",
    # Product/category imagery: the owner has none and agrees to draft visuals,
    # will upload their own, or wants none.
    "generate_visuals", "will_upload_photos", "no_visuals",
]
# What the owner agreed to about pictures for the site. Draft visuals are drawn
# only after an explicit yes, marked as drafts, and always lose to a real photo.
VisualConsent = Literal["unknown", "draft_visuals", "own_photos", "none"]
# What a catalogue group still needs before it can be sold or shown well.
CatalogueNeed = Literal["varieties", "cuts", "sizes", "price", "photo"]
DraftProvenance = Literal["ai_suggestion", "owner_claim", "owner_edited", "owner_approved"]

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


class TargetState(StrictModel):
    """What Locah knows about one discovery target, and how often it asked.

    Asking is tracked by concept, not by question text: "What do you sell?"
    and "What do people come to you for?" are the same target, so the second
    is never asked once the first has an answer.
    """

    status: TargetStatus = "open"
    asked: int = 0
    last_asked_turn: int | None = None
    # Locah's understanding in a short line ("Sold by weight — customers pick
    # the kg"), backed by the owner's own words in `quote`.
    summary: str = Field(default="", max_length=240)
    quote: str = Field(default="", max_length=600)


class TargetAnswer(StrictModel):
    target: DiscoveryTargetId
    status: Literal["answered", "partial", "declined"] = "answered"
    summary: str = Field(default="", max_length=240)
    # The owner's words that answer it — exact, from the current message.
    quote: str = Field(default="", max_length=600)


class DraftText(StrictModel):
    """Website wording and where it came from.

    Suggestions are Locah's; claims are the owner's own marketing lines;
    edited and approved text belongs to the owner and is never rewritten by a
    later model pass. Draft text is presentation — it is never read back as a
    business fact.
    """

    text: str = Field(max_length=800)
    provenance: DraftProvenance = "ai_suggestion"
    updated_at: datetime = Field(default_factory=now)


class OfferingDraft(StrictModel):
    name: str = Field(max_length=80)
    description: DraftText | None = None


class OwnerClaim(StrictModel):
    """A line the owner asked to have said ("fresh from the farm to your home")."""

    claim: str = Field(max_length=240)
    quote: str = Field(max_length=600)


DraftField = Literal["hero_headline", "hero_subheadline", "about", "cta_label", "offering"]


class WebsiteDraft(StrictModel):
    hero_headline: DraftText | None = None
    hero_subheadline: DraftText | None = None
    about: DraftText | None = None
    cta_label: DraftText | None = None
    offerings: list[OfferingDraft] = Field(default_factory=list, max_length=12)
    owner_claims: list[OwnerClaim] = Field(default_factory=list, max_length=10)
    # Fields the owner removed; Locah does not quietly put them back.
    dismissed: list[str] = Field(default_factory=list, max_length=20)


class RecommendationEvidence(StrictModel):
    kind: Literal["owner_said", "operating_model", "answer", "dependency", "profile"]
    text: str = Field(max_length=300)


class CatalogueItem(StrictModel):
    """One thing sold inside a group: a cut, a variety, a dish, a project.

    Name, price and unit are the owner's; a description is website wording and
    may be Locah's suggestion.
    """

    name: str = Field(max_length=80)
    price: str = Field(default="", max_length=40)
    unit: str = Field(default="", max_length=40)
    description: str = Field(default="", max_length=240)
    source: Literal["owner", "owner_edited"] = "owner"


class CatalogueGroup(StrictModel):
    """A category or product family — "Chicken", "Fish & Seafood", "Thokku".

    A group is not an item: "fish different varieties" is the group Fish with
    `varieties` still needed, never a product called that.
    """

    name: str = Field(max_length=80)
    items: list[CatalogueItem] = Field(default_factory=list, max_length=24)
    # How it is sold, in the owner's terms: "by weight (kg)", "250g jars".
    sold_by: str = Field(default="", max_length=80)
    price: str = Field(default="", max_length=40)
    unit: str = Field(default="", max_length=40)
    needs: list[CatalogueNeed] = Field(default_factory=list, max_length=5)
    # "owner" when the group's name is the owner's own words; "ai_suggestion"
    # when Locah grouped owner-named items under a label ("Fish & Seafood").
    label_source: Literal["owner", "ai_suggestion"] = "owner"
    description: str = Field(default="", max_length=240)


class OfferingTaxonomy(StrictModel):
    groups: list[CatalogueGroup] = Field(default_factory=list, max_length=12)


class Readiness(StrictModel):
    """Whether there is enough for a strong first website, for THIS business."""

    ready: bool = False
    missing: list[str] = Field(default_factory=list)  # target ids still essential
    reason: str = Field(default="", max_length=200)
    # Whether the first WEBSITE can be designed well, separately from whether
    # every operational detail is known: content (what is sold, organised),
    # conversion (what a visitor does), visuals (pictures or consent to draft
    # them), story (something true to say). Opening hours never block this.
    website: dict[str, bool] = Field(default_factory=dict)


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
    # "visual" is a draft picture for one slot of the site ("hero",
    # "category:chicken", "project:green-meadows"), identified by `key`.
    role: Literal["hero", "logo", "visual"]
    key: str = Field(default="", max_length=120)
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
    # Evidence-based recommendation (see capabilities.recommend). `strong`
    # needs the owner's own words or an answered question; `dependency` is here
    # only because another recommended tool needs it.
    strength: Literal["strong", "useful", "dependency"] = "useful"
    evidence: list[RecommendationEvidence] = Field(default_factory=list, max_length=6)
    configuration_needed: str = Field(default="", max_length=240)
    needed_by: list[str] = Field(default_factory=list)


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
    # Discovery: every concept Locah wants to understand, by target id.
    discovery: dict[str, TargetState] = Field(default_factory=dict)
    last_asked_target: str | None = None
    # Website wording, kept apart from business truth.
    website_draft: WebsiteDraft = Field(default_factory=WebsiteDraft)
    readiness: Readiness = Field(default_factory=Readiness)
    # What is sold, as a structure: groups, items, units, prices, what is missing.
    taxonomy: OfferingTaxonomy = Field(default_factory=OfferingTaxonomy)
    visual_consent: VisualConsent = "unknown"
    # Owner-approved draft catalogue items created from the interview. Never
    # infer this from website copy or create sellable items automatically.
    applied_setup_offerings: list[str] = Field(default_factory=list, max_length=12)


class ExtractedFact(StrictModel):
    field: FactKey
    # Exact quotation, not a paraphrase. Negation/ambiguity still needs owner review.
    quote: str = Field(min_length=1, max_length=4000)
    # "add" extends what is known ("we also do office lunch subscriptions");
    # "replace" is a correction ("actually wardrobes are the main thing").
    mode: Literal["add", "replace"] = "replace"


class OfferingDraftUpdate(StrictModel):
    name: str = Field(max_length=80)
    description: str = Field(default="", max_length=240)


class DraftUpdate(StrictModel):
    """Website wording the model proposes this turn. Every field optional."""

    hero_headline: str = Field(default="", max_length=80)
    hero_subheadline: str = Field(default="", max_length=220)
    about: str = Field(default="", max_length=700)
    cta_label: str = Field(default="", max_length=32)
    offerings: list[OfferingDraftUpdate] = Field(default_factory=list, max_length=10)
    owner_claims: list[OwnerClaim] = Field(default_factory=list, max_length=5)


class ItemProposal(StrictModel):
    name: str = Field(max_length=80)
    # Only what the owner said: "240", "per kg". Numbers are checked against
    # their words before anything is kept.
    price: str = Field(default="", max_length=40)
    unit: str = Field(default="", max_length=40)


class GroupProposal(StrictModel):
    """How the model reads the owner's range this turn: groups and their items."""

    group: str = Field(max_length=80)
    items: list[ItemProposal] = Field(default_factory=list, max_length=24)
    sold_by: str = Field(default="", max_length=80)
    price: str = Field(default="", max_length=40)
    unit: str = Field(default="", max_length=40)
    # The owner said there are more of these without naming them
    # ("different varieties", "all kinds"), or options exist that matter for
    # ordering (cuts, sizes) that are not known yet.
    unknown: list[Literal["varieties", "cuts", "sizes"]] = Field(default_factory=list, max_length=3)


class TurnIntelligence(StrictModel):
    """Everything one owner message means, from ONE model call.

    Facts and answers are quotation-backed and validated before anything is
    kept. The next target is only a proposal: the discovery planner accepts it
    when it is still worth asking, and otherwise asks its own.
    """

    off_topic: bool = False
    language: LanguageStyle = "en"
    facts: list[ExtractedFact] = Field(default_factory=list, max_length=20)
    answered: list[TargetAnswer] = Field(default_factory=list, max_length=12)
    intents: list[CapabilityIntent] = Field(default_factory=list, max_length=12)
    operating_patterns: list[PatternEvidence] = Field(default_factory=list, max_length=10)
    highlights: list[Highlight] = Field(default_factory=list, max_length=8)
    owner_signal: OwnerSignal = "none"
    media_intent: MediaIntent = "none"
    draft: DraftUpdate = Field(default_factory=DraftUpdate)
    catalogue: list[GroupProposal] = Field(default_factory=list, max_length=12)
    acknowledgement: str = Field(default="", max_length=140)
    next_target: str = Field(default="none", max_length=40)
    next_question: str = Field(default="", max_length=300)


# The name the rest of the codebase knew this as.
Extraction = TurnIntelligence


class DraftCommand(StrictModel):
    field: DraftField
    op: Literal["edit", "approve", "dismiss", "regenerate"]
    text: str = Field(default="", max_length=800)
    offering_name: str = Field(default="", max_length=80)


class CatalogueEdit(StrictModel):
    """The owner completing the catalogue by hand: a price, a unit, a variety."""

    group: str = Field(min_length=1, max_length=80)
    item: str = Field(default="", max_length=80)  # empty: the group itself
    price: str = Field(default="", max_length=40)
    unit: str = Field(default="", max_length=40)
    add_items: list[str] = Field(default_factory=list, max_length=12)


class InterviewCommand(StrictModel):
    revision: int = Field(ge=0)
    request_id: UUID
    action: Literal[
        "turn", "confirm", "choices", "template", "media", "image", "build", "draft", "setup",
        "catalogue",
    ]
    text: str = Field(default="", max_length=4000)
    # Explicit correction also works without an AI provider.
    field: FactKey | None = None
    choices: dict[str, Literal["approved", "declined"]] = Field(default_factory=dict)
    template_id: str | None = Field(default=None, max_length=80)
    media: MediaReference | None = None
    # For action="image": what the owner asked Locah to draw.
    image_role: Literal["hero", "logo"] = "hero"
    # For action="draft": the owner editing, keeping or removing website wording.
    draft: DraftCommand | None = None
    # For action="catalogue": prices, units and varieties typed by the owner.
    catalogue: list[CatalogueEdit] = Field(default_factory=list, max_length=24)
