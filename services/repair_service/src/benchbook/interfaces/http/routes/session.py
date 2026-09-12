"""Public workbench session management routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response

from benchbook.config import settings
from benchbook.infrastructure.session import (
    COOKIE_MAX_AGE_SECONDS,
    COOKIE_NAME,
    MAX_GLOBAL_WORKSPACES,
    MAX_JOBS_PER_WORKSPACE,
    SessionManager,
)
from benchbook.interfaces.http.dependencies import get_session_manager
from benchbook.interfaces.http.schemas import SessionResponse

router = APIRouter(prefix="/session", tags=["Session"])


@router.post("", response_model=SessionResponse)
def create_or_resume_session(
    request: Request,
    response: Response,
    session_mgr: SessionManager = Depends(get_session_manager),
) -> SessionResponse:
    """Explicitly start or resume an isolated public workbench session."""
    raw_token = request.cookies.get(COOKIE_NAME)
    origin = request.headers.get("origin")

    workspace, token_to_set, is_new = session_mgr.create_or_resume_session(
        raw_token=raw_token,
        origin=origin,
        allowed_origins=settings.cors_origins,
        environment=settings.environment,
    )

    if is_new or raw_token != token_to_set:
        response.set_cookie(
            key=COOKIE_NAME,
            value=token_to_set,
            max_age=COOKIE_MAX_AGE_SECONDS,
            httponly=True,
            samesite="lax",
            secure=settings.is_production,
            path="/",
        )

    job_count = session_mgr.store.count_workspace_jobs(workspace.workspace_id)
    active_ws = session_mgr.store.count_active_workspaces()

    return SessionResponse(
        workspace_id=workspace.workspace_id,
        status="active",
        created_at=workspace.created_at,
        expires_at=workspace.expires_at,
        job_count=job_count,
        max_jobs=MAX_JOBS_PER_WORKSPACE,
        active_workspaces=active_ws,
        max_workspaces=MAX_GLOBAL_WORKSPACES,
        is_new=is_new,
    )


@router.get("", response_model=SessionResponse)
def get_session_status(
    request: Request,
    session_mgr: SessionManager = Depends(get_session_manager),
) -> SessionResponse:
    """Report status of current workbench session."""
    raw_token = request.cookies.get(COOKIE_NAME)
    status = session_mgr.get_session_status(raw_token)

    if not status.authenticated:
        return SessionResponse(
            workspace_id="anonymous",
            status="not_found" if not raw_token else "expired",
            created_at="",
            expires_at="",
            job_count=0,
            max_jobs=MAX_JOBS_PER_WORKSPACE,
            active_workspaces=session_mgr.store.count_active_workspaces(),
            max_workspaces=MAX_GLOBAL_WORKSPACES,
            authenticated=False,
        )

    return SessionResponse(
        workspace_id=status.workspace_id or "",
        status="active",
        created_at=status.created_at or "",
        expires_at=status.expires_at or "",
        job_count=status.job_count,
        max_jobs=status.job_capacity,
        active_workspaces=session_mgr.store.count_active_workspaces(),
        max_workspaces=MAX_GLOBAL_WORKSPACES,
        authenticated=True,
    )
