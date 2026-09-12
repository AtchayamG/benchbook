"""Benchbook Public Workbench Session Management and Isolation.

Enforces:
1. Opaque 32-byte HttpOnly session cookies, 30-day lifetime.
2. SHA-256 token hashing in SQL (token plaintext never logged or returned).
3. Exact Origin header validation in production.
4. Quota ceilings: max 50 jobs/workspace, 1000 active workspaces globally, 30 sessions/min.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from benchbook.config import is_production_environment
from benchbook.domain.errors import (
    OriginRefusedError,
    SessionExpiredError,
)
from benchbook.domain.models import SessionStatus, Workspace

COOKIE_NAME = "benchbook_session"
COOKIE_MAX_AGE_SECONDS = 30 * 86400  # 30 days
TOKEN_BYTES = 32
MAX_JOBS_PER_WORKSPACE = 50
MAX_GLOBAL_WORKSPACES = 1000
MAX_SESSIONS_PER_MINUTE = 30
LEGACY_WORKSPACE_ID = "legacy_local_workspace"


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def generate_session_token() -> str:
    """Generate cryptographically secure 32-byte (64 hex char) opaque token."""
    return secrets.token_hex(TOKEN_BYTES)


def hash_session_token(raw_token: str) -> str:
    """Hash session token with SHA-256 for durable SQL storage."""
    return hashlib.sha256(raw_token.strip().encode("utf-8")).hexdigest()


def validate_origin(
    origin: str | None,
    allowed_origins: list[str],
    environment: str,
) -> None:
    """Verify request Origin header against configured CORS origins.

    Fails closed in production on missing, null, or untrusted Origin.
    """
    if is_production_environment(environment):
        if not origin or origin.strip() == "" or origin.lower() == "null":
            raise OriginRefusedError("Missing or null Origin header rejected in production.")
        normalized_allowed = {o.strip().rstrip("/") for o in allowed_origins if o.strip()}
        if origin.strip().rstrip("/") not in normalized_allowed:
            raise OriginRefusedError(f"Untrusted Origin '{origin}' rejected in production.")


class SessionManager:
    """Session and workspace lifetime, lookup, and quota enforcement."""

    def __init__(self, store: Any) -> None:
        self.store = store

    def create_or_resume_session(
        self,
        raw_token: str | None,
        origin: str | None,
        allowed_origins: list[str],
        environment: str,
    ) -> tuple[Workspace, str, bool]:
        """Create a new workspace session or resume an existing valid one.

        Returns (workspace, raw_token_to_set, is_new).
        """
        validate_origin(origin, allowed_origins, environment)

        now = _now_utc()
        now_str = _iso(now)

        if raw_token:
            token_hash = hash_session_token(raw_token)
            ws = self.store.get_workspace_by_token_hash(token_hash)
            if ws and ws.workspace_id != LEGACY_WORKSPACE_ID:
                try:
                    exp_dt = datetime.fromisoformat(ws.expires_at)
                    if exp_dt > now:
                        self.store.touch_workspace_activity(ws.workspace_id, now_str)
                        return ws, raw_token, False
                except (ValueError, TypeError):
                    pass

        workspace_id = f"ws_{secrets.token_hex(12)}"
        expires_at = _iso(now + timedelta(days=30))
        workspace = Workspace(
            workspace_id=workspace_id,
            created_at=now_str,
            expires_at=expires_at,
            last_active_at=now_str,
        )

        new_raw_token = generate_session_token()
        new_token_hash = hash_session_token(new_raw_token)

        if hasattr(self.store, "create_workspace_and_token"):
            self.store.create_workspace_and_token(
                workspace=workspace,
                token_hash=new_token_hash,
                expires_at=expires_at,
                max_sessions_per_minute=MAX_SESSIONS_PER_MINUTE,
                max_global_workspaces=MAX_GLOBAL_WORKSPACES,
            )
        else:
            self.store.save_workspace_and_token(
                workspace=workspace,
                token_hash=new_token_hash,
                expires_at=expires_at,
            )

        return workspace, new_raw_token, True

    def authenticate_session(
        self,
        raw_token: str | None,
        environment: str,
    ) -> str:
        """Resolve workspace_id from session cookie, failing closed on invalid/expired tokens."""
        now = _now_utc()
        if not raw_token:
            if is_production_environment(environment):
                raise SessionExpiredError(
                    "No active workspace session cookie found. Call POST /api/session."
                )
            # In local/test environment, provide the legacy local workspace
            return LEGACY_WORKSPACE_ID

        token_hash = hash_session_token(raw_token)
        ws = self.store.get_workspace_by_token_hash(token_hash)
        if not ws:
            raise SessionExpiredError("Session token not found or invalid.")

        if ws.workspace_id == LEGACY_WORKSPACE_ID:
            raise SessionExpiredError("Access to legacy workspace is reserved and forbidden.")

        try:
            exp_dt = datetime.fromisoformat(ws.expires_at)
            if exp_dt <= now:
                raise SessionExpiredError(
                    "Session has expired. Call POST /api/session to start a new workbench."
                )
        except (ValueError, TypeError) as err:
            raise SessionExpiredError("Malformed session expiry timestamp.") from err

        self.store.touch_workspace_activity(ws.workspace_id, _iso(now))
        return str(ws.workspace_id)

    def get_session_status(self, raw_token: str | None) -> SessionStatus:
        """Get status of the current workspace session."""
        if not raw_token:
            return SessionStatus(authenticated=False)

        token_hash = hash_session_token(raw_token)
        ws = self.store.get_workspace_by_token_hash(token_hash)
        if not ws or ws.workspace_id == LEGACY_WORKSPACE_ID:
            return SessionStatus(authenticated=False)

        now = _now_utc()
        try:
            exp_dt = datetime.fromisoformat(ws.expires_at)
            if exp_dt <= now:
                return SessionStatus(authenticated=False)
        except (ValueError, TypeError):
            return SessionStatus(authenticated=False)

        job_count = self.store.count_workspace_jobs(ws.workspace_id)
        return SessionStatus(
            authenticated=True,
            workspace_id=ws.workspace_id,
            created_at=ws.created_at,
            expires_at=ws.expires_at,
            job_count=job_count,
            job_capacity=MAX_JOBS_PER_WORKSPACE,
        )
