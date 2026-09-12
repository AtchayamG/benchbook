"""Pytest fixtures for Benchbook test suite."""

from __future__ import annotations

import sys
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from benchbook.infrastructure.sqlite_store import (
    PostgresRepairJobStore,
    SqliteRepairJobStore,
)
from benchbook.interfaces.http.app import create_app

test_dir = Path(__file__).resolve().parent
if str(test_dir) not in sys.path:
    sys.path.insert(0, str(test_dir))

from disposable_postgres import DisposablePostgresCluster, find_pg_bin  # noqa: E402


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


@pytest.fixture(scope="session")
def pg_cluster() -> Generator[DisposablePostgresCluster, None, None]:
    """Provide a session-scoped ephemeral PostgreSQL 16.10 server."""
    pg_bin = find_pg_bin()
    if not pg_bin:
        pytest.skip("Local PostgreSQL binaries not found on this environment")

    cluster = DisposablePostgresCluster(pg_bin=pg_bin)
    try:
        cluster.start()
        yield cluster
    finally:
        cluster.stop()


@pytest.fixture
def pg_db_url(pg_cluster: DisposablePostgresCluster) -> str:
    """Create a fresh isolated database on the ephemeral PostgreSQL cluster."""
    return str(pg_cluster.create_isolated_db("bb003"))


@pytest.fixture
def pg_store(pg_db_url: str) -> PostgresRepairJobStore:
    """Provide a fresh PostgresRepairJobStore connected to an isolated test database."""
    return PostgresRepairJobStore(db_path=pg_db_url)


@pytest.fixture
def pg_client(pg_db_url: str) -> Generator[TestClient, None, None]:
    """Provide a TestClient connected to an isolated PostgreSQL test database."""
    app = create_app(db_path=pg_db_url, assistant_mode="deterministic")
    with TestClient(app) as test_client:
        yield test_client
