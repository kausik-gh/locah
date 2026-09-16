"""Supabase JWT verification — dual-mode (auth hardening).

The Supabase project's current signing key is asymmetric **ES256** ("JWT
Signing Keys"): every real login token is signed ES256 and can only be
verified with the public key published at the project's JWKS endpoint. A
legacy HS256 shared secret (``SUPABASE_JWT_SECRET``) still covers
pre-migration tokens that are inside their TTL, and the test suite's own
hand-minted tokens.

``verify_supabase_jwt`` dispatches on the token's ``alg`` header:

* ``ES* / RS* / PS*`` → JWKS public key (``PyJWKClient``, in-process cache,
  ``lifespan`` 300s, warmed at API startup)
* ``HS256``           → ``SUPABASE_JWT_SECRET``

The JWKS URL is derived from ``SUPABASE_URL`` (``…/auth/v1/.well-known/jwks.json``)
or taken directly from ``SUPABASE_JWKS_URL``.
"""

from __future__ import annotations

import os
from typing import Any

import jwt
from jwt import PyJWKClient
from platform_core.logging import get_logger

logger = get_logger("platform_api.jwt")

_ASYMMETRIC_ALG_PREFIXES = ("ES", "RS", "PS")

_jwks_client: PyJWKClient | None = None
_jwks_client_url: str | None = None


class JWTVerificationError(Exception):
    """Any invalid / malformed / unverifiable token. Callers map this to 401."""


class JWTExpiredError(JWTVerificationError):
    """The token's signature was valid but it has expired. Callers map to 401."""


def _jwks_url() -> str | None:
    base = os.getenv("SUPABASE_URL")
    if base:
        return f"{base.rstrip('/')}/auth/v1/.well-known/jwks.json"
    return os.getenv("SUPABASE_JWKS_URL")


def get_jwks_client() -> PyJWKClient | None:
    """Lazily build (and cache) the JWKS client. ``None`` when no URL is configured."""
    global _jwks_client, _jwks_client_url
    url = _jwks_url()
    if not url:
        return None
    if _jwks_client is None or _jwks_client_url != url:
        _jwks_client = PyJWKClient(
            url,
            cache_keys=True,
            max_cached_keys=8,
            cache_jwk_set=True,
            lifespan=300,
            timeout=10,
        )
        _jwks_client_url = url
    return _jwks_client


def warm_jwks_cache() -> None:
    """Fetch the JWKS once so the first real request doesn't pay the round-trip.

    Blocking (urllib) — call from a worker thread at API startup. Best-effort:
    a failure here just means the first verify retries the fetch.
    """
    client = get_jwks_client()
    if client is None:
        return
    try:
        client.get_jwk_set(refresh=True)
    except Exception:  # noqa: BLE001 — startup warm is advisory
        pass


def verify_supabase_jwt(token: str) -> dict[str, Any]:
    """Verify a Supabase-issued JWT and return its claims, or raise.

    Blocking: the asymmetric path may do one HTTP fetch (cached). Call from a
    worker thread inside async code (``anyio.to_thread.run_sync``).
    """
    try:
        alg = str(jwt.get_unverified_header(token).get("alg", ""))
    except jwt.PyJWTError as exc:
        raise JWTVerificationError("Malformed token header") from exc

    try:
        if alg.startswith(_ASYMMETRIC_ALG_PREFIXES):
            client = get_jwks_client()
            if client is None:
                logger.warning("jwt.verifier_misconfigured", alg=alg, missing="SUPABASE_URL")
                raise JWTVerificationError(
                    "Asymmetric token, but neither SUPABASE_URL nor SUPABASE_JWKS_URL is set"
                )
            signing_key = client.get_signing_key_from_jwt(token)
            return jwt.decode(
                token, signing_key.key, algorithms=[alg], options={"verify_aud": False}
            )
        if alg == "HS256":
            secret = os.getenv("SUPABASE_JWT_SECRET")
            if not secret:
                logger.warning(
                    "jwt.verifier_misconfigured", alg=alg, missing="SUPABASE_JWT_SECRET"
                )
                raise JWTVerificationError("HS256 token, but SUPABASE_JWT_SECRET is not set")
            return jwt.decode(
                token, secret, algorithms=["HS256"], options={"verify_aud": False}
            )
        raise JWTVerificationError(f"Unsupported token alg: {alg!r}")
    except jwt.ExpiredSignatureError as exc:
        raise JWTExpiredError("Token has expired") from exc
    except jwt.PyJWTError as exc:
        raise JWTVerificationError(str(exc) or "Invalid token") from exc
