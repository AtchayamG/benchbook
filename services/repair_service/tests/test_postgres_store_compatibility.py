"""Tests for PostgreSQL compatibility, schema adaptation, and store factory logic."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from benchbook.infrastructure.database import ConnectionWrapper, get_postgres_schema_sql
from benchbook.infrastructure.sqlite_store import PostgresRepairJobStore, SqliteRepairJobStore
from benchbook.infrastructure.store_factory import get_repair_job_store


def test_postgres_schema_strips_sqlite_pragmas() -> None:
    """Verify that PostgreSQL schema DDL omits PRAGMA statements while retaining tables."""
    ddl = get_postgres_schema_sql()
    assert "PRAGMA" not in ddl
    assert "CREATE TABLE IF NOT EXISTS jobs" in ddl
    assert "CREATE TABLE IF NOT EXISTS technician_notes" in ddl
    assert "CREATE TABLE IF NOT EXISTS part_items" in ddl
    assert "CREATE TABLE IF NOT EXISTS estimates" in ddl
    assert "CREATE TABLE IF NOT EXISTS customer_approvals" in ddl
    assert "CREATE TABLE IF NOT EXISTS supplier_statuses" in ddl
    assert "CREATE TABLE IF NOT EXISTS repair_completions" in ddl
    assert "CREATE TABLE IF NOT EXISTS pickup_notifications" in ddl
    assert "CREATE TABLE IF NOT EXISTS follow_ups" in ddl
    assert "CREATE TABLE IF NOT EXISTS job_closes" in ddl
    assert "CREATE TABLE IF NOT EXISTS audit_events" in ddl
    assert "CREATE TABLE IF NOT EXISTS idempotency_records" in ddl


def test_connection_wrapper_placeholder_adaptation() -> None:
    """Verify ConnectionWrapper transforms '?' placeholders to '%s' in Postgres mode."""
    mock_raw_conn: Any = MagicMock()

    # SQLite mode
    sqlite_wrapper = ConnectionWrapper(mock_raw_conn, is_postgres=False)
    sqlite_wrapper.execute("SELECT * FROM jobs WHERE job_id = ? AND version = ?", ("j-1", 2))
    mock_raw_conn.execute.assert_called_with(
        "SELECT * FROM jobs WHERE job_id = ? AND version = ?", ("j-1", 2)
    )

    # Postgres mode
    mock_raw_conn.reset_mock()
    pg_wrapper = ConnectionWrapper(mock_raw_conn, is_postgres=True)
    pg_wrapper.execute("SELECT * FROM jobs WHERE job_id = ? AND version = ?", ("j-1", 2))
    mock_raw_conn.execute.assert_called_with(
        "SELECT * FROM jobs WHERE job_id = %s AND version = %s", ("j-1", 2)
    )


def test_store_factory_sqlite_resolution(tmp_path: object) -> None:
    """Verify store factory returns SqliteRepairJobStore for sqlite:// or local paths."""
    db_path = str(tmp_path) + "/store_fact.db"
    store = get_repair_job_store(f"sqlite:///{db_path}")
    assert isinstance(store, SqliteRepairJobStore)
    assert store.engine_name == "sqlite"
    assert store.ping() is True


def test_store_factory_postgres_resolution() -> None:
    """Verify store factory instantiates PostgresRepairJobStore for postgres:// URLs."""
    # We pass URL without triggering connect (mocking or checking type)
    pg_url = "postgres://user:pass@ep-cool-bench.neon.tech:5432/benchbook_db"
    # Temporarily monkeypatch init_db to avoid connecting to non-existent external host during test
    from unittest.mock import patch

    with patch("benchbook.infrastructure.sqlite_store.init_db"):
        store = get_repair_job_store(pg_url)
        assert isinstance(store, PostgresRepairJobStore)
        assert store.engine_name == "postgres"
