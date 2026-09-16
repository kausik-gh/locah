"""Rate limiting (Doc 11 §21.1 gate 8).

The suite-wide conftest disables the limiter on the real app, so these tests
build their own app with `RateLimitMiddleware` explicitly attached and exercise
it directly. No database.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from platform_api.rate_limit import BUCKETS, Bucket, RateLimiter, RateLimitMiddleware


def _app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware)

    @app.post("/v1/b/x/website/generate")
    async def generate() -> dict[str, str]:
        return {"ok": "generated"}

    @app.get("/v1/public/websites/acme")
    async def public_read() -> dict[str, str]:
        return {"ok": "read"}

    @app.get("/v1/platform/businesses/x/orders")
    async def not_limited() -> dict[str, str]:
        return {"ok": "unlimited"}

    return app


# ---------------------------------------------------------------------------
# RateLimiter unit — deterministic, injected clock
# ---------------------------------------------------------------------------
def test_limiter_allows_up_to_limit_then_blocks() -> None:
    limiter = RateLimiter()
    bucket = Bucket(
        name="t", methods=frozenset({"GET"}), prefixes=("/x",), limit=3, window_seconds=60
    )
    now = 1000.0
    assert limiter.check(bucket, "ip1", now)[0] is True
    assert limiter.check(bucket, "ip1", now)[0] is True
    assert limiter.check(bucket, "ip1", now)[0] is True

    allowed, retry_after = limiter.check(bucket, "ip1", now)
    assert allowed is False
    assert retry_after >= 1


def test_limiter_window_slides_and_resets() -> None:
    limiter = RateLimiter()
    bucket = Bucket(
        name="t", methods=frozenset({"GET"}), prefixes=("/x",), limit=2, window_seconds=60
    )
    assert limiter.check(bucket, "ip1", 1000.0)[0] is True
    assert limiter.check(bucket, "ip1", 1000.0)[0] is True
    assert limiter.check(bucket, "ip1", 1030.0)[0] is False  # still inside the window

    # 61s after the first request — the window has fully slid past it.
    assert limiter.check(bucket, "ip1", 1061.0)[0] is True


def test_limiter_is_per_client_key() -> None:
    limiter = RateLimiter()
    bucket = Bucket(
        name="t", methods=frozenset({"GET"}), prefixes=("/x",), limit=1, window_seconds=60
    )
    assert limiter.check(bucket, "ip1", 1000.0)[0] is True
    assert limiter.check(bucket, "ip1", 1000.0)[0] is False
    # A different client still has its full quota.
    assert limiter.check(bucket, "ip2", 1000.0)[0] is True


# ---------------------------------------------------------------------------
# Middleware integration
# ---------------------------------------------------------------------------
def test_route_is_throttled_after_the_bucket_limit() -> None:
    client = TestClient(_app())

    # website_generate bucket is limit=5/min.
    for i in range(5):
        assert client.post("/v1/b/x/website/generate").status_code == 200, f"call {i}"

    blocked = client.post("/v1/b/x/website/generate")
    assert blocked.status_code == 429
    body = blocked.json()
    assert body["error"]["code"] == "RATE_LIMITED"
    assert body["error"]["details"]["bucket"] == "website_generate"
    assert int(blocked.headers["retry-after"]) >= 1
    assert body["error"]["details"]["retry_after_seconds"] == int(blocked.headers["retry-after"])


def test_unmatched_route_is_never_throttled() -> None:
    client = TestClient(_app())
    for _ in range(50):
        assert client.get("/v1/platform/businesses/x/orders").status_code == 200


def test_separate_buckets_have_separate_counters() -> None:
    client = TestClient(_app())
    # Exhaust website_generate.
    for _ in range(5):
        client.post("/v1/b/x/website/generate")
    assert client.post("/v1/b/x/website/generate").status_code == 429
    # public_read (limit 120) is untouched.
    assert client.get("/v1/public/websites/acme").status_code == 200


def test_x_forwarded_for_is_used_as_the_client_key() -> None:
    client = TestClient(_app())
    # Two distinct upstream clients behind the same proxy get separate quotas.
    for _ in range(5):
        assert (
            client.post(
                "/v1/b/x/website/generate", headers={"x-forwarded-for": "1.1.1.1"}
            ).status_code
            == 200
        )
    assert (
        client.post(
            "/v1/b/x/website/generate", headers={"x-forwarded-for": "1.1.1.1"}
        ).status_code
        == 429
    )
    assert (
        client.post(
            "/v1/b/x/website/generate", headers={"x-forwarded-for": "2.2.2.2"}
        ).status_code
        == 200
    )


def test_every_bucket_name_is_unique() -> None:
    names = [b.name for b in BUCKETS]
    assert len(names) == len(set(names))
