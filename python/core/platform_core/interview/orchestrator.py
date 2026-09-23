"""One state machine for chat and future voice. No DB or HTTP dependencies."""
from __future__ import annotations

import asyncio
import json
import os
import re
import time
from typing import Protocol

from platform_core.interview.conversation import (
    REQUIRED,
    SYSTEM_PROMPT,
    TEMPLATES,
    accept_highlights,
    accept_patterns,
    ask_order,
    compose_reply,
    merge_fact,
)
from platform_core.interview.models import (
    BusinessBlueprint,
    ExtractedFact,
    Extraction,
    FactKey,
    MediaGenerationRequest,
    Message,
    Question,
    TurnTelemetry,
    now,
)
from platform_core.logging import get_logger
from platform_core.website.ai_provider import AIModelProvider, get_ai_provider

# Which model extracts is the provider's decision, keyed by purpose
# ("business.interview"), so no vendor model name lives in business logic.

QUESTIONS = (
    Question(field="description", text=TEMPLATES["description"]["en"],
             reason="Your website needs a truthful introduction."),
    Question(field="offerings", text=TEMPLATES["offerings"]["en"],
             reason="Use your actual products or services, never invented examples."),
    Question(field="customer_actions", text=TEMPLATES["customer_actions"]["en"],
             reason="Recommend only the tools needed for your chosen customer journey."),
)


