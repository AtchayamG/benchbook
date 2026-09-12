"""Benchbook Database Engine and Schema Definitions."""

from __future__ import annotations

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager

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
    response_payload TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def init_sqlite_db(db_path: str) -> None:
    """Initialize SQLite database with full Benchbook schema."""
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
    finally:
        conn.close()


@contextmanager
def get_db_connection(db_path: str) -> Generator[sqlite3.Connection, None, None]:
    """Provide a transactional scope around SQLite operations."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
