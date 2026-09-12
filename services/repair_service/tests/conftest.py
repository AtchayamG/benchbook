"""Pytest fixtures for Benchbook test suite."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from benchbook.infrastructure.sqlite_store import SqliteRepairJobStore
from benchbook.interfaces.http.app import create_app


@pytest.fixture
def temp_db_path(tmp_path: Path) -> str:
    """Create a unique temporary database file for isolation."""
    db_file = tmp_path / "test_benchbook.db"
    return str(db_file)


@pytest.fixture
def store(temp_db_path: str) -> SqliteRepairJobStore:
    """Provide a fresh SQLite store instance."""
    return SqliteRepairJobStore(db_path=temp_db_path)


@pytest.fixture
def client(temp_db_path: str) -> Generator[TestClient, None, None]:
    """Provide a TestClient connected to a test app instance."""
    app = create_app(db_path=temp_db_path, assistant_mode="deterministic")
    with TestClient(app) as test_client:
        yield test_client
