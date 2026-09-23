"""Durable, owner-scoped interview application service.

The versioned Blueprint is an onboarding configuration document in the existing
tenant's metadata, not a second store of operational records. Confirmed profile
facts use the owning services when the owner builds. No schema migration needed.
"""

from __future__ import annotations

import re

from dataclasses import replace
import time
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.entitlements.module_registry import ModuleRegistry
from platform_core.entitlements.models import ResolvedEntitlement
from platform_core.entitlements.resolver import BusinessEntitlementResolver
from platform_core.exceptions import ConflictError, ResourceNotFound, ValidationError
from platform_core.gates import assert_business_mutable
from platform_core.interview.capabilities import (
    available_modules,
    classification_seed,
    operational_modules,
    resolve_recommendations,
    surface_new_unsupported_requests,
)
from platform_core.interview.design_strategy import (
    DESIGN_STRATEGY_VERSION,
    GENERATION_PLAN_VERSION,
    derive_strategy,
    generate_website_plan,
    select_contextual_template,
)
from platform_core.interview.models import (
    BusinessBlueprint,
    DraftCommand,
    DraftText,
    Fact,
    InterviewCommand,
    Message,
    MediaGenerationRequest,
    OfferingDraft,
    TargetState,
    now,
)
from platform_core.interview import voice
from platform_core.interview.orchestrator import BusinessInterviewOrchestrator, QUESTIONS
from platform_core.interview.understanding import understanding
from platform_core.interview.website import build_preview
from platform_core.logging import get_logger
from platform_core.models import Business, WebsiteGenerationJob, WebsiteVersion
from platform_core.resolvers.website_resolver import WebsiteResolver
from platform_core.services.async_jobs import AsyncJobService
from platform_core.services.audit import AuditService
from platform_core.services.entitlement import ModuleService
from platform_core.services.media import MediaService
from platform_core.services.outbox import OutboxService
from platform_core.services.website import WebsiteService
from platform_core.services.website_composition import WebsiteCompositionService
from platform_core.website.generation_plan import GenerationPlan, build_plan
from platform_core.website.image_generation import image_generation_available
from platform_core.website.template_registry import TEMPLATES_BY_ID


def public_contact(bp: BusinessBlueprint) -> dict[str, Any]:
    """The contact details the owner gave, shaped for their public site.

    Only what they actually said: a phone number they stated, and WhatsApp only
    if they mentioned WhatsApp. A number is normalised to digits so a button can
    dial it; anything that does not look like a phone number is left out rather
    than guessed at.
    """
    facts = {**bp.known_facts, **bp.unconfirmed_facts}
    contact: dict[str, Any] = {}
    phone = facts.get("phone")
    if phone:
        digits = re.sub(r"\D", "", phone.value)
        if 10 <= len(digits) <= 13:
            if len(digits) == 10:
                digits = "91" + digits  # an Indian mobile written without its country code
            contact["phone"] = "+" + digits
            said = " ".join(
                [fact.value for fact in facts.values()]
                + [m.text for m in bp.messages if m.role == "user"]
            )
            # Said in any script the owner used: "WhatsApp", "வாட்ஸ்அப்", "व्हाट्सएप".
            if re.search(r"whats\s?app|வாட்ஸ்\s?(?:அப்|ஆப்)|व्हाट्स\s?(?:एप|ऐप)", said, re.I):
                contact["whatsapp"] = "+" + digits
    email = facts.get("email")
    if email and re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email.value.strip()):
        contact["email"] = email.value.strip()
    return contact


def _carry_media(fresh: BusinessBlueprint, proposed: BusinessBlueprint) -> None:
    """Keep media the worker finished while a turn was being understood."""
    known = {m.asset_id for m in proposed.media_assets}
    for media in fresh.media_assets:
        if media.asset_id not in known:
            proposed.media_assets.append(media)
    for request in fresh.media_generation_requests:
        mine = next((r for r in proposed.media_generation_requests if r.role == request.role), None)
        newer = (
            mine is None
            or request.status == "ready"
            # the worker moved on from what this turn started with...
            or (mine.status == "queued" and request.status in {"failed", "ready"})
        )
        # ...but a fresh ask this turn ("try again") beats an old failure.
        if newer and not (mine is not None and mine.status == "requested"):
            proposed.media_generation_requests = [
                r for r in proposed.media_generation_requests if r.role != request.role
            ] + [request]
    if fresh.logo_state == "generated":
        proposed.logo_state = "generated"


