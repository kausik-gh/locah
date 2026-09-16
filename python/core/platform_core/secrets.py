"""Resolution of signing secrets (Doc 12 §15 — platform security).

A signing secret that silently falls back to a constant committed in this
repository is not a secret. Both the Website preview token and the payment
webhook signature previously did exactly that, so anyone reading the repo could
mint a preview token for any Business, or forge a webhook.

The fallback is kept for local development, where the alternative is that
nothing runs out of the box, but it is refused anywhere else and it says so
loudly when it is used.
"""

from __future__ import annotations

import os

from platform_core.logging import get_logger

_log = get_logger("platform.secrets")

# Anything not in this set is treated as a deployed environment.
_DEV_ENVIRONMENTS = {"", "development", "dev", "local", "test", "testing", "ci"}

_warned: set[str] = set()


def is_development() -> bool:
    return os.getenv("ENVIRONMENT", "").strip().lower() in _DEV_ENVIRONMENTS


def resolve_signing_secret(name: str, dev_default: str, *, fallback_env: str | None = None) -> str:
    """The configured secret, or the development default if that is allowed.

    Raises in a deployed environment when `name` (and any `fallback_env`) is
    unset, rather than signing with a value that is public.
    """
    value = os.getenv(name, "").strip()
    if not value and fallback_env:
        value = os.getenv(fallback_env, "").strip()
    if value:
        return value

    if not is_development():
        raise RuntimeError(
            f"{name} is not set. It signs security tokens and has no safe default "
            f"outside development."
        )

    if name not in _warned:
        _warned.add(name)
        _log.warning(
            "platform.signing_secret_default_in_use",
            secret=name,
            detail="development default in use; set this before deploying",
        )
    return dev_default
