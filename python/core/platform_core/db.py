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
        # Supersedes an earlier "pre_ping is too expensive" tuning. That was
        # measured against an ap-northeast-1 pooler; the project has since moved
        # to ap-south-1, and the assumption it rested on — "idle pooled
        # connections survive here for minutes" — is simply not true of this
        # pooler. Re-measured against it: a checkout costs ~570ms WITHOUT the
        # ping, which is a full reconnect, i.e. the pooler is dropping
        # connections between requests regardless. pool_recycle cannot catch
        # that: a connection killed server-side thirty seconds after checkin is
        # still handed out, and the request dies on
        # `asyncpg.InterfaceError: connection is closed` — a 500 for the owner,
        # which is exactly what Marketplace Presence and identity bootstrap were
        # returning.
        #
        # pre_ping adds ~250ms and turns that 500 into a transparent reconnect.
        # A slower correct answer beats a fast error page.
        pool_pre_ping=True,
        # Well inside the pooler's idle tolerance rather than the 30 minutes it
        # demonstrably does not honour.
        pool_recycle=600,
        # The pooler allots each client a small number of slots, shared by the
        # API and the worker. Overrunning it is what gets connections killed, so
        # keep the ceiling modest instead of the default 5 + 10 overflow.
        pool_size=5,
        max_overflow=5,
        # Connecting through the pooler measurably exceeds 10s under load; that
        # timeout was itself turning slow connects into hard failures.
        connect_args={"timeout": 30},
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
