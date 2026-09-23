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
from datetime import datetime, timedelta, timezone
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
                    "description": (
                        "Exactly what the owner said, transcribed verbatim. English words "
                        "in English letters, Tamil words in Tamil script."
                    ),
                }
            },
            "required": ["transcript"],
        },
    }
]


def is_configured() -> bool:
    """Whether voice can work at all, without revealing anything about the key."""
    provider = os.getenv("VOICE_PROVIDER", "gemini").strip().lower() or "gemini"
    if provider == "gemini":
        return bool(os.getenv("GEMINI_API_KEY", "").strip())
    return provider in {"xai", "grok"} and bool(os.getenv("XAI_API_KEY", "").strip())


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
    lines.append(f"How the owner has been talking so far: {bp.language_style}")
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
    else:
        understood = [
            f"  - {tid}: {(state.summary or state.quote)[:160]}"
            for tid, state in bp.discovery.items() if state.status in {"answered", "partial"}
        ]
        if understood:
            lines.append("Also understood:")
            lines += understood[:12]
        # The next question always comes back from the tool; the voice never
        # chooses one. Opening a session, it asks the tool's last question.
        last = next((m.text for m in reversed(bp.messages) if m.role == "assistant"), "")
        if last:
            lines.append(f"Locah's last question was: \"{last[:240]}\"")
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
Every time the owner says something about their business, you may first say one or
two words so they know you heard — "Seri.", "Okay.", "Got it." — and nothing more.
Then call the tool `process_business_interview_turn` with exactly what they said,
verbatim, in the language they said it. The tool is Locah itself; it decides what
was understood and what to ask next, and it returns `say`. Speak `say` naturally,
as your own words, without changing its meaning and without adding questions. Do
not ask anything before the tool answers.

Never invent a different question. Never ask several of your own questions instead
of the one that comes back. Never promise the platform can do something: if the
owner asks for something and the tool says it is not supported, say briefly that
Locah cannot do that part today and carry on. You do not decide what the platform
can do.

If the tool says enough information has been collected, stop interviewing.

If the owner asks about something unrelated — the weather, sport, a general
question — do not answer it. Say in one friendly sentence that you are here to get
their business set up, and return to the question you were on.

The owner may speak English, Indian English, Tamil, or mix Tamil and English the
way people in Tamil Nadu actually talk ("WhatsApp pannitu showroom-ku varuvanga").
That is normal. Mirror them: if they mix, you may mix; if they switch to English,
follow. Do not over-do Tamil to show off, and never make them feel they should
speak formally. Pass on a faithful transcript, never a translation — and write
each word in the script it was spoken in: English words such as "custom
wardrobes" or "WhatsApp" in English letters, Tamil words in Tamil script. Those
words become the owner's website, and "கஸ்டம் வார்ட்ரோப்ஸ்" is not how they
would write "custom wardrobes".

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


# ---------------------------------------------------------------- providers
#
# Voice has its own provider switch because the realtime products differ far
# more than the text APIs do. Both paths share the same instructions, the same
# single tool and the same Blueprint; only the wire protocol differs.

GEMINI_LIVE_MODEL = os.getenv("GEMINI_LIVE_MODEL", "gemini-3.8-live")
GEMINI_VOICE_NAME = os.getenv("GEMINI_VOICE", "Kore")
_GEMINI_TOKENS_URL = "https://generativelanguage.googleapis.com/v1beta/auth_tokens"
GEMINI_LIVE_URL = (
    "wss://generativelanguage.googleapis.com/ws/"
    "google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContentConstrained"
)
# The owner must open the socket within a minute of asking; the session itself
# may then run long enough for a relaxed conversation.
GEMINI_NEW_SESSION_SECONDS = 60
GEMINI_SESSION_SECONDS = 30 * 60


def voice_provider() -> str:
    """Which realtime provider is configured. Gemini unless told otherwise."""
    return os.getenv("VOICE_PROVIDER", "gemini").strip().lower() or "gemini"


