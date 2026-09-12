"""Vercel Python entrypoint for the Benchbook FastAPI application."""

from __future__ import annotations

import sys
from pathlib import Path

SERVICE_SRC = Path(__file__).resolve().parents[1] / "services" / "repair_service" / "src"
sys.path.insert(0, str(SERVICE_SRC))

from benchbook.interfaces.http.app import app  # noqa: E402

__all__ = ["app"]