def _apply_draft(bp: BusinessBlueprint, command: DraftCommand) -> None:
    """The owner editing, keeping or removing website wording. The owner wins."""
    wd = bp.website_draft
    text = " ".join(command.text.split())
    if command.field == "offering":
        name = " ".join(command.offering_name.split())
        offering = next((o for o in wd.offerings if o.name.casefold() == name.casefold()), None)
        if offering is None:
            if command.op != "edit" or not name:
                raise ValidationError("That item is not in the draft")
            offering = OfferingDraft(name=name[:80])
            wd.offerings.append(offering)
        if command.op == "edit":
            offering.description = DraftText(text=text[:800], provenance="owner_edited") if text else None
        elif command.op == "approve" and offering.description:
            offering.description = offering.description.model_copy(update={"provenance": "owner_approved"})
        elif command.op == "dismiss":
            wd.offerings = [o for o in wd.offerings if o is not offering]
        return
    current = getattr(wd, command.field)
    if command.op == "edit":
        if not text:
            raise ValidationError("Write something, or remove it instead")
        limits = {"hero_headline": 90, "hero_subheadline": 220, "about": 800, "cta_label": 32}
        setattr(wd, command.field, DraftText(text=text[: limits[command.field]], provenance="owner_edited"))
        wd.dismissed = [f for f in wd.dismissed if f != command.field]
    elif command.op == "approve":
        if current is None:
            raise ValidationError("There is nothing there to keep yet")
        setattr(wd, command.field, current.model_copy(update={"provenance": "owner_approved"}))
    elif command.op == "dismiss":
        setattr(wd, command.field, None)
        if command.field not in wd.dismissed:
            wd.dismissed.append(command.field)


async def _queue_logo(
    session: AsyncSession, business: Business, bp: BusinessBlueprint, *, actor_id: UUID
) -> None:
    """Draw a requested logo now, in the background, while the owner carries on."""
    request = next(
        (r for r in bp.media_generation_requests if r.role == "logo" and r.status == "requested"),
        None,
    )
    if request is None or not image_generation_available():
        return
    await AsyncJobService.enqueue(
        session,
        job_type="interview.generate_logo",
        business_id=business.id,
        payload={"business_id": str(business.id), "actor_id": str(actor_id)},
        max_attempts=1,
    )
    request.status = "queued"


