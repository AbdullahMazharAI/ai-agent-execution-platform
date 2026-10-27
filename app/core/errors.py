"""
app/core/errors.py
==================
Custom exception hierarchy for the AI Agent Execution Platform.

Design:
  AppError (base, maps to HTTP response)
  ├─ NotFoundError          → 404
  ├─ UnauthorizedError      → 401
  ├─ ForbiddenError         → 403
  ├─ ConflictError          → 409
  ├─ ValidationError        → 422
  ├─ RateLimitError         → 429
  └─ InternalError          → 500
      ├─ DatabaseError
      ├─ QueueError
      └─ AgentError
             ├─ LLMError
             │   ├─ LLMRateLimitError
             │   └─ LLMTimeoutError
             ├─ ToolError
             │   ├─ ToolUnavailableError
             │   └─ ToolTimeoutError
             └─ VerificationError
"""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Base exception that maps to an HTTP response.

    Args:
        detail:     Human-readable error message.
        error_code: Machine-readable identifier (e.g. ``"TASK_NOT_FOUND"``).
        status_code: HTTP status code.
        context:    Optional dict with extra debugging context.
    """

    status_code: int = 500
    error_code: str = "INTERNAL_SERVER_ERROR"

    def __init__(
        self,
        detail: str = "An unexpected error occurred.",
        error_code: str | None = None,
        status_code: int | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        self.detail = detail
        self.error_code = error_code or self.__class__.error_code
        self.status_code = status_code or self.__class__.status_code
        self.context = context or {}
        super().__init__(detail)

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"status_code={self.status_code}, "
            f"error_code={self.error_code!r}, "
            f"detail={self.detail!r})"
        )


# ── 4xx Client Errors ─────────────────────────────────────────────────────────

class NotFoundError(AppError):
    """Resource does not exist or does not belong to the caller."""
    status_code = 404
    error_code = "NOT_FOUND"

    def __init__(self, resource: str = "Resource", resource_id: Any = None) -> None:
        detail = (
            f"{resource} not found."
            if resource_id is None
            else f"{resource} '{resource_id}' not found."
        )
        super().__init__(detail=detail, context={"resource": resource, "id": str(resource_id)})


class UnauthorizedError(AppError):
    """Missing or invalid authentication credentials."""
    status_code = 401
    error_code = "UNAUTHORIZED"

    def __init__(self, detail: str = "Authentication required.") -> None:
        super().__init__(detail=detail)


class ForbiddenError(AppError):
    """Authenticated user lacks permission for this resource."""
    status_code = 403
    error_code = "FORBIDDEN"

    def __init__(self, detail: str = "You do not have permission to access this resource.") -> None:
        super().__init__(detail=detail)


class ConflictError(AppError):
    """Resource state conflict (e.g. cancelling an already completed task)."""
    status_code = 409
    error_code = "CONFLICT"

    def __init__(self, detail: str = "Resource state conflict.", current_state: str | None = None) -> None:
        ctx = {"current_state": current_state} if current_state else {}
        super().__init__(detail=detail, context=ctx)


class InvalidInputError(AppError):
    """Client provided invalid input parameters."""
    status_code = 400
    error_code = "INVALID_INPUT"

    def __init__(self, detail: str = "Invalid input provided.", field: str | None = None) -> None:
        ctx = {"field": field} if field else {}
        super().__init__(detail=detail, context=ctx)


class ValidationError(AppError):
    """Semantic validation error beyond Pydantic's schema validation."""
    status_code = 422
    error_code = "VALIDATION_ERROR"

    def __init__(self, detail: str = "Validation failed.", errors: list[dict[str, Any]] | None = None) -> None:
        ctx = {"errors": errors} if errors else {}
        super().__init__(detail=detail, context=ctx)


# Backward-compatibility alias
RequestValidationError = ValidationError


class RateLimitError(AppError):
    """Caller has exceeded their rate limit."""
    status_code = 429
    error_code = "RATE_LIMIT_EXCEEDED"

    def __init__(self, retry_after: int = 60) -> None:
        super().__init__(
            detail=f"Rate limit exceeded. Retry after {retry_after} seconds.",
            context={"retry_after": retry_after},
        )


