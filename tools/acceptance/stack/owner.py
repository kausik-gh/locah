"""Local acceptance setup: a test owner in the LOCAL database and a session for the browser.

Usage: uv run python tools/acceptance/stack/owner.py <db_name> <out_json>
Creates auth.users row (the trigger creates the platform identity), mints an
HS256 token with the local test secret, and writes the Supabase SSR cookie
value (sb-127-auth-token) for the local mock auth. Test data only.
"""

from __future__ import annotations

import asyncio
import base64
import json
import sys
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from sqlalchemy.ext.asyncio import create_async_engine

from platform_testing.db_helpers import ensure_auth_user

SECRET = "local-acceptance-secret-with-at-least-32-characters"


async def main(db: str, out: str) -> None:
    user_id = uuid.uuid4()
    email = f"accept-{user_id.hex[:8]}@locah.test"
    engine = create_async_engine(f"postgresql+asyncpg://postgres@localhost:54329/{db}")
    from sqlalchemy.ext.asyncio import AsyncSession

    async with AsyncSession(engine) as session:
        await ensure_auth_user(session, user_id, email)
        await session.commit()
    await engine.dispose()
    exp = datetime.now(timezone.utc) + timedelta(hours=12)
    token = jwt.encode({"sub": str(user_id), "email": email, "aud": "authenticated", "role": "authenticated",
                        "exp": exp}, SECRET, algorithm="HS256")
    session_json = {
        "access_token": token, "token_type": "bearer", "expires_in": 43200,
        "expires_at": int(exp.timestamp()), "refresh_token": "local-refresh",
        "user": {"id": str(user_id), "aud": "authenticated", "role": "authenticated", "email": email,
                 "app_metadata": {"provider": "email"}, "user_metadata": {}},
    }
    cookie = "base64-" + base64.urlsafe_b64encode(json.dumps(session_json).encode()).decode().rstrip("=")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump({"user_id": str(user_id), "email": email, "token": token, "cookie_name": "sb-127-auth-token",
                   "cookie": cookie}, fh)
    print(json.dumps({"user_id": str(user_id), "email": email, "cookie_len": len(cookie)}))


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], sys.argv[2]))
