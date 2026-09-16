import uuid
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from platform_api.jwt_verify import (
    JWTExpiredError,
    JWTVerificationError,
    verify_supabase_jwt,
)

security = HTTPBearer()


class RequestContext(BaseModel):
    user_id: Optional[uuid.UUID] = None  # Future domain user/person id
    auth_user_id: uuid.UUID
    email: str


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> RequestContext:
    # Dual-mode: ES256 (Supabase JWT Signing Keys, via JWKS) or legacy HS256.
    # This is a sync dependency, so FastAPI already runs it in a worker thread —
    # the JWKS fetch inside verify_supabase_jwt does not block the event loop.
    try:
        payload = verify_supabase_jwt(credentials.credentials)
    except JWTExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )
    except JWTVerificationError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    auth_user_id_str = payload.get("sub")
    email = payload.get("email")

    if not auth_user_id_str or not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    return RequestContext(auth_user_id=uuid.UUID(auth_user_id_str), email=email)
