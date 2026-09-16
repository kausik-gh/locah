"""Shared pytest setup for the apps/api suite.

Rate limiting is disabled for the whole test session. `RateLimitMiddleware`
keeps its sliding windows keyed by client IP, and every `TestClient(app)`
request arrives from the same synthetic host, so a test file that creates many
businesses / payments / bookings in quick succession would trip the shared
buckets and fail for reasons that have nothing to do with what it is testing.

The rate limiter has its own dedicated coverage in `test_rate_limiting.py`,
which re-enables it explicitly.

This must run before any test module executes `from platform_api.main import
app`, because the middleware reads the flag at import time. conftest.py is
imported by pytest before test collection, so it does.
"""

import os

os.environ.setdefault("RATE_LIMIT_ENABLED", "0")

# The suite mints its own HS256 tokens; nothing here exercises the ES256 / JWKS
# path. Drop any real SUPABASE_URL / SUPABASE_JWKS_URL from the environment so
# the API-startup JWKS warm (main.py lifespan) never makes a network call.
# test_jwt_verify.py stubs the JWKS client and manages these vars itself.
os.environ.pop("SUPABASE_URL", None)
os.environ.pop("SUPABASE_JWKS_URL", None)

# Website generation must never make a live AI call from the suite. Drop any
# GEMINI_API_KEY the environment/.env carries so `get_ai_provider()` returns
# `UnavailableAIProvider` by default; the live Gemini path is covered with a
# stubbed provider in test_website_generation.py.
os.environ.pop("GEMINI_API_KEY", None)

# AUD-11: keep the per-request INFO line ("request.completed") out of the test
# transcript. WARN/ERROR — gate denials, 5xx, webhook signature rejections —
# still print, and the redaction filter is exercised directly by
# test_logging_redaction.py regardless of level.
os.environ.setdefault("LOG_LEVEL", "WARNING")
