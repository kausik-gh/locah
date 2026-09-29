#!/usr/bin/env bash
# The API for acceptance runs: local database, a local token secret, NO
# provider keys, every paid AI call refused (LOCAH_TEST_NO_EXTERNAL_AI=1), the
# model and voice replayed from recordings. Never point this at staging.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
OUT=${LOCAH_ACCEPT_OUT:-$ROOT/acceptance-out}
cd "$ROOT"
export DATABASE_URL=${ACCEPT_DATABASE_URL:-postgresql+asyncpg://postgres@localhost:54329/locah_accept}
case "$DATABASE_URL" in *@localhost:*|*@127.0.0.1:*) ;; *) echo "local databases only" >&2; exit 1 ;; esac
export API_DATABASE_URL=$DATABASE_URL
export SUPABASE_JWT_SECRET=local-acceptance-secret-with-at-least-32-characters
export SUPABASE_URL=http://127.0.0.1:54321
export WEBSITE_PREVIEW_SECRET=local-preview-secret-with-at-least-32-characters
export LOCAH_TEST_NO_EXTERNAL_AI=1
export AI_PROVIDER=replay
export LOCAH_AI_REPLAY_FILE=${LOCAH_AI_REPLAY_FILE:-$OUT/replay_ai.json}
export VOICE_PROVIDER=replay
export LOCAH_VOICE_REPLAY_FILE=${LOCAH_VOICE_REPLAY_FILE:-$OUT/replay_voice.json}
export IMAGE_PROVIDER=none
export LOCAH_JOBS_INERT=1
# The WhatsApp sandbox: messages are recorded, never delivered (no Meta number).
export MESSAGING_SANDBOX=1
export RATE_LIMIT_ENABLED=0
# The local web (3100) and Workspace (3101) call the API from the browser.
export CORS_ALLOWED_ORIGINS=${ACCEPT_CORS:-http://localhost:3100,http://localhost:3101}
unset GEMINI_API_KEY XAI_API_KEY OPENAI_API_KEY ANTHROPIC_API_KEY || true
exec uv run --no-env-file uvicorn platform_api.main:app --app-dir apps/api/src --port "${API_PORT:-8010}"
