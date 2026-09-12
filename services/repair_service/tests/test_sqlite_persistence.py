"""Tests for SQLite persistence, transactions, and foreign key integrity."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from benchbook.domain.errors import JobNotFoundError
from benchbook.domain.models import Job, JobState
from benchbook.infrastructure.database import get_db_connection
from benchbook.infrastructure.sqlite_store import SqliteRepairJobStore


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def test_sqlite_wal_and_foreign_keys(temp_db_path: str) -> None:
    """Verify SQLite WAL journal mode and foreign key constraints are enabled."""
    store = SqliteRepairJobStore(db_path=temp_db_path)
    assert store is not None

    with get_db_connection(temp_db_path) as conn:
        fk = conn.execute("PRAGMA foreign_keys;").fetchone()[0]
        assert fk == 1

        journal = conn.execute("PRAGMA journal_mode;").fetchone()[0]
        assert journal.lower() == "wal"


def test_job_not_found_raises_domain_error(store: SqliteRepairJobStore) -> None:
    """Querying a non-existent job ID raises JobNotFoundError."""
    with pytest.raises(JobNotFoundError):
        store.get_job_details("non-existent-uuid")


def test_cascade_delete_cleans_child_records(temp_db_path: str) -> None:
    """Verify that deleting a job cascades cleanly to child records."""
    store = SqliteRepairJobStore(db_path=temp_db_path)
    job = Job(
        job_id=str(uuid4()),
        job_number="BB-2026-DEL1",
        customer_name="Test Customer",
        customer_phone="+91 99999 00000",
        device_kind="Fan",
        brand_model="TestModel",
        intake_symptoms="None",
        current_state=JobState.INTAKE,
        version=1,
        created_at=_now_iso(),
        updated_at=_now_iso(),
    )
    store.create_job(job)

    # Manually check audit events has 1 entry
    with get_db_connection(temp_db_path) as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM audit_events WHERE job_id = ?", (job.job_id,)
        ).fetchone()[0]
        assert count == 1

        # Delete job directly
        conn.execute("DELETE FROM jobs WHERE job_id = ?", (job.job_id,))

        # Verify audit event cascaded
        count_after = conn.execute(
            "SELECT COUNT(*) FROM audit_events WHERE job_id = ?", (job.job_id,)
        ).fetchone()[0]
        assert count_after == 0
