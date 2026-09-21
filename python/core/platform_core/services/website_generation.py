"""Website AI generation orchestration (Doc 12 §12.1–§12.2)."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.exceptions import ConflictError, ValidationError
from platform_core.gates import assert_business_mutable
from platform_core.models import BusinessProfile, WebsiteGenerationJob, WebsiteVersion
from platform_core.resolvers.website_resolver import WebsiteResolver
from platform_core.services.async_jobs import AsyncJobService
from platform_core.services.audit import AuditService
from platform_core.services.business import BusinessService
from platform_core.services.outbox import OutboxService
from platform_core.services.website import WebsiteService
from platform_core.validation.website import validate_generation_payload
from platform_core.website.ai_provider import get_ai_provider
from platform_core.website.fallback_generator import build_deterministic_draft
from platform_core.website.generation_brief import (
    apply_intake_theme,
    build_generation_prompt,
    default_theme_for_type,
)
from platform_core.website.generation_plan import (
    GenerationPlan,
    build_plan,
    enforce_capabilities,
    normalise_theme,
)
from platform_core.website.questionnaire import validate_intake
from platform_core.website.section_registry import WEBSITE_GENERATION_SCHEMA, catalogue_section_for_page


class WebsiteGenerationService:
    @staticmethod
    async def enqueue_generation(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        actor_id: uuid.UUID,
        correlation_id: str,
        auto: bool = False,
        intake: dict[str, Any] | None = None,
    ) -> WebsiteGenerationJob:
        business = await BusinessService.get_by_id(session, business_id)
        assert_business_mutable(business.state, action="generate website")
        await WebsiteService.provision_for_business(
            session, business_id=business_id, actor_id=actor_id
        )

        cleaned_intake = validate_intake(business.business_type, intake) if intake else {}

        running = await session.execute(
            select(WebsiteGenerationJob).where(
                WebsiteGenerationJob.business_id == business_id,
                WebsiteGenerationJob.status.in_(("pending", "running")),
            )
        )
        existing = running.scalars().first()
        if existing is not None:
            # A human-triggered generation (explicit questionnaire answers)
            # supersedes an auto-enqueued job that the worker has not yet
            # claimed — the owner's answers must win over the bootstrap draft.
            if cleaned_intake and existing.status == "pending":
                existing.status = "superseded"
                await session.flush()
            else:
                raise ConflictError(
                    "Website generation already in progress",
                    details={"job_id": str(existing.id), "status": existing.status},
                )

        job = WebsiteGenerationJob(
            business_id=business_id,
            status="pending",
            prompt_version="v2",
            triggered_by=actor_id,
            intake=cleaned_intake or None,
        )
        session.add(job)
        await session.flush()

        await AsyncJobService.enqueue(
            session,
            job_type="website.generate",
            payload={
                "business_id": str(business_id),
                "generation_job_id": str(job.id),
                "triggered_by": str(actor_id),
                "correlation_id": correlation_id,
                "auto": auto,
            },
            business_id=business_id,
            max_attempts=3,
        )
        return job

    @staticmethod
    async def latest_job(
        session: AsyncSession, *, business_id: uuid.UUID
    ) -> WebsiteGenerationJob | None:
        result = await session.execute(
            select(WebsiteGenerationJob)
            .where(WebsiteGenerationJob.business_id == business_id)
            .order_by(WebsiteGenerationJob.created_at.desc())
            .limit(1)
        )
        return result.scalars().first()

    @staticmethod
    async def _load_context(
        session: AsyncSession, business_id: uuid.UUID
    ) -> dict[str, Any]:
        business = await BusinessService.get_by_id(session, business_id)
        profile_result = await session.execute(
            select(BusinessProfile).where(BusinessProfile.business_id == business_id)
        )
        profile = profile_result.scalars().first()
        return {
            "display_name": business.display_name,
            "business_type": business.business_type,
            "tagline": profile.tagline if profile else None,
            "description": profile.description if profile else None,
        }

    @staticmethod
    async def _build_plan(
        session: AsyncSession, business_id: uuid.UUID, business_type: str | None
    ) -> GenerationPlan:
        """The capability inventory and reference composition for this business."""
        from platform_core.services.website_composition import WebsiteCompositionService

        active = await WebsiteCompositionService.active_modules(session, business_id=business_id)
        capability_rows = await WebsiteCompositionService.available_section_types(
            session, business_id=business_id
        )
        return build_plan(
            business_type=business_type,
            active_modules=active,
            capability_rows=capability_rows,
        )

    @staticmethod
    async def _try_ai(
        context: dict[str, Any],
        intake: dict[str, Any] | None = None,
        plan: GenerationPlan | None = None,
    ) -> tuple[dict[str, Any], str, str, dict[str, Any] | None]:
        from platform_core.website.ai_provider import UnavailableAIProvider

        provider = get_ai_provider()
        # Unconfigured provider (no XAI_API_KEY) fails immediately — no retry delay.
        if isinstance(provider, UnavailableAIProvider):
            raise RuntimeError(
                "AI provider not configured (no XAI_API_KEY); use deterministic fallback"
            )
        prompt = build_generation_prompt(context, intake, plan)
        from platform_core.website.ai_provider import AIProviderPermanentError

        last_error: Exception | None = None
        usage: dict[str, Any] | None = None
        for attempt in range(3):
            try:
                raw = await provider.generate_structured(
                    prompt,
                    WEBSITE_GENERATION_SCHEMA,
                    {
                        "purpose": "website.generate",
                        "max_output_tokens": 16384,
                        "schema_name": "website_generation",
                    },
                    timeout_seconds=75,
                )
                usage = getattr(provider, "last_usage", None)
                return (
                    validate_generation_payload(raw),
                    provider.provider_name,
                    provider.model_name,
                    usage if isinstance(usage, dict) else None,
                )
            except AIProviderPermanentError as exc:
                raise RuntimeError(str(exc)) from exc
            except Exception as exc:  # noqa: BLE001 — retry then fallback
                last_error = exc
                if attempt < 2:
                    await asyncio.sleep(min(2**attempt, 8))
        raise RuntimeError(str(last_error or "AI generation failed"))

    @staticmethod
    def _apply_intake_assets(
        payload: dict[str, Any], intake: dict[str, Any] | None
    ) -> dict[str, Any]:
        """Place questionnaire-uploaded images into the generated draft.

        Asset ids are never sent to the model — it has nothing useful to do
        with a UUID. They are stitched in afterwards, onto the first section
        whose SectionType actually has an image slot.
        """
        if not intake:
            return payload
        hero_asset = intake.get("hero_image_asset_id")
        if not hero_asset:
            return payload
        for page in payload.get("pages") or []:
            for section in page.get("sections") or []:
                if section.get("section_type_id") in {"hero", "about"}:
                    content = section.setdefault("content", {})
                    content["image_asset_id"] = str(hero_asset)
                    return payload
        return payload

    # Page types that exist to list what the business sells. The model is told
    # about these but routinely returns the page with only a hero on it.
    _CATALOGUE_PAGE_TYPES = frozenset(
        {"offerings", "services", "menu", "rooms", "plans", "classes", "products"}
    )
    _CATALOGUE_SLUGS = frozenset(
        {"menu", "offerings", "services", "rooms", "plans", "classes", "products", "shop", "courses"}
    )
    _LIST_SECTION_IDS = frozenset(
        {
            "offerings_list",
            "menu_section",
            "plans_section",
            "rooms_section",
            "classes_section",
        }
    )

    @staticmethod
    def _offerings_section(title: str, name: str) -> dict[str, Any]:
        return {
            "section_type_id": "offerings_list",
            "layout_variant": "cards",
            "content": {
                "title": title,
                "subtitle": f"Explore {title.lower()} from {name}",
                "max_items": 12,
            },
            "module_binding": {"module": "offerings-catalog"},
            "is_visible": True,
        }

    @staticmethod
    def _complete_structure(
        payload: dict[str, Any],
        context: dict[str, Any],
        intake: dict[str, Any] | None = None,
        plan: GenerationPlan | None = None,
        used_template: bool = False,
    ) -> dict[str, Any]:
        """Guarantee catalogue structure and type-appropriate theme defaults.

        The AI supplies voice and copy. It is not trusted to remember that a
        Menu page needs a menu, or that theme_hints must carry a personality.

        Completion is itself bounded by the capability inventory. This pass used
        to append the section a page *type* implies without asking whether the
        business has that module — so a Rooms page got a rooms list whether or
        not bookings existed, and the page rendered empty. Adding a section here
        is still adding a section, and the same rule applies.
        """
        name = context.get("display_name") or "this business"
        btype = context.get("business_type")
        # A template's palette is the baseline only when the template was
        # genuinely the reference. The deterministic fallback builds from the
        # business type and never sees a template, so it keeps the business-type
        # palette and is not stamped with a template it did not use.
        from_template = plan is not None and used_template
        baseline = (
            plan.theme_baseline()
            if from_template and plan is not None
            else default_theme_for_type(btype)
        )
        theme = apply_intake_theme(
            {**baseline, **(payload.get("theme_hints") or {})},
            intake,
        )
        payload["theme_hints"] = normalise_theme(
            theme,
            baseline=baseline,
            template_id=plan.template.id if from_template and plan is not None else None,
        )

        allowed = plan.available_ids if plan is not None else None

        def _permitted(section: dict[str, Any] | None) -> dict[str, Any] | None:
            if section is None or allowed is None:
                return section
            return section if section.get("section_type_id") in allowed else None

        for page in payload.get("pages") or []:
            sections = page.get("sections")
            if not isinstance(sections, list):
                continue
            has_list = any(s.get("section_type_id") in WebsiteGenerationService._LIST_SECTION_IDS for s in sections)
            page_type = str(page.get("page_type") or "").lower()
            slug = str(page.get("slug") or "").strip("/").lower()
            title = str(page.get("title") or "What we offer")

            if not has_list:
                typed = _permitted(catalogue_section_for_page(page_type, slug, title, name))
                if typed is not None:
                    sections.append(typed)
                elif (page_type == "home" or slug in {"", "home", "index"}) and (
                    allowed is None or "offerings_list" in allowed
                ):
                    preview = WebsiteGenerationService._offerings_section("What we offer", name)
                    preview["content"]["max_items"] = 6
                    cta_at = next(
                        (
                            i
                            for i, s in enumerate(sections)
                            if s.get("section_type_id") == "cta_band"
                        ),
                        len(sections),
                    )
                    sections.insert(cta_at, preview)
            if (
                page_type == "enquire"
                and (allowed is None or "enquiry_form" in allowed)
                and not any(s.get("section_type_id") == "enquiry_form" for s in sections)
            ):
                sections.append(
                    {
                        "section_type_id": "enquiry_form",
                        "layout_variant": "default",
                        "content": {
                            "title": "Tell us what you need",
                            "subtitle": "A short note is enough — we will come back to you.",
                        },
                        "is_visible": True,
                    }
                )

        navigation = payload.get("navigation")
        if isinstance(navigation, list):
            for item in navigation:
                if not isinstance(item, dict):
                    continue
                path = str(item.get("path") or "/").strip() or "/"
                if path in {"home", "/home"}:
                    path = "/"
                elif not path.startswith("/"):
                    path = f"/{path}"
                item["path"] = path
        return payload

    @staticmethod
    async def _seed_offerings_from_intake(
        session: AsyncSession,
        *,
        business_id: uuid.UUID,
        actor_id: uuid.UUID,
        correlation_id: str,
        business_type: str | None,
        intake: dict[str, Any] | None,
    ) -> None:
        """Persist questionnaire catalogue answers as real Offerings.

        List sections bind to the live catalogue. If the owner typed menu items
        or services during onboarding and we only stuffed them into the prompt,
        the published site would show empty cards. This stays inside OfferingService.
        """
        if not intake:
            return
        from platform_core.models import Offering
        from platform_core.services.offering import OfferingService

        existing = (
            await session.execute(
                select(Offering).where(
                    Offering.business_id == business_id,
                    Offering.deleted_at.is_(None),
                ).limit(1)
            )
        ).scalars().first()
        if existing is not None:
            return

        type_map = {
            "menu_items": "menu_item",
            "services": "service",
            "products": "product",
            "rooms": "accommodation",
            "classes": "class_session"
            if (business_type or "") in {"gym", "studio", "education"}
            else "membership_plan",
        }
        for key, offering_type in type_map.items():
            rows = intake.get(key)
            if not isinstance(rows, list):
                continue
            for row in rows:
                if not isinstance(row, dict):
                    continue
                title = str(row.get("name") or "").strip()
                if not title:
                    continue
                description = str(
                    row.get("description")
                    or row.get("what_to_expect")
                    or row.get("occupancy_hint")
                    or row.get("schedule_hint")
                    or ""
                ).strip() or None
                try:
                    await OfferingService.create_offering(
                        session,
                        business_id=business_id,
                        actor_id=actor_id,
                        correlation_id=correlation_id,
                        payload={
                            "title": title,
                            "description": description,
                            "offering_type": offering_type,
                            "status": "active",
                            "visibility": "public",
                            "price_type": "enquiry",
                        },
                    )
                except Exception:  # noqa: BLE001 — never fail generation on a seed miss
                    continue

    @staticmethod
    async def execute_job(
        session: AsyncSession,
        *,
        generation_job_id: uuid.UUID,
        correlation_id: str,
    ) -> dict[str, Any]:
        result = await session.execute(
            select(WebsiteGenerationJob).where(WebsiteGenerationJob.id == generation_job_id)
        )
        job = result.scalars().first()
        if job is None:
            raise ValidationError("Generation job not found")
        if job.status in {"completed", "fallback_used"}:
            return {"status": job.status, "job_id": str(job.id), "duplicate": True}

        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        job.attempt_count = (job.attempt_count or 0) + 1
        await session.flush()

        website = await WebsiteResolver.resolve_website(session, business_id=job.business_id)
        context = await WebsiteGenerationService._load_context(session, job.business_id)
        intake = job.intake if isinstance(job.intake, dict) else None
        plan = await WebsiteGenerationService._build_plan(
            session, job.business_id, context.get("business_type")
        )

        def _deterministic() -> dict[str, Any]:
            return validate_generation_payload(
                build_deterministic_draft(
                    display_name=context["display_name"],
                    business_type=context.get("business_type"),
                    tagline=context.get("tagline"),
                    description=context.get("description"),
                )
            )

        generated_by = "ai_generation"
        fallback_reason: str | None = None
        try:
            payload, provider_name, model_name, usage = await WebsiteGenerationService._try_ai(
                context, intake, plan
            )
            job.ai_provider = provider_name
            job.model_name = model_name
            if usage:
                job.provider_usage = usage
        except Exception as exc:  # noqa: BLE001
            payload = _deterministic()
            generated_by = "deterministic_fallback"
            fallback_reason = str(exc)
            job.ai_provider = None
            job.model_name = None

        def _finalise(candidate: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, str]]]:
            """Completion, then the capability fence, then the schema — in that order.

            Every draft leaves through here, whichever way it arrived. The fence
            is applied to the answer rather than merely asked for in the prompt,
            and it runs on the deterministic fallback too: that generator builds
            from the business type alone and knows nothing about which modules
            are on, so it is no more entitled to emit a menu than the model is.

            Re-validating last matters because completion and the stitched asset
            id have not been through the schema and content-safety pass that
            `_try_ai` and the fallback already applied to what they produced.
            """
            candidate = WebsiteGenerationService._complete_structure(
                candidate,
                context,
                intake,
                plan,
                # Read at call time, so the recovery path below — which reaches
                # here after `generated_by` has been switched — is correctly
                # treated as a draft that did not come from the template.
                used_template=generated_by == "ai_generation",
            )
            candidate, removed = enforce_capabilities(candidate, plan)
            return validate_generation_payload(candidate), removed

        payload = WebsiteGenerationService._apply_intake_assets(payload, intake)
        payload, dropped = _finalise(payload)
        await WebsiteGenerationService._seed_offerings_from_intake(
            session,
            business_id=job.business_id,
            actor_id=job.triggered_by,
            correlation_id=correlation_id,
            business_type=context.get("business_type"),
            intake=intake,
        )
        # Re-read the live draft from the database. The owner may have edited
        # it on another connection while this job was talking to the model;
        # replacing it now would throw those edits away.
        live_draft = (
            await session.execute(
                select(WebsiteVersion)
                .where(
                    WebsiteVersion.website_id == website.id,
                    WebsiteVersion.version_type == "draft",
                    WebsiteVersion.superseded_at.is_(None),
                )
                .execution_options(populate_existing=True)
            )
        ).scalars().first()
        if (
            live_draft is not None
            and job.started_at is not None
            and live_draft.updated_at is not None
            and live_draft.updated_at > job.started_at
            and live_draft.generation_job_id != job.id
        ):
            job.status = "superseded"
            job.fallback_reason = (
                "The owner edited the draft while generation was running; "
                "the generated draft was not applied."
            )
            job.completed_at = datetime.now(timezone.utc)
            await session.flush()
            return {
                "status": job.status,
                "job_id": str(job.id),
                "preserved_owner_edits": True,
            }

        async def _write(p: dict[str, Any], source: str) -> Any:
            return await WebsiteService.replace_draft_from_generation(
                session,
                business_id=job.business_id,
                website=website,
                payload=p,
                generated_by=source,
                generation_job_id=job.id,
            )

        if generated_by == "ai_generation":
            try:
                # Savepoint: a DB reject of the AI draft (an enum/CHECK the model
                # drifted past) must not poison the session — roll back to here
                # and write the deterministic draft instead.
                async with session.begin_nested():
                    draft = await _write(payload, generated_by)
            except Exception as exc:  # noqa: BLE001
                generated_by = "deterministic_fallback"
                fallback_reason = f"AI draft rejected on write: {exc}"
                job.ai_provider = None
                job.model_name = None
                # Through the same finalisation as everything else. A draft that
                # arrives by the recovery path is still a draft this business
                # has to be entitled to.
                recovered, dropped = _finalise(_deterministic())
                draft = await _write(recovered, generated_by)
        else:
            draft = await _write(payload, generated_by)

        job.fallback_reason = fallback_reason
        job.result_version_id = draft.id
        job.completed_at = datetime.now(timezone.utc)
        job.status = "fallback_used" if generated_by == "deterministic_fallback" else "completed"
        await session.flush()

        await OutboxService.publish(
            session,
            event_type="website.draft_generated",
            payload={
                "business_id": str(job.business_id),
                "website_id": str(website.id),
                "version_id": str(draft.id),
                "generated_by": generated_by,
                "generation_job_id": str(job.id),
                "template_id": plan.template.id if generated_by == "ai_generation" else None,
            },
            business_id=job.business_id,
            correlation_id=correlation_id,
        )
        await AuditService.record(
            session,
            event_type="website.draft_generated",
            actor_identity_id=job.triggered_by,
            actor_context="business",
            business_id=job.business_id,
            resource_type="website_version",
            resource_id=draft.id,
            action="generated",
            after_state={
                "generated_by": generated_by,
                "fallback_reason": fallback_reason,
                "job_status": job.status,
                # Which reference was chosen and why, whether it was actually
                # used, and anything the capability fence removed. "Why does my
                # site look like this" and "where did my menu go" are both
                # support questions with an answer only if it was written down
                # at the time. The template is selected before the model is
                # called, so a fallback draft still records which one it would
                # have personalised.
                "template_id": plan.template.id,
                "template_used": generated_by == "ai_generation",
                "template_reason": plan.template_reason,
                "dropped_sections": dropped or None,
            },
        )
        if generated_by == "deterministic_fallback":
            await OutboxService.publish(
                session,
                event_type="website.generation_failed",
                payload={
                    "business_id": str(job.business_id),
                    "generation_job_id": str(job.id),
                    "fallback_reason": fallback_reason,
                },
                business_id=job.business_id,
                correlation_id=correlation_id,
            )
            await AuditService.record(
                session,
                event_type="website.generation_failed",
                actor_identity_id=job.triggered_by,
                actor_context="business",
                business_id=job.business_id,
                resource_type="website_generation_job",
                resource_id=job.id,
                action="fell_back",
                after_state={"fallback_reason": fallback_reason},
            )
        await AsyncJobService.enqueue(
            session,
            job_type="media.generate_website_images",
            payload={
                "business_id": str(job.business_id),
                "actor_id": str(job.triggered_by),
                "correlation_id": correlation_id,
                "generation_job_id": str(job.id),
            },
            business_id=job.business_id,
        )
        return {
            "status": job.status,
            "job_id": str(job.id),
            "version_id": str(draft.id),
            "generated_by": generated_by,
        }

    @staticmethod
    def serialize_job(job: WebsiteGenerationJob) -> dict[str, Any]:
        return {
            "id": str(job.id),
            "business_id": str(job.business_id),
            "status": job.status,
            "ai_provider": job.ai_provider,
            "model_name": job.model_name,
            "provider_usage": job.provider_usage if isinstance(job.provider_usage, dict) else None,
            "prompt_version": job.prompt_version,
            "attempt_count": job.attempt_count,
            "error_detail": job.error_detail,
            "fallback_reason": job.fallback_reason,
            "intake": job.intake if isinstance(job.intake, dict) else None,
            "result_version_id": str(job.result_version_id) if job.result_version_id else None,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "created_at": job.created_at.isoformat() if job.created_at else None,
        }
