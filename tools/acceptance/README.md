# Phase A browser acceptance (local, zero AI spend)

Drives **Create Business → Talk to LOCAH → confirm → build → website** in a
headless Chrome against a local stack. Nothing reaches a paid provider: the
API runs with `LOCAH_TEST_NO_EXTERNAL_AI=1` and no keys, the model and voice
are replayed from recordings, and a message without a recording takes the
model-down path — exactly what production does when the model is unreachable.

## Run

```bash
# 1. a local Postgres on 54329 with a fresh database
tools/acceptance/stack/db.sh locah_accept
# 2. recordings (model readings, personas, voice)
uv run python tools/acceptance/stack/recordings.py acceptance-out
# 3. the stack — mock sign-in, API, web (three terminals, or preview configs)
node tools/acceptance/stack/mock-auth.mjs
tools/acceptance/stack/api.sh
tools/acceptance/stack/web.sh
# 4. a test owner and its local session cookie
uv run python tools/acceptance/stack/owner.py locah_accept acceptance-out/session.json
# 5. the flows (all, or some: A C L)
LOCAH_ACCEPT_SESSION=acceptance-out/session.json \
LOCAH_ACCEPT_PERSONAS=acceptance-out/personas.json \
LOCAH_VOICE_REPLAY_FILE=acceptance-out/replay_voice.json \
LOCAH_ACCEPT_OUT=acceptance-out node tools/acceptance/flows.mjs
# phone size
LOCAH_ACCEPT_MOBILE=1 … node tools/acceptance/flows.mjs
```

`acceptance-out/` is git-ignored: screenshots, transcripts and
`results.json` stay local.

## Flows

| | Flow |
|---|---|
| A | Talk-first meat shop — typed first message, no category, no name |
| B | Category-first restaurant |
| C | Talk-first gym, by voice (replayed utterance) |
| D | Salon, owner writes Tamil |
| E | Real-estate developer, through to the website |
| F | Wedding photographer, through to the website |
| G | Industrial supplier (quotes, never bookings), through to the website |
| H | Model unavailable for every message |
| I | Owner says "Build it" mid-way |
| J | "Keep refining" at the checkpoint |
| K | Structured correction in the side panel, then a kind correction in words |
| L | Voice first, then typing — one conversation |

`mock-auth.mjs` answers only Supabase's "who is this token" call, from the
locally minted token's own claims; the API still verifies the token's
signature with the local secret. Test-only — never deploy it.
