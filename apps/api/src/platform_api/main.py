import os
from typing import Any, AsyncIterator
from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from contextlib import asynccontextmanager
from platform_core.db import create_worker_session_factory
from platform_core.exceptions import PlatformError
from platform_core.logging import configure as configure_logging, get_logger
from platform_api.errors import platform_error_handler
from platform_api.observability import RequestLogMiddleware
from platform_api.rate_limit import RateLimitMiddleware
from platform_api.routers import (
    me,
    v1_me,
    v1_businesses,
    v1_business,
    v1_team_modules,
    v1_admin,
    v1_platform_members,
    v1_platform_invitations,
    v1_platform_settings,
    v1_platform_configuration,
    v1_platform_entitlements,
    v1_platform_permissions,
    v1_platform_locations,
    v1_platform_employees,
    v1_platform_customers,
    v1_platform_offerings,
    v1_platform_inventory,
    v1_platform_orders,
    v1_platform_bookings,
    v1_platform_payments,
    webhooks_payments,
    v1_website,
    v1_public_websites,
    v1_public_search,
    v1_marketplace,
    v1_fulfilment,
    v1_public_checkout,
    v1_workforce,
    v1_public_bookings,
    v1_platform_leads,
    v1_platform_memberships,
    v1_platform_notifications,
    v1_media,
)

# Database lifecycle state
db_engine = None
db_session_factory = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[Any]:
    global db_engine, db_session_factory

    # AUD-11: structlog must be configured (redaction processor installed)
    # before the first line ships.
    configure_logging()
    get_logger("platform_api").info(
        "api.startup", rate_limit=os.getenv("RATE_LIMIT_ENABLED", "1") != "0"
    )

    # Warm the Supabase JWKS cache so the first authenticated request doesn't
    # pay the fetch. Best-effort; the ES256 verify path retries on miss.
    from anyio import to_thread

    from platform_api.jwt_verify import warm_jwks_cache

    await to_thread.run_sync(warm_jwks_cache)

    if os.getenv("DATABASE_URL"):
        try:
            # role="user" → the NOBYPASSRLS platform_api connection. The API
            # request path is subject to row-level policies (AUD-02).
            db_engine, db_session_factory = create_worker_session_factory(role="user")
        except Exception as e:
            get_logger("platform_api").error("api.db_session_factory_init_failed", error=str(e))
            db_engine = None
            db_session_factory = None

    app.state.db_session_factory = db_session_factory
    # AUD-02 follow-up: get_db_session binds one Connection per request off
    # this engine directly (rather than handing out Engine-bound Sessions),
    # so an in-request commit() can't silently swap the physical connection
    # under the session and strip the RLS GUCs bind_session_context set. See
    # the comment on get_db_session for the full mechanism. db_session_factory
    # stays published too — /health/ready and /health/worker only ever run one
    # transaction per call, so the swap risk doesn't apply to them.
    app.state.db_engine = db_engine

    yield

    # Clear the advertised factory/engine before disposing. Leaving a disposed
    # engine on app.state makes get_db_session hand out sessions bound to a
    # closed event loop and suppresses its NullPool fallback — which breaks
    # every later bare-TestClient(app) test in the same process once any
    # `with TestClient(app)` test has run lifespan.
    app.state.db_session_factory = None
    app.state.db_engine = None
    if db_engine:
        await db_engine.dispose()
    db_engine = None
    db_session_factory = None


