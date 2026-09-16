"""Test helpers for database integration tests."""

import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def ensure_auth_user(
    session: AsyncSession, user_id: uuid.UUID, email: str | None = None
) -> None:
    """Create a minimal auth.users row for local integration tests."""
    resolved_email = email or f"{user_id}@example.com"
    await session.execute(
        text("""
            INSERT INTO auth.users (
                id, instance_id, aud, role, email,
                encrypted_password, email_confirmed_at,
                created_at, updated_at
            )
            VALUES (
                :id,
                '00000000-0000-0000-0000-000000000000',
                'authenticated',
                'authenticated',
                :email,
                crypt('test-password', extensions.gen_salt('bf')),
                now(),
                now(),
                now()
            )
            ON CONFLICT (id) DO NOTHING
        """),
        {"id": str(user_id), "email": resolved_email},
    )
    await session.flush()
