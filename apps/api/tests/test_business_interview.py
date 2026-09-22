"""No database, network or paid model calls: interview domain + service contracts."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from pydantic import ValidationError as SchemaError

from platform_core.entitlements.models import FeatureState, ModuleState, ResolvedEntitlement
from platform_core.entitlements.module_registry import ModuleRegistry
from platform_core.exceptions import ConflictError, PermissionDenied, ValidationError
from platform_core.interview.capabilities import (
    classification_seed,
    resolve_recommendations,
    surface_new_unsupported_requests,
)
from platform_core.interview.design_strategy import (
    DesignStrategy,
    derive_strategy,
    generate_strategy,
    select_contextual_template,
    validate_strategy,
)
from platform_core.interview.models import (
    BusinessBlueprint,
    CapabilityIntent,
    Extraction,
    Fact,
    InterviewCommand,
    MediaReference,
    now,
)
from platform_core.interview.orchestrator import BusinessInterviewOrchestrator as Engine, QUESTIONS
from platform_core.interview.website import build_preview
from platform_core.models import Business, WebsiteGenerationJob
from platform_core.services.business_interview import BusinessInterviewService as Service
from platform_core.services.media import MediaService
from platform_core.website.generation_plan import build_plan
from platform_core.website.section_registry import CORE_SECTION_SCHEMAS
from platform_core.website.template_registry import TEMPLATES_BY_ID


class MockProvider:
    provider_name = "mock"
    model_name = "fixture"
    last_usage = {"prompt_tokens": 100, "completion_tokens": 40}

    def __init__(self, result=None, error=None):
        self.result = result or {}
        self.error = error
        self.prompts = []

    async def generate_structured(self, prompt, schema, model_config, timeout_seconds):
        self.prompts.append(prompt)
        if self.error:
            raise self.error
        return self.result


def blueprint():
    return BusinessBlueprint(
        business_id=uuid4(),
        identity={
            "display_name": Fact(
                value="Example business", source="PLATFORM", confirmation="confirmed"
            ),
        },
        remaining_questions=list(QUESTIONS),
    )


def confirmed():
    bp = blueprint()
    bp.known_facts = {
        k: Fact(value=v, source="USER_STATEMENT", confirmation="confirmed")
        for k, v in {
            "description": "We make furniture.",
            "offerings": "Sofas and dining tables",
            "customer_actions": "Learn about us",
        }.items()
    }
    Engine.project(bp)
    return bp


def entitlements():
    modules = {row["module_id"] for row in ModuleRegistry.list_modules()}
    features = {
        fid: FeatureState(fid, mid, True, True, "test")
        for mid in modules
        for fid in ModuleRegistry.get(mid).features
    }
    return ResolvedEntitlement(
        str(uuid4()),
        "test",
        "1",
        "1",
        "other",
        frozenset(modules),
        frozenset(features),
        {mid: ModuleState(mid, True, "active", True, True, "test") for mid in modules},
        features,
        {},
        {},
        1,
    )


def plan(bp, template=None):
    active = {row["module_id"] for row in ModuleRegistry.list_modules()}
    variants = {
        "hero": ["centered", "left_aligned", "image_left", "image_right", "full_width"],
        "about": ["text_only", "image_left", "image_right"],
        "contact": ["full", "compact"],
        "text_block": ["default", "highlighted"],
        "location_list": ["cards", "list"],
        "offerings_list": ["cards", "list", "grid"],
        "cta_band": ["centered", "left_aligned"],
        "gallery": ["grid", "masonry", "carousel"],
        "enquiry_form": ["default", "compact"],
        "menu_section": ["categorized", "simple"],
        "rooms_section": ["cards", "list"],
        "plans_section": ["cards", "comparison"],
        "classes_section": ["schedule", "cards"],
    }
    rows = [
        {"id": sid, "available": True, "allowed_variants": variants[sid], "requires_module": None}
        for sid in CORE_SECTION_SCHEMAS
    ]
    result = build_plan(
        business_type=classification_seed(bp), active_modules=active, capability_rows=rows
    )
    return replace(result, template=TEMPLATES_BY_ID[template]) if template else result


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "description,offering,action,seed,module",
    [
        (
            "We are a hospital",
            "Cardiology and blood tests",
            "book appointments",
            "clinic",
            "bookings",
        ),
        (
            "We are a furniture shop",
            "Sofas and custom tables",
            "view products",
            "retail",
            "offerings-catalog",
        ),
        ("We are a restaurant", "Rice bowls and salads", "order meals", "restaurant", "orders"),
        ("We are a meat shop", "Fresh chicken", "order for pickup", "retail", "orders"),
        (
            "We are a clothing shop",
            "Shirts and dresses",
            "view products",
            "retail",
            "offerings-catalog",
        ),
        ("We run a gym", "Yoga classes", "book classes and buy memberships", "gym", "memberships"),
        (
            "We work in real estate",
            "Property visits",
            "send enquiries",
            "professional_service",
            "leads",
        ),
        ("We run a home-food business", "Lunch boxes", "order meals", "restaurant", "orders"),
        ("We run a salon", "Haircuts", "book appointments", "salon", "bookings"),
    ],
)
async def test_business_intakes(description, offering, action, seed, module):
    text = f"{description}. {offering}. {action}."
    provider = MockProvider(
        {
            "facts": [
                {"field": k, "quote": v}
                for k, v in (
                    ("description", description),
                    ("offerings", offering),
                    ("customer_actions", action),
                )
            ]
        }
    )
    bp = await Engine.turn(blueprint(), text, provider=provider)
    assert bp.completion_state.sufficient and not bp.completion_state.confirmed
    assert not bp.remaining_questions  # One rich answer, no arbitrary question count.
    assert not bp.known_facts
    assert classification_seed(bp) == seed
    Engine.confirm(bp)
    resolve_recommendations(bp, entitlements())
    assert module in {r.module_id for r in bp.recommended_modules}
    assert all(ModuleRegistry.get(r.module_id) for r in bp.recommended_modules)
    assert bp.completion_state.confirmed


@pytest.mark.asyncio
async def test_off_topic_never_becomes_a_fact():
    bp = await Engine.turn(
        blueprint(), "Tell me a joke", provider=MockProvider({"off_topic": True})
    )
    assert not bp.known_facts and not bp.unconfirmed_facts
    assert "stay with" in bp.messages[-1].text
    assert len(bp.remaining_questions) == 3


@pytest.mark.asyncio
async def test_missing_info_asks_only_next_required_question():
    bp = await Engine.turn(blueprint(), "We make furniture", field="description")
    assert [q.field for q in bp.remaining_questions] == ["offerings", "customer_actions"]
    assert bp.messages[-1].text == QUESTIONS[1].text


@pytest.mark.asyncio
async def test_conflicting_correction_keeps_previous_until_confirmation():
    bp = confirmed()
    old = bp.known_facts["offerings"].value
    bp = await Engine.turn(bp, "Chairs only", field="offerings")
    assert bp.known_facts["offerings"].value == old
    assert bp.unconfirmed_facts["offerings"].value == "Chairs only"
    assert not bp.completion_state.confirmed
    Engine.confirm(bp)
    assert bp.known_facts["offerings"].value == "Chairs only"


@pytest.mark.parametrize(
    "intent", ["live_courier_tracking", "drone_delivery", "invented_module_123"]
)
def test_unsupported_requests_are_evidence_not_mechanics(intent):
    bp = confirmed()
    bp.requested_capabilities = [
        CapabilityIntent(intent=intent, original_request="I need " + intent)
    ]
    resolve_recommendations(bp, entitlements())
    assert not bp.recommended_modules
    assert bp.unsupported_requests[0].normalized_intent == intent
    assert bp.unsupported_requests[0].session_reference == bp.session_id


def test_live_tracking_detected_without_provider():
    bp = confirmed()
    bp.known_facts["customer_actions"].value = "Live courier map tracking"
    resolve_recommendations(bp, entitlements())
    assert bp.unsupported_requests
    assert all("tracking" not in r.module_id for r in bp.recommended_modules)


@pytest.mark.asyncio
async def test_fabricated_operational_facts_rejected_even_from_schema_valid_model():
    bp = await Engine.turn(
        blueprint(),
        "We run a hospital",
        provider=MockProvider(
            {
                "facts": [
                    {"field": "opening_hours", "quote": "24 hours"},
                    {"field": "offerings", "quote": "Surgery by Dr Smith costs 500"},
                    {"field": "locations", "quote": "42 Main Street"},
                ]
            }
        ),
    )
    assert not bp.unconfirmed_facts
    assert not bp.known_facts


def test_module_ids_cannot_enter_extraction_schema():
    with pytest.raises(SchemaError):
        Extraction.model_validate({"module_ids": ["magic"], "facts": []})


def test_declined_module_is_not_repeatedly_pushed():
    bp = confirmed()
    bp.requested_capabilities = [CapabilityIntent(intent="orders", original_request="orders")]
    bp.declined_modules = ["orders"]
    for _ in range(3):
        resolve_recommendations(bp, entitlements())
        assert (
            next(r for r in bp.recommended_modules if r.module_id == "orders").choice == "declined"
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [TimeoutError(), RuntimeError("provider unavailable")])
async def test_provider_failure_saves_turn_and_has_offline_path(error):
    bp = await Engine.turn(blueprint(), "We make furniture", provider=MockProvider(error=error))
    assert bp.messages[0].text == "We make furniture"
    assert bp.last_turn.fallback_reason == type(error).__name__
    bp = await Engine.turn(
        bp, "We make furniture", field="description", provider=MockProvider(error=error)
    )
    assert bp.unconfirmed_facts["description"].source == "USER_STATEMENT"


def test_resume_roundtrip_all_required_areas():
    bp = confirmed()
    restored = BusinessBlueprint.model_validate_json(bp.model_dump_json())
    assert restored == bp
    expected = "identity business_classification operating_model locations offerings customer_actions operational_characteristics brand tone colours logo_state media_assets media_generation_requests requested_capabilities recommended_modules declined_modules website_content website_priorities template_preferences known_facts suggested_content unconfirmed_facts unsupported_requests remaining_questions completion_state".split()
    assert set(expected) <= set(type(restored).model_fields)


@pytest.mark.asyncio
async def test_prompt_compact_without_transcript():
    bp = blueprint()
    from platform_core.interview.models import Message

    bp.messages = [Message(role="user", text="SECRET_OLD_TRANSCRIPT")]
    provider = MockProvider()
    await Engine.turn(bp, "We make tables", provider=provider)
    assert "SECRET_OLD_TRANSCRIPT" not in provider.prompts[0]


@pytest.mark.parametrize("template", list(TEMPLATES_BY_ID))
def test_each_template_uses_only_confirmed_truth_and_original_structure(template):
    bp = confirmed()
    p = plan(bp, template)
    payload = build_preview(bp, p)
    assert payload["theme_hints"]["template_id"] == template
    assert payload == build_preview(bp, p)
    assert "Sofas" in json.dumps(payload) or "We make furniture" in json.dumps(payload)
    for page in payload["pages"]:
        original = next(x for x in p.template.pages if x.slug == page["slug"])
        assert {s["section_type_id"] for s in page["sections"]} <= {
            s.section_type_id for s in original.sections
        }
    assert "24 hours" not in json.dumps(payload)


def test_preview_does_not_need_images_or_wait_for_media_generation():
    bp = confirmed()
    from platform_core.interview.models import MediaGenerationRequest

    bp.media_generation_requests = [MediaGenerationRequest(role="hero", status="queued")]
    assert build_preview(bp, plan(bp))["pages"]
    assert not bp.media_assets


@pytest.mark.asyncio
async def test_design_strategy_cannot_supply_claims_or_mechanics():
    bp = confirmed()
    p = plan(bp)
    strategy = derive_strategy(bp, p).model_dump(mode="json")
    with pytest.raises(SchemaError):
        await generate_strategy(
            bp, p, provider=MockProvider({**strategy, "claim": "Open 24 hours"})
        )
    selected, _ = await generate_strategy(bp, p, provider=MockProvider(strategy))
    assert selected.strategy.source == "ai"
    assert "Open 24 hours" not in selected.model_dump_json()


def test_strategy_repairs_unknown_sections_variants_actions_and_media():
    bp = confirmed()
    p = plan(bp)
    raw = derive_strategy(bp, p).model_dump(mode="json")
    raw["section_variants"][0]["variant"] = "invented_layout"
    raw["section_variants"].append(
        {
            "section_type_id": "testimonials",
            "variant": "carousel",
            "emphasis": "primary",
            "include": True,
            "order": 0,
        }
    )
    raw["media_strategy"]["hero_asset_id"] = str(uuid4())
    raw["cta_hierarchy"]["primary"] = "join"
    restricted = replace(p, active_modules=frozenset({"core-business-identity"}))
    repaired, quality = validate_strategy(DesignStrategy.model_validate(raw), bp, restricted)
    assert quality.valid and quality.repair_count >= 4
    assert "testimonials" not in {item.section_type_id for item in repaired.section_variants}
    assert repaired.media_strategy.hero_asset_id is None
    assert repaired.cta_hierarchy.primary != "join"


@pytest.mark.parametrize(
    "name,description,offerings,actions,brand",
    [
        (
            "Saffron Table",
            "A family restaurant serving regional food.",
            "Thalis and seasonal dishes",
            "order meals",
            "warm handmade local",
        ),
        (
            "Northline Clinic",
            "A neighbourhood clinic.",
            "Consultations and diagnostics",
            "book appointments",
            "calm clinical trusted",
        ),
        (
            "Forge Fitness",
            "A strength and conditioning gym.",
            "Coaching and group classes",
            "join a membership",
            "bold high energy",
        ),
        (
            "Stillwater Stay",
            "A quiet hillside homestay.",
            "Rooms for short stays",
            "book a room",
            "premium calm editorial",
        ),
        (
            "Arc Studio",
            "A design consultancy.",
            "Brand and product design",
            "send an enquiry",
            "minimal modern",
        ),
        (
            "Little Loom",
            "A local textile shop.",
            "Handwoven clothing",
            "browse products",
            "warm craft",
        ),
        (
            "Blue Door Academy",
            "An after-school learning centre.",
            "Maths and science courses",
            "see courses",
            "clear reassuring",
        ),
        (
            "Moss Spa",
            "A small day spa.",
            "Massage and skin treatments",
            "book a treatment",
            "grounded natural",
        ),
        (
            "Harbour Cafe",
            "Coffee and breakfast by the water.",
            "Coffee, bread and breakfast",
            "view the menu",
            "welcoming bright",
        ),
        (
            "Keystone Realty",
            "A property advisory business.",
            "Home sales and property visits",
            "request a property visit",
            "professional confident",
        ),
    ],
)
def test_ten_diverse_businesses_produce_valid_renderer_backed_websites(
    name,
    description,
    offerings,
    actions,
    brand,
):
    bp = BusinessBlueprint(
        business_id=uuid4(),
        identity={
            "display_name": Fact(value=name, source="PLATFORM", confirmation="confirmed"),
        },
    )
    bp.known_facts = {
        key: Fact(value=value, source="USER_STATEMENT", confirmation="confirmed")
        for key, value in {
            "description": description,
            "offerings": offerings,
            "customer_actions": actions,
            "brand": brand,
        }.items()
    }
    p = plan(bp)
    selected = select_contextual_template(bp, p)
    contextual = replace(p, template=selected)
    payload = build_preview(bp, contextual, derive_strategy(bp, contextual))
    assert payload["theme_hints"]["quality"]["valid"]
    assert payload["theme_hints"]["design_strategy_version"] == "1.0"
    assert payload["pages"] and payload["navigation"]
    assert all(
        section["section_type_id"] in contextual.available_ids
        for page in payload["pages"]
        for section in page["sections"]
    )
    assert name in json.dumps(payload)


def test_same_type_businesses_diverge_on_identity_goal_brand_and_media():
    first = confirmed()
    first.identity["display_name"].value = "Ember Kitchen"
    first.known_facts["description"].value = "A lively neighbourhood restaurant."
    first.known_facts["customer_actions"].value = "Order dinner for pickup"
    first.known_facts["brand"] = Fact(
        value="bold energetic", source="USER_STATEMENT", confirmation="confirmed"
    )
    first.media_assets = [MediaReference(asset_id=uuid4(), role="hero", label="Dining room")]

    second = confirmed()
    second.identity["display_name"].value = "Quiet Rice House"
    second.known_facts["description"].value = "A calm family restaurant."
    second.known_facts["customer_actions"].value = "Read our story and contact us"
    second.known_facts["brand"] = Fact(
        value="warm traditional", source="USER_STATEMENT", confirmation="confirmed"
    )

    first_plan = replace(plan(first), template=select_contextual_template(first, plan(first)))
    second_plan = replace(plan(second), template=select_contextual_template(second, plan(second)))
    one = build_preview(first, first_plan)
    two = build_preview(second, second_plan)
    assert classification_seed(first) == classification_seed(second) == "restaurant"
    assert one["theme_hints"]["design_strategy"] != two["theme_hints"]["design_strategy"]
    assert one["pages"][0]["sections"] != two["pages"][0]["sections"]


def test_revision_and_idempotent_retry():
    bp = confirmed()
    cmd = InterviewCommand(action="confirm", revision=0, request_id=uuid4())
    assert Service.check_revision(bp, cmd)
    bp.revision = 1
    with pytest.raises(ConflictError):
        Service.check_revision(bp, cmd)
    bp.applied_requests = [cmd.request_id]
    assert not Service.check_revision(bp, cmd)


def test_tenant_blueprint_cannot_be_rebound():
    bp = confirmed()
    business = Business(id=uuid4(), metadata_={"interview": bp.model_dump(mode="json")})
    with pytest.raises(ValidationError):
        Service.read(business)


@pytest.mark.asyncio
async def test_owner_authorization_denies_member(monkeypatch):
    import platform_api.routers.v1_business_interview as routes

    monkeypatch.setattr(
        routes,
        "resolve_business_actor",
        AsyncMock(
            return_value=SimpleNamespace(
                actor_membership=SimpleNamespace(role="staff"),
                request=SimpleNamespace(effective_permissions={"website.edit"}),
            )
        ),
    )
    with pytest.raises(PermissionDenied):
        await routes.owner(uuid4(), MagicMock(), AsyncMock())


@pytest.mark.asyncio
async def test_gallery_resolves_only_ready_tenant_assets():
    asset_id = uuid4()
    asset = SimpleNamespace(
        id=asset_id, public_url="https://storage.example/image", alt_text="Our showroom"
    )
    session = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = [asset]
    session.execute.return_value = result
    tenant = uuid4()
    sections = [{"content": {"image_asset_ids": [str(asset_id)]}}]
    await MediaService.attach_section_asset_urls(session, sections, business_id=tenant)
    assert sections[0]["assets"]["image_asset_id_0"]["alt_text"] == "Our showroom"
    query = session.execute.call_args.args[0]
    assert tenant in query.compile().params.values()
    assert "ready" in query.compile().params.values()


@pytest.mark.asyncio
async def test_creation_never_enqueues_or_calls_ai(monkeypatch):
    from platform_core.services.business import BusinessService
    from platform_core.services.website import WebsiteService
    from platform_core.services.website_generation import WebsiteGenerationService
    from platform_core.services.audit import AuditService
    from platform_core.services.outbox import OutboxService

    monkeypatch.setattr(BusinessService, "_allocate_slug", AsyncMock(return_value="example"))
    monkeypatch.setattr(BusinessService, "_set_identity_default_business", AsyncMock())
    monkeypatch.setattr("platform_core.context_resolver.bind_session_context", AsyncMock())
    monkeypatch.setattr(AuditService, "record", AsyncMock())
    monkeypatch.setattr(OutboxService, "publish", AsyncMock())
    monkeypatch.setattr(WebsiteService, "provision_for_business", AsyncMock())
    enqueue = AsyncMock(side_effect=AssertionError("AI job called during creation"))
    monkeypatch.setattr(WebsiteGenerationService, "enqueue_generation", enqueue)
    session = AsyncMock()
    session.add = MagicMock(side_effect=lambda obj: setattr(obj, "id", uuid4()))
    business, _, _, _ = await BusinessService.create_business(
        session,
        identity_id=uuid4(),
        correlation_id=str(uuid4()),
        payload={"display_name": "Furniture Store", "business_type": "retail"},
    )
    assert business.display_name == "Furniture Store"
    enqueue.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("edited", [False, True])
async def test_worker_failure_keeps_preview_and_owner_edits(monkeypatch, edited):
    import platform_core.services.business_interview as service_module

    bp = confirmed()
    stamp = now()
    draft = SimpleNamespace(
        id=uuid4(), updated_at=stamp + timedelta(seconds=1) if edited else stamp
    )
    job = WebsiteGenerationJob(
        id=uuid4(),
        business_id=bp.business_id,
        triggered_by=uuid4(),
        intake={
            "blueprint": bp.model_dump(mode="json"),
            "base_version_id": str(draft.id),
            "base_updated_at": stamp.isoformat(),
        },
    )
    monkeypatch.setattr(
        Service, "load_business", AsyncMock(return_value=Business(id=bp.business_id))
    )
    monkeypatch.setattr(Service, "plan", AsyncMock(return_value=plan(bp)))
    monkeypatch.setattr(
        service_module, "generate_strategy", AsyncMock(side_effect=TimeoutError())
    )
    monkeypatch.setattr(service_module.OutboxService, "publish", AsyncMock())
    session = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.first.return_value = draft
    session.execute.return_value = result
    response = await Service.personalize_job(session, job, str(uuid4()))
    assert response["status"] == ("superseded" if edited else "fallback_used")


@pytest.mark.asyncio
async def test_media_attachment_requires_tenant_ready_asset(monkeypatch):
    bp = confirmed()
    business = Business(
        id=bp.business_id, version=1, metadata_={"interview": bp.model_dump(mode="json")}
    )
    monkeypatch.setattr(Service, "load_business", AsyncMock(return_value=business))
    monkeypatch.setattr(
        "platform_core.services.business_interview.BusinessEntitlementResolver.resolve",
        AsyncMock(return_value=entitlements()),
    )
    lookup = AsyncMock(return_value={"status": "pending"})
    monkeypatch.setattr(MediaService, "get", lookup)
    asset = MediaReference(asset_id=uuid4(), role="logo")
    with pytest.raises(ValidationError):
        await Service.execute(
            AsyncMock(),
            bp.business_id,
            InterviewCommand(action="media", media=asset, revision=0, request_id=uuid4()),
            actor_id=uuid4(),
            correlation_id=str(uuid4()),
        )
    assert lookup.call_args.kwargs["business_id"] == bp.business_id


def test_classification_reads_every_thing_the_owner_said_not_two_fields():
    """A hospital must not classify as "other" because of where a quote landed.

    Found in the browser: a full hospital paragraph put "we run a 24 hour
    emergency department" in `description`, leaving the word "hospital" only in
    the business name and the offerings. Reading two fields seeded "other",
    which then picks the template and drives the entire website.
    """
    bp = blueprint()
    bp.identity["display_name"] = Fact(
        value="Sunrise Multispeciality Hospital", source="PLATFORM", confirmation="confirmed"
    )
    bp.known_facts = {
        "description": Fact(value="we run a 24 hour emergency department", source="AI_EXTRACTION"),
        "offerings": Fact(
            value="cardiology, orthopaedics, blood tests and scans", source="AI_EXTRACTION"
        ),
        "customer_actions": Fact(value="book an appointment online", source="AI_EXTRACTION"),
    }
    assert classification_seed(bp) == "clinic"


def test_classification_still_prefers_an_explicit_statement():
    bp = confirmed()
    assert classification_seed(bp) == "retail"


def test_unsupported_ask_is_raised_wherever_the_owner_happened_to_say_it():
    """The gap notice must not depend on which field the quote was filed under.

    Found in the browser: "live GPS tracking of our ambulances" was extracted as
    an operational characteristic rather than a customer action, so nothing was
    raised and the request passed silently into the Blueprint — which reads to
    the owner as the platform having accepted it.
    """
    bp = confirmed()
    bp.known_facts["operational_characteristics"] = Fact(
        value="live GPS tracking of our ambulances on the site", source="AI_EXTRACTION"
    )
    resolve_recommendations(bp, entitlements())
    assert [gap.normalized_intent for gap in bp.unsupported_requests] == ["live_courier_tracking"]
    assert "GPS" in bp.unsupported_requests[0].original_request
    assert all("track" not in r.module_id for r in bp.recommended_modules)


def test_a_business_with_no_unsupported_ask_raises_nothing():
    bp = confirmed()
    resolve_recommendations(bp, entitlements())
    assert bp.unsupported_requests == []


def test_interview_extraction_does_not_run_on_the_website_reasoning_model():
    """Extraction is quotation, not reasoning, and the owner waits through it.

    Measured against the same key and provider, the reasoning default took
    8.6s-10.2s per turn versus 1.5s-2.3s, and was the less accurate of the two.
    """
    from platform_core.interview.orchestrator import INTERVIEW_MODEL
    from platform_core.website.ai_provider import _DEFAULT_MODEL

    assert INTERVIEW_MODEL != _DEFAULT_MODEL


@pytest.mark.asyncio
async def test_the_turn_sends_the_fast_model_and_no_registry_dump():
    provider = MockProvider({"facts": [{"field": "description", "quote": "We make furniture"}]})
    captured: dict = {}
    original = provider.generate_structured

    async def spy(prompt, schema, model_config, timeout_seconds):
        captured.update(model_config)
        return await original(prompt, schema, model_config, timeout_seconds)

    provider.generate_structured = spy  # type: ignore[method-assign]
    await Engine.turn(blueprint(), "We make furniture", provider=provider)
    from platform_core.interview.orchestrator import INTERVIEW_MODEL

    assert captured["model"] == INTERVIEW_MODEL
    # Capability resolution is deterministic and stays out of the prompt.
    assert "offerings-catalog" not in provider.prompts[0]
    assert "module" not in provider.prompts[0].lower()
    assert "multilingual or code-switched" in captured["system_prompt"]


@pytest.mark.asyncio
async def test_tamil_booking_action_is_retained_when_model_omits_it():
    text = (
        "நான் சென்னையில் அன்பு சலூன் நடத்துறேன். "
        "ஹேர் கட், பிரைடல் மேக்கப், ஃபேஷியல் எல்லாம் பண்றோம். "
        "கஸ்டமர்ஸ்ல அபாயிண்ட்மென்ட் புக் பண்ணனும்."
    )
    provider = MockProvider(
        {
            "facts": [
                {
                    "field": "description",
                    "quote": "நான் சென்னையில் அன்பு சலூன் நடத்துறேன்.",
                },
                {
                    "field": "offerings",
                    "quote": "ஹேர் கட், பிரைடல் மேக்கப், ஃபேஷியல் எல்லாம் பண்றோம்.",
                },
            ]
        }
    )

    result = await Engine.turn(blueprint(), text, provider=provider)

    assert result.unconfirmed_facts["customer_actions"].value == (
        "கஸ்டமர்ஸ்ல அபாயிண்ட்மென்ட் புக் பண்ணனும்."
    )
    assert result.completion_state.sufficient is True


@pytest.mark.asyncio
async def test_location_correction_removes_old_city_from_duplicated_description():
    bp = blueprint()
    bp.unconfirmed_facts = {
        "description": Fact(
            value="I run North Star Bakery in Chennai. We sell bread and celebration cakes.",
            evidence="I run North Star Bakery in Chennai. We sell bread and celebration cakes.",
            source="AI_EXTRACTION",
        ),
        "locations": Fact(value="Chennai", source="AI_EXTRACTION"),
        "offerings": Fact(value="bread and celebration cakes", source="AI_EXTRACTION"),
    }
    Engine.project(bp)
    provider = MockProvider(
        {"facts": [{"field": "locations", "quote": "Coimbatore"}]}
    )

    result = await Engine.turn(
        bp,
        "Correction: North Star Bakery is in Coimbatore, not Chennai.",
        provider=provider,
    )

    assert result.unconfirmed_facts["locations"].value == "Coimbatore"
    assert result.unconfirmed_facts["description"].value == (
        "We sell bread and celebration cakes."
    )
    assert "Chennai" not in " ".join(
        fact.value for fact in result.unconfirmed_facts.values()
    )


@pytest.mark.asyncio
async def test_location_correction_keeps_the_current_business_summary_prefix():
    bp = blueprint()
    bp.unconfirmed_facts = {
        "description": Fact(
            value="I run North Star Bakery in Chennai.", source="AI_EXTRACTION"
        ),
        "locations": Fact(value="Chennai", source="AI_EXTRACTION"),
    }
    Engine.project(bp)
    provider = MockProvider(
        {
            "facts": [
                {
                    "field": "description",
                    "quote": "North Star Bakery is in Coimbatore, not Chennai.",
                },
                {"field": "locations", "quote": "Coimbatore"},
            ]
        }
    )

    result = await Engine.turn(
        bp, "North Star Bakery is in Coimbatore, not Chennai.", provider=provider
    )

    assert result.unconfirmed_facts["description"].value == (
        "North Star Bakery is in Coimbatore"
    )
    assert result.unconfirmed_facts["locations"].value == "Coimbatore"


@pytest.mark.parametrize("template", list(TEMPLATES_BY_ID))
def test_navigation_is_spelled_the_way_the_renderer_reads_it(template):
    """Found in the browser: the site rendered an unhandled error, not a home page.

    `build_preview` emitted `page_slug` where every other generator emits
    `path`, the payload validator treats navigation as free-form, and the
    renderer dereferences `item.path` — so the first thing the owner saw after
    "Build my website" was a crash on their own website.
    """
    bp = confirmed()
    payload = build_preview(bp, plan(bp, template))
    slugs = {page["slug"] for page in payload["pages"]}
    assert payload["navigation"], "a site with pages needs navigation"
    for item in payload["navigation"]:
        assert set(item) == {"label", "path"}, item
        assert item["path"].startswith("/"), item
        assert item["path"].lstrip("/") in slugs or item["path"] == "/"
    assert any(item["path"] == "/" for item in payload["navigation"]) == ("home" in slugs)


def test_interview_navigation_matches_the_template_generator_shape():
    """One renderer, one navigation contract, whichever door the draft came in by."""
    from platform_core.website.template_registry import (
        TEMPLATES_BY_ID as T,
        template_to_generation_payload,
    )

    bp = confirmed()
    template = T["plain-and-good"]
    from_template = template_to_generation_payload(template, business_name="Example business")
    from_interview = build_preview(bp, plan(bp, "plain-and-good"))
    assert {k for item in from_template["navigation"] for k in item} == {
        k for item in from_interview["navigation"] for k in item
    }


def test_unsupported_ask_is_raised_even_when_extraction_dropped_the_sentence():
    """Found in the browser: a hospital asked for ambulance GPS and nothing said no.

    The owner said it in the same paragraph as everything else. Extraction has
    no field for it, so the sentence survived nowhere, no gap was raised, and
    the request passed in silence — which reads as the platform agreeing to
    build it. What the owner said is evidence whether or not a fact kept it.
    """
    from platform_core.interview.models import Message

    bp = confirmed()
    bp.messages = [Message(role="user", text=(
        "We're a 200-bed hospital in Chennai. I also want live GPS tracking of "
        "our ambulances on the site."))]
    resolve_recommendations(bp, entitlements())
    assert [gap.normalized_intent for gap in bp.unsupported_requests] == ["live_courier_tracking"]
    # The quote is the sentence asked, not the whole paragraph.
    quoted = bp.unsupported_requests[0].original_request
    assert "GPS" in quoted and "200-bed" not in quoted


def test_a_new_unsupported_ask_is_surfaced_in_the_authoritative_reply():
    from platform_core.interview.models import Message

    bp = confirmed()
    bp.messages = [
        Message(role="user", text="I want live GPS tracking for our riders."),
        Message(role="assistant", text="What do you mainly sell?"),
    ]
    resolve_recommendations(bp, entitlements())
    surface_new_unsupported_requests(bp, set())

    reply = bp.messages[-1].text
    assert reply.startswith("That request is not supported today")
    assert reply.endswith("What do you mainly sell?")


def test_an_already_surfaced_gap_does_not_repeat_in_later_replies():
    from platform_core.interview.models import Message

    bp = confirmed()
    bp.messages = [
        Message(role="user", text="I want live GPS tracking for our riders."),
        Message(role="assistant", text="What do you mainly sell?"),
    ]
    resolve_recommendations(bp, entitlements())
    previous = {gap.normalized_intent for gap in bp.unsupported_requests}
    surface_new_unsupported_requests(bp, previous)
    assert bp.messages[-1].text == "What do you mainly sell?"


def test_an_ordinary_delivery_business_raises_no_false_gap():
    from platform_core.interview.models import Message

    bp = confirmed()
    bp.messages = [Message(role="user", text="We make furniture and deliver around Chennai.")]
    resolve_recommendations(bp, entitlements())
    assert bp.unsupported_requests == []


def test_an_approved_module_decides_the_call_to_action_when_words_do_not():
    """A premium restaurant that said "reserve a table" was getting "Explore".

    Nobody switches bookings on and then wants their website to lead with a
    generic verb. Approval is a stronger statement of intent than prose.
    """
    from platform_core.interview.design_strategy import derive_strategy

    bp = confirmed()
    bp.known_facts["customer_actions"] = Fact(
        value="Guests should reserve a table in advance", source="USER_STATEMENT",
        confirmation="confirmed")
    bp.approved_modules = ["bookings", "offerings-catalog"]
    strategy = derive_strategy(bp, plan(bp))
    assert strategy.cta_hierarchy.primary == "book"


def test_every_strategy_field_reaches_the_rendered_page():
    """No decorative metadata: a field the model decides must change something.

    `brand_mood`, `colour_direction`, `section_rhythm`, `whitespace`,
    `section_emphasis`, `primary_business_goal`, `secondary_customer_action`
    and `generated_media_role` were computed, persisted and never read by
    anything. They are gone; this keeps them gone.
    """
    from platform_core.interview.design_strategy import DesignStrategy

    gone = {
        "brand_mood", "colour_direction", "section_emphasis",
    }
    assert gone.isdisjoint(DesignStrategy.model_fields)
    from platform_core.interview.design_strategy import CompositionStrategy, MediaStrategy, VisualPriority

    assert {"section_rhythm", "whitespace"}.isdisjoint(CompositionStrategy.model_fields)
    assert "generated_media_role" not in MediaStrategy.model_fields
    assert {"primary_business_goal", "secondary_customer_action"}.isdisjoint(
        VisualPriority.model_fields
    )
