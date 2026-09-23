"""One conversation engine for chat and voice. No DB or HTTP dependencies.

Per owner message: ONE model call returns a TurnIntelligence; Locah validates
and merges it; the discovery planner decides what is still worth knowing and
whether the model's proposed question may be asked; the reply is short enough
to be spoken. Voice calls exactly this through its single tool.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import time
from typing import Any, Protocol

from platform_core.business_type_profiles.registry import BusinessTypeProfileRegistry
from platform_core.interview.conversation import (
    ANYTHING_ELSE,
    LOGO_QUEUED,
    LOGO_UNAVAILABLE,
    LOGO_UPLOAD,
    READY,
    REDIRECT,
    REDUNDANT,
    SYSTEM_PROMPT,
    UNAVAILABLE,
    UNCLEAR,
    _lang,
    accept_answers,
    accept_highlights,
    accept_patterns,
    acknowledgement,
    drafted_parts,
    govern_acknowledgement,
    govern_draft,
    govern_question,
    mark_redundant,
    merge_fact,
)
from platform_core.interview.discovery import (
    TARGETS,
    candidates,
    characteristics,
    choose,
    fallback_question,
    profile_type,
    rank,
    readiness,
    sync_from_facts,
)
from platform_core.interview.models import (
    BusinessBlueprint,
    DraftUpdate,
    ExtractedFact,
    FactKey,
    MediaGenerationRequest,
    Message,
    Question,
    TargetAnswer,
    TargetState,
    TurnIntelligence,
    TurnTelemetry,
    now,
)
from platform_core.logging import get_logger
from platform_core.website.ai_provider import AIModelProvider, get_ai_provider

# Kept for callers that seed a new Blueprint; the planner decides what is
# actually asked.
QUESTIONS = (
    Question(field="description",
             text="Tell me a little about your business — what kind of business is it?",
             reason="Your website needs a truthful introduction."),
)


def _retain_explicit_multilingual_actions(extraction: TurnIntelligence, text: str) -> None:
    """Keep an exact Tamil booking sentence when the extractor overlooks it.

    This is deliberately narrow and quotation-only. It does not translate,
    infer a capability or invent an action; it preserves a sentence that
    explicitly contains both the Tamil-script appointment and booking terms.
    """
    if any(
        item.field == "customer_actions" and item.quote in text
        for item in extraction.facts
    ):
        return
    for sentence in re.findall(r"[^.!?]+[.!?]?", text):
        quote = sentence.strip()
        if re.search(r"அப்பாயிண்ட்மென்ட்|அபாயிண்ட்மென்ட்|முன்பதிவு", quote) and re.search(
            r"புக்|பண்ண|செய்ய", quote
        ):
            extraction.facts.append(
                ExtractedFact(field="customer_actions", quote=quote)
            )
            return


def _remove_superseded_location_echoes(bp: BusinessBlueprint, old_location: str) -> None:
    """Remove an old place from duplicated summary facts after a correction.

    Extractors often quote a rich opening answer both as `description` and as
    dedicated fields. Updating `locations` must not leave the old city visible
    inside that copied description. We retain only an unchanged sentence from
    the owner's earlier evidence; if none survives, the stale summary fact is
    removed and can be asked again.
    """
    if not old_location.strip():
        return
    pattern = re.compile(r"\b" + re.escape(old_location.strip()) + r"\b", re.I)
    for facts in (bp.unconfirmed_facts, bp.known_facts):
        for key, fact in list(facts.items()):
            if key == "locations" or not pattern.search(fact.value):
                continue
            negated_old = re.search(
                r"(?:,\s*)?\bnot\s+" + re.escape(old_location.strip()) + r"\b[.!?]?\s*$",
                fact.value,
                re.I,
            )
            if negated_old:
                survivor = fact.value[: negated_old.start()].strip()
                if survivor:
                    facts[key] = fact.model_copy(
                        update={
                            "value": survivor,
                            "evidence": survivor,
                            "confirmation": "unconfirmed",
                        }
                    )
                    continue
            location_suffix = re.search(
                r"(?:,\s*)?(?:and\s+)?(?:we\s+are\s+)?(?:located|based)\s+in\s+"
                + re.escape(old_location.strip())
                + r"[.!?]?\s*$|\s+in\s+"
                + re.escape(old_location.strip())
                + r"[.!?]?\s*$",
                fact.value,
                re.I,
            )
            if location_suffix:
                survivor = fact.value[: location_suffix.start()].strip().rstrip(",")
                if survivor:
                    facts[key] = fact.model_copy(
                        update={"value": survivor, "evidence": survivor, "confirmation": "unconfirmed"}
                    )
                    continue
            sentences = [
                sentence.strip()
                for sentence in re.findall(r"[^.!?]+[.!?]?", fact.value)
                if sentence.strip() and not pattern.search(sentence)
            ]
            if sentences:
                survivor = max(sentences, key=len)
                facts[key] = fact.model_copy(
                    update={
                        "value": survivor,
                        "evidence": survivor,
                        "confirmation": "unconfirmed",
                    }
                )
            else:
                del facts[key]


class VoiceAdapter(Protocol):
    """A real adapter supplies a final transcript to the SAME turn endpoint.

    No browser speech API or simulated microphone is offered as production voice.
    Transport must not own its own facts, history, completion rules or credentials.
    """
    async def transcribe(self, audio: bytes, *, mime_type: str) -> str: ...
    async def speak(self, text: str) -> bytes: ...


class BusinessInterviewOrchestrator:
    @staticmethod
    def project(bp: BusinessBlueprint, business_type: str | None = None) -> None:
        """Derive everything that follows from what is known — nothing is asked here."""
        sync_from_facts(bp)
        facts = {**bp.known_facts, **bp.unconfirmed_facts}
        bp.business_classification = facts.get("classification")
        for field in ("operating_model", "locations", "offerings", "customer_actions",
                      "operational_characteristics", "brand", "tone", "colours", "website_priorities"):
            setattr(bp, field, facts.get(field))
        bp.website_content = {k: v for k, v in facts.items() if k in {
            "description", "opening_hours", "phone", "email",
        }}
        bp.readiness = readiness(bp, business_type)
        # The few still-open essentials that map onto a business-truth field, so
        # the "save this answer as…" fallback always has somewhere to put it.
        open_fields: list[Question] = []
        for item in rank(bp, business_type):
            fact = item.target.fact
            if fact and fact not in facts and all(q.field != fact for q in open_fields):
                open_fields.append(Question(field=fact, text=fallback_question(
                    item.target.id, bp, bp.language_style), reason=item.target.learn))
        bp.remaining_questions = open_fields[:3]
        sufficient = bp.readiness.ready
        bp.completion_state.sufficient = sufficient
        bp.completion_state.confirmed = sufficient and not bp.unconfirmed_facts
        if bp.completion_state.status != "built":
            bp.completion_state.status = (
                "ready" if bp.completion_state.confirmed else "review" if sufficient else "collecting"
            )
        if sufficient and bp.completion_state.completed_at is None:
            bp.completion_state.completed_at = now()

    @staticmethod
    def confirm(bp: BusinessBlueprint, business_type: str | None = None) -> None:
        for key, fact in bp.unconfirmed_facts.items():
            bp.known_facts[key] = fact.model_copy(update={"confirmation": "confirmed"})
        bp.unconfirmed_facts.clear()
        BusinessInterviewOrchestrator.project(bp, business_type)

    @staticmethod
    def opening_question(bp: BusinessBlueprint) -> str:
        return str(fallback_question("business.identity", bp, bp.language_style))

    @staticmethod
    def payload(bp: BusinessBlueprint, text: str, business_type: str | None) -> dict[str, Any]:
        """Compact structured state for the model — never the transcript."""
        facts = {**bp.known_facts, **bp.unconfirmed_facts}
        profile = BusinessTypeProfileRegistry.get_or_default(profile_type(bp, business_type))
        chars = characteristics(bp, business_type)
        understood = {
            tid: (state.summary or state.quote)[:160]
            for tid, state in bp.discovery.items()
            if state.status in {"answered", "partial"}
        }
        recent = sorted(
            (tid for tid, state in bp.discovery.items() if state.last_asked_turn is not None),
            key=lambda tid: -(bp.discovery[tid].last_asked_turn or 0),
        )[:3]
        wd = bp.website_draft
        locked = [f for f in ("hero_headline", "hero_subheadline", "about", "cta_label")
                  if getattr(wd, f) and getattr(wd, f).provenance in {"owner_edited", "owner_approved"}]
        last_question = next((m.text for m in reversed(bp.messages) if m.role == "assistant"), "")
        return {
            "business_name": bp.identity["display_name"].value if "display_name" in bp.identity else "",
            "profile_hint": {
                "type": profile.display_name,
                "observed": sorted(c for c, how in chars.items() if how == "observed"),
            },
            "known": {k: v.value[:400] for k, v in facts.items()},
            "understood": understood,
            "asked_recently": recent,
            "declined": [tid for tid, s in bp.discovery.items() if s.status in {"declined", "deferred"}],
            "candidates": candidates(bp, business_type),
            "last_question": last_question[:300],
            "last_target": bp.last_asked_target or "",
            "draft": {
                "fields": [f for f in ("hero_headline", "hero_subheadline", "about", "cta_label")
                           if getattr(wd, f)],
                "locked": locked + [f"offering:{o.name}" for o in wd.offerings if o.description
                                    and o.description.provenance in {"owner_edited", "owner_approved"}],
                "offerings": [o.name for o in wd.offerings],
                "owner_claims": [c.claim for c in wd.owner_claims],
            },
            "message": text,
        }

    @staticmethod
    async def turn(
        bp: BusinessBlueprint,
        text: str,
        *,
        field: FactKey | None = None,
        provider: AIModelProvider | None = None,
        business_type: str | None = None,
        image_available: bool = False,
    ) -> BusinessBlueprint:
        bp = bp.model_copy(deep=True)
        text = text.strip()
        if not text:
            raise ValueError("Tell us a little about your business first.")
        started = time.monotonic()
        provider = provider or get_ai_provider()
        fallback: str | None = None
        sync_from_facts(bp)
        was_ready = bp.readiness.ready
        # Explicit edits are user data, not a model task. This is also the offline path.
        if field:
            ti = TurnIntelligence(
                facts=[ExtractedFact(field=field, quote=text, mode="replace")],
                language=bp.language_style,
            )
        else:
            try:
                config: dict[str, object] = {
                    "purpose": "business.interview",
                    "schema_name": "business_interview",
                    "system_prompt": SYSTEM_PROMPT,
                    "max_output_tokens": 4000,
                    "temperature": 0.3,
                }
                override = os.getenv("AI_INTERVIEW_MODEL", "").strip()
                if override:
                    config["model"] = override
                raw = await asyncio.wait_for(provider.generate_structured(
                    json.dumps(BusinessInterviewOrchestrator.payload(bp, text, business_type),
                               ensure_ascii=False),
                    TurnIntelligence.model_json_schema(), config, timeout_seconds=20,
                ), timeout=21)
                ti = TurnIntelligence.model_validate(raw)
                _retain_explicit_multilingual_actions(ti, text)
            except Exception as exc:
                # Do not log raw provider errors or the owner's private business narrative.
                fallback = type(exc).__name__
                ti = TurnIntelligence(language=bp.language_style)
        if not field and fallback is None:
            bp.language_style = ti.language
        _contextual_signals(bp, ti, text)
        # This check applies even if the model misclassifies a common off-topic query.
        off_topic = ti.off_topic or bool(re.search(
            r"\b(weather|tell me a joke|who is the president|who won|cricket match|"
            r"write (?:a|some) code|ignore .*instructions)\b",
            text, re.I,
        ))
        understood = 0
        media_note = ""
        if not off_topic:
            understood += _merge_facts(bp, ti, text, "USER_STATEMENT" if field else "AI_EXTRACTION")
            if field:
                target = next((t for t in TARGETS if t.fact == field), None)
                if target:
                    ti.answered.append(TargetAnswer(target=target.id, quote=text[:600],
                                                    summary=text[:240]))
            understood += accept_answers(bp, ti.answered, text,
                                         source="USER_STATEMENT" if field else "AI_EXTRACTION")
            # Unknown intents are retained as evidence, NEVER interpreted as module IDs.
            for intent in ti.intents:
                if intent.original_request.strip() and intent.original_request in text:
                    if intent not in bp.requested_capabilities:
                        bp.requested_capabilities.append(intent)
                        understood += 1
            bp.requested_capabilities = bp.requested_capabilities[-40:]
            understood += accept_patterns(bp, ti.operating_patterns, text)
            accept_highlights(bp, ti.highlights, text)
            if ti.owner_signal == "redundant":
                mark_redundant(bp)
                understood += 1
            elif ti.owner_signal == "wants_to_finish":
                _defer_open_targets(bp, business_type)
                understood += 1
            media_note = _record_media_intent(bp, ti.media_intent, image_available)
            if media_note:
                understood += 1
            if govern_draft(bp, ti.draft, text):
                understood += 1
        BusinessInterviewOrchestrator.project(bp, business_type)

        style = bp.language_style
        lang = _lang(style)
        if bp.readiness.ready:
            question = (READY[lang].format(drafted=drafted_parts(bp)) if not was_ready
                        else ANYTHING_ELSE[lang])
            asked_target = None
        else:
            asked_target = choose(bp, ti.next_target, business_type)
            question = ""
            if asked_target and asked_target == ti.next_target:
                question = govern_question(ti.next_question, text, bp) or ""
            if asked_target and not question:
                question = fallback_question(asked_target, bp, style)
            if not asked_target:
                question = ANYTHING_ELSE[lang]
        if asked_target:
            state = bp.discovery.setdefault(asked_target, TargetState())
            state.asked += 1
            state.last_asked_turn = bp.turn_count + 1
            if state.status == "open":
                state.status = "asked"
        bp.last_asked_target = asked_target

        if off_topic:
            reply = REDIRECT[lang] + question
        elif fallback and not understood:
            reply = UNAVAILABLE[lang] + question
        elif not understood:
            reply = UNCLEAR[lang] + question
        else:
            ack = (REDUNDANT[lang] if ti.owner_signal == "redundant"
                   and not govern_acknowledgement(ti.acknowledgement, text)
                   else acknowledgement(bp, ti.acknowledgement, text, style))
            reply = " ".join(part for part in (ack, media_note, question) if part)
        bp.messages.extend([Message(role="user", text=text), Message(role="assistant", text=reply)])
        bp.messages = bp.messages[-60:]
        bp.turn_count += 1
        usage = getattr(provider, "last_usage", None) or {}
        bp.last_turn = TurnTelemetry(
            provider="none" if field else provider.provider_name,
            model="deterministic" if field else str(usage.get("model") or provider.model_name),
            latency_ms=int((time.monotonic() - started) * 1000),
            input_tokens=usage.get("prompt_tokens"), output_tokens=usage.get("completion_tokens"),
            cost=usage.get("cost"), fallback_reason=fallback,
        )
        get_logger("business.interview").info(
            "interview.turn", business_id=str(bp.business_id), session_id=str(bp.session_id),
            turn_count=bp.turn_count, language=bp.language_style, next_target=asked_target,
            ready=bp.readiness.ready, **bp.last_turn.model_dump(),
        )
        return bp

    @staticmethod
    async def regenerate_draft(
        bp: BusinessBlueprint,
        field: str,
        offering_name: str = "",
        *,
        provider: AIModelProvider | None = None,
        business_type: str | None = None,
    ) -> BusinessBlueprint:
        """Rewrite one piece of website wording because the owner asked to."""
        from platform_core.interview.website_brief import build_brief

        bp = bp.model_copy(deep=True)
        provider = provider or get_ai_provider()
        wd = bp.website_draft
        facts = {**bp.known_facts, **bp.unconfirmed_facts}
        payload = {
            "business_name": bp.identity["display_name"].value if "display_name" in bp.identity else "",
            "known": {k: v.value[:400] for k, v in facts.items()},
            "brief": build_brief(bp, business_type).model_dump(exclude_defaults=True),
            "rewrite": field if field != "offering" else f"offerings: {offering_name}",
            "current": (getattr(wd, field).text if field != "offering" and getattr(wd, field) else ""),
        }
        prompt = (
            "Rewrite ONE piece of website wording for this small business: the field named in "
            "`rewrite`. Return JSON with only that field filled (for an offering, one item with "
            "the same name and a new one-sentence description). Make it clearly different from "
            "`current`, specific and warm. Never add facts the owner did not give — no prices, "
            "hours, years, certifications, 'fresh', 'farm', 'organic', 'premium', delivery, "
            "ratings — except lines in brief.owner_claims. No 'Welcome to'."
        )
        try:
            raw = await asyncio.wait_for(provider.generate_structured(
                json.dumps(payload, ensure_ascii=False), DraftUpdate.model_json_schema(),
                {"purpose": "business.interview", "system_prompt": prompt,
                 "max_output_tokens": 1500, "temperature": 0.7},
                timeout_seconds=20,
            ), timeout=21)
            proposal = DraftUpdate.model_validate(raw)
        except Exception as exc:
            raise ValueError("Locah couldn't rewrite that just now — try again in a moment.") from exc
        only = DraftUpdate()
        if field == "offering":
            only.offerings = [o for o in proposal.offerings if o.name.casefold() == offering_name.casefold()]
            for offering in wd.offerings:
                if offering.name.casefold() == offering_name.casefold() and offering.description:
                    offering.description = offering.description.model_copy(update={"provenance": "ai_suggestion"})
        else:
            setattr(only, field, getattr(proposal, field))
            wd.dismissed = [f for f in wd.dismissed if f != field]
            current = getattr(wd, field)
            if current is not None:  # the owner asked, so their lock is lifted for this field
                setattr(wd, field, current.model_copy(update={"provenance": "ai_suggestion"}))
        govern_draft(bp, only, "")
        return bp


_GENERATE = re.compile(r"\b(generate|create|make|design|draw)\b.{0,20}\b(one|it|logo|for me)?", re.I)
_DECLINE = re.compile(r"^\s*(no|nope|skip|later|not now|don'?t know|no idea|nothing|illa|venaam)\b", re.I)


def _contextual_signals(bp: BusinessBlueprint, ti: TurnIntelligence, text: str) -> None:
    """Read a short reply in the light of the question it answers.

    "Generate one" means nothing on its own and everything after "should I
    create a logo?". The model usually gets this; this makes sure of it.
    """
    last = bp.last_asked_target
    if last == "media.logo" and ti.media_intent == "none" and _GENERATE.search(text):
        ti.media_intent = "generate_logo"
    if last and _DECLINE.search(text) and len(text) < 40 and not ti.answered and ti.media_intent == "none":
        ti.answered.append(TargetAnswer(target=last, status="declined"))


def _merge_facts(bp: BusinessBlueprint, ti: TurnIntelligence, text: str, source: str) -> int:
    accepted = 0
    # A clear spoken "Coimbatore, not Chennai" is a location correction even
    # when the extractor filed the sentence as a new description and the old
    # city lived only inside that description.
    correction = re.search(
        r"\b(?P<new>[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*,\s*not\s+"
        r"(?P<old>[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b",
        text,
    )
    if correction:
        _remove_superseded_location_echoes(bp, correction.group("old"))
        ti.facts = [item for item in ti.facts if item.field != "locations"]
        ti.facts.append(ExtractedFact(field="locations", quote=correction.group("new")))
    for item in ti.facts:
        if item.quote not in text:
            continue
        if correction and item.field == "description" and correction.group(0) in item.quote:
            prefix = item.quote.split(", not " + correction.group("old"), 1)[0]
            prefix = re.sub(r"^(?:Correction,\s*|Actually\s+)", "", prefix, flags=re.I)
            if " is in " not in prefix or prefix not in text:
                continue
            item = ExtractedFact(field="description", quote=prefix, mode="replace")
        # An unsupported workflow (live GPS tracking) stays as capability-gap
        # evidence and never becomes website content.
        if re.search(
            r"\b(?:gps|live\s+(?:\w+\s+)?track\w*|track\w*\s+live|courier.{0,40}\bmap)\b",
            item.quote, re.I,
        ):
            continue
        # Where the business delivers is not where it is: "we deliver around
        # Nookampalayam and Perumbakkam" once became part of the shop's address.
        if item.field == "locations" and (
            any(a.target == "fulfilment.area" and item.quote.casefold() in (a.quote or "").casefold()
                for a in ti.answered)
            or re.search(r"\b(?:deliver\w*|ship\w*)\b[^.]{0,60}" + re.escape(item.quote), text, re.I)
        ):
            continue
        previous = bp.unconfirmed_facts.get(item.field) or bp.known_facts.get(item.field)
        if (
            item.field == "locations" and item.mode == "replace" and previous
            and previous.value.casefold() != item.quote.casefold()
        ):
            _remove_superseded_location_echoes(bp, previous.value)
        if merge_fact(bp, item.field, item.quote, item.mode, source):
            accepted += 1
    return accepted


def _defer_open_targets(bp: BusinessBlueprint, business_type: str | None) -> None:
    """"That's all, build it" — the owner decides when enough is enough."""
    for item in rank(bp, business_type):
        state = bp.discovery.setdefault(item.target.id, TargetState())
        if state.status in {"open", "asked"}:
            state.status = "deferred"


def _record_media_intent(bp: BusinessBlueprint, intent: str, image_available: bool) -> str:
    """Record a request to draw something, and say what will happen — specifically."""
    name = bp.identity["display_name"].value if "display_name" in bp.identity else "your business"
    lang = _lang(bp.language_style)
    logo = bp.discovery.setdefault("media.logo", TargetState())
    if intent == "will_upload_logo":
        logo.status = "answered"
        logo.summary = "Will upload their own logo."
        return str(LOGO_UPLOAD[lang])
    if intent == "no_logo":
        logo.status = "declined"
        return ""
    role = {"generate_logo": "logo", "generate_hero": "hero"}.get(intent)
    if role is None:
        return ""
    if role == "logo":
        logo.status = "answered"
        logo.summary = "Wants Locah to create a logo."
    if any(m.role == role and m.source == "USER_UPLOAD" for m in bp.media_assets):
        return ""
    existing = next((r for r in bp.media_generation_requests if r.role == role), None)
    if existing and existing.status in {"requested", "queued", "ready"}:
        return LOGO_QUEUED[lang].format(name=name) if role == "logo" else ""
    bp.media_generation_requests = [r for r in bp.media_generation_requests if r.role != role]
    if image_available:
        bp.media_generation_requests.append(MediaGenerationRequest(role=role, status="requested"))
        if role == "logo":
            bp.logo_state = "generation_requested"
        return LOGO_QUEUED[lang].format(name=name) if role == "logo" else ""
    bp.media_generation_requests.append(MediaGenerationRequest(
        role=role, status="unavailable",
        reason="Image generation isn't available on this environment right now.",
    ))
    return LOGO_UNAVAILABLE[lang] if role == "logo" else ""
