"""Benchbook Domain Exceptions."""

from __future__ import annotations

from typing import Any


class BenchbookError(Exception):
    """Base exception for all Benchbook domain errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class JobNotFoundError(BenchbookError):
    """Raised when a requested repair job does not exist."""


class InvalidStateTransitionError(BenchbookError):
    """Raised when attempting an unauthorized or invalid lifecycle transition."""

    def __init__(self, current_state: str, target_state: str, reason: str = "") -> None:
        msg = f"Cannot transition from '{current_state}' to '{target_state}'."
        if reason:
            msg += f" Reason: {reason}"
        super().__init__(
            msg, {"current_state": current_state, "target_state": target_state, "reason": reason}
        )
        self.current_state = current_state
        self.target_state = target_state


class StateConflictError(BenchbookError):
    """Raised when an optimistic concurrency check fails (version mismatch)."""

    def __init__(
        self,
        expected_version: int,
        current_version: int,
        current_job: Any = None,
        message: str | None = None,
    ) -> None:
        msg = (
            message
            or f"State conflict: expected version {expected_version}, but current version is {current_version}."
        )
        super().__init__(
            msg,
            {
                "expected_version": expected_version,
                "current_version": current_version,
                "current_job": current_job,
            },
        )
        self.expected_version = expected_version
        self.current_version = current_version
        self.current_job = current_job


class HumanApprovalRequiredError(BenchbookError):
    """Raised when an automated or assistant actor attempts a human-only action."""

    def __init__(self, action: str, actor_type: str) -> None:
        super().__init__(
            f"Human approval required for action '{action}'. Actor '{actor_type}' cannot perform this action.",
            {"action": action, "actor_type": actor_type},
        )
        self.action = action
        self.actor_type = actor_type


class ValidationError(BenchbookError):
    """Raised when domain validation rules are violated."""


class IdempotencyConflictError(BenchbookError):
    """Raised when an idempotency key is reused with a different request payload or operation."""

    def __init__(self, message: str, idempotency_key: str | None = None) -> None:
        details = {"idempotency_key": idempotency_key} if idempotency_key else {}
        super().__init__(message, details)
        self.idempotency_key = idempotency_key


class AssistantError(BenchbookError):
    """Base error for assistant adapter failures."""


class AssistantTimeoutError(AssistantError):
    """Assistant invocation timed out."""


class AssistantBusyError(AssistantError):
    """Assistant service is busy or rate-limited."""


class AssistantUnavailableError(AssistantError):
    """Assistant service is unreachable or disabled."""


class AssistantInvalidOutputError(AssistantError):
    """Assistant produced ungrounded or unparseable output."""


class CapacityExceededError(BenchbookError):
    """Raised when a workspace or global capacity/rate limit ceiling is exceeded."""


class SessionExpiredError(BenchbookError):
    """Raised when a workbench session token is invalid, missing, or expired."""


class WorkspaceNotFoundError(BenchbookError):
    """Raised when a requested workspace does not exist or has expired."""


class OriginRefusedError(BenchbookError):
    """Raised when an Origin header fails closed in production."""


class IneligibleAdviceError(BenchbookError):
    """Raised when a job state is not eligible for the requested advisory operation."""
