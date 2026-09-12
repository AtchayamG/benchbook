"""Health check endpoint for Benchbook service."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from benchbook.config import settings

router = APIRouter(tags=["Health"])


@router.get("/health")
def health_check() -> dict[str, Any]:
    """Return service health, shop identity, and assistant status."""
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": "0.1.0",
        "milestone": "M1",
        "shop": {
            "name": settings.shop_name,
            "location": settings.shop_location,
            "phone": settings.shop_phone,
        },
        "assistant": {
            "mode": settings.assistant_mode,
            "role": "advisory_only",
            "human_approval_required": True,
        },
    }
