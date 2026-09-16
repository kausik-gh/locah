"""Create a Business for an already-signed-up user - the first-run helper.

There is no Business-creation UI yet (the Workspace app only opens an existing
Business at /b/{id}). After you sign up at http://localhost:3000/login this
script does the one API-equivalent step: it resolves your Platform Identity
from your Supabase auth user and calls BusinessService.create_business
directly.

    uv run --env-file .env python tools/create_business.py you@example.com "My Shop" retail

Args: <email> <display_name> [business_type]
business_type is optional; one of: retail restaurant cafe hotel homestay salon
spa gym studio clinic professional_service education other not_sure
(default: not_sure).
"""

from __future__ import annotations

import asyncio
import sys
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from platform_core.business_types import SUPPORTED_BUSINESS_TYPES
from platform_core.db import get_database_url
from platform_core.services.business import BusinessService
from platform_core.services.identity import IdentityService


async def _run(email: str, display_name: str, business_type: str | None) -> None:
    url = get_database_url()
    if not url:
        sys.exit("DATABASE_URL is not set — run with `uv run --env-file .env ...`")
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)

    engine = create_async_engine(url, poolclass=NullPool)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        row = (
            await session.execute(
                text("SELECT id, email FROM auth.users WHERE lower(email) = lower(:e)"),
                {"e": email},
            )
        ).first()
        if row is None:
            sys.exit(
                f"No Supabase auth user for {email!r}. Sign up first at "
                "http://localhost:3000/login (and confirm the email if confirmation is on)."
            )
        supabase_user_id = uuid.UUID(str(row.id))

        identity = await IdentityService.bootstrap_identity(
            session, supabase_user_id, str(row.email)
        )
        await session.flush()

        business, location, membership, _profile = await BusinessService.create_business(
            session,
            identity_id=identity.id,
            display_name=display_name,
            business_type=business_type,
            correlation_id=str(uuid.uuid4()),
        )
        await session.commit()

    await engine.dispose()

    print("\n  Business created")
    print(f"    id            {business.id}")
    print(f"    slug          {business.slug}")
    print(f"    display_name  {business.display_name}")
    print(f"    type          {business.business_type}")
    print(f"    your role     {membership.role} (primary owner)")
    print(f"    primary loc   {location.id}")
    print(f"\n  Open the Workspace:  http://localhost:3001/b/{business.id}\n")


def main() -> None:
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    email = sys.argv[1]
    display_name = sys.argv[2]
    business_type = sys.argv[3] if len(sys.argv) > 3 else None
    if business_type and business_type not in SUPPORTED_BUSINESS_TYPES:
        sys.exit(
            f"business_type {business_type!r} not supported. One of: "
            + " ".join(sorted(SUPPORTED_BUSINESS_TYPES))
        )
    asyncio.run(_run(email, display_name, business_type))


if __name__ == "__main__":
    main()
