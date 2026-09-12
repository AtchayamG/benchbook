"""Release configuration and legacy data regressions found during Codex review."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from benchbook.config import Settings
from benchbook.infrastructure.database import get_db_connection, init_db
from benchbook.interfaces.http.app import create_app


@pytest.mark.parametrize(
    "origin",
    [
        "*",
        "https://app.example,http://localhost:5173",
        "https://app.example/path",
        "http://app.example",
    ],
)
def test_production_rejects_invalid_origins(monkeypatch: pytest.MonkeyPatch, origin: str) -> None:
    monkeypatch.setenv("BENCHBOOK_ENVIRONMENT", "production")
    monkeypatch.setenv("BENCHBOOK_DATABASE_URL", "postgresql://localhost/test")
    monkeypatch.setenv("BENCHBOOK_CORS_ORIGINS", origin)
    with pytest.raises(ValueError, match="CORS"):
        Settings()


@pytest.mark.parametrize("database", ["sqlite:///test.db", "postgresql://", "postgresql://host/"])
def test_production_requires_postgres(monkeypatch: pytest.MonkeyPatch, database: str) -> None:
    monkeypatch.setenv("BENCHBOOK_ENVIRONMENT", "production")
    monkeypatch.setenv("BENCHBOOK_DATABASE_URL", database)
    with pytest.raises(ValueError, match="PostgreSQL"):
        Settings()


def test_production_accepts_explicit_https_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BENCHBOOK_ENVIRONMENT", "production")
    monkeypatch.setenv("BENCHBOOK_DATABASE_URL", "postgresql://localhost/test")
    monkeypatch.setenv("BENCHBOOK_CORS_ORIGINS", "https://app.example")
    assert Settings().cors_origins == ["https://app.example"]


def check_legacy_migration(target: str) -> None:
    with get_db_connection(target, write=True) as conn:
        conn.execute(
            "CREATE TABLE idempotency_records (idempotency_key TEXT PRIMARY KEY, job_id TEXT NOT NULL, action TEXT NOT NULL, response_payload TEXT NOT NULL, created_at TEXT NOT NULL)"
        )
        conn.execute(
            "INSERT INTO idempotency_records VALUES (?, ?, ?, ?, ?)",
            ("legacy", "job", "create_job", "{}", "2026-09-12"),
        )
    init_db(target)
    init_db(target)
    with get_db_connection(target) as conn:
        row = conn.execute(
            "SELECT * FROM idempotency_records WHERE idempotency_key = ?", ("legacy",)
        ).fetchone()
        assert row["job_id"] == "job"
        assert row["response_payload"] == "{}"
        assert row["payload_hash"] == ""
        assert row["scope"] == ""


def test_sqlite_legacy_migration(tmp_path: Path) -> None:
    check_legacy_migration(str(tmp_path / "legacy.db"))


def test_postgres_legacy_migration(pg_db_url: str) -> None:
    check_legacy_migration(pg_db_url)


def test_existing_app_keeps_its_own_database(tmp_path: Path) -> None:
    first = create_app(db_path=str(tmp_path / "first.db"))
    second = create_app(db_path=str(tmp_path / "second.db"))
    with TestClient(first) as a, TestClient(second) as b:
        response = a.post(
            "/api/jobs",
            json={
                "customer_name": "Synthetic",
                "customer_phone": "0000000000",
                "device_kind": "fan",
                "brand_model": "test",
                "intake_symptoms": "no spin",
            },
        )
        assert response.status_code == 201
        assert len(a.get("/api/jobs").json()["jobs"]) == 1
        assert b.get("/api/jobs").json()["jobs"] == []
