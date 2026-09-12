"""Store Factory for Benchbook Storage Implementations."""

from __future__ import annotations

from benchbook.infrastructure.sqlite_store import (
    PostgresRepairJobStore,
    SqliteRepairJobStore,
    SqlRepairJobStore,
)


def get_repair_job_store(database_url: str) -> SqlRepairJobStore:
    """Create appropriate store instance based on database URL scheme."""
    if database_url.startswith(("postgres://", "postgresql://")):
        return PostgresRepairJobStore(database_url)
    db_path = database_url.replace("sqlite:///", "")
    return SqliteRepairJobStore(db_path)
