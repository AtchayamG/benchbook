"""Retired unscoped assistant routes returning HTTP 410 Gone."""

from __future__ import annotations

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/assistant", tags=["Assistant Advisory (Retired)"])

RETIRED_PAYLOAD = {
    "error": "ENDPOINT_RETIRED",
    "message": (
        "The unscoped /api/assistant/* endpoints have been retired per ADR-004. "
        "Use canonical POST /api/jobs/{job_id}/advice scoped to an owned job instead."
    ),
    "canonical_route": "POST /api/jobs/{job_id}/advice",
}


@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
def retired_assistant_route(path: str) -> JSONResponse:
    """Return HTTP 410 Gone for all retired unscoped assistant routes."""
    return JSONResponse(
        status_code=status.HTTP_410_GONE,
        content=RETIRED_PAYLOAD,
    )
