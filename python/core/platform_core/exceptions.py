from fastapi import HTTPException, status


from typing import Any


class PlatformError(HTTPException):
    def __init__(
        self, status_code: int, code: str, message: str, details: dict[str, Any] | None = None
    ):
        super().__init__(
            status_code=status_code,
            detail={"code": code, "message": message, "details": details or {}},
        )
        self.code = code


class AuthenticationRequired(PlatformError):
    def __init__(self, message: str = "Authentication required"):
        super().__init__(status.HTTP_401_UNAUTHORIZED, "AUTHENTICATION_REQUIRED", message)


class ValidationError(PlatformError):
    def __init__(self, message: str = "Validation failed", details: dict[str, Any] | None = None):
        # Doc 12 §10.6 maps validation failures to HTTP 422 VALIDATION_ERROR.
        status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
        super().__init__(
            status_code,
            "VALIDATION_ERROR",
            message,
            details,
        )


class ConflictError(PlatformError):
    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(status.HTTP_409_CONFLICT, "CONFLICT", message, details)


class SessionExpired(PlatformError):
    def __init__(self, message: str = "Session expired"):
        super().__init__(status.HTTP_401_UNAUTHORIZED, "SESSION_EXPIRED", message)


class PermissionDenied(PlatformError):
    def __init__(self, permission: str):
        super().__init__(
            status.HTTP_403_FORBIDDEN,
            "PERMISSION_DENIED",
            f"Permission denied: {permission}",
            {"permission": permission},
        )


class EntitlementRequired(PlatformError):
    def __init__(self, module_id: str):
        super().__init__(
            status.HTTP_403_FORBIDDEN,
            "ENTITLEMENT_REQUIRED",
            f"Entitlement required: {module_id}",
            {"module_id": module_id},
        )


class ModuleNotActive(PlatformError):
    def __init__(self, module_id: str):
        super().__init__(
            status.HTTP_403_FORBIDDEN,
            "MODULE_NOT_ACTIVE",
            f"Module not active: {module_id}",
            {"module_id": module_id},
        )


class LocationAccessDenied(PlatformError):
    def __init__(self) -> None:
        super().__init__(
            status.HTTP_403_FORBIDDEN,
            "LOCATION_ACCESS_DENIED",
            "Location access denied",
        )


class MembershipRequired(PlatformError):
    def __init__(self) -> None:
        super().__init__(
            status.HTTP_403_FORBIDDEN,
            "MEMBERSHIP_REQUIRED",
            "Active business membership required",
        )


class ResourceNotFound(PlatformError):
    def __init__(self, resource: str = "Resource"):
        super().__init__(
            status.HTTP_404_NOT_FOUND,
            "RESOURCE_NOT_FOUND",
            f"{resource} not found",
        )


class ResourceStateDenied(PlatformError):
    """Canonical resource/workflow-state gate (Doc 12 §8.9 gate [9] → CONFLICT)."""

    def __init__(
        self,
        resource: str,
        state: str,
        *,
        action: str | None = None,
        allowed_states: list[str] | None = None,
    ):
        details: dict[str, Any] = {
            "gate": "resource_state",
            "resource": resource,
            "state": state,
        }
        if action is not None:
            details["action"] = action
        if allowed_states is not None:
            details["allowed_states"] = allowed_states
        super().__init__(
            status.HTTP_409_CONFLICT,
            "CONFLICT",
            f"Resource state does not permit this action: {resource} is {state}",
            details,
        )


class BusinessSuspended(PlatformError):
    """Platform standing blocks commercial intake (Doc 04 §6.1, Doc 09 §15.1).

    Distinct from ResourceStateDenied: that gate is about the Business
    *lifecycle* (`state`), this one is about platform *standing* (`status`).
    They are independent axes (Doc 03 §1.6) and a caller must be able to tell
    "your business is closed" from "your business is suspended" — the second
    has an appeal path, the first does not.

    Doc 09 §15.1 requires the suspended state be conveyed "without exposing
    sensitive policy internals", so no reason detail is returned here.
    """

    def __init__(self, action: str | None = None):
        details: dict[str, Any] = {"gate": "business_status", "status": "suspended"}
        if action is not None:
            details["action"] = action
        super().__init__(
            status.HTTP_409_CONFLICT,
            "BUSINESS_SUSPENDED",
            "This business is suspended and cannot accept new orders or bookings.",
            details,
        )


class PermissionDelegationError(PlatformError):
    def __init__(self, excess: set[str]):
        super().__init__(
            status.HTTP_403_FORBIDDEN,
            "PERMISSION_DENIED",
            f"Cannot grant permissions not held: {', '.join(sorted(excess))}",
            {"excess_permissions": sorted(excess)},
        )
