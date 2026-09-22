"""Realtime voice for the Business Interview — transport only.

Voice is a second way into the interview that already exists, not a second
interview. Nothing here extracts facts, decides completion, resolves a
capability or recommends a module: the browser hands every spoken utterance to
the same `POST /v1/b/{id}/interview` command the typed form posts, and the
answer that comes back is the authority for what Locah says next. The realtime
model supplies ears, a voice and turn-taking. It does not supply truth.

Two things live here because they must be server-side.

The permanent xAI key is one. The browser cannot send an Authorization header
on a WebSocket, and it must never hold the account key anyway, so the key is
exchanged here for a short-lived client secret that is useless for anything
else and expires in minutes.

The session instruction is the other. Grok's behaviour is versioned in this
repository rather than typed into a console — this team cannot use console
agents at all (`/v1/agents` answers 403), and a personality that lives in a
web form is a personality nobody can review, diff or roll back.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

from platform_core.interview.models import BusinessBlueprint
from platform_core.logging import get_logger

_log = get_logger("interview.voice")

_CLIENT_SECRETS_URL = "https://api.x.ai/v1/realtime/client_secrets"
REALTIME_URL = "wss://api.x.ai/v1/realtime"

# What the account actually serves, confirmed against `session.created`:
# model `grok-voice-think-fast-2.0`, voice `xai_ara`, and turn detection off
# until the session asks for it. The fast voice model is the deliberate choice
# — the text interview already showed the non-reasoning model was both quicker
# and more accurate at structured extraction, and here the thinking that
# matters happens in Locah's own deterministic code, not in the model.
VOICE_MODEL = os.getenv("XAI_VOICE_MODEL", "grok-voice-think-fast-2.0")
VOICE_NAME = os.getenv("XAI_VOICE", "xai_ara")

# Long enough to open a socket on a slow phone, short enough to be worthless if
# it leaks. The secret is single-use in practice: a second connection with the
# same value is refused, so one session means one mint.
SECRET_TTL_SECONDS = 120

# The one tool Grok may call. It carries an utterance to Locah and returns what
# Locah decided; it cannot enable a module, write a fact or build a website,
# because it is executed by the browser against the ordinary authenticated
# interview endpoint with the owner's own session.
VOICE_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "name": "process_business_interview_turn",
        "description": (
            "Send what the owner just said to Locah, and receive the next thing to say. "
            "Call this for every substantive utterance about their business. The reply "
            "tells you what Locah understood and the single next question to ask."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "transcript": {
                    "type": "string",
                    "description": "Exactly what the owner said, transcribed verbatim.",
                }
            },
            "required": ["transcript"],
        },
    }
]


def is_configured() -> bool:
    """Whether voice can work at all, without revealing anything about the key."""
    return bool(os.getenv("XAI_API_KEY", "").strip()) and os.getenv(
        "AI_PROVIDER", "xai"
    ).strip().lower() in {"xai", "grok"}


def _compact_state(bp: BusinessBlueprint) -> str:
    """The Blueprint as the model needs to hear it, and no more.

    Grok is told what is already known so it does not ask again, and what is
    missing so it asks the right thing. It is not told the module registry, the
    website schema, the section types or the transcript — none of which it
    decides, and all of which would cost tokens on every session.
    """
    facts = {**bp.known_facts, **bp.unconfirmed_facts}
    lines: list[str] = []
    name = bp.identity.get("display_name")
    if name:
        lines.append(f"Business name: {name.value}")
    if facts:
        lines.append("Already known — never ask about these again:")
        lines += [f"  - {key.replace('_', ' ')}: {fact.value[:220]}" for key, fact in facts.items()]
    else:
        lines.append("Nothing known yet.")
    if bp.completion_state.sufficient:
        lines.append(
            "ENOUGH INFORMATION HAS BEEN COLLECTED. Stop interviewing. Say one short "
            "sentence such as 'I've got enough to build a strong first version', then "
            "stop asking setup questions and let them review on screen."
        )
    elif bp.remaining_questions:
        question = bp.remaining_questions[0]
        lines.append(f"Still needed: {question.field.replace('_', ' ')}.")
        lines.append(f"Ask something close to: \"{question.text}\"")
    return "\n".join(lines)


def build_session_instructions(bp: BusinessBlueprint) -> str:
    """Locah's voice, and the fence around it."""
    return f"""You are Locah, helping a small business owner set their business up by talking.

Sound like a warm, capable friend who happens to be very good at this. Relaxed,
curious, unhurried, never impressed by yourself. Short sentences. One question at
a time, and only when you actually need the answer.

Never say things like "please provide your business description". Say "tell me a
little about what you do". When you already have context, use it — "so most people
find you through the showroom first?" is better than starting again.

Do not flatter. Do not say "great question" or "amazing". Do not summarise back
everything they said. Do not read lists aloud. Do not ask two things at once.

HOW THIS WORKS
Every time the owner says something about their business, call the tool
`process_business_interview_turn` with exactly what they said. The tool is Locah
itself; it decides what was understood and what to ask next. Then say the question
it gives you, in your own natural words, with at most a few words of glue in front
of it — "got it", "right", "okay".

Never invent a different question. Never ask several of your own questions instead
of the one that comes back. Never promise the platform can do something: if the
owner asks for something and the tool says it is not supported, say briefly that
Locah cannot do that part today and carry on. You do not decide what the platform
can do.

If the tool says enough information has been collected, stop interviewing.

If the owner asks about something unrelated — the weather, sport, a general
question — do not answer it. Say in one friendly sentence that you are here to get
their business set up, and return to the question you were on.

The owner may speak English, Indian English, or mix in another language such as
Tamil. That is normal. Understand them and pass on a faithful transcript.

CURRENT STATE
{_compact_state(bp)}"""


