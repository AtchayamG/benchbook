"""FastAPI dependencies for Benchbook endpoints."""

from __future__ import annotations

from typing import cast

from fastapi import Depends, Request

from benchbook.config import settings
from benchbook.infrastructure.session import (
    COOKIE_NAME,
    SessionManager,
    validate_origin,
)
from benchbook.infrastructure.sqlite_store import SqliteRepairJobStore


def get_store(request: Request) -> SqliteRepairJobStore:
    """Retrieve SQLite/PostgreSQL store instance from application state."""
    return cast(SqliteRepairJobStore, request.app.state.store)


def get_session_manager(
    store: SqliteRepairJobStore = Depends(get_store),
) -> SessionManager:
    """Retrieve session manager bound to current database store."""
    return SessionManager(store)


def get_current_workspace_id(
    request: Request,
    session_manager: SessionManager = Depends(get_session_manager),
) -> str:
    """Resolve and authenticate current workspace from session cookie.

    Enforces Origin validation on mutating methods in production.
    """
    if request.method in ("POST", "PUT", "DELETE", "PATCH"):
        origin = request.headers.get("origin")
        validate_origin(origin, settings.cors_origins, settings.environment)

    cookie_val = request.cookies.get(COOKIE_NAME)
    return session_manager.authenticate_session(cookie_val, settings.environment)
