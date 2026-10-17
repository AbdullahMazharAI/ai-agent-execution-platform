"""
tests/test_errors.py
====================
Unit tests for custom exception hierarchy in app/core/errors.py.

Verifies:
  - Error class hierarchy and inheritance
  - Status codes and default error codes
  - Serialization and string representations
  - Context attachment
"""

from __future__ import annotations

import pytest

from app.core.errors import (
    AgentError,
    AppError,
    ConflictError,
    DatabaseError,
    ForbiddenError,
    InternalError,
    InvalidInputError,
    LLMError,
    LLMRateLimitError,
    LLMTimeoutError,
    NotFoundError,
    QueueError,
    RateLimitError,
    ToolError,
    ToolTimeoutError,
    ToolUnavailableError,
    UnauthorizedError,
    ValidationError,
    VerificationError,
)


class TestAppErrors:
    def test_base_app_error_defaults(self) -> None:
        err = AppError("Something went wrong")
        assert err.status_code == 500
        assert err.error_code == "INTERNAL_SERVER_ERROR"
        assert err.detail == "Something went wrong"
        assert err.context == {}
        assert "AppError" in repr(err)

    def test_not_found_error(self) -> None:
        err = NotFoundError("Task", "12345")
        assert err.status_code == 404
        assert err.error_code == "NOT_FOUND"
        assert "Task '12345' not found" in err.detail
        assert err.context["id"] == "12345"

    def test_unauthorized_error(self) -> None:
        err = UnauthorizedError()
        assert err.status_code == 401
        assert err.error_code == "UNAUTHORIZED"

    def test_forbidden_error(self) -> None:
        err = ForbiddenError("Access forbidden")
        assert err.status_code == 403
        assert err.error_code == "FORBIDDEN"

    def test_conflict_error(self) -> None:
        err = ConflictError("Resource already exists")
        assert err.status_code == 409
        assert err.error_code == "CONFLICT"

    def test_validation_error(self) -> None:
        err = ValidationError("Field required", errors=[{"field": "goal", "issue": "missing"}])
        assert err.status_code == 422
        assert err.error_code == "VALIDATION_ERROR"
        assert "errors" in err.context

    def test_rate_limit_error(self) -> None:
        err = RateLimitError(retry_after=60)
        assert err.status_code == 429
        assert err.error_code == "RATE_LIMIT_EXCEEDED"
        assert err.context.get("retry_after") == 60

    def test_invalid_input_error(self) -> None:
        err = InvalidInputError("Invalid parameter")
        assert err.status_code == 400
        assert err.error_code == "INVALID_INPUT"

    def test_internal_error_hierarchy(self) -> None:
        db_err = DatabaseError("Connection timeout")
        assert isinstance(db_err, InternalError)
        assert isinstance(db_err, AppError)
        assert db_err.status_code == 500

        queue_err = QueueError("Redis connection refused")
        assert isinstance(queue_err, InternalError)

        agent_err = AgentError("Agent failed")
        assert isinstance(agent_err, InternalError)

    def test_llm_and_tool_errors(self) -> None:
        llm_rl = LLMRateLimitError(provider="groq", retry_after=30)
        assert isinstance(llm_rl, LLMError)
        assert isinstance(llm_rl, AgentError)
        assert llm_rl.error_code == "LLM_RATE_LIMITED"
        assert llm_rl.context["provider"] == "groq"
        assert llm_rl.context["retry_after"] == 30

        llm_timeout = LLMTimeoutError(provider="groq", timeout_ms=45000)
        assert isinstance(llm_timeout, LLMError)
        assert llm_timeout.error_code == "LLM_TIMEOUT"
        assert llm_timeout.context["timeout_ms"] == 45000

        tool_unavail = ToolUnavailableError(tool_name="web_search")
        assert isinstance(tool_unavail, ToolError)
        assert tool_unavail.error_code == "TOOL_UNAVAILABLE"

        tool_timeout = ToolTimeoutError(tool_name="web_search", timeout_ms=10000)
        assert isinstance(tool_timeout, ToolError)
        assert tool_timeout.error_code == "TOOL_TIMEOUT"

        verif_err = VerificationError(issues=["Goal criteria not satisfied"])
        assert isinstance(verif_err, AgentError)
        assert verif_err.error_code == "VERIFICATION_FAILED"
        assert "Goal criteria not satisfied" in verif_err.detail