app = FastAPI(
    title="Multi-Tenant Platform API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Rate limiting (Doc 11 §21.1 gate 8). Added BEFORE CORS so CORS ends up the
# outer layer (Starlette wraps last-added first): a 429 short-circuited here
# still travels back out through CORS and gets its headers, so a browser sees
# the 429 rather than an opaque network error. Opt out per-process with
# RATE_LIMIT_ENABLED=0 — the test suite does, so parallel workers hammering
# shared buckets don't trip each other.
if os.getenv("RATE_LIMIT_ENABLED", "1") != "0":
    app.add_middleware(RateLimitMiddleware)

# AUD-11: request-line logging + correlation-id propagation. Added after the
# rate limiter so it stays inside CORS but wraps the limiter — a 429 still gets
# a log line and an X-Correlation-Id.
app.add_middleware(RequestLogMiddleware)

# Standard CORS. Credentials cannot be used with wildcard origins.
_cors_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:3000,http://localhost:3001,http://localhost:3002",
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(me.router)
app.include_router(v1_me.router)
app.include_router(v1_businesses.router)
app.include_router(v1_platform_members.router)
app.include_router(v1_platform_invitations.router)
app.include_router(v1_platform_settings.router)
app.include_router(v1_platform_configuration.router)
app.include_router(v1_platform_entitlements.router)
app.include_router(v1_platform_permissions.router)
app.include_router(v1_platform_locations.router)
app.include_router(v1_platform_employees.router)
app.include_router(v1_platform_customers.router)
app.include_router(v1_platform_offerings.router)
app.include_router(v1_platform_inventory.router)
app.include_router(v1_platform_orders.router)
app.include_router(v1_platform_bookings.router)
app.include_router(v1_workforce.router)
app.include_router(v1_platform_payments.router)
app.include_router(webhooks_payments.router)
app.include_router(v1_website.router)
app.include_router(v1_public_websites.router)
app.include_router(v1_public_search.router)
app.include_router(v1_marketplace.router)
app.include_router(v1_fulfilment.router)
app.include_router(v1_public_checkout.router)
app.include_router(v1_public_bookings.router)
app.include_router(v1_business.router)
app.include_router(v1_team_modules.router)
app.include_router(v1_admin.router)
app.include_router(v1_platform_leads.router)
app.include_router(v1_platform_memberships.router)
app.include_router(v1_platform_notifications.router)
app.include_router(v1_media.router)

app.add_exception_handler(PlatformError, platform_error_handler)


@app.get("/health/live", status_code=status.HTTP_200_OK)
async def liveness_check() -> dict[str, Any]:
    """
    Liveness check to verify the process is alive.
    """
    return {"status": "ok", "message": "Liveness check passed"}


@app.get("/health/ready")
async def readiness_check(request: Request, response: Response) -> dict[str, Any]:
    """
    Readiness check to verify DB connection and required services.
    """
    session_factory = getattr(request.app.state, "db_session_factory", None)
    if not session_factory:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "error",
            "database": "not_configured",
            "message": "Database is not configured",
        }

    try:
        async with session_factory() as session:
            # Perform a quick select to verify connectivity
            await session.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "error", "message": f"Database connectivity failed: {str(e)}"}


@app.get("/health/worker")
async def worker_health_check(request: Request, response: Response) -> dict[str, Any]:
    """Worker/outbox lag health gate (Doc 12 §22.2)."""
    session_factory = getattr(request.app.state, "db_session_factory", None)
    if not session_factory:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "error",
            "worker": "not_configured",
            "message": "Database is not configured",
        }

    lag_threshold_seconds = int(os.getenv("WORKER_LAG_THRESHOLD_SECONDS", "300"))
    try:
        async with session_factory() as session:
            result = await session.execute(
                text("""
                    SELECT COALESCE(
                        EXTRACT(EPOCH FROM (now() - MIN(created_at))),
                        0
                    )::int AS lag_seconds,
                    COUNT(*) FILTER (WHERE status = 'pending') AS pending_count
                    FROM platform_outbox_events
                    WHERE status IN ('pending', 'processing')
                """)
            )
            row = result.one()
            lag_seconds = int(row.lag_seconds or 0)
            pending_count = int(row.pending_count or 0)
        if lag_seconds > lag_threshold_seconds and pending_count > 0:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return {
                "status": "error",
                "worker": "lag_exceeded",
                "lag_seconds": lag_seconds,
                "pending_count": pending_count,
            }
        return {
            "status": "ok",
            "worker": "healthy",
            "lag_seconds": lag_seconds,
            "pending_count": pending_count,
        }
    except Exception as e:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "error", "message": f"Worker health check failed: {str(e)}"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("platform_api.main:app", host="0.0.0.0", port=8000, reload=True)