# ── 5xx Server / Infrastructure Errors ────────────────────────────────────────

class InternalError(AppError):
    """Generic unexpected server error."""
    status_code = 500
    error_code = "INTERNAL_SERVER_ERROR"


class DatabaseError(InternalError):
    """Database operation failed."""
    error_code = "DATABASE_ERROR"

    def __init__(self, detail: str = "Database operation failed.", operation: str | None = None) -> None:
        ctx = {"operation": operation} if operation else {}
        super().__init__(detail=detail, context=ctx)


class QueueError(InternalError):
    """ARQ / Redis queue operation failed."""
    error_code = "QUEUE_ERROR"

    def __init__(self, detail: str = "Failed to enqueue task.", task_id: str | None = None) -> None:
        ctx = {"task_id": task_id} if task_id else {}
        super().__init__(detail=detail, context=ctx)


# ── Agent / LLM / Tool Errors ─────────────────────────────────────────────────

class AgentError(InternalError):
    """Base for errors raised inside the LangGraph agent."""
    error_code = "AGENT_ERROR"


class LLMError(AgentError):
    """Generic LLM provider error."""
    error_code = "LLM_ERROR"

    def __init__(self, detail: str = "LLM call failed.", provider: str | None = None) -> None:
        ctx = {"provider": provider} if provider else {}
        super().__init__(detail=detail, context=ctx)


class LLMRateLimitError(LLMError):
    """LLM provider returned a 429 / rate-limit response."""
    error_code = "LLM_RATE_LIMITED"

    def __init__(self, provider: str, retry_after: int = 60) -> None:
        super().__init__(
            detail=f"{provider} rate limit hit. Retry after {retry_after}s.",
            provider=provider,
        )
        self.context["retry_after"] = retry_after


class LLMTimeoutError(LLMError):
    """LLM request timed out."""
    error_code = "LLM_TIMEOUT"

    def __init__(self, provider: str, timeout_ms: int | None = None) -> None:
        detail = f"{provider} request timed out."
        if timeout_ms:
            detail += f" (after {timeout_ms}ms)"
        super().__init__(detail=detail, provider=provider)
        if timeout_ms:
            self.context["timeout_ms"] = timeout_ms


class ToolError(AgentError):
    """Generic tool execution error."""
    error_code = "TOOL_ERROR"

    def __init__(self, detail: str = "Tool execution failed.", tool_name: str | None = None) -> None:
        ctx = {"tool_name": tool_name} if tool_name else {}
        super().__init__(detail=detail, context=ctx)


class ToolUnavailableError(ToolError):
    """External tool / service is unavailable."""
    error_code = "TOOL_UNAVAILABLE"

    def __init__(self, tool_name: str) -> None:
        super().__init__(
            detail=f"Tool '{tool_name}' is currently unavailable.",
            tool_name=tool_name,
        )


class ToolTimeoutError(ToolError):
    """Tool execution exceeded the allowed duration."""
    error_code = "TOOL_TIMEOUT"

    def __init__(self, tool_name: str, timeout_ms: int | None = None) -> None:
        detail = f"Tool '{tool_name}' timed out."
        if timeout_ms:
            detail += f" (after {timeout_ms}ms)"
        super().__init__(detail=detail, tool_name=tool_name)


class VerificationError(AgentError):
    """Verification node detected an issue with the generated result."""
    error_code = "VERIFICATION_FAILED"

    def __init__(self, issues: list[str] | None = None) -> None:
        detail = "Verification failed: " + "; ".join(issues or ["unknown issue"])
        super().__init__(detail=detail, context={"issues": issues or []})


class PlannerError(AgentError):
    """Planner failed to produce a valid execution plan."""
    error_code = "PLANNER_ERROR"

    def __init__(self, detail: str = "Planner failed to generate a valid plan.", reason: str | None = None) -> None:
        ctx = {"reason": reason} if reason else {}
        super().__init__(detail=detail, context=ctx)