class BusinessInterviewService:
    @staticmethod
    async def load_business(
        session: AsyncSession, business_id: UUID, *, lock: bool = False
    ) -> Business:
        query = select(Business).where(Business.id == business_id, Business.deleted_at.is_(None))
        if lock:
            query = query.with_for_update()
        business = (
            (await session.execute(query.execution_options(populate_existing=True)))
            .scalars()
            .first()
        )
        if business is None:
            raise ResourceNotFound("Business")
        assert_business_mutable(business.state, action="interview")
        return business

    @staticmethod
    def read(business: Business) -> BusinessBlueprint:
        stored = (business.metadata_ or {}).get("interview")
        if stored:
            bp = BusinessBlueprint.model_validate(stored)
            if bp.business_id != business.id:
                raise ValidationError("Interview does not belong to this business")
            return bp
        bp = BusinessBlueprint(
            business_id=business.id,
            identity={
                "display_name": Fact(
                    value=business.display_name, source="PLATFORM", confirmation="confirmed"
                ),
            },
            remaining_questions=list(QUESTIONS),
        )
        bp.messages = [Message(role="assistant", text=BusinessInterviewOrchestrator.opening_question(bp))]
        return bp

    @staticmethod
    async def save(session: AsyncSession, business: Business, bp: BusinessBlueprint) -> None:
        bp.updated_at = now()
        business.metadata_ = {**(business.metadata_ or {}), "interview": bp.model_dump(mode="json")}
        business.version += 1
        await session.flush()

    @staticmethod
    async def plan(
        session: AsyncSession, business: Business, bp: BusinessBlueprint
    ) -> GenerationPlan:
        entitlement = await BusinessEntitlementResolver.resolve(
            session, business.id, business=business
        )
        active = operational_modules(entitlement)
        rows = await WebsiteCompositionService.available_section_types(
            session, business_id=business.id
        )
        for row in rows:
            row["available"] = row["requires_module"] is None or row["requires_module"] in active
        plan = build_plan(
            business_type=classification_seed(bp), active_modules=active, capability_rows=rows
        )
        selected = bp.template_preferences.template_id
        if selected and bp.template_preferences.source == "USER_STATEMENT":
            template = TEMPLATES_BY_ID.get(selected)
            if not template or not set(template.required_modules) <= active:
                raise ValidationError(
                    "That design is not available with your current tools. Choose another design."
                )
            plan = replace(plan, template=template, template_reason="the owner chose this design")
        else:
            template = select_contextual_template(bp, plan)
            plan = replace(
                plan,
                template=template,
                template_reason="its composition best matches this Business Blueprint",
            )
        return plan

    @staticmethod
    async def response(
        session: AsyncSession,
        business: Business,
        bp: BusinessBlueprint,
        entitlement: ResolvedEntitlement | None = None,
    ) -> dict[str, Any]:
        # `execute` has already resolved this for the same request a few lines
        # earlier, and resolving twice was costing a measurable share of a
        # round trip on commands that cannot change module state at all — a
        # button that only records a choice was doing the platform's most
        # expensive read twice. `build` still re-resolves, because activating a
        # module is exactly the case where the first answer is stale.
        if entitlement is None:
            entitlement = await BusinessEntitlementResolver.resolve(
                session, business.id, business=business
            )
        resolve_recommendations(bp, entitlement, business.business_type)
        active = operational_modules(entitlement)
        logo_url = None
        logo = next((m for m in reversed(bp.media_assets) if m.role == "logo"), None)
        if logo:
            try:
                logo_url = (await MediaService.get(
                    session, business_id=business.id, asset_id=logo.asset_id))["url"]
            except Exception:  # noqa: BLE001 — a missing picture never breaks the page
                logo_url = None
        return {
            "blueprint": bp.model_dump(mode="json"),
            "understanding": understanding(bp, business.business_type, logo_url),
            "available_modules": [
                item.model_dump(mode="json") for item in available_modules(bp, entitlement)
            ],
            "classification_seed": classification_seed(bp),
            "templates": [
                t.serialize(
                    available=set(t.required_modules) <= active,
                    missing=tuple(sorted(set(t.required_modules) - active)),
                )
                for t in TEMPLATES_BY_ID.values()
            ],
            "voice": {
                "available": voice.is_configured(),
                "reason": "Talk to Locah instead of typing. You can switch between talking and "
                "typing at any time — it is the same setup either way."
                if voice.is_configured()
                else "Voice isn't available on this server. Chat saves the same interview state.",
            },
            "image_generation": {
                "available": image_generation_available(),
                "reason": "Locah can draw a logo if you have none, or cover artwork. It is "
                "marked as generated — never a photo of your business. Your own photos and "
                "logo always come first.",
            },
        }

    @staticmethod
    async def get(session: AsyncSession, business_id: UUID) -> dict[str, Any]:
        business = await BusinessInterviewService.load_business(session, business_id, lock=True)
        bp = BusinessInterviewService.read(business)
        if not (business.metadata_ or {}).get("interview"):
            await BusinessInterviewService.save(session, business, bp)
        result = await BusinessInterviewService.response(session, business, bp)
        await session.commit()
        return result

    @staticmethod
    def check_revision(bp: BusinessBlueprint, command: InterviewCommand) -> bool:
        if command.request_id in bp.applied_requests:
            return False
        if bp.revision != command.revision:
            raise ConflictError(
                "Your setup changed in another tab. Reload to keep the latest answers.",
                details={"current_revision": bp.revision},
            )
        return True

    @staticmethod
    async def execute(
        session: AsyncSession,
        business_id: UUID,
        command: InterviewCommand,
        *,
        actor_id: UUID,
        correlation_id: str,
    ) -> dict[str, Any]:
        business = await BusinessInterviewService.load_business(session, business_id)
        initial = BusinessInterviewService.read(business)
        if not BusinessInterviewService.check_revision(initial, command):
            return await BusinessInterviewService.response(session, business, initial)
        proposed = None
        if command.action == "turn":
            # No row locks or open DB transaction across a network/provider call.
            await session.commit()
            try:
                proposed = await BusinessInterviewOrchestrator.turn(
                    initial, command.text, field=command.field,
                    business_type=business.business_type,
                    image_available=image_generation_available(),
                )
            except ValueError as exc:
                raise ValidationError(str(exc)) from exc
        elif command.action == "draft" and command.draft and command.draft.op == "regenerate":
            await session.commit()
            proposed = await BusinessInterviewOrchestrator.regenerate_draft(
                initial, command.draft.field, command.draft.offering_name,
                business_type=business.business_type,
            )
        business = await BusinessInterviewService.load_business(session, business_id, lock=True)
        bp = BusinessInterviewService.read(business)
        if not BusinessInterviewService.check_revision(bp, command):
            return await BusinessInterviewService.response(session, business, bp)
        if proposed is not None:
            # A logo can finish drawing while the model was thinking about this
            # turn. Keep what the worker wrote; everything else is this turn's.
            _carry_media(bp, proposed)
            bp = proposed
            if bp.completion_state.status == "built":
                bp.completion_state.status = "review"
                BusinessInterviewOrchestrator.project(bp, business.business_type)
        entitlement = await BusinessEntitlementResolver.resolve(
            session, business_id, business=business
        )
        previous_unsupported = {
            gap.normalized_intent for gap in initial.unsupported_requests
        }
        resolve_recommendations(bp, entitlement, business.business_type)
        if proposed is not None and command.action == "turn":
            surface_new_unsupported_requests(bp, previous_unsupported)
        if command.action == "confirm":
            BusinessInterviewOrchestrator.confirm(bp, business.business_type)
        elif command.action == "draft":
            if command.draft is None:
                raise ValidationError("Nothing to change")
            if command.draft.op != "regenerate":
                _apply_draft(bp, command.draft)
        elif command.action == "choices":
            allowed = {item.module_id for item in bp.recommended_modules}
            allowed.update(item.module_id for item in available_modules(bp, entitlement))
            if not set(command.choices) <= allowed:
                raise ValidationError("Choose only tools available for this business")
            for module, choice in command.choices.items():
                bp.approved_modules = [m for m in bp.approved_modules if m != module]
                bp.declined_modules = [m for m in bp.declined_modules if m != module]
                (bp.approved_modules if choice == "approved" else bp.declined_modules).append(
                    module
                )
        elif command.action == "template":
            if command.template_id not in TEMPLATES_BY_ID:
                raise ValidationError("Unknown design")
            bp.template_preferences.template_id = command.template_id
            bp.template_preferences.source = "USER_STATEMENT"
            await BusinessInterviewService.plan(session, business, bp)
        elif command.action == "media":
            if command.media is None:
                raise ValidationError("Choose an uploaded image")
            asset = await MediaService.get(
                session, business_id=business_id, asset_id=command.media.asset_id
            )
            if asset["status"] != "ready" or command.media.source != "USER_UPLOAD":
                raise ValidationError("Finish uploading this image first")
            if len(bp.media_assets) >= 20:
                raise ValidationError("You can attach up to 20 images during setup")
            bp.media_assets = [
                m
                for m in bp.media_assets
                if m.asset_id != command.media.asset_id
                and not (m.role == command.media.role and m.role in {"hero", "logo"})
            ]
            bp.media_assets.append(command.media)
            if command.media.role == "logo":
                bp.logo_state = "uploaded"
        elif command.action == "image":
            if not image_generation_available():
                raise ValidationError(
                    "Image generation is not configured. You can upload an image instead."
                )
            if bp.completion_state.status == "built":
                raise ValidationError(
                    "Use the website editor to request more artwork after building."
                )
            role = command.image_role
            if role == "logo" and any(m.role == "logo" for m in bp.media_assets):
                raise ValidationError("You already added a logo. Your own logo is used.")
            bp.media_generation_requests = [
                r for r in bp.media_generation_requests if r.role != role
            ] + [MediaGenerationRequest(role=role, status="requested")]
            if role == "logo":
                bp.logo_state = "generation_requested"
                bp.discovery.setdefault("media.logo", TargetState()).status = "answered"
        elif command.action == "build":
            await BusinessInterviewService.build(
                session, business, bp, actor_id=actor_id, correlation_id=correlation_id
            )
        await _queue_logo(session, business, bp, actor_id=actor_id)
        bp.revision += 1
        bp.applied_requests = (bp.applied_requests + [command.request_id])[-30:]
        await BusinessInterviewService.save(session, business, bp)
        await AuditService.record(
            session,
            event_type="business.interview.updated",
            actor_identity_id=actor_id,
            actor_context="business",
            business_id=business_id,
            resource_type="business",
            resource_id=business_id,
            action=command.action,
            after_state={
                "revision": bp.revision,
                "session_id": str(bp.session_id),
                "completion": bp.completion_state.status,
                "turn_count": bp.turn_count,
            },
        )
        result = await BusinessInterviewService.response(
            session, business, bp, None if command.action == "build" else entitlement
        )
        await session.commit()
        return result

    @staticmethod
    async def build(
        session: AsyncSession,
        business: Business,
        bp: BusinessBlueprint,
        *,
        actor_id: UUID,
        correlation_id: str,
    ) -> None:
        BusinessInterviewOrchestrator.project(bp, business.business_type)
        if not bp.completion_state.confirmed:
            raise ValidationError("Review and confirm your business details before building")
        if any(r.choice == "pending" for r in bp.recommended_modules):
            raise ValidationError(
                "Choose or decline the suggested tools first. You can skip all of them."
            )
        existing = (
            (
                await session.execute(
                    select(WebsiteGenerationJob).where(
                        WebsiteGenerationJob.business_id == business.id,
                        WebsiteGenerationJob.status.in_(("pending", "running")),
                    )
                )
            )
            .scalars()
            .first()
        )
        if existing:
            raise ConflictError(
                "Personalization is already queued. Your existing preview is available."
            )
        if bp.completion_state.status == "built":
            return
        entitlement = await BusinessEntitlementResolver.resolve(
            session, business.id, business=business
        )
        active = {
            m
            for m, state in entitlement.module_states.items()
            if state.activation_state == "active" and state.entitled
        }
        pending = set(bp.approved_modules) & set(entitlement.entitled_modules)
        while pending:
            ready = {
                mid
                for mid in pending
                if set(ModuleRegistry.get_or_raise(mid).dependencies) <= active
            }
            if not ready:
                raise ValidationError(
                    "A selected tool needs another tool you haven't approved. Adjust your choices."
                )
            for mid in sorted(ready):
                if mid not in active:
                    await ModuleService.enable_module(
                        session,
                        business_id=business.id,
                        module_id=mid,
                        actor_id=actor_id,
                        entitlements=BusinessEntitlementResolver.to_entitlement_set(entitlement),
                    )
                active.add(mid)
            pending -= ready
        from platform_core.services.business_settings import BusinessSettingsService
        from platform_core.services.business_configuration import BusinessConfigurationService

        # Discovery can confirm the business from structured answers without
        # producing the legacy free-text description fact. Do not fabricate a
        # profile description or fail the entire website build in that case.
        description = bp.known_facts.get("description")
        profile: dict[str, Any] = {"description": description.value} if description else {}
        contact = public_contact(bp)
        if contact:
            profile["contact"] = contact
        if profile:
            await BusinessSettingsService.patch_profile(
                session,
                business_id=business.id,
                raw=profile,
                actor_id=actor_id,
                correlation_id=correlation_id,
            )
        seed = classification_seed(bp)
        if seed != business.business_type:
            await BusinessConfigurationService.patch_business_type(
                session,
                business_id=business.id,
                payload={"business_type": seed},
                actor_id=actor_id,
                correlation_id=correlation_id,
            )
        for media in bp.media_assets:
            # Revalidate at use time, not just attachment time.
            asset = await MediaService.get(
                session, business_id=business.id, asset_id=media.asset_id
            )
            if asset["status"] != "ready":
                raise ValidationError("An attached image is no longer ready")
            if media.role == "logo":
                await BusinessSettingsService.patch_branding(
                    session,
                    business_id=business.id,
                    raw={"logo_asset_id": str(media.asset_id)},
                    actor_id=actor_id,
                    correlation_id=correlation_id,
                )
        plan = await BusinessInterviewService.plan(session, business, bp)
        bp.template_preferences.template_id = plan.template.id
        immediate_strategy = derive_strategy(bp, plan)
        payload = build_preview(bp, plan, immediate_strategy)
        website = await WebsiteResolver.resolve_website(session, business_id=business.id)
        job = WebsiteGenerationJob(
            business_id=business.id,
            status="pending",
            triggered_by=actor_id,
            prompt_version=GENERATION_PLAN_VERSION,
        )
        session.add(job)
        await session.flush()
        draft = await WebsiteService.replace_draft_from_generation(
            session,
            business_id=business.id,
            website=website,
            payload=payload,
            generated_by="interview_template",
            generation_job_id=job.id,
        )
        bp.completion_state.status = "built"
        bp.completion_state.first_preview_at = now()
        bp.completion_state.generation_job_id = job.id
        job.intake = {
            "blueprint": bp.model_dump(mode="json"),
            "base_version_id": str(draft.id),
            "base_updated_at": draft.updated_at.isoformat(),
            "design_strategy": immediate_strategy.model_dump(mode="json"),
            "design_strategy_version": DESIGN_STRATEGY_VERSION,
            "generation_plan_version": GENERATION_PLAN_VERSION,
        }
        await AsyncJobService.enqueue(
            session,
            job_type="website.generate",
            business_id=business.id,
            payload={
                "generation_job_id": str(job.id),
                "business_id": str(business.id),
                "correlation_id": correlation_id,
            },
            max_attempts=2,
        )
        if any(r.role == "hero" and r.status == "requested" for r in bp.media_generation_requests):
            await AsyncJobService.enqueue(
                session,
                job_type="interview.generate_media",
                business_id=business.id,
                payload={
                    "business_id": str(business.id),
                    "actor_id": str(actor_id),
                    "generation_job_id": str(job.id),
                },
                max_attempts=1,
            )
            for request in bp.media_generation_requests:
                if request.role == "hero" and request.status == "requested":
                    request.status = "queued"
        get_logger("business.interview").info(
            "interview.preview_ready",
            business_id=str(business.id),
            time_to_preview_ms=int((now() - bp.created_at).total_seconds() * 1000),
            time_to_completion_ms=int(
                ((bp.completion_state.completed_at or now()) - bp.created_at).total_seconds() * 1000
            ),
            turn_count=bp.turn_count,
            template_id=plan.template.id,
            design_strategy_version=DESIGN_STRATEGY_VERSION,
            generation_plan_version=GENERATION_PLAN_VERSION,
        )

    @staticmethod
    async def personalize_job(
        session: AsyncSession, job: WebsiteGenerationJob, correlation_id: str
    ) -> dict[str, Any]:
        snapshot = job.intake or {}
        bp = BusinessBlueprint.model_validate(snapshot["blueprint"])
        business = await BusinessInterviewService.load_business(session, job.business_id)
        plan = await BusinessInterviewService.plan(session, business, bp)
        job.status = "running"
        job.started_at = now()
        job.attempt_count = (job.attempt_count or 0) + 1
        fallback = None
        strategy_source = "deterministic"
        personalization_started = time.monotonic()
        try:
            result, copy, provider = await generate_website_plan(bp, plan)
            payload = build_preview(bp, plan, result.strategy, copy)
            job.ai_provider = provider.provider_name
            job.model_name = provider.model_name
            provider_usage = dict(getattr(provider, "last_usage", None) or {})
            provider_usage.update(
                {
                    "design_strategy_version": DESIGN_STRATEGY_VERSION,
                    "generation_plan_version": GENERATION_PLAN_VERSION,
                    "strategy_latency_ms": result.latency_ms,
                    "strategy_repair_count": result.quality.repair_count,
                    "strategy_validation_issue_count": len(result.quality.issues),
                    "website_quality_valid": payload["theme_hints"]["quality"]["valid"],
                    "website_quality_issue_count": len(
                        payload["theme_hints"]["quality"]["issues"]
                    ),
                }
            )
            job.provider_usage = provider_usage
            strategy_source = result.strategy.source
        except Exception as exc:
            fallback = type(exc).__name__
            payload = build_preview(bp, plan, derive_strategy(bp, plan))
        # Business row first, then the draft: the same order the artwork job
        # takes, so the two never deadlock and the later one places the artwork.
        locked = await BusinessInterviewService.load_business(session, job.business_id, lock=True)
        # Lock and refresh the *exact* immediate preview. Edits before the worker
        # starts count too; compare against enqueue time, not job.started_at.
        draft = (
            (
                await session.execute(
                    select(WebsiteVersion)
                    .where(
                        WebsiteVersion.business_id == job.business_id,
                        WebsiteVersion.version_type == "draft",
                        WebsiteVersion.superseded_at.is_(None),
                    )
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
            )
            .scalars()
            .first()
        )
        if (
            not draft
            or str(draft.id) != snapshot["base_version_id"]
            or draft.updated_at.isoformat() != snapshot["base_updated_at"]
        ):
            job.status = "superseded"
            job.fallback_reason = "Owner edits preserved; personalization was not applied."
        elif fallback:
            # The first preview is already the safe fallback. Do not replace it.
            job.status = "fallback_used"
            job.fallback_reason = fallback
            job.result_version_id = draft.id
        else:
            website = await WebsiteResolver.resolve_website(session, business_id=job.business_id)
            generated = await WebsiteService.replace_draft_from_generation(
                session,
                business_id=job.business_id,
                website=website,
                payload=payload,
                generated_by="interview_personalization",
                generation_job_id=job.id,
            )
            job.result_version_id = generated.id
            job.status = "completed"
            job.fallback_reason = None  # an earlier failed attempt is not this result
        from platform_core.interview.media import place_ready_artwork

        await place_ready_artwork(session, job.business_id, BusinessInterviewService.read(locked))
        job.provider_usage = {
            **(job.provider_usage or {}),
            "personalization_latency_ms": int(
                (time.monotonic() - personalization_started) * 1000
            ),
            "total_time_to_personalized_preview_ms": int(
                (now() - bp.created_at).total_seconds() * 1000
            ),
        }
        job.completed_at = now()
        await session.flush()
        await OutboxService.publish(
            session,
            event_type="website.draft_generated",
            business_id=job.business_id,
            correlation_id=correlation_id,
            payload={
                "business_id": str(job.business_id),
                "job_id": str(job.id),
                "status": job.status,
                "template_id": plan.template.id,
                "design_strategy_version": DESIGN_STRATEGY_VERSION,
                "generation_plan_version": GENERATION_PLAN_VERSION,
                "strategy_source": strategy_source,
            },
        )
        get_logger("business.interview").info(
            "interview.website_personalized",
            business_id=str(job.business_id),
            job_id=str(job.id),
            status=job.status,
            template_id=plan.template.id,
            model=job.model_name,
            strategy_source=strategy_source,
            fallback_reason=job.fallback_reason,
            personalization_latency_ms=(job.provider_usage or {}).get(
                "personalization_latency_ms"
            ),
            total_time_to_personalized_preview_ms=(job.provider_usage or {}).get(
                "total_time_to_personalized_preview_ms"
            ),
            strategy_repair_count=(job.provider_usage or {}).get("strategy_repair_count"),
            prompt_tokens=(job.provider_usage or {}).get("prompt_tokens"),
            completion_tokens=(job.provider_usage or {}).get("completion_tokens"),
        )
        return {"status": job.status, "job_id": str(job.id)}