def _gemini_tools() -> list[dict[str, Any]]:
    """The same single tool, in Gemini's declaration shape."""
    tool = VOICE_TOOLS[0]
    return [{
        "functionDeclarations": [{
            "name": tool["name"],
            "description": tool["description"],
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "transcript": {
                        "type": "STRING",
                        "description": (
                            "Exactly what the owner said, verbatim, never translated. "
                            "English words in English letters, Tamil words in Tamil script."
                        ),
                    }
                },
                "required": ["transcript"],
            },
        }]
    }]


def gemini_setup(bp: BusinessBlueprint) -> dict[str, Any]:
    """The Live setup, locked into the ephemeral token itself.

    Because the token carries this setup, a browser that tampers with its own
    copy cannot swap Locah's instructions or add a tool — the server enforces
    what was minted. `gemini-3.8-live` takes no thinking configuration and picks
    the spoken language automatically, which is what lets an owner move between
    Tamil and English mid-sentence.
    """
    return {
        "model": f"models/{GEMINI_LIVE_MODEL}",
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": GEMINI_VOICE_NAME}}
            },
        },
        "systemInstruction": {"parts": [{"text": build_session_instructions(bp)}]},
        "tools": _gemini_tools(),
        # Server-side activity detection: the owner can cut in at any moment
        # (start sensitivity high), but a turn ends only after a real pause.
        # With end sensitivity high and 650 ms, the live test cut an owner off
        # at the full stop between two sentences — the second half arrived as
        # its own garbled turn. People describing their business pause to
        # think; a clipped sentence costs far more than 250 ms of waiting.
        "realtimeInputConfig": {
            "automaticActivityDetection": {
                "startOfSpeechSensitivity": "START_SENSITIVITY_HIGH",
                "endOfSpeechSensitivity": "END_SENSITIVITY_LOW",
                "prefixPaddingMs": 120,
                "silenceDurationMs": 900,
            }
        },
        "inputAudioTranscription": {},
        "outputAudioTranscription": {},
    }


def _iso(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


async def mint_gemini_token(
    bp: BusinessBlueprint, *, timeout_seconds: int = 12
) -> dict[str, Any]:
    """Exchange the Gemini key for a one-use, setup-locked Live token."""
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise VoiceSessionError("Voice is not configured on this server.")
    now = datetime.now(timezone.utc)
    setup = gemini_setup(bp)
    body = {
        "uses": 1,
        "expireTime": _iso(now + timedelta(seconds=GEMINI_SESSION_SECONDS)),
        "newSessionExpireTime": _iso(now + timedelta(seconds=GEMINI_NEW_SESSION_SECONDS)),
        "bidiGenerateContentSetup": setup,
    }
    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.post(
                _GEMINI_TOKENS_URL,
                headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
                json=body,
            )
    except Exception as exc:  # noqa: BLE001
        _log.warning("interview.voice.mint_failed", provider="gemini", error=type(exc).__name__)
        raise VoiceSessionError("Could not reach the voice service.") from exc
    if response.status_code >= 400:
        _log.warning("interview.voice.mint_rejected", provider="gemini", status_code=response.status_code)
        raise VoiceSessionError("The voice service refused the request.")
    token = response.json().get("name")
    if not isinstance(token, str) or not token.startswith("auth_tokens/"):
        raise VoiceSessionError("The voice service returned no credential.")
    return {
        "provider": "gemini",
        "token": token,
        "expires_at": int((now + timedelta(seconds=GEMINI_NEW_SESSION_SECONDS)).timestamp()),
        "url": GEMINI_LIVE_URL,
        "model": GEMINI_LIVE_MODEL,
        "voice": GEMINI_VOICE_NAME,
        # The browser sends only the model: everything else is locked in the
        # token, and a mismatching copy would be rejected anyway.
        "setup": {"model": setup["model"]},
    }


async def create_voice_session(bp: BusinessBlueprint) -> dict[str, Any]:
    """A short-lived credential and session description for the configured provider."""
    if voice_provider() == "gemini":
        return await mint_gemini_token(bp)
    minted = await mint_client_secret()
    return {
        "provider": "xai",
        **minted,
        "url": REALTIME_URL,
        "model": VOICE_MODEL,
        "voice": VOICE_NAME,
        "session": session_config(bp),
    }
