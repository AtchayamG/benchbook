"""Tests for configuration parsing, CORS allow-lists, and readiness probes."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from benchbook.config import Settings
from benchbook.infrastructure.sqlite_store import SqliteRepairJobStore
from benchbook.interfaces.http.app import create_app


def test_config_defaults() -> None:
    """Verify default settings values and engine properties."""
    cfg = Settings()
    assert cfg.database_url.startswith("sqlite:///")
    assert cfg.is_sqlite is True
    assert cfg.is_postgres is False
    assert cfg.db_engine_name == "sqlite"
    assert "http://localhost:5173" in cfg.cors_origins


def test_config_postgres_normalization() -> None:
    """Verify postgres:// is normalized to postgresql:// and properties set correctly."""
    cfg = Settings(database_url="postgres://user:pass@neon.tech:5432/benchbook_db")
    assert cfg.database_url.startswith("postgresql://")
    assert cfg.is_postgres is True
    assert cfg.is_sqlite is False
    assert cfg.db_engine_name == "postgres"


def test_config_cors_parsing_comma_separated(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify comma-separated CORS origins string is parsed into a list."""
    monkeypatch.setenv(
        "BENCHBOOK_CORS_ORIGINS",
        "https://benchbook.vercel.app, https://custom.domain.com, http://localhost:3000",
    )
    cfg = Settings()
    assert len(cfg.cors_origins) == 3
    assert "https://benchbook.vercel.app" in cfg.cors_origins
    assert "https://custom.domain.com" in cfg.cors_origins
    assert "http://localhost:3000" in cfg.cors_origins


def test_config_cors_parsing_json_list(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify JSON list format for CORS origins is parsed correctly."""
    monkeypatch.setenv(
        "BENCHBOOK_CORS_ORIGINS",
        '["https://app1.vercel.app", "https://app2.vercel.app"]',
    )
    cfg = Settings()
    assert len(cfg.cors_origins) == 2
    assert "https://app1.vercel.app" in cfg.cors_origins
    assert "https://app2.vercel.app" in cfg.cors_origins


def test_cors_middleware_allowed_origin(tmp_path: object) -> None:
    """Verify CORS preflight succeeds for configured allowlist origin."""
    db_file = str(tmp_path) + "/cors_test.db"
    app = create_app(db_path=db_file)
    client = TestClient(app)

    headers = {
        "Origin": "http://localhost:5173",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    }
    resp = client.options("/api/jobs", headers=headers)
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_readiness_probe_healthy(tmp_path: object) -> None:
    """Verify /api/ready returns 200 when database connection is alive."""
    db_file = str(tmp_path) + "/ready_test.db"
    app = create_app(db_path=db_file)
    client = TestClient(app)

    resp = client.get("/api/ready")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ready"
    assert data["database"]["status"] == "connected"
    assert data["database"]["engine"] == "sqlite"


def test_readiness_probe_failure_reports_503(monkeypatch: object) -> None:
    """Verify /api/ready returns 503 if database ping fails."""
    app = create_app()
    client = TestClient(app)

    # Monkeypatch ping to simulate disconnected database
    monkeypatch.setattr(SqliteRepairJobStore, "ping", lambda self: False)  # type: ignore[attr-defined]

    resp = client.get("/api/ready")
    assert resp.status_code == 503
    data = resp.json()
    assert data["detail"]["status"] == "not_ready"
    assert data["detail"]["database"] == "disconnected"
