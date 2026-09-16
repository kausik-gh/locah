"""Symmetric encryption for secret material stored at rest.

Currently the only user is the Razorpay merchant Key Secret
(`MerchantConnection.encrypted_credentials`). Payment provider API secrets are
the same class of material as everything the AUD-11 redaction filter scrubs —
never logged, never returned to a client, encrypted in the database.

Key source, in order:
  1. `PAYMENT_CREDENTIAL_KEY` — a urlsafe-base64 32-byte Fernet key. Set this
     in real deploys and rotate it there.
  2. Fallback: HKDF-SHA256 over `SUPABASE_JWT_SECRET` with a fixed info label,
     so local/dev works without a second secret. Logged once at WARNING.

Rotation: `Fernet` tokens carry no key id. To rotate, use `MultiFernet` with
the new key first and the old key second, re-encrypt on next write. Not
implemented until a deploy actually needs it.
"""

from __future__ import annotations

import base64
import os

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from platform_core.logging import get_logger

logger = get_logger("platform_core.crypto")

_HKDF_INFO = b"platform:payment-credential-key:v1"
_fernet: Fernet | None = None
_warned = False


def _derive_from_jwt_secret(secret: str) -> bytes:
    raw = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=_HKDF_INFO,
    ).derive(secret.encode("utf-8"))
    return base64.urlsafe_b64encode(raw)


def _get_fernet() -> Fernet:
    global _fernet, _warned
    if _fernet is not None:
        return _fernet

    configured = os.getenv("PAYMENT_CREDENTIAL_KEY")
    if configured:
        try:
            _fernet = Fernet(configured.encode("utf-8"))
            return _fernet
        except (ValueError, TypeError) as exc:
            raise RuntimeError(
                "PAYMENT_CREDENTIAL_KEY is set but is not a valid Fernet key "
                "(urlsafe-base64, 32 bytes)."
            ) from exc

    jwt_secret = os.getenv("SUPABASE_JWT_SECRET")
    if not jwt_secret:
        raise RuntimeError(
            "Cannot encrypt payment credentials: set PAYMENT_CREDENTIAL_KEY "
            "(or SUPABASE_JWT_SECRET for the dev fallback)."
        )
    if not _warned:
        logger.warning("crypto.payment_key_derived_from_jwt_secret")
        _warned = True
    _fernet = Fernet(_derive_from_jwt_secret(jwt_secret))
    return _fernet


def encrypt_secret(plaintext: str) -> str:
    """Return a self-describing ciphertext token (str) for `plaintext`."""
    return _get_fernet().encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt_secret(token: str) -> str:
    """Inverse of `encrypt_secret`. Raises `ValueError` if the token is not ours
    or the key has changed."""
    try:
        return _get_fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError) as exc:
        raise ValueError("Stored credential could not be decrypted") from exc
