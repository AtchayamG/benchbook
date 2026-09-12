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

CREATE TABLE IF NOT EXISTS workspaces (
    workspace_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    last_active_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_workspaces_expires ON workspaces(expires_at);

CREATE TABLE IF NOT EXISTS session_tokens (
    token_hash TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(workspace_id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_session_tokens_workspace ON session_tokens(workspace_id);
CREATE INDEX IF NOT EXISTS idx_session_tokens_expires ON session_tokens(expires_at);

CREATE TABLE IF NOT EXISTS inference_admissions (
    reservation_id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    request_key_hash TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    reserved_sends INTEGER NOT NULL DEFAULT 6,
    deadline_at TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'RESERVED',
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    dispatched_at TEXT,
    completed_at TEXT,
    released_at TEXT,
    actual_sends INTEGER,
    actual_total_tokens INTEGER,
    cleanup_completed INTEGER,
    failure_code TEXT,
    recovery_operator_id TEXT,
    recovery_reason TEXT,
    recovered_at TEXT,
    response_body TEXT
);
CREATE INDEX IF NOT EXISTS idx_admissions_workspace_key ON inference_admissions(workspace_id, request_key_hash);
CREATE INDEX IF NOT EXISTS idx_admissions_cooldown ON inference_admissions(failure_code, completed_at);
CREATE INDEX IF NOT EXISTS idx_admissions_created ON inference_admissions(created_at);
CREATE INDEX IF NOT EXISTS idx_admissions_active ON inference_admissions(is_active);
CREATE UNIQUE INDEX IF NOT EXISTS ux_inference_admissions_single_active ON inference_admissions(is_active) WHERE is_active = 1;

CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL DEFAULT 'legacy_local_workspace',
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
CREATE INDEX IF NOT EXISTS idx_jobs_workspace ON jobs(workspace_id);

CREATE TABLE IF NOT EXISTS technician_notes (
    note_id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL DEFAULT 'legacy_local_workspace',
    job_id TEXT NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
    technician_name TEXT NOT NULL,
    diagnosis_findings TEXT NOT NULL,
    root_cause TEXT NOT NULL,
    recommended_action TEXT NOT NULL,
    test_measurements TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_notes_job_id ON technician_notes(job_id);
CREATE INDEX IF NOT EXISTS idx_notes_workspace ON technician_notes(workspace_id);

CREATE TABLE IF NOT EXISTS part_items (
    part_id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL DEFAULT 'legacy_local_workspace',
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
CREATE INDEX IF NOT EXISTS idx_parts_workspace ON part_items(workspace_id);

CREATE TABLE IF NOT EXISTS estimates (
    estimate_id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL DEFAULT 'legacy_local_workspace',
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
CREATE INDEX IF NOT EXISTS idx_estimates_workspace ON estimates(workspace_id);

CREATE TABLE IF NOT EXISTS customer_approvals (
    approval_id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL DEFAULT 'legacy_local_workspace',
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
CREATE INDEX IF NOT EXISTS idx_approvals_workspace ON customer_approvals(workspace_id);

CREATE TABLE IF NOT EXISTS supplier_statuses (
    status_id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL DEFAULT 'legacy_local_workspace',
    job_id TEXT NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
    supplier_name TEXT NOT NULL,
    order_reference TEXT,
    parts_status TEXT NOT NULL DEFAULT 'ordered',
    expected_arrival_date TEXT,
    tracking_notes TEXT,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_supplier_job_id ON supplier_statuses(job_id);
CREATE INDEX IF NOT EXISTS idx_supplier_workspace ON supplier_statuses(workspace_id);

CREATE TABLE IF NOT EXISTS repair_completions (
    completion_id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL DEFAULT 'legacy_local_workspace',
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
CREATE INDEX IF NOT EXISTS idx_completions_workspace ON repair_completions(workspace_id);

CREATE TABLE IF NOT EXISTS pickup_notifications (
    notification_id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL DEFAULT 'legacy_local_workspace',
    job_id TEXT NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
    channel TEXT NOT NULL DEFAULT 'whatsapp',
    recipient_phone TEXT NOT NULL,
    message_text TEXT NOT NULL,
    sent_by_technician TEXT NOT NULL,
    sent_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_notifications_job_id ON pickup_notifications(job_id);
CREATE INDEX IF NOT EXISTS idx_notifications_workspace ON pickup_notifications(workspace_id);

CREATE TABLE IF NOT EXISTS follow_ups (
    followup_id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL DEFAULT 'legacy_local_workspace',
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
CREATE INDEX IF NOT EXISTS idx_followups_workspace ON follow_ups(workspace_id);

CREATE TABLE IF NOT EXISTS job_closes (
    close_id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL DEFAULT 'legacy_local_workspace',
    job_id TEXT NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
    closed_by TEXT NOT NULL,
    resolution_summary TEXT NOT NULL,
    closed_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_closes_job_id ON job_closes(job_id);
CREATE INDEX IF NOT EXISTS idx_closes_workspace ON job_closes(workspace_id);

CREATE TABLE IF NOT EXISTS audit_events (
    event_id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL DEFAULT 'legacy_local_workspace',
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
    workspace_id TEXT NOT NULL DEFAULT 'legacy_local_workspace',
    idempotency_key TEXT NOT NULL,
    job_id TEXT NOT NULL,
    action TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    scope TEXT NOT NULL,
    response_payload TEXT NOT NULL,
    response_status INTEGER NOT NULL DEFAULT 200,
    created_at TEXT NOT NULL,
    PRIMARY KEY (workspace_id, idempotency_key)
);
"""

TABLES_TO_MIGRATE = [
    "jobs",
    "technician_notes",
    "part_items",
    "estimates",
    "customer_approvals",
    "supplier_statuses",
    "repair_completions",
    "pickup_notifications",
    "follow_ups",
    "job_closes",
    "audit_events",
    "idempotency_records",
]


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
    """Initialize database schema for either SQLite or PostgreSQL with safe transactional schema evolution."""
    if db_target.startswith(("postgresql://", "postgres://")):
        norm_url = db_target
        if norm_url.startswith("postgres://"):
            norm_url = "postgresql://" + norm_url[len("postgres://") :]
        with (
            psycopg.connect(norm_url, autocommit=False, connect_timeout=10) as pg_conn,
            pg_conn.transaction(),
            pg_conn.cursor() as cur,
        ):
            # 1. First ensure workspaces table exists and seed legacy workspace
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS workspaces (
                    workspace_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    last_active_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_workspaces_expires ON workspaces(expires_at);

                CREATE TABLE IF NOT EXISTS session_tokens (
                    token_hash TEXT PRIMARY KEY,
                    workspace_id TEXT NOT NULL REFERENCES workspaces(workspace_id) ON DELETE CASCADE,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_session_tokens_workspace ON session_tokens(workspace_id);
                CREATE INDEX IF NOT EXISTS idx_session_tokens_expires ON session_tokens(expires_at);

                INSERT INTO workspaces (workspace_id, created_at, expires_at, last_active_at)
                VALUES ('legacy_local_workspace', '1970-01-01T00:00:00+00:00', '1970-01-01T00:00:00+00:00', '1970-01-01T00:00:00+00:00')
                ON CONFLICT (workspace_id) DO NOTHING;
                """
            )

            # 2. Schema evolution for existing tables: add workspace_id BEFORE creating any dependent indexes
            for tbl in TABLES_TO_MIGRATE:
                cur.execute(
                    """
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = current_schema() AND table_name = %s
                    """,
                    (tbl,),
                )
                if cur.fetchone() is not None:
                    cur.execute(
                        """
                        SELECT column_name FROM information_schema.columns
                        WHERE table_schema = current_schema() AND table_name = %s
                        """,
                        (tbl,),
                    )
                    existing_cols = {row[0] for row in cur.fetchall()}
                    if "workspace_id" not in existing_cols:
                        cur.execute(
                            f"ALTER TABLE {tbl} ADD COLUMN workspace_id TEXT DEFAULT 'legacy_local_workspace'"
                        )
                    cur.execute(
                        f"UPDATE {tbl} SET workspace_id = 'legacy_local_workspace' WHERE workspace_id IS NULL OR workspace_id = ''"
                    )

            # 3. Schema evolution for idempotency_records: columns and composite PK
            cur.execute(
                """
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = current_schema() AND table_name = 'idempotency_records'
                """
            )
            if cur.fetchone() is not None:
                cur.execute(
                    """
                    SELECT column_name FROM information_schema.columns
                    WHERE table_schema = current_schema() AND table_name = 'idempotency_records'
                    """
                )
                existing_idemp_cols = {row[0] for row in cur.fetchall()}
                if "payload_hash" not in existing_idemp_cols:
                    cur.execute(
                        "ALTER TABLE idempotency_records ADD COLUMN payload_hash TEXT DEFAULT ''"
                    )
                if "scope" not in existing_idemp_cols:
                    cur.execute("ALTER TABLE idempotency_records ADD COLUMN scope TEXT DEFAULT ''")
                if "response_status" not in existing_idemp_cols:
                    cur.execute(
                        "ALTER TABLE idempotency_records ADD COLUMN response_status INTEGER DEFAULT 200"
                    )

                # Migrate primary key constraint to (workspace_id, idempotency_key) if needed
                cur.execute(
                    """
                    SELECT kcu.column_name, tc.constraint_name
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu
                      ON tc.constraint_name = kcu.constraint_name
                      AND tc.table_schema = kcu.table_schema
                    WHERE tc.table_schema = current_schema()
                      AND tc.table_name = 'idempotency_records'
                      AND tc.constraint_type = 'PRIMARY KEY'
                    """
                )
                pk_rows = cur.fetchall()
                pk_cols = {r[0] for r in pk_rows}
                if pk_cols != {"workspace_id", "idempotency_key"}:
                    if pk_rows:
                        c_name = pk_rows[0][1]
                        cur.execute(f"ALTER TABLE idempotency_records DROP CONSTRAINT {c_name}")
                    cur.execute(
                        "ALTER TABLE idempotency_records ADD PRIMARY KEY (workspace_id, idempotency_key)"
                    )

            # 4. Now that all columns and constraints are evolved, execute the full schema SQL for tables and indexes
            cur.execute(get_postgres_schema_sql())
    else:
        db_path = db_target.replace("sqlite:///", "")
        sqlite_conn = sqlite3.connect(db_path, timeout=15.0)
        try:
            sqlite_conn.execute("PRAGMA foreign_keys = ON;")
            sqlite_conn.execute("PRAGMA journal_mode = WAL;")
            with sqlite_conn:
                sqlite_conn.execute("BEGIN IMMEDIATE")
                # 1. First ensure workspaces table exists and seed legacy workspace
                sqlite_conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS workspaces (
                        workspace_id TEXT PRIMARY KEY,
                        created_at TEXT NOT NULL,
                        expires_at TEXT NOT NULL,
                        last_active_at TEXT NOT NULL
                    );
                    """
                )
                sqlite_conn.execute(
                    """
                    INSERT OR IGNORE INTO workspaces (workspace_id, created_at, expires_at, last_active_at)
                    VALUES ('legacy_local_workspace', '1970-01-01T00:00:00+00:00', '1970-01-01T00:00:00+00:00', '1970-01-01T00:00:00+00:00')
                    """
                )

                # 2. Check and evolve existing tables in SQLite before executing indexes
                for tbl in TABLES_TO_MIGRATE:
                    tbl_check = sqlite_conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                        (tbl,),
                    ).fetchone()
                    if tbl_check:
                        info = sqlite_conn.execute(f"PRAGMA table_info({tbl})")
                        existing_cols = {row[1] for row in info.fetchall()}
                        if "workspace_id" not in existing_cols:
                            sqlite_conn.execute(
                                f"ALTER TABLE {tbl} ADD COLUMN workspace_id TEXT DEFAULT 'legacy_local_workspace'"
                            )
                        sqlite_conn.execute(
                            f"UPDATE {tbl} SET workspace_id = 'legacy_local_workspace' WHERE workspace_id IS NULL OR workspace_id = ''"
                        )

                # 3. Check existing idempotency_records and migrate PK if needed
                idemp_check = sqlite_conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='idempotency_records'"
                ).fetchone()
                if idemp_check:
                    idemp_info = sqlite_conn.execute(
                        "PRAGMA table_info(idempotency_records)"
                    ).fetchall()
                    existing_cols = {row[1] for row in idemp_info}
                    pk_cols = {row[1] for row in idemp_info if row[5] > 0}

                    # If not composite PK (workspace_id, idempotency_key), rebuild table preserving rows
                    if pk_cols != {"workspace_id", "idempotency_key"}:
                        sqlite_conn.execute(
                            """
                            CREATE TABLE idempotency_records_new (
                                workspace_id TEXT NOT NULL DEFAULT 'legacy_local_workspace',
                                idempotency_key TEXT NOT NULL,
                                job_id TEXT NOT NULL,
                                action TEXT NOT NULL,
                                payload_hash TEXT NOT NULL DEFAULT '',
                                scope TEXT NOT NULL DEFAULT '',
                                response_payload TEXT NOT NULL,
                                response_status INTEGER NOT NULL DEFAULT 200,
                                created_at TEXT NOT NULL,
                                PRIMARY KEY (workspace_id, idempotency_key)
                            );
                            """
                        )
                        col_workspace = (
                            "COALESCE(NULLIF(workspace_id, ''), 'legacy_local_workspace')"
                            if "workspace_id" in existing_cols
                            else "'legacy_local_workspace'"
                        )
                        col_payload_hash = (
                            "COALESCE(payload_hash, '')"
                            if "payload_hash" in existing_cols
                            else "''"
                        )
                        col_scope = "COALESCE(scope, '')" if "scope" in existing_cols else "''"
                        col_resp_status = (
                            "COALESCE(response_status, 200)"
                            if "response_status" in existing_cols
                            else "200"
                        )

                        sqlite_conn.execute(
                            f"""
                            INSERT INTO idempotency_records_new (
                                workspace_id, idempotency_key, job_id, action, payload_hash, scope, response_payload, response_status, created_at
                            )
                            SELECT
                                {col_workspace},
                                idempotency_key, job_id, action,
                                {col_payload_hash},
                                {col_scope},
                                response_payload,
                                {col_resp_status},
                                created_at
                            FROM idempotency_records;
                            """
                        )
                        sqlite_conn.execute("DROP TABLE idempotency_records;")
                        sqlite_conn.execute(
                            "ALTER TABLE idempotency_records_new RENAME TO idempotency_records;"
                        )
                    else:
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

                # 4. Now execute SCHEMA_SQL to ensure all tables and indexes are created
                # executescript commits an open transaction; execute this static DDL
                # statement by statement so migration failures roll back completely.
                for statement in SCHEMA_SQL.split(";"):
                    if statement.strip() and not statement.strip().startswith("PRAGMA"):
                        sqlite_conn.execute(statement)
                for tbl in TABLES_TO_MIGRATE:
                    sqlite_conn.execute(
                        f"CREATE INDEX IF NOT EXISTS idx_{tbl}_workspace ON {tbl}(workspace_id)"
                    )
                sqlite_conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_idempotency_scope ON idempotency_records(scope);"
                )
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
