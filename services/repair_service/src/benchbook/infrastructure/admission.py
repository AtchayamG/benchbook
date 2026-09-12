"""Benchbook SQL-Backed Atomic Inference Admission Engine.

Enforces:
1. Exactly one active advisory operation across the database globally.
2. Atomic 6-send reservations consumed on attempt (no refund bypass).
3. Ceilings: max 6 sends/60s globally, 120 sends/24h globally, 24 sends/24h per workspace.
4. Durable 15-minute provider 429 cooldown.
5. Idempotent response replay for identical (workspace, request_key, payload).
6. Zero DB transactions held across provider network I/O.
7. Strict concurrency and cleanup guarantees across SQLite and PostgreSQL.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

from benchbook.domain.errors import (
    AssistantBusyError,
    AssistantUnavailableError,
    IdempotencyConflictError,
)
from benchbook.infrastructure.database import get_db_connection

RESERVED_SENDS: int = 6
GLOBAL_LIMIT_60S: int = 6
GLOBAL_LIMIT_24H: int = 120
WORKSPACE_LIMIT_24H: int = 24
STORED_DEADLINE_SECONDS: float = 120.0
PROVIDER_429_COOLDOWN_SECONDS: float = 900.0  # 15 minutes
_ADMISSION_LOCK: int = 8_801_103_331_031


class AdmissionState(StrEnum):
    RESERVED = "RESERVED"
    DISPATCHED = "DISPATCHED"
    SUCCEEDED = "SUCCEEDED"
    FAILED_CONFIRMED = "FAILED_CONFIRMED"
    UNCERTAIN = "UNCERTAIN"
    RECOVERED = "RECOVERED"


class AdmissionFailureCode(StrEnum):
    PROVIDER_429 = "provider_429"
    PROVIDER_FAILURE = "provider_failure"
    INVALID_OUTPUT = "invalid_output"
    CANCELLED = "cancelled"
    DEADLINE_EXPIRED = "deadline_expired"
    EXECUTION_UNKNOWN = "execution_unknown"


class AdmissionRefusedError(AssistantBusyError):
    """Admission refused due to active concurrency, quotas, cooldown, or state."""


class AdmissionReplayConflictError(IdempotencyConflictError):
    """Replay conflict due to altered request payload or execution identity."""


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


@dataclass(frozen=True)
class AdmissionReservationRequest:
    reservation_id: str
    workspace_id: str
    owner_id: str
    request_key_hash: str
    payload_hash: str
    reserved_sends: int = RESERVED_SENDS


class InferenceAdmissionStore:
    """Atomic multi-process admission controller over SQLite or PostgreSQL."""

    def __init__(self, db_target: str) -> None:
        self.db_target = db_target

    def _lock_admission(self, conn: Any) -> None:
        if conn.is_postgres:
            conn.execute("SELECT pg_advisory_xact_lock(?)", (_ADMISSION_LOCK,))

    def reserve(self, request: AdmissionReservationRequest) -> dict[str, Any]:
        """Atomically reserve inference admission slot or return cached completed response."""
        now = _now_utc()
        now_str = _iso(now)
        deadline_str = _iso(now + timedelta(seconds=STORED_DEADLINE_SECONDS))

        try:
            with get_db_connection(self.db_target, write=True) as conn:
                self._lock_admission(conn)

                # Check for existing reservation by ID
                cur_by_id = conn.execute(
                    "SELECT * FROM inference_admissions WHERE reservation_id = ?",
                    (request.reservation_id,),
                )
                row_by_id = cur_by_id.fetchone()

                # Check for existing reservation by (workspace_id, request_key_hash)
                cur_by_key = conn.execute(
                    """
                    SELECT * FROM inference_admissions
                    WHERE workspace_id = ? AND request_key_hash = ?
                    """,
                    (request.workspace_id, request.request_key_hash),
                )
                row_by_key = cur_by_key.fetchone()

                if row_by_id is not None:
                    row_dict = dict(row_by_id)
                    matches = (
                        row_dict["workspace_id"] == request.workspace_id
                        and row_dict["owner_id"] == request.owner_id
                        and row_dict["request_key_hash"] == request.request_key_hash
                        and row_dict["payload_hash"] == request.payload_hash
                    )
                    if matches:
                        return row_dict
                    raise AdmissionReplayConflictError(
                        "Reservation identity replay conflict on changed payload.",
                        idempotency_key=request.request_key_hash,
                    )

                if row_by_key is not None:
                    row_dict = dict(row_by_key)
                    if row_dict["payload_hash"] == request.payload_hash:
                        return row_dict
                    raise AdmissionReplayConflictError(
                        "Request key already exists with different request parameters.",
                        idempotency_key=request.request_key_hash,
                    )

                # Check 15-minute provider 429 cooldown
                cooldown_cutoff = _iso(now - timedelta(seconds=PROVIDER_429_COOLDOWN_SECONDS))
                cur_cooldown = conn.execute(
                    """
                    SELECT 1 FROM inference_admissions
                    WHERE failure_code = ? AND completed_at > ?
                    LIMIT 1
                    """,
                    (AdmissionFailureCode.PROVIDER_429.value, cooldown_cutoff),
                )
                if cur_cooldown.fetchone() is not None:
                    raise AdmissionRefusedError("Provider 429 cooldown active (15 minutes).")

                # Check single active operation globally
                cur_active = conn.execute(
                    "SELECT 1 FROM inference_admissions WHERE is_active = 1 LIMIT 1"
                )
                if cur_active.fetchone() is not None:
                    raise AdmissionRefusedError(
                        "Another advisory inference operation is currently active."
                    )

                # Check global rolling 60-second limit (max 6 sends)
                g60_cutoff = _iso(now - timedelta(seconds=60))
                cur_g60 = conn.execute(
                    """
                    SELECT COALESCE(SUM(reserved_sends), 0) AS total FROM inference_admissions
                    WHERE is_active = 1 OR released_at > ?
                    """,
                    (g60_cutoff,),
                )
                g60_row = cur_g60.fetchone()
                g60_total = g60_row["total"] if g60_row else 0
                if g60_total + request.reserved_sends > GLOBAL_LIMIT_60S:
                    raise AdmissionRefusedError(
                        f"Global 60-second reservation limit exceeded ({g60_total}/{GLOBAL_LIMIT_60S} reserved sends)."
                    )

                # Check global rolling 24-hour limit (max 120 sends)
                g24h_cutoff = _iso(now - timedelta(hours=24))
                cur_g24h = conn.execute(
                    """
                    SELECT COALESCE(SUM(reserved_sends), 0) AS total FROM inference_admissions
                    WHERE is_active = 1 OR released_at > ?
                    """,
                    (g24h_cutoff,),
                )
                g24h_row = cur_g24h.fetchone()
                g24h_total = g24h_row["total"] if g24h_row else 0
                if g24h_total + request.reserved_sends > GLOBAL_LIMIT_24H:
                    raise AdmissionRefusedError(
                        f"Global 24-hour reservation limit exceeded ({g24h_total}/{GLOBAL_LIMIT_24H} reserved sends)."
                    )

                # Check workspace rolling 24-hour limit (max 24 sends)
                cur_w24h = conn.execute(
                    """
                    SELECT COALESCE(SUM(reserved_sends), 0) AS total FROM inference_admissions
                    WHERE workspace_id = ? AND (is_active = 1 OR released_at > ?)
                    """,
                    (request.workspace_id, g24h_cutoff),
                )
                w24h_row = cur_w24h.fetchone()
                w24h_total = w24h_row["total"] if w24h_row else 0
                if w24h_total + request.reserved_sends > WORKSPACE_LIMIT_24H:
                    raise AdmissionRefusedError(
                        f"Workspace 24-hour reservation limit exceeded ({w24h_total}/{WORKSPACE_LIMIT_24H} reserved sends)."
                    )

                # Insert reservation
                conn.execute(
                    """
                    INSERT INTO inference_admissions (
                        reservation_id, workspace_id, owner_id, request_key_hash,
                        payload_hash, reserved_sends, deadline_at, state,
                        is_active, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
                    """,
                    (
                        request.reservation_id,
                        request.workspace_id,
                        request.owner_id,
                        request.request_key_hash,
                        request.payload_hash,
                        request.reserved_sends,
                        deadline_str,
                        AdmissionState.RESERVED.value,
                        now_str,
                    ),
                )
                cur_inserted = conn.execute(
                    "SELECT * FROM inference_admissions WHERE reservation_id = ?",
                    (request.reservation_id,),
                )
                row = cur_inserted.fetchone()
                assert row is not None
                return dict(row)
        except (AdmissionRefusedError, AdmissionReplayConflictError):
            raise
        except Exception as exc:
            raise AssistantUnavailableError("Inference admission storage unavailable.") from exc

    def mark_dispatched(self, reservation_id: str, owner_id: str) -> dict[str, Any]:
        """Mark reservation as dispatched to network transport."""
        now_str = _iso(_now_utc())
        try:
            with get_db_connection(self.db_target, write=True) as conn:
                self._lock_admission(conn)
                cur = conn.execute(
                    "SELECT * FROM inference_admissions WHERE reservation_id = ?",
                    (reservation_id,),
                )
                row = cur.fetchone()
                if not row or row["owner_id"] != owner_id:
                    raise AdmissionRefusedError("Reservation unavailable to this execution.")
                if row["state"] != AdmissionState.RESERVED.value:
                    raise AdmissionRefusedError("Reservation already dispatched or closed.")

                conn.execute(
                    """
                    UPDATE inference_admissions SET
                        state = ?,
                        dispatched_at = ?
                    WHERE reservation_id = ?
                    """,
                    (AdmissionState.DISPATCHED.value, now_str, reservation_id),
                )
                cur_updated = conn.execute(
                    "SELECT * FROM inference_admissions WHERE reservation_id = ?",
                    (reservation_id,),
                )
                updated = cur_updated.fetchone()
                assert updated is not None
                return dict(updated)
        except AdmissionRefusedError:
            raise
        except Exception as exc:
            raise AssistantUnavailableError("Admission dispatch failed.") from exc

    def finish(
        self,
        reservation_id: str,
        owner_id: str,
        state: AdmissionState,
        *,
        cleanup_completed: bool,
        actual_sends: int | None = None,
        actual_total_tokens: int | None = None,
        failure_code: AdmissionFailureCode | None = None,
        response_body: str | None = None,
    ) -> dict[str, Any]:
        """Record final outcome, releasing active concurrency only when cleanup is completed."""
        now_str = _iso(_now_utc())
        if state not in (
            AdmissionState.SUCCEEDED,
            AdmissionState.FAILED_CONFIRMED,
            AdmissionState.UNCERTAIN,
        ):
            raise AdmissionRefusedError("Invalid settlement state.")
        if not cleanup_completed:
            state = AdmissionState.UNCERTAIN
        is_terminal = state not in (
            AdmissionState.UNCERTAIN,
            AdmissionState.RESERVED,
            AdmissionState.DISPATCHED,
        )
        can_release = is_terminal and (cleanup_completed is True)
        is_active = 0 if can_release else 1
        released_at = now_str if can_release else None

        failure_code_val = failure_code.value if failure_code else None

        try:
            with get_db_connection(self.db_target, write=True) as conn:
                self._lock_admission(conn)
                cur_check = conn.execute(
                    "SELECT * FROM inference_admissions WHERE reservation_id = ?",
                    (reservation_id,),
                )
                existing = cur_check.fetchone()
                if not existing or existing["owner_id"] != owner_id:
                    raise AdmissionRefusedError("Reservation unavailable to this execution.")

                existing_dict = dict(existing)
                # Idempotent replay if already settled to same terminal state
                if (
                    existing_dict["state"] == state.value
                    and existing_dict.get("actual_sends") == actual_sends
                    and existing_dict.get("failure_code") == failure_code_val
                    and bool(existing_dict.get("cleanup_completed")) == cleanup_completed
                    and existing_dict.get("response_body") == response_body
                ):
                    return existing_dict

                if existing_dict["state"] in (
                    AdmissionState.SUCCEEDED.value,
                    AdmissionState.FAILED_CONFIRMED.value,
                    AdmissionState.RECOVERED.value,
                ):
                    raise AdmissionRefusedError("Reservation is already terminal.")

                conn.execute(
                    """
                    UPDATE inference_admissions SET
                        state = ?,
                        is_active = ?,
                        completed_at = ?,
                        released_at = ?,
                        actual_sends = ?,
                        actual_total_tokens = ?,
                        cleanup_completed = ?,
                        failure_code = ?,
                        response_body = ?
                    WHERE reservation_id = ? AND owner_id = ?
                    """,
                    (
                        state.value,
                        is_active,
                        now_str,
                        released_at,
                        actual_sends,
                        actual_total_tokens,
                        1 if cleanup_completed else 0,
                        failure_code_val,
                        response_body,
                        reservation_id,
                        owner_id,
                    ),
                )
                cur = conn.execute(
                    "SELECT * FROM inference_admissions WHERE reservation_id = ?",
                    (reservation_id,),
                )
                row = cur.fetchone()
                assert row is not None
                return dict(row)
        except (AdmissionRefusedError, AdmissionReplayConflictError):
            raise
        except Exception as exc:
            raise AssistantUnavailableError("Admission settlement failed.") from exc

    def recover_dead(
        self,
        reservation_id: str,
        owner_id: str | None = None,
        *,
        operator_id: str,
        reason: str = "operator_reset",
        confirmed_dead: bool = False,
    ) -> dict[str, Any]:
        """Safely recover a fenced, orphaned, or uncertain reservation without refunding quota."""
        if not confirmed_dead:
            raise AdmissionRefusedError("Explicit confirmation of terminated execution required.")
        now_str = _iso(_now_utc())
        try:
            with get_db_connection(self.db_target, write=True) as conn:
                self._lock_admission(conn)
                cur = conn.execute(
                    "SELECT * FROM inference_admissions WHERE reservation_id = ?",
                    (reservation_id,),
                )
                row = cur.fetchone()
                if not row:
                    raise AdmissionRefusedError("Reservation not found.")
                if owner_id is not None and row["owner_id"] != owner_id:
                    raise AdmissionRefusedError("Owner mismatch.")

                row_dict = dict(row)
                if row_dict["state"] == AdmissionState.RECOVERED.value:
                    if (
                        row_dict.get("recovery_operator_id") == operator_id
                        and row_dict.get("recovery_reason") == reason
                    ):
                        return row_dict
                    raise AdmissionReplayConflictError("Recovery replay conflict.")

                if row_dict["state"] in (
                    AdmissionState.SUCCEEDED.value,
                    AdmissionState.FAILED_CONFIRMED.value,
                ):
                    raise AdmissionRefusedError("Reservation is already settled.")

                conn.execute(
                    """
                    UPDATE inference_admissions SET
                        state = ?,
                        is_active = 0,
                        released_at = ?,
                        recovered_at = ?,
                        recovery_operator_id = ?,
                        recovery_reason = ?,
                        completed_at = COALESCE(completed_at, ?)
                    WHERE reservation_id = ?
                    """,
                    (
                        AdmissionState.RECOVERED.value,
                        now_str,
                        now_str,
                        operator_id,
                        reason,
                        now_str,
                        reservation_id,
                    ),
                )
                cur_updated = conn.execute(
                    "SELECT * FROM inference_admissions WHERE reservation_id = ?",
                    (reservation_id,),
                )
                updated = cur_updated.fetchone()
                assert updated is not None
                return dict(updated)
        except (AdmissionRefusedError, AdmissionReplayConflictError):
            raise
        except Exception as exc:
            raise AssistantUnavailableError("Admission recovery failed.") from exc
