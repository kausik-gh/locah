"""Dual-mode Supabase JWT verification (auth hardening).

The project's real login tokens are ES256 (Supabase JWT Signing Keys, verified
via the JWKS public key). Legacy HS256 with a shared secret still has to work
for pre-migration tokens and for the test suite's own hand-minted tokens.

No network: the JWKS client is stubbed with an in-memory EC public key.
"""

from __future__ import annotations

import datetime
import uuid
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from platform_api import jwt_verify
from platform_api.jwt_verify import (
    JWTExpiredError,
    JWTVerificationError,
    verify_supabase_jwt,
)


@pytest.fixture
def ec_keypair() -> tuple[ec.EllipticCurvePrivateKey, ec.EllipticCurvePublicKey]:
    priv = ec.generate_private_key(ec.SECP256R1())
    return priv, priv.public_key()


@pytest.fixture(autouse=True)
def _no_real_jwks(monkeypatch: pytest.MonkeyPatch) -> None:
    # Guarantee the real PyJWKClient is never built during these tests.
    monkeypatch.setattr(jwt_verify, "_jwks_client", None)
    monkeypatch.setattr(jwt_verify, "_jwks_client_url", None)
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_JWKS_URL", raising=False)


def _stub_jwks(monkeypatch: pytest.MonkeyPatch, public_key: object) -> None:
    monkeypatch.setattr(
        jwt_verify,
        "get_jwks_client",
        lambda: SimpleNamespace(
            get_signing_key_from_jwt=lambda _token: SimpleNamespace(key=public_key)
        ),
    )


def _claims(**extra: object) -> dict[str, object]:
    now = datetime.datetime.now(datetime.timezone.utc)
    base: dict[str, object] = {
        "sub": str(uuid.uuid4()),
        "email": "real.user@example.com",
        "aud": "authenticated",
        "role": "authenticated",
        "iat": now,
        "exp": now + datetime.timedelta(hours=1),
    }
    base.update(extra)
    return base


def test_es256_token_verifies_against_the_jwks_key(
    monkeypatch: pytest.MonkeyPatch, ec_keypair: tuple
) -> None:
    priv, pub = ec_keypair
    _stub_jwks(monkeypatch, pub)
    token = jwt.encode(
        _claims(), priv, algorithm="ES256", headers={"kid": "dcbbdf07-e93f-4843-9640-50b4fa54fc3d"}
    )

    payload = verify_supabase_jwt(token)

    assert payload["email"] == "real.user@example.com"
    assert payload["aud"] == "authenticated"


def test_es256_token_signed_by_a_different_key_is_rejected(
    monkeypatch: pytest.MonkeyPatch, ec_keypair: tuple
) -> None:
    _, pub = ec_keypair
    other_priv = ec.generate_private_key(ec.SECP256R1())
    _stub_jwks(monkeypatch, pub)  # JWKS holds `pub`
    token = jwt.encode(_claims(), other_priv, algorithm="ES256")  # signed by someone else

    with pytest.raises(JWTVerificationError):
        verify_supabase_jwt(token)


def test_es256_token_without_configured_jwks_is_rejected() -> None:
    # autouse fixture cleared SUPABASE_URL / SUPABASE_JWKS_URL and the client.
    priv = ec.generate_private_key(ec.SECP256R1())
    token = jwt.encode(_claims(), priv, algorithm="ES256")

    with pytest.raises(JWTVerificationError, match="SUPABASE_URL"):
        verify_supabase_jwt(token)


def test_hs256_token_still_verifies_with_the_shared_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "super-secret-jwt-token-with-at-least-32-characters-long"
    monkeypatch.setenv("SUPABASE_JWT_SECRET", secret)
    token = jwt.encode(_claims(), secret, algorithm="HS256")

    payload = verify_supabase_jwt(token)

    assert payload["email"] == "real.user@example.com"


def test_hs256_token_with_the_wrong_secret_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "the-configured-secret-value-32-chars-min")
    token = jwt.encode(_claims(), "a-completely-different-secret-value-x", algorithm="HS256")

    with pytest.raises(JWTVerificationError):
        verify_supabase_jwt(token)


def test_expired_es256_token_raises_expired(
    monkeypatch: pytest.MonkeyPatch, ec_keypair: tuple
) -> None:
    priv, pub = ec_keypair
    _stub_jwks(monkeypatch, pub)
    past = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=2)
    token = jwt.encode(
        _claims(iat=past, exp=past + datetime.timedelta(minutes=5)), priv, algorithm="ES256"
    )

    with pytest.raises(JWTExpiredError):
        verify_supabase_jwt(token)


def test_alg_none_token_is_rejected() -> None:
    token = jwt.encode(_claims(), key="", algorithm="none")

    with pytest.raises(JWTVerificationError):
        verify_supabase_jwt(token)
