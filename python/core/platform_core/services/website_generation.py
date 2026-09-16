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
from platform_core.models import BusinessProfile, WebsiteGenerationJob
from platform_core.resolvers.website_resolver import WebsiteResolver
from platform_core.services.async_jobs import AsyncJobService
from platform_core.services.audit import AuditService
from platform_core.services.business import BusinessService
from platform_core.services.outbox import OutboxService
from platform_core.services.website import WebsiteService
from platform_core.validation.website import validate_generation_payload
from platform_core.website.ai_provider import get_ai_provider
from platform_core.website.fallback_generator import build_deterministic_draft
from platform_core.website.questionnaire import build_intake_brief, validate_intake
from platform_core.website.section_registry import SECTION_CATALOGUE_PROMPT, WEBSITE_GENERATION_SCHEMA


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
            prompt_version="v1",
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
    async def _try_ai(
        context: dict[str, Any], intake: dict[str, Any] | None = None
    ) -> tuple[dict[str, Any], str, str]:
        from platform_core.website.ai_provider import UnavailableAIProvider

        provider = get_ai_provider()
        # Unconfigured provider (no XAI_API_KEY) fails immediately — no retry delay.
        if isinstance(provider, UnavailableAIProvider):
            raise RuntimeError(
                "AI provider not configured (no XAI_API_KEY); use deterministic fallback"
            )
        prompt = (
            f"Generate a structured multi-page business website draft for "
            f"{context['display_name']} ({context.get('business_type') or 'business'}).\n"
            "Write real, specific, publishable copy in the business's own voice — "
            "no lorem ipsum, no placeholders, no bracketed instructions. Produce 3-5 "
            "pages. Every page needs at least a hero plus one or two more sections. "
            "Do not invent navigation, cart, checkout, or booking behaviour — content only.\n\n"
            f"{SECTION_CATALOGUE_PROMPT}"
        )
        if context.get("tagline"):
            prompt += f"\nTagline: {context['tagline']}."
        if context.get("description"):
            prompt += f"\nAbout: {context['description']}."
        prompt += build_intake_brief(context, intake)
        from platform_core.website.ai_provider import AIProviderPermanentError

        last_error: Exception | None = None
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
                    # A full multi-page site is a big generation; allow headroom.
                    timeout_seconds=75,
                )
                return (
                    validate_generation_payload(raw),
                    provider.provider_name,
                    provider.model_name,
                )
            except AIProviderPermanentError as exc:
                # A rejected key or unknown model answers the same way every
                # time. Retrying it just makes the owner wait ~15s longer for
                # the deterministic draft they were always going to get.
                raise RuntimeError(str(exc)) from exc
            except Exception as exc:  # noqa: BLE001 — retry then fallback
                last_error = exc
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
        {"menu", "offerings", "services", "rooms", "plans", "classes", "products", "shop"}
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
            # Bound to the module, not to generated copy — the section renders
            # the Business's real catalogue and stays correct as it changes.
            "module_binding": {"module": "offerings-catalog"},
            "is_visible": True,
        }

    @staticmethod
    def _complete_structure(
        payload: dict[str, Any], context: dict[str, Any]
    ) -> dict[str, Any]:
        """Guarantee the structure the model is unreliable about.

        The AI supplies voice and copy; it must not be trusted to remember that
        a Menu page needs a menu on it. Any page whose type or slug says it
        lists the catalogue gets a module-bound offerings section if the model
        omitted one, and the home page gets a preview of the catalogue so the
        first thing a visitor sees is what the business actually sells.
        """
        name = context.get("display_name") or "this business"
        for page in payload.get("pages") or []:
            sections = page.get("sections")
            if not isinstance(sections, list):
                continue
            has_offerings = any(
                s.get("section_type_id") == "offerings_list" for s in sections
            )
            if has_offerings:
                continue
            page_type = str(page.get("page_type") or "").lower()
            slug = str(page.get("slug") or "").strip("/").lower()
            title = str(page.get("title") or "What we offer")

            if (
                page_type in WebsiteGenerationService._CATALOGUE_PAGE_TYPES
                or slug in WebsiteGenerationService._CATALOGUE_SLUGS
            ):
                sections.append(WebsiteGenerationService._offerings_section(title, name))
            elif page_type == "home" or slug in {"", "home", "index"}:
                # Sits after the hero, before any closing CTA band.
                preview = WebsiteGenerationService._offerings_section(
                    "What we offer", name
                )
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
        return payload

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
            payload, provider_name, model_name = await WebsiteGenerationService._try_ai(
                context, intake
            )
            job.ai_provider = provider_name
            job.model_name = model_name
        except Exception as exc:  # noqa: BLE001
            payload = _deterministic()
            generated_by = "deterministic_fallback"
            fallback_reason = str(exc)
            job.ai_provider = None
            job.model_name = None

        payload = WebsiteGenerationService._apply_intake_assets(payload, intake)
        payload = WebsiteGenerationService._complete_structure(payload, context)
        # Re-validate: the stitched asset id and the completion pass have not
        # been through the schema + content-safety pass that _try_ai / the
        # fallback already applied.
        payload = validate_generation_payload(payload)

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
                draft = await _write(_deterministic(), generated_by)
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
