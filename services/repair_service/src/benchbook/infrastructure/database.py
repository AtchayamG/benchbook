"""Benchbook Database Engine, Schema Definitions, and Unified Connection Manager."""

from __future__ import annotations

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager, suppress
from typing import Any

import psycopg
from psycopg.rows import dict_row

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    job_number TEXT UNIQUE NOT NULL,
    customer_name TEXT NOT NULL,
    customer_phone TEXT NOT NULL,
    customer_address TEXT,
    device_kind TEXT NOT NULL,
    brand_model TEXT NOT NULL,
    serial_number TEXT,
    intake_symptoms TEXT NOT NULL,
    physical_condition TEXT,
    accessories_received TEXT NOT NULL DEFAULT '[]',
    promised_date TEXT,
    assigned_technician TEXT,
    current_state TEXT NOT NULL DEFAULT 'intake',
    version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_jobs_current_state ON jobs(current_state);
CREATE INDEX IF NOT EXISTS idx_jobs_job_number ON jobs(job_number);

CREATE TABLE IF NOT EXISTS technician_notes (
    note_id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
    technician_name TEXT NOT NULL,
    diagnosis_findings TEXT NOT NULL,
    root_cause TEXT NOT NULL,
    recommended_action TEXT NOT NULL,
    test_measurements TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_notes_job_id ON technician_notes(job_id);

CREATE TABLE IF NOT EXISTS part_items (
    part_id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
    part_name TEXT NOT NULL,
    part_number TEXT,
    supplier_name TEXT,
    unit_cost_inr REAL NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1,
    availability_status TEXT NOT NULL DEFAULT 'in_stock',
    suggested_by TEXT NOT NULL DEFAULT 'technician',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_parts_job_id ON part_items(job_id);

CREATE TABLE IF NOT EXISTS estimates (
    estimate_id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
    labor_charge_inr REAL NOT NULL,
    parts_total_inr REAL NOT NULL,
    tax_inr REAL NOT NULL,
    total_amount_inr REAL NOT NULL,
    promised_delivery_date TEXT,
    notes TEXT,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_estimates_job_id ON estimates(job_id);

CREATE TABLE IF NOT EXISTS customer_approvals (
    approval_id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
    approved INTEGER NOT NULL,
    approved_by TEXT NOT NULL,
    recorded_by_technician TEXT NOT NULL,
    channel TEXT NOT NULL DEFAULT 'phone',
    approval_notes TEXT,
    agreed_amount_inr REAL NOT NULL,
    approved_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_approvals_job_id ON customer_approvals(job_id);

CREATE TABLE IF NOT EXISTS supplier_statuses (
    status_id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
    supplier_name TEXT NOT NULL,
    order_reference TEXT,
    parts_status TEXT NOT NULL DEFAULT 'ordered',
    expected_arrival_date TEXT,
    tracking_notes TEXT,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_supplier_job_id ON supplier_statuses(job_id);

CREATE TABLE IF NOT EXISTS repair_completions (
    completion_id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
    technician_name TEXT NOT NULL,
    actions_taken TEXT NOT NULL,
    parts_replaced TEXT NOT NULL DEFAULT '[]',
    qc_tests_passed TEXT NOT NULL DEFAULT '[]',
    burn_in_duration_minutes INTEGER NOT NULL DEFAULT 0,
    technician_signature_confirmed INTEGER NOT NULL DEFAULT 1,
    completed_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_completions_job_id ON repair_completions(job_id);

CREATE TABLE IF NOT EXISTS pickup_notifications (
    notification_id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
    channel TEXT NOT NULL DEFAULT 'whatsapp',
    recipient_phone TEXT NOT NULL,
    message_text TEXT NOT NULL,
    sent_by_technician TEXT NOT NULL,
    sent_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_notifications_job_id ON pickup_notifications(job_id);

CREATE TABLE IF NOT EXISTS follow_ups (
    followup_id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
    picked_up_at TEXT NOT NULL,
    amount_paid_inr REAL NOT NULL,
    payment_method TEXT NOT NULL DEFAULT 'upi',
    payment_reference TEXT,
    warranty_days INTEGER NOT NULL DEFAULT 30,
    customer_feedback TEXT,
    feedback_rating INTEGER,
    recorded_by TEXT NOT NULL,
    recorded_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_followups_job_id ON follow_ups(job_id);

CREATE TABLE IF NOT EXISTS job_closes (
    close_id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
    closed_by TEXT NOT NULL,
    resolution_summary TEXT NOT NULL,
    closed_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_closes_job_id ON job_closes(job_id);

CREATE TABLE IF NOT EXISTS audit_events (
    event_id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
    from_state TEXT NOT NULL,
    to_state TEXT NOT NULL,
    action TEXT NOT NULL,
    actor_type TEXT NOT NULL,
    actor_name TEXT NOT NULL,
    idempotency_key TEXT,
    version_before INTEGER NOT NULL,
    version_after INTEGER NOT NULL,
    payload TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_job_id ON audit_events(job_id);
CREATE INDEX IF NOT EXISTS idx_audit_idempotency ON audit_events(idempotency_key);

CREATE TABLE IF NOT EXISTS idempotency_records (
    idempotency_key TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    action TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    scope TEXT NOT NULL,
    response_payload TEXT NOT NULL,
    response_status INTEGER NOT NULL DEFAULT 200,
    created_at TEXT NOT NULL
);
"""


def get_postgres_schema_sql() -> str:
    """Return PostgreSQL-compatible DDL omitting SQLite-specific PRAGMAs."""
    return "\n".join(
        line for line in SCHEMA_SQL.splitlines() if not line.strip().startswith("PRAGMA")
    )


class ConnectionWrapper:
    """Unified database connection wrapper abstracting SQLite and PostgreSQL cursor differences."""

    def __init__(self, raw_conn: Any, is_postgres: bool = False) -> None:
        self.raw_conn = raw_conn
        self.is_postgres = is_postgres

    def execute(self, sql: str, params: tuple[Any, ...] | list[Any] = ()) -> Any:
        """Execute query with automatic parameter placeholder adaptation."""
        if self.is_postgres:
            sql = sql.replace("?", "%s")
            return self.raw_conn.execute(sql, tuple(params))
        return self.raw_conn.execute(sql, tuple(params))


def init_db(db_target: str) -> None:
    """Initialize database schema for either SQLite or PostgreSQL with safe column evolution."""
    if db_target.startswith(("postgresql://", "postgres://")):
        norm_url = db_target
        if norm_url.startswith("postgres://"):
            norm_url = "postgresql://" + norm_url[len("postgres://") :]
        with (
            psycopg.connect(norm_url, autocommit=True, connect_timeout=10) as pg_conn,
            pg_conn.cursor() as cur,
        ):
            cur.execute(get_postgres_schema_sql())
            # Safe schema evolution for existing idempotency_records
            cur.execute(
                """
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'idempotency_records'
                """
            )
            existing_cols = {row[0] for row in cur.fetchall()}
            if "payload_hash" not in existing_cols:
                cur.execute(
                    "ALTER TABLE idempotency_records ADD COLUMN payload_hash TEXT DEFAULT ''"
                )
            if "scope" not in existing_cols:
                cur.execute("ALTER TABLE idempotency_records ADD COLUMN scope TEXT DEFAULT ''")
            if "response_status" not in existing_cols:
                cur.execute(
                    "ALTER TABLE idempotency_records ADD COLUMN response_status INTEGER DEFAULT 200"
                )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_idempotency_scope ON idempotency_records(scope);"
            )
    else:
        db_path = db_target.replace("sqlite:///", "")
        sqlite_conn = sqlite3.connect(db_path, timeout=15.0)
        try:
            # Safe schema evolution for pre-existing idempotency_records before executescript
            sqlite_cur = sqlite_conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='idempotency_records'"
            )
            if sqlite_cur.fetchone():
                info = sqlite_conn.execute("PRAGMA table_info(idempotency_records)")
                existing_cols = {row[1] for row in info.fetchall()}
                if "payload_hash" not in existing_cols:
                    sqlite_conn.execute(
                        "ALTER TABLE idempotency_records ADD COLUMN payload_hash TEXT DEFAULT ''"
                    )
                if "scope" not in existing_cols:
                    sqlite_conn.execute(
                        "ALTER TABLE idempotency_records ADD COLUMN scope TEXT DEFAULT ''"
                    )
                if "response_status" not in existing_cols:
                    sqlite_conn.execute(
                        "ALTER TABLE idempotency_records ADD COLUMN response_status INTEGER DEFAULT 200"
                    )

            sqlite_conn.executescript(SCHEMA_SQL)
            sqlite_conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_idempotency_scope ON idempotency_records(scope);"
            )
            sqlite_conn.commit()
        finally:
            sqlite_conn.close()


def init_sqlite_db(db_path: str) -> None:
    """Backwards-compatible SQLite initializer."""
    init_db(db_path)


@contextmanager
def get_db_connection(
    db_target: str, write: bool = False
) -> Generator[ConnectionWrapper, None, None]:
    """Provide a transactional scope around SQLite or PostgreSQL operations."""
    if db_target.startswith(("postgresql://", "postgres://")):
        norm_url = db_target
        if norm_url.startswith("postgres://"):
            norm_url = "postgresql://" + norm_url[len("postgres://") :]
        pg_conn = psycopg.connect(norm_url, row_factory=dict_row, connect_timeout=10)
        try:
            with pg_conn.transaction():
                yield ConnectionWrapper(pg_conn, is_postgres=True)
        finally:
            pg_conn.close()
    else:
        db_path = db_target.replace("sqlite:///", "")
        sqlite_conn = sqlite3.connect(db_path, timeout=15.0, isolation_level=None)
        sqlite_conn.row_factory = sqlite3.Row
        sqlite_conn.execute("PRAGMA foreign_keys = ON;")
        if write:
            try:
                sqlite_conn.execute("BEGIN IMMEDIATE;")
                yield ConnectionWrapper(sqlite_conn, is_postgres=False)
                sqlite_conn.execute("COMMIT;")
            except Exception:
                with suppress(Exception):
                    sqlite_conn.execute("ROLLBACK;")
                raise
            finally:
                sqlite_conn.close()
        else:
            try:
                yield ConnectionWrapper(sqlite_conn, is_postgres=False)
            finally:
                sqlite_conn.close()
