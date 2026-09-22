"""Durable, owner-scoped interview application service.

The versioned Blueprint is an onboarding configuration document in the existing
tenant's metadata, not a second store of operational records. Confirmed profile
facts use the owning services when the owner builds. No schema migration needed.
"""

from __future__ import annotations

from dataclasses import replace
import os
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
    classification_seed,
    operational_modules,
    resolve_recommendations,
)
from platform_core.interview.design_strategy import (
    DESIGN_STRATEGY_VERSION,
    GENERATION_PLAN_VERSION,
    derive_strategy,
    generate_strategy,
    select_contextual_template,
)
from platform_core.interview.models import (
    BusinessBlueprint,
    Fact,
    InterviewCommand,
    Message,
    MediaGenerationRequest,
    now,
)
from platform_core.interview import voice
from platform_core.interview.orchestrator import BusinessInterviewOrchestrator, QUESTIONS
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
from platform_core.website.template_registry import TEMPLATES_BY_ID


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
            messages=[Message(role="assistant", text=QUESTIONS[0].text)],
        )
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
        resolve_recommendations(bp, entitlement)
        active = operational_modules(entitlement)
        return {
            "blueprint": bp.model_dump(mode="json"),
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
                "available": bool(os.getenv("XAI_API_KEY")),
                "reason": "Optional AI cover artwork uses the existing image provider. It is an illustration, not a photo of your business. Logo generation is not supported; upload your own logo.",
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
                    initial, command.text, field=command.field
                )
            except ValueError as exc:
                raise ValidationError(str(exc)) from exc
        business = await BusinessInterviewService.load_business(session, business_id, lock=True)
        bp = BusinessInterviewService.read(business)
        if not BusinessInterviewService.check_revision(bp, command):
            return await BusinessInterviewService.response(session, business, bp)
        if proposed is not None:
            bp = proposed
            if bp.completion_state.status == "built":
                bp.completion_state.status = "review"
                BusinessInterviewOrchestrator.project(bp)
        entitlement = await BusinessEntitlementResolver.resolve(
            session, business_id, business=business
        )
        resolve_recommendations(bp, entitlement)
        if command.action == "confirm":
            BusinessInterviewOrchestrator.confirm(bp)
        elif command.action == "choices":
            allowed = {item.module_id for item in bp.recommended_modules}
            if not set(command.choices) <= allowed:
                raise ValidationError("Choose only tools recommended by the platform")
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
            if not os.getenv("XAI_API_KEY"):
                raise ValidationError(
                    "Image generation is not configured. You can upload an image instead."
                )
            if bp.completion_state.status == "built":
                raise ValidationError(
                    "Use the website editor to request more artwork after building."
                )
            bp.media_generation_requests = [MediaGenerationRequest(role="hero", status="requested")]
        elif command.action == "build":
            await BusinessInterviewService.build(
                session, business, bp, actor_id=actor_id, correlation_id=correlation_id
            )
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
        BusinessInterviewOrchestrator.project(bp)
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

        await BusinessSettingsService.patch_profile(
            session,
            business_id=business.id,
            raw={"description": bp.known_facts["description"].value},
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
                job_type="interview.generate_hero",
                business_id=business.id,
                payload={
                    "business_id": str(business.id),
                    "actor_id": str(actor_id),
                    "generation_job_id": str(job.id),
                },
                max_attempts=1,
            )
            for request in bp.media_generation_requests:
                if request.role == "hero":
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
            result, provider = await generate_strategy(bp, plan)
            payload = build_preview(bp, plan, result.strategy)
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
