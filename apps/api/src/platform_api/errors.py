from fastapi import Request
from fastapi.responses import JSONResponse

from platform_core.exceptions import PlatformError
from platform_core.logging import get_logger

logger = get_logger("platform_api.error")


async def platform_error_handler(request: Request, exc: PlatformError) -> JSONResponse:
    correlation_id = request.headers.get("X-Correlation-Id", "")
    detail = exc.detail if isinstance(exc.detail, dict) else {"message": str(exc.detail)}
    code = detail.get("code", "UNKNOWN")

    # AUD-11: every handled error leaves a line. 4xx (gate denials, auth
    # failures, validation) at WARNING; 5xx at ERROR with the traceback.
    # correlation_id / identity_id / business_id ride along from contextvars.
    log = logger.error if exc.status_code >= 500 else logger.warning
    log(
        "platform_error",
        code=code,
        status=exc.status_code,
        method=request.method,
        path=request.url.path,
        exc_info=exc if exc.status_code >= 500 else None,
    )

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": code,
                "message": detail.get("message", str(exc.detail)),
                "details": detail.get("details", {}),
            },
            "meta": {"correlation_id": correlation_id},
        },
        headers={"X-Correlation-Id": correlation_id} if correlation_id else None,
    )