def _retain_explicit_multilingual_actions(extraction: Extraction, text: str) -> None:
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
    def project(bp: BusinessBlueprint) -> None:
        facts = {**bp.known_facts, **bp.unconfirmed_facts}
        bp.business_classification = facts.get("classification")
        for field in ("operating_model", "locations", "offerings", "customer_actions",
                      "operational_characteristics", "brand", "tone", "colours", "website_priorities"):
            setattr(bp, field, facts.get(field))
        bp.website_content = {k: v for k, v in facts.items() if k in {
            "description", "opening_hours", "phone", "email",
        }}
        bp.remaining_questions = [q for q in QUESTIONS if q.field not in facts]
        sufficient = not bp.remaining_questions
        bp.completion_state.sufficient = sufficient
        bp.completion_state.confirmed = sufficient and not bp.unconfirmed_facts
        if bp.completion_state.status != "built":
            bp.completion_state.status = (
                "ready" if bp.completion_state.confirmed else "review" if sufficient else "collecting"
            )
        if sufficient and bp.completion_state.completed_at is None:
            bp.completion_state.completed_at = now()

    @staticmethod
    def confirm(bp: BusinessBlueprint) -> None:
        for key, fact in bp.unconfirmed_facts.items():
            bp.known_facts[key] = fact.model_copy(update={"confirmation": "confirmed"})
        bp.unconfirmed_facts.clear()
        BusinessInterviewOrchestrator.project(bp)

    @staticmethod
    async def turn(
        bp: BusinessBlueprint, text: str, *, field: FactKey | None = None,
        provider: AIModelProvider | None = None,
    ) -> BusinessBlueprint:
        bp = bp.model_copy(deep=True)
        text = text.strip()
        if not text:
            raise ValueError("Tell us a little about your business first.")
        started = time.monotonic()
        provider = provider or get_ai_provider()
        fallback: str | None = None
        facts_before = {**bp.known_facts, **bp.unconfirmed_facts}
        was_sufficient = all(required in facts_before for required in REQUIRED)
        # Explicit edits are user data, not a model task. This is also the offline path.
        if field:
            extraction = Extraction(
                facts=[ExtractedFact(field=field, quote=text, mode="replace")],
                language=bp.language_style,
            )
        else:
            try:
                last_question = next(
                    (m.text for m in reversed(bp.messages) if m.role == "assistant"), ""
                )
                # Compact structured state, never the transcript: what is known,
                # what is still worth asking, and the one thing just said.
                payload = {
                    "business_name": bp.identity["display_name"].value
                    if "display_name" in bp.identity else "",
                    "known": {k: v.value for k, v in facts_before.items()},
                    "ask_order": ask_order(bp),
                    "last_question": last_question[:400],
                    "message": text,
                }
                config: dict[str, object] = {
                    "purpose": "business.interview",
                    "schema_name": "business_interview",
                    "system_prompt": SYSTEM_PROMPT,
                    "max_output_tokens": 3000,
                    "temperature": 0.2,
                }
                override = os.getenv("AI_INTERVIEW_MODEL", "").strip()
                if override:
                    config["model"] = override
                raw = await asyncio.wait_for(provider.generate_structured(
                    json.dumps(payload, ensure_ascii=False),
                    Extraction.model_json_schema(), config, timeout_seconds=12,
                ), timeout=13)
                extraction = Extraction.model_validate(raw)
                _retain_explicit_multilingual_actions(extraction, text)
            except Exception as exc:
                # Do not log raw provider errors or the owner's private business narrative.
                fallback = type(exc).__name__
                extraction = Extraction(language=bp.language_style)
        if not field:
            bp.language_style = extraction.language
        # This check applies even if the model misclassifies a common off-topic query.
        off_topic = extraction.off_topic or bool(re.search(
            r"\b(weather|tell me a joke|who is the president|who won|cricket match|"
            r"write (?:a|some) code|ignore .*instructions)\b",
            text, re.I,
        ))
        accepted = 0
        if not off_topic:
            # A clear spoken "Coimbatore, not Chennai" is a location
            # correction even when the extractor filed the sentence as a new
            # description and the old city lived only inside that description.
            # Both city names are direct substrings of the owner's message.
            correction = re.search(
                r"\b(?P<new>[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*,\s*not\s+"
                r"(?P<old>[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b",
                text,
            )
            if correction:
                _remove_superseded_location_echoes(bp, correction.group("old"))
                extraction.facts = [
                    item for item in extraction.facts
                    if item.field != "locations"
                ]
                extraction.facts.append(
                    ExtractedFact(field="locations", quote=correction.group("new"))
                )
            for item in extraction.facts:
                if item.quote not in text:
                    continue
                if correction and item.field == "description" and correction.group(0) in item.quote:
                    prefix = item.quote.split(", not " + correction.group("old"), 1)[0]
                    prefix = re.sub(r"^(?:Correction,\s*|Actually\s+)", "", prefix, flags=re.I)
                    if " is in " not in prefix or prefix not in text:
                        continue
                    item = ExtractedFact(field="description", quote=prefix, mode="replace")
                # A model can misfile an unsupported workflow as an offering or
                # visitor action. Keep the owner's words in the conversation for
                # capability-gap evidence, but never replace a real business fact
                # or put the unsupported workflow into website content.
                if re.search(
                    r"\b(?:gps|live\s+(?:\w+\s+)?track\w*|track\w*\s+live|courier.{0,40}\bmap)\b",
                    item.quote,
                    re.I,
                ):
                    continue
                previous = bp.unconfirmed_facts.get(item.field) or bp.known_facts.get(item.field)
                if (
                    item.field == "locations"
                    and item.mode == "replace"
                    and previous
                    and previous.value.casefold() != item.quote.casefold()
                ):
                    _remove_superseded_location_echoes(bp, previous.value)
                if merge_fact(
                    bp, item.field, item.quote, item.mode,
                    "USER_STATEMENT" if field else "AI_EXTRACTION",
                ):
                    accepted += 1
            # Unknown intents are retained as evidence, NEVER interpreted as module IDs.
            for intent in extraction.intents:
                if intent.original_request in text and intent.original_request.strip():
                    if intent not in bp.requested_capabilities:
                        bp.requested_capabilities.append(intent)
            bp.requested_capabilities = bp.requested_capabilities[-40:]
            accept_patterns(bp, extraction.operating_patterns, text)
            accept_highlights(bp, extraction.highlights, text)
            _record_asset_request(bp, extraction.asset_request)
        BusinessInterviewOrchestrator.project(bp)
        reply = compose_reply(
            bp,
            extraction,
            heard=text,
            off_topic=off_topic,
            accepted=accepted,
            became_sufficient=bp.completion_state.sufficient and not was_sufficient,
        )
        bp.messages.extend([Message(role="user", text=text), Message(role="assistant", text=reply)])
        bp.messages = bp.messages[-40:]
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
            turn_count=bp.turn_count, language=bp.language_style,
            **bp.last_turn.model_dump(),
        )
        return bp


def _record_asset_request(bp: BusinessBlueprint, request: str) -> None:
    """The owner asked Locah to draw something. Queued for build, never run now.

    Generation happens only for a business that actually builds, so an owner who
    says "yes, make me a logo" and then leaves has cost nothing. A real upload
    always wins: asking to draw a logo after attaching one changes nothing.
    """
    role = {"generate_logo": "logo", "generate_hero": "hero"}.get(request)
    if role is None:
        return
    if any(media.role == role for media in bp.media_assets):
        return
    if any(existing.role == role for existing in bp.media_generation_requests):
        return
    bp.media_generation_requests.append(MediaGenerationRequest(role=role, status="requested"))
    if role == "logo":
        bp.logo_state = "generation_requested"
