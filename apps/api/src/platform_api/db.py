import os
from typing import AsyncGenerator
from fastapi import Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool


_RESET_GUCS = text(
    "SELECT set_config('app.current_business_id', '', false), "
    "set_config('app.current_identity_id', '', false)"
)

# The GUC reset only matters when the API is on the RLS-enforcing connection —
# there it stops a pooled connection from carrying one request's tenant scope
# into the next. On the bypass connection (API_DATABASE_URL unset) it is pure
# overhead: an extra transaction per request, which at test-suite parallelism
# adds enough connection pressure against the 15-slot pooler to tip load-
# sensitive tests over. So gate it on enforcement being active.
_RLS_ENFORCING = os.getenv("API_DATABASE_URL") is not None


async def _reset_and_close(session: AsyncSession) -> None:
    """Clear the RLS session GUCs before the connection returns to the pool.

    `bind_session_context` sets them at SESSION scope so they survive a
    handler's commits; without this reset the next request to reuse the
    connection would inherit the previous tenant's scope until it re-binds
    (and a public/unbound path would inherit it outright). Best-effort — a
    failed reset just means that connection stays bound until its next bind,
    which every authenticated request performs.
    """
    if not _RLS_ENFORCING:
        return
    try:
        await session.rollback()
        await session.execute(_RESET_GUCS)
        await session.commit()
    except Exception:
        pass


async def get_db_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """Yield one AsyncSession bound to one Connection for the whole request.

    AUD-02 follow-up: `bind_session_context` sets the RLS GUCs at SESSION
    scope specifically so they survive an in-request `commit()` (see its
    docstring). That guarantee only holds if the *physical* connection stays
    the same across the request. A Session bound to an Engine (rather than a
    Connection) does not guarantee that: SQLAlchemy checks the connection
    back into the pool at every commit() and checks a new one out for the
    next statement, and a real pool can legitimately hand back a *different*
    connection — one with no GUCs set, or (before the reset below runs) a
    stale tenant's. A handler that writes, commits, and immediately reads
    back what it wrote (e.g. create_employee's post-commit get_by_id,
    create_order's post-commit line-item load) would then see its own read
    filtered out by RLS even though the write is already durably committed.
    Holding one Connection open for the request's lifetime — checked out
    once here, released once when this generator's `finally` runs — removes
    that swap entirely, regardless of which pool class backs the engine.
    """
    # db_engine is stored in app.state during lifespan
    engine = getattr(request.app.state, "db_engine", None)
    if engine is not None:
        async with engine.connect() as conn:
            async with AsyncSession(bind=conn, expire_on_commit=False) as session:
                try:
                    yield session
                finally:
                    await _reset_and_close(session)
        return

    # Fallback: lifespan never ran (e.g. TestClient(app) instantiated without
    # entering the lifespan context). Build a throwaway engine per call with
    # NullPool so no connection is pooled beyond this request — a cached pool
    # on app.state would outlive the caller's event loop and break across
    # independent TestClient(app) instances. Mirrors the URL handling and
    # session construction in platform_core.db.create_worker_session_factory.
    #
    # Uses API_DATABASE_URL (the RLS-enforcing role) when set, so the test
    # suite actually exercises the policies rather than the bypass path.
    #
    # Same single-Connection binding as the primary path above, and for the
    # same reason — NullPool makes it *worse* than a real pool, since every
    # post-commit checkout is guaranteed to be a brand-new physical
    # connection with no GUCs at all, so an Engine-bound session here would
    # fail every read-after-write-in-one-request deterministically rather
    # than intermittently.
    db_url = os.getenv("API_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("Database session factory is not initialized")

    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    engine = create_async_engine(db_url, echo=False, poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            async with AsyncSession(bind=conn, expire_on_commit=False) as session:
                yield session
    finally:
        await engine.dispose()


async def get_service_db_session() -> AsyncGenerator[AsyncSession, None]:
    """A session on the `postgres` (rolbypassrls) connection.

    For the handful of endpoints that legitimately cross tenant boundaries and
    cannot be expressed as a row-level policy — Super Admin inspection
    (Doc 11 §17.7: "Admin can inspect and support") and the payment provider
    webhook (no business context; the signature is the auth). Every such
    endpoint enforces its own gate: `require_super_admin` for admin,
    `verify_webhook_signature` for the webhook. Uses DATABASE_URL, never
    API_DATABASE_URL.
    """
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL is not set")
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = create_async_engine(db_url, echo=False, poolclass=NullPool)
    try:
        factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            yield session
    finally:
        await engine.dispose()