def session_config(bp: BusinessBlueprint) -> dict[str, Any]:
    """The `session.update` payload the browser sends once the socket opens.

    Server-side VAD is what makes this a conversation rather than a walkie-talkie:
    the model decides when the owner has finished a thought, and the owner can cut
    in while Locah is talking.
    """
    return {
        "instructions": build_session_instructions(bp),
        "voice": VOICE_NAME,
        "modalities": ["audio", "text"],
        "audio": {
            "input": {
                "format": {"type": "audio/pcm", "rate": 24000},
                # xAI emits one cumulative `updated` stream followed by one
                # authoritative `completed` event for this model. The legacy
                # flat `whisper-1` setting emitted repeated partial
                # `completed` events, which made one utterance look like many.
                "transcription": {"model": "grok-transcribe"},
            },
            "output": {"format": {"type": "audio/pcm", "rate": 24000}},
        },
        "turn_detection": {
            "type": "server_vad",
            "threshold": 0.5,
            "prefix_padding_ms": 300,
            "silence_duration_ms": 700,
        },
        "tools": VOICE_TOOLS,
        "tool_choice": "auto",
    }


class VoiceSessionError(RuntimeError):
    """Voice could not start. Onboarding continues in chat regardless."""


async def mint_client_secret(*, timeout_seconds: int = 12) -> dict[str, Any]:
    """Exchange the account key for a short-lived browser credential.

    The permanent key never leaves this process. Nothing about the response is
    persisted — it expires on its own in a couple of minutes, and storing it
    would only create somewhere for it to be stolen from.
    """
    api_key = os.getenv("XAI_API_KEY", "").strip()
    if not api_key:
        raise VoiceSessionError("Voice is not configured on this server.")
    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.post(
                _CLIENT_SECRETS_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "expires_after": {"anchor": "created_at", "seconds": SECRET_TTL_SECONDS}
                },
            )
    except Exception as exc:  # noqa: BLE001 — network failure is a voice failure, not an outage
        _log.warning("interview.voice.mint_failed", error=type(exc).__name__)
        raise VoiceSessionError("Could not reach the voice service.") from exc

    if response.status_code >= 400:
        # Deliberately no response body in the log: a rejected credential reply
        # can echo the credential back.
        _log.warning("interview.voice.mint_rejected", status_code=response.status_code)
        raise VoiceSessionError("The voice service refused the request.")

    data = response.json()
    secret = data.get("value")
    if not isinstance(secret, str) or not secret:
        raise VoiceSessionError("The voice service returned no credential.")
    return {"client_secret": secret, "expires_at": data.get("expires_at")}
