"""Health check and readiness endpoints for Benchbook service."""

from __future__ import annotations

from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException, Request, status

from benchbook.config import settings
from benchbook.infrastructure.sqlite_store import SqliteRepairJobStore

router = APIRouter(tags=["Health"])


def get_store(request: Request) -> SqliteRepairJobStore:
    return cast(SqliteRepairJobStore, request.app.state.store)


@router.get("/health")
def health_check(store: SqliteRepairJobStore = Depends(get_store)) -> dict[str, Any]:
    """Return service health, database status, shop identity, and assistant status."""
    db_connected = store.ping()
    return {
        "status": "ok" if db_connected else "degraded",
        "app": settings.app_name,
        "version": "0.2.0",
        "milestone": settings.milestone,
        "environment": settings.environment,
        "database": {
            "engine": store.engine_name,
            "status": "connected" if db_connected else "disconnected",
        },
        "shop": {
            "name": settings.shop_name,
            "location": settings.shop_location,
            "phone": settings.shop_phone,
        },
        "assistant": {
            "mode": settings.assistant_mode,
            "role": "advisory_only",
            "provider": "offline_rules",
            "live_calls": False,
            "human_approval_required": True,
        },
    }


@router.get("/ready")
def readiness_check(store: SqliteRepairJobStore = Depends(get_store)) -> dict[str, Any]:
    """Readiness probe for container orchestrators and deployment platforms."""
    if not store.ping():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "not_ready", "database": "disconnected"},
        )
    return {
        "status": "ready",
        "database": {
            "engine": store.engine_name,
            "status": "connected",
        },
    }
