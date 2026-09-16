import os
from typing import Tuple, AsyncGenerator
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
    AsyncEngine,
)


def get_database_url() -> str | None:
    # Explicitly check for DATABASE_URL; no masked defaults.
    return os.getenv("DATABASE_URL")


def get_api_database_url() -> str | None:
    """Connection string for the RLS-enforcing `platform_api` role.

    Falls back to DATABASE_URL when unset, so a deploy that has not yet
    provisioned the role keeps working (RLS just stays inert, as before).
    """
    return os.getenv("API_DATABASE_URL") or os.getenv("DATABASE_URL")


def create_worker_session_factory(
    role: str = "service",
) -> Tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    """
    Creates an async engine and session factory.

    role="service"  -> DATABASE_URL, the `postgres` role (rolbypassrls=true).
                       Worker, migrations, and anything that legitimately needs
                       to cross tenant boundaries.
    role="user"     -> API_DATABASE_URL, the `platform_api` role
                       (NOBYPASSRLS). The API request path — every query is
                       subject to the row-level policies, scoped by the
                       `app.current_business_id` / `app.current_identity_id`
                       session GUCs bound per request (see
                       platform_core.context_resolver.bind_session_context).
    """
    db_url = get_api_database_url() if role == "user" else get_database_url()
    if not db_url:
        raise ValueError("DATABASE_URL environment variable is not set")

    # In asyncpg, we must use postgresql+asyncpg
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    engine = create_async_engine(
        db_url,
        echo=False,
        # Perf (measured, ap-northeast-1 pooler from ap-south-1): pool_pre_ping
        # emits a SELECT 1 on every checkout that, on this asyncpg + Supavisor
        # session-pooler combination, costs ~400-500ms — it roughly *doubled*
        # every query. Idle pooled connections survive here for minutes, so the
        # ping buys little; pool_recycle is the safety net for a connection the
        # pooler drops out from under us (SQLAlchemy transparently reconnects on
        # the next use). pool_size default 5 + overflow 10 is plenty for a
        # single-instance API.
        pool_pre_ping=False,
        pool_recycle=1800,
        connect_args={"timeout": 10},
    )

    factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    return engine, factory


@asynccontextmanager
async def transactional_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession, None]:
    """
    Foundational transaction helper for operations that require atomic commits
    (e.g., domain mutation + outbox event insert).
    """
    async with session_factory() as session:
        async with session.begin():
            yield session
