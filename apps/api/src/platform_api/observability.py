"""Request logging + correlation-id middleware (AUD-11).

Pure ASGI so it wraps everything (including a rate-limit 429) and can read the
final status. Binds `correlation_id` into structlog contextvars at request
start — `resolve_request_context` adds `identity_id` / `business_id` once the
identity resolves — and clears them at the end so nothing leaks between
requests on a reused worker.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from platform_core.logging import bind_request_context, clear_request_context, get_logger
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = get_logger("platform_api.request")

# Paths not worth a log line each (health probes, docs).
_QUIET_PREFIXES = ("/health", "/docs", "/redoc", "/openapi.json", "/favicon")


class RequestLogMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
        correlation_id = headers.get("x-correlation-id") or str(uuid.uuid4())
        method = scope["method"]
        path = scope["path"]

        clear_request_context()
        bind_request_context(correlation_id=correlation_id)

        status_code = 500
        started = time.monotonic()

        async def _send(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                message.setdefault("headers", [])
                message["headers"].append(
                    (b"x-correlation-id", correlation_id.encode())
                )
            await send(message)

        try:
            await self.app(scope, receive, _send)
        except Exception:
            logger.error(
                "request.unhandled_exception",
                method=method,
                path=path,
                duration_ms=round((time.monotonic() - started) * 1000, 1),
                exc_info=True,
            )
            raise
        finally:
            if not path.startswith(_QUIET_PREFIXES):
                duration_ms = round((time.monotonic() - started) * 1000, 1)
                event = "request.completed"
                if status_code >= 500:
                    logger.error(event, method=method, path=path, status=status_code, duration_ms=duration_ms)
                elif status_code >= 400:
                    logger.warning(event, method=method, path=path, status=status_code, duration_ms=duration_ms)
                else:
                    logger.info(event, method=method, path=path, status=status_code, duration_ms=duration_ms)
            clear_request_context()


def log_gate_denial(code: str, detail: dict[str, Any]) -> None:
    """Called from the PlatformError handler for 4xx auth/gate failures."""
    logger.warning(
        "gate.denied",
        code=code,
        gate=detail.get("gate"),
        permission=detail.get("permission"),
        module_id=detail.get("module_id"),
    )
