"""Benchbook SQLite Storage Implementation."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from benchbook.domain.errors import (
    JobNotFoundError,
    StateConflictError,
    ValidationError,
)
from benchbook.domain.models import (
    ActorType,
    AuditEvent,
    CustomerApproval,
    Estimate,
    FollowUpRecord,
    Job,
    JobClose,
    JobState,
    PartItem,
    PickupNotification,
    RepairCompletion,
    SupplierStatus,
    TechnicianNote,
)
from benchbook.domain.workflow import validate_transition
from benchbook.infrastructure.database import get_db_connection, init_db


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


class SqliteRepairJobStore:
    """Thread-safe SQL store for Benchbook jobs, records, and audit events (SQLite & PostgreSQL)."""

    def __init__(self, db_path: str = "./benchbook.db") -> None:
        self.db_path = db_path
        init_db(self.db_path)

    @property
    def engine_name(self) -> str:
        """Return 'postgres' if using PostgreSQL connection string, else 'sqlite'."""
        if self.db_path.startswith(("postgresql://", "postgres://")):
            return "postgres"
        return "sqlite"

    def ping(self) -> bool:
        """Verify database connectivity and query readiness."""
        try:
            with get_db_connection(self.db_path) as conn:
                cur = conn.execute("SELECT 1")
                return cur.fetchone() is not None
        except Exception:
            return False

    def _row_to_job(self, row: Any) -> Job:
        return Job(
            job_id=row["job_id"],
            job_number=row["job_number"],
            customer_name=row["customer_name"],
            customer_phone=row["customer_phone"],
            customer_address=row["customer_address"],
            device_kind=row["device_kind"],
            brand_model=row["brand_model"],
            serial_number=row["serial_number"],
            intake_symptoms=row["intake_symptoms"],
            physical_condition=row["physical_condition"],
            accessories_received=json.loads(row["accessories_received"]),
            promised_date=row["promised_date"],
            assigned_technician=row["assigned_technician"],
            current_state=JobState(row["current_state"]),
            version=row["version"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def get_idempotent_response(self, idempotency_key: str | None) -> dict[str, Any] | None:
        if not idempotency_key:
            return None
        with get_db_connection(self.db_path) as conn:
            cur = conn.execute(
                "SELECT response_payload FROM idempotency_records WHERE idempotency_key = ?",
                (idempotency_key,),
            )
            row = cur.fetchone()
            if row:
                result: dict[str, Any] = json.loads(row["response_payload"])
                return result
            return None

    def save_idempotent_response(
        self, idempotency_key: str | None, job_id: str, action: str, payload: dict[str, Any]
    ) -> None:
        if not idempotency_key:
            return
        with get_db_connection(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO idempotency_records (idempotency_key, job_id, action, response_payload, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT (idempotency_key) DO UPDATE SET
                    job_id = EXCLUDED.job_id,
                    action = EXCLUDED.action,
                    response_payload = EXCLUDED.response_payload,
                    created_at = EXCLUDED.created_at
                """,
                (idempotency_key, job_id, action, json.dumps(payload), _now_iso()),
            )

    def create_job(self, job: Job, idempotency_key: str | None = None) -> Job:
        with get_db_connection(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO jobs (
                    job_id, job_number, customer_name, customer_phone, customer_address,
                    device_kind, brand_model, serial_number, intake_symptoms, physical_condition,
                    accessories_received, promised_date, assigned_technician, current_state,
                    version, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job.job_id,
                    job.job_number,
                    job.customer_name,
                    job.customer_phone,
                    job.customer_address,
                    job.device_kind,
                    job.brand_model,
                    job.serial_number,
                    job.intake_symptoms,
                    job.physical_condition,
                    json.dumps(job.accessories_received),
                    job.promised_date,
                    job.assigned_technician,
                    job.current_state.value,
                    job.version,
                    job.created_at,
                    job.updated_at,
                ),
            )
            # Create initial audit event
            event_id = str(uuid4())
            conn.execute(
                """
                INSERT INTO audit_events (
                    event_id, job_id, from_state, to_state, action, actor_type, actor_name,
                    idempotency_key, version_before, version_after, payload, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    job.job_id,
                    "none",
                    job.current_state.value,
                    "create_job",
                    ActorType.TECHNICIAN.value,
                    job.assigned_technician or "intake_desk",
                    idempotency_key,
                    0,
                    job.version,
                    json.dumps({"job_number": job.job_number, "customer": job.customer_name}),
                    job.created_at,
                ),
            )
        return job

    def get_job(self, job_id: str) -> Job | None:
        with get_db_connection(self.db_path) as conn:
            cur = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
            row = cur.fetchone()
            if row:
                return self._row_to_job(row)
            return None

    def get_job_by_number(self, job_number: str) -> Job | None:
        with get_db_connection(self.db_path) as conn:
            cur = conn.execute("SELECT * FROM jobs WHERE job_number = ?", (job_number,))
            row = cur.fetchone()
            if row:
                return self._row_to_job(row)
            return None

    def list_jobs(
        self, state: JobState | None = None, limit: int = 50, offset: int = 0
    ) -> list[Job]:
        with get_db_connection(self.db_path) as conn:
            if state:
                cur = conn.execute(
                    "SELECT * FROM jobs WHERE current_state = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                    (state.value, limit, offset),
                )
            else:
                cur = conn.execute(
                    "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ? OFFSET ?",
                    (limit, offset),
                )
            return [self._row_to_job(row) for row in cur.fetchall()]

    def _get_and_lock_job(self, conn: Any, job_id: str, expected_version: int) -> Job:
        cur = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
        row = cur.fetchone()
        if not row:
            raise JobNotFoundError(f"Job with id '{job_id}' not found.")
        current_job = self._row_to_job(row)
        if current_job.version != expected_version:
            raise StateConflictError(
                expected_version=expected_version,
                current_version=current_job.version,
                current_job=current_job.model_dump(),
            )
        return current_job

    def add_technician_note(
        self,
        note: TechnicianNote,
        expected_version: int,
        actor_name: str,
        idempotency_key: str | None = None,
    ) -> tuple[TechnicianNote, Job]:
        with get_db_connection(self.db_path) as conn:
            job = self._get_and_lock_job(conn, note.job_id, expected_version)
            target_state = JobState.DIAGNOSIS
            validate_transition(
                job.current_state, target_state, "add_diagnosis", ActorType.TECHNICIAN
            )

            new_version = job.version + 1
            now = _now_iso()

            conn.execute(
                """
                INSERT INTO technician_notes (
                    note_id, job_id, technician_name, diagnosis_findings, root_cause,
                    recommended_action, test_measurements, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    note.note_id,
                    note.job_id,
                    note.technician_name,
                    note.diagnosis_findings,
                    note.root_cause,
                    note.recommended_action,
                    json.dumps(note.test_measurements),
                    note.created_at,
                ),
            )

            conn.execute(
                """
                UPDATE jobs SET current_state = ?, version = ?, updated_at = ?, assigned_technician = ?
                WHERE job_id = ?
                """,
                (target_state.value, new_version, now, note.technician_name, note.job_id),
            )

            conn.execute(
                """
                INSERT INTO audit_events (
                    event_id, job_id, from_state, to_state, action, actor_type, actor_name,
                    idempotency_key, version_before, version_after, payload, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid4()),
                    note.job_id,
                    job.current_state.value,
                    target_state.value,
                    "add_diagnosis",
                    ActorType.TECHNICIAN.value,
                    actor_name,
                    idempotency_key,
                    job.version,
                    new_version,
                    json.dumps({"note_id": note.note_id, "root_cause": note.root_cause}),
                    now,
                ),
            )

            cur = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (note.job_id,))
            updated_job = self._row_to_job(cur.fetchone())
            return note, updated_job

    def add_parts_lookup(
        self,
        job_id: str,
        parts: list[PartItem],
        expected_version: int,
        actor_type: ActorType,
        actor_name: str,
        idempotency_key: str | None = None,
    ) -> tuple[list[PartItem], Job]:
        if not parts:
            raise ValidationError("Parts list cannot be empty.")
        with get_db_connection(self.db_path) as conn:
            job = self._get_and_lock_job(conn, job_id, expected_version)
            target_state = JobState.PARTS_LOOKUP
            validate_transition(job.current_state, target_state, "lookup_parts", actor_type)

            new_version = job.version + 1
            now = _now_iso()

            for part in parts:
                conn.execute(
                    """
                    INSERT INTO part_items (
                        part_id, job_id, part_name, part_number, supplier_name,
                        unit_cost_inr, quantity, availability_status, suggested_by, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        part.part_id,
                        part.job_id,
                        part.part_name,
                        part.part_number,
                        part.supplier_name,
                        part.unit_cost_inr,
                        part.quantity,
                        part.availability_status,
                        part.suggested_by,
                        part.created_at,
                    ),
                )

            conn.execute(
                """
                UPDATE jobs SET current_state = ?, version = ?, updated_at = ? WHERE job_id = ?
                """,
                (target_state.value, new_version, now, job_id),
            )

            conn.execute(
                """
                INSERT INTO audit_events (
                    event_id, job_id, from_state, to_state, action, actor_type, actor_name,
                    idempotency_key, version_before, version_after, payload, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid4()),
                    job_id,
                    job.current_state.value,
                    target_state.value,
                    "lookup_parts",
                    actor_type.value,
                    actor_name,
                    idempotency_key,
                    job.version,
                    new_version,
                    json.dumps({"parts_count": len(parts)}),
                    now,
                ),
            )

            cur = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
            updated_job = self._row_to_job(cur.fetchone())
            return parts, updated_job

    def create_estimate(
        self,
        estimate: Estimate,
        expected_version: int,
        actor_name: str,
        idempotency_key: str | None = None,
    ) -> tuple[Estimate, Job]:
        with get_db_connection(self.db_path) as conn:
            job = self._get_and_lock_job(conn, estimate.job_id, expected_version)
            target_state = JobState.ESTIMATE_PENDING
            validate_transition(
                job.current_state, target_state, "create_estimate", ActorType.TECHNICIAN
            )

            new_version = job.version + 1
            now = _now_iso()

            conn.execute(
                """
                INSERT INTO estimates (
                    estimate_id, job_id, labor_charge_inr, parts_total_inr, tax_inr,
                    total_amount_inr, promised_delivery_date, notes, created_by, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    estimate.estimate_id,
                    estimate.job_id,
                    estimate.labor_charge_inr,
                    estimate.parts_total_inr,
                    estimate.tax_inr,
                    estimate.total_amount_inr,
                    estimate.promised_delivery_date,
                    estimate.notes,
                    estimate.created_by,
                    estimate.created_at,
                ),
            )

            conn.execute(
                """
                UPDATE jobs SET current_state = ?, version = ?, updated_at = ? WHERE job_id = ?
                """,
                (target_state.value, new_version, now, estimate.job_id),
            )

            conn.execute(
                """
                INSERT INTO audit_events (
                    event_id, job_id, from_state, to_state, action, actor_type, actor_name,
                    idempotency_key, version_before, version_after, payload, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid4()),
                    estimate.job_id,
                    job.current_state.value,
                    target_state.value,
                    "create_estimate",
                    ActorType.TECHNICIAN.value,
                    actor_name,
                    idempotency_key,
                    job.version,
                    new_version,
                    json.dumps({"total_inr": estimate.total_amount_inr}),
                    now,
                ),
            )

            cur = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (estimate.job_id,))
            updated_job = self._row_to_job(cur.fetchone())
            return estimate, updated_job

    def record_customer_approval(
        self,
        approval: CustomerApproval,
        expected_version: int,
        actor_type: ActorType,
        actor_name: str,
        idempotency_key: str | None = None,
    ) -> tuple[CustomerApproval, Job]:
        with get_db_connection(self.db_path) as conn:
            job = self._get_and_lock_job(conn, approval.job_id, expected_version)
            action = "approve_estimate" if approval.approved else "reject_estimate"
            target_state = (
                JobState.CUSTOMER_APPROVED if approval.approved else JobState.ESTIMATE_REJECTED
            )
            # Strict human validation check
            validate_transition(job.current_state, target_state, action, actor_type)

            new_version = job.version + 1
            now = _now_iso()

            conn.execute(
                """
                INSERT INTO customer_approvals (
                    approval_id, job_id, approved, approved_by, recorded_by_technician,
                    channel, approval_notes, agreed_amount_inr, approved_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    approval.approval_id,
                    approval.job_id,
                    1 if approval.approved else 0,
                    approval.approved_by,
                    approval.recorded_by_technician,
                    approval.channel,
                    approval.approval_notes,
                    approval.agreed_amount_inr,
                    approval.approved_at,
                ),
            )

            conn.execute(
                """
                UPDATE jobs SET current_state = ?, version = ?, updated_at = ? WHERE job_id = ?
                """,
                (target_state.value, new_version, now, approval.job_id),
            )

            conn.execute(
                """
                INSERT INTO audit_events (
                    event_id, job_id, from_state, to_state, action, actor_type, actor_name,
                    idempotency_key, version_before, version_after, payload, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid4()),
                    approval.job_id,
                    job.current_state.value,
                    target_state.value,
                    action,
                    actor_type.value,
                    actor_name,
                    idempotency_key,
                    job.version,
                    new_version,
                    json.dumps(
                        {
                            "approved": approval.approved,
                            "approved_by": approval.approved_by,
                            "agreed_amount_inr": approval.agreed_amount_inr,
                        }
                    ),
                    now,
                ),
            )

            cur = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (approval.job_id,))
            updated_job = self._row_to_job(cur.fetchone())
            return approval, updated_job

    def update_supplier_status(
        self,
        status: SupplierStatus,
        expected_version: int,
        actor_name: str,
        idempotency_key: str | None = None,
    ) -> tuple[SupplierStatus, Job]:
        with get_db_connection(self.db_path) as conn:
            job = self._get_and_lock_job(conn, status.job_id, expected_version)
            target_state = (
                JobState.PARTS_READY
                if status.parts_status in ("delivered", "in_stock")
                else JobState.SUPPLIER_ORDERED
            )
            validate_transition(
                job.current_state, target_state, "update_supplier_status", ActorType.TECHNICIAN
            )

            new_version = job.version + 1
            now = _now_iso()

            conn.execute(
                """
                INSERT INTO supplier_statuses (
                    status_id, job_id, supplier_name, order_reference, parts_status,
                    expected_arrival_date, tracking_notes, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    status.status_id,
                    status.job_id,
                    status.supplier_name,
                    status.order_reference,
                    status.parts_status,
                    status.expected_arrival_date,
                    status.tracking_notes,
                    status.updated_at,
                ),
            )

            conn.execute(
                """
                UPDATE jobs SET current_state = ?, version = ?, updated_at = ? WHERE job_id = ?
                """,
                (target_state.value, new_version, now, status.job_id),
            )

            conn.execute(
                """
                INSERT INTO audit_events (
                    event_id, job_id, from_state, to_state, action, actor_type, actor_name,
                    idempotency_key, version_before, version_after, payload, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid4()),
                    status.job_id,
                    job.current_state.value,
                    target_state.value,
                    "update_supplier_status",
                    ActorType.TECHNICIAN.value,
                    actor_name,
                    idempotency_key,
                    job.version,
                    new_version,
                    json.dumps(
                        {
                            "supplier": status.supplier_name,
                            "parts_status": status.parts_status,
                        }
                    ),
                    now,
                ),
            )

            cur = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (status.job_id,))
            updated_job = self._row_to_job(cur.fetchone())
            return status, updated_job

    def transition_repair_queue(
        self,
        job_id: str,
        target_state: JobState,
        expected_version: int,
        actor_name: str,
        idempotency_key: str | None = None,
    ) -> Job:
        with get_db_connection(self.db_path) as conn:
            job = self._get_and_lock_job(conn, job_id, expected_version)
            action = "queue_repair" if target_state == JobState.REPAIR_QUEUE else "start_repair"
            validate_transition(job.current_state, target_state, action, ActorType.TECHNICIAN)

            new_version = job.version + 1
            now = _now_iso()

            conn.execute(
                """
                UPDATE jobs SET current_state = ?, version = ?, updated_at = ? WHERE job_id = ?
                """,
                (target_state.value, new_version, now, job_id),
            )

            conn.execute(
                """
                INSERT INTO audit_events (
                    event_id, job_id, from_state, to_state, action, actor_type, actor_name,
                    idempotency_key, version_before, version_after, payload, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid4()),
                    job_id,
                    job.current_state.value,
                    target_state.value,
                    action,
                    ActorType.TECHNICIAN.value,
                    actor_name,
                    idempotency_key,
                    job.version,
                    new_version,
                    json.dumps({"action": action}),
                    now,
                ),
            )

            cur = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
            return self._row_to_job(cur.fetchone())

    def record_repair_completion(
        self,
        completion: RepairCompletion,
        expected_version: int,
        actor_type: ActorType,
        actor_name: str,
        idempotency_key: str | None = None,
    ) -> tuple[RepairCompletion, Job]:
        with get_db_connection(self.db_path) as conn:
            job = self._get_and_lock_job(conn, completion.job_id, expected_version)
            target_state = JobState.REPAIR_COMPLETED
            # Human approval check strictly enforced
            validate_transition(job.current_state, target_state, "complete_repair", actor_type)

            new_version = job.version + 1
            now = _now_iso()

            conn.execute(
                """
                INSERT INTO repair_completions (
                    completion_id, job_id, technician_name, actions_taken, parts_replaced,
                    qc_tests_passed, burn_in_duration_minutes, technician_signature_confirmed,
                    completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    completion.completion_id,
                    completion.job_id,
                    completion.technician_name,
                    completion.actions_taken,
                    json.dumps(completion.parts_replaced),
                    json.dumps(completion.qc_tests_passed),
                    completion.burn_in_duration_minutes,
                    1 if completion.technician_signature_confirmed else 0,
                    completion.completed_at,
                ),
            )

            conn.execute(
                """
                UPDATE jobs SET current_state = ?, version = ?, updated_at = ? WHERE job_id = ?
                """,
                (target_state.value, new_version, now, completion.job_id),
            )

            conn.execute(
                """
                INSERT INTO audit_events (
                    event_id, job_id, from_state, to_state, action, actor_type, actor_name,
                    idempotency_key, version_before, version_after, payload, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid4()),
                    completion.job_id,
                    job.current_state.value,
                    target_state.value,
                    "complete_repair",
                    actor_type.value,
                    actor_name,
                    idempotency_key,
                    job.version,
                    new_version,
                    json.dumps(
                        {
                            "technician": completion.technician_name,
                            "qc_tests": completion.qc_tests_passed,
                        }
                    ),
                    now,
                ),
            )

            cur = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (completion.job_id,))
            updated_job = self._row_to_job(cur.fetchone())
            return completion, updated_job

    def record_pickup_notification(
        self,
        notification: PickupNotification,
        expected_version: int,
        actor_name: str,
        idempotency_key: str | None = None,
    ) -> tuple[PickupNotification, Job]:
        with get_db_connection(self.db_path) as conn:
            job = self._get_and_lock_job(conn, notification.job_id, expected_version)
            target_state = JobState.READY_FOR_PICKUP
            validate_transition(
                job.current_state, target_state, "send_pickup_notification", ActorType.TECHNICIAN
            )

            new_version = job.version + 1
            now = _now_iso()

            conn.execute(
                """
                INSERT INTO pickup_notifications (
                    notification_id, job_id, channel, recipient_phone, message_text,
                    sent_by_technician, sent_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    notification.notification_id,
                    notification.job_id,
                    notification.channel,
                    notification.recipient_phone,
                    notification.message_text,
                    notification.sent_by_technician,
                    notification.sent_at,
                ),
            )

            conn.execute(
                """
                UPDATE jobs SET current_state = ?, version = ?, updated_at = ? WHERE job_id = ?
                """,
                (target_state.value, new_version, now, notification.job_id),
            )

            conn.execute(
                """
                INSERT INTO audit_events (
                    event_id, job_id, from_state, to_state, action, actor_type, actor_name,
                    idempotency_key, version_before, version_after, payload, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid4()),
                    notification.job_id,
                    job.current_state.value,
                    target_state.value,
                    "send_pickup_notification",
                    ActorType.TECHNICIAN.value,
                    actor_name,
                    idempotency_key,
                    job.version,
                    new_version,
                    json.dumps(
                        {
                            "channel": notification.channel,
                            "recipient": notification.recipient_phone,
                        }
                    ),
                    now,
                ),
            )

            cur = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (notification.job_id,))
            updated_job = self._row_to_job(cur.fetchone())
            return notification, updated_job

    def record_follow_up(
        self,
        followup: FollowUpRecord,
        expected_version: int,
        actor_name: str,
        idempotency_key: str | None = None,
    ) -> tuple[FollowUpRecord, Job]:
        with get_db_connection(self.db_path) as conn:
            job = self._get_and_lock_job(conn, followup.job_id, expected_version)
            target_state = JobState.FOLLOW_UP
            validate_transition(
                job.current_state, target_state, "customer_pickup", ActorType.TECHNICIAN
            )

            new_version = job.version + 1
            now = _now_iso()

            conn.execute(
                """
                INSERT INTO follow_ups (
                    followup_id, job_id, picked_up_at, amount_paid_inr, payment_method,
                    payment_reference, warranty_days, customer_feedback, feedback_rating,
                    recorded_by, recorded_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    followup.followup_id,
                    followup.job_id,
                    followup.picked_up_at,
                    followup.amount_paid_inr,
                    followup.payment_method,
                    followup.payment_reference,
                    followup.warranty_days,
                    followup.customer_feedback,
                    followup.feedback_rating,
                    followup.recorded_by,
                    followup.recorded_at,
                ),
            )

            conn.execute(
                """
                UPDATE jobs SET current_state = ?, version = ?, updated_at = ? WHERE job_id = ?
                """,
                (target_state.value, new_version, now, followup.job_id),
            )

            conn.execute(
                """
                INSERT INTO audit_events (
                    event_id, job_id, from_state, to_state, action, actor_type, actor_name,
                    idempotency_key, version_before, version_after, payload, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid4()),
                    followup.job_id,
                    job.current_state.value,
                    target_state.value,
                    "customer_pickup",
                    ActorType.TECHNICIAN.value,
                    actor_name,
                    idempotency_key,
                    job.version,
                    new_version,
                    json.dumps(
                        {
                            "amount_paid_inr": followup.amount_paid_inr,
                            "payment_method": followup.payment_method,
                        }
                    ),
                    now,
                ),
            )

            cur = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (followup.job_id,))
            updated_job = self._row_to_job(cur.fetchone())
            return followup, updated_job

    def record_job_close(
        self,
        close: JobClose,
        expected_version: int,
        actor_type: ActorType,
        actor_name: str,
        idempotency_key: str | None = None,
    ) -> tuple[JobClose, Job]:
        with get_db_connection(self.db_path) as conn:
            job = self._get_and_lock_job(conn, close.job_id, expected_version)
            target_state = JobState.CLOSED
            # Human approval check strictly enforced
            validate_transition(job.current_state, target_state, "close_job", actor_type)

            new_version = job.version + 1
            now = _now_iso()

            conn.execute(
                """
                INSERT INTO job_closes (
                    close_id, job_id, closed_by, resolution_summary, closed_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    close.close_id,
                    close.job_id,
                    close.closed_by,
                    close.resolution_summary,
                    close.closed_at,
                ),
            )

            conn.execute(
                """
                UPDATE jobs SET current_state = ?, version = ?, updated_at = ? WHERE job_id = ?
                """,
                (target_state.value, new_version, now, close.job_id),
            )

            conn.execute(
                """
                INSERT INTO audit_events (
                    event_id, job_id, from_state, to_state, action, actor_type, actor_name,
                    idempotency_key, version_before, version_after, payload, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid4()),
                    close.job_id,
                    job.current_state.value,
                    target_state.value,
                    "close_job",
                    actor_type.value,
                    actor_name,
                    idempotency_key,
                    job.version,
                    new_version,
                    json.dumps({"closed_by": close.closed_by}),
                    now,
                ),
            )

            cur = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (close.job_id,))
            updated_job = self._row_to_job(cur.fetchone())
            return close, updated_job

    def get_job_details(self, job_id: str) -> dict[str, Any]:
        with get_db_connection(self.db_path) as conn:
            cur = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
            job_row = cur.fetchone()
            if not job_row:
                raise JobNotFoundError(f"Job with id '{job_id}' not found.")
            job = self._row_to_job(job_row)

            notes_cur = conn.execute(
                "SELECT * FROM technician_notes WHERE job_id = ? ORDER BY created_at ASC", (job_id,)
            )
            notes = [
                {
                    "note_id": r["note_id"],
                    "job_id": r["job_id"],
                    "technician_name": r["technician_name"],
                    "diagnosis_findings": r["diagnosis_findings"],
                    "root_cause": r["root_cause"],
                    "recommended_action": r["recommended_action"],
                    "test_measurements": json.loads(r["test_measurements"]),
                    "created_at": r["created_at"],
                }
                for r in notes_cur.fetchall()
            ]

            parts_cur = conn.execute(
                "SELECT * FROM part_items WHERE job_id = ? ORDER BY created_at ASC", (job_id,)
            )
            parts = [
                {
                    "part_id": r["part_id"],
                    "job_id": r["job_id"],
                    "part_name": r["part_name"],
                    "part_number": r["part_number"],
                    "supplier_name": r["supplier_name"],
                    "unit_cost_inr": r["unit_cost_inr"],
                    "quantity": r["quantity"],
                    "availability_status": r["availability_status"],
                    "suggested_by": r["suggested_by"],
                    "created_at": r["created_at"],
                }
                for r in parts_cur.fetchall()
            ]

            est_cur = conn.execute(
                "SELECT * FROM estimates WHERE job_id = ? ORDER BY created_at DESC LIMIT 1",
                (job_id,),
            )
            est_row = est_cur.fetchone()
            estimate = (
                {
                    "estimate_id": est_row["estimate_id"],
                    "job_id": est_row["job_id"],
                    "labor_charge_inr": est_row["labor_charge_inr"],
                    "parts_total_inr": est_row["parts_total_inr"],
                    "tax_inr": est_row["tax_inr"],
                    "total_amount_inr": est_row["total_amount_inr"],
                    "promised_delivery_date": est_row["promised_delivery_date"],
                    "notes": est_row["notes"],
                    "created_by": est_row["created_by"],
                    "created_at": est_row["created_at"],
                }
                if est_row
                else None
            )

            appr_cur = conn.execute(
                "SELECT * FROM customer_approvals WHERE job_id = ? ORDER BY approved_at DESC LIMIT 1",
                (job_id,),
            )
            appr_row = appr_cur.fetchone()
            approval = (
                {
                    "approval_id": appr_row["approval_id"],
                    "job_id": appr_row["job_id"],
                    "approved": bool(appr_row["approved"]),
                    "approved_by": appr_row["approved_by"],
                    "recorded_by_technician": appr_row["recorded_by_technician"],
                    "channel": appr_row["channel"],
                    "approval_notes": appr_row["approval_notes"],
                    "agreed_amount_inr": appr_row["agreed_amount_inr"],
                    "approved_at": appr_row["approved_at"],
                }
                if appr_row
                else None
            )

            sup_cur = conn.execute(
                "SELECT * FROM supplier_statuses WHERE job_id = ? ORDER BY updated_at DESC",
                (job_id,),
            )
            supplier_statuses = [
                {
                    "status_id": r["status_id"],
                    "job_id": r["job_id"],
                    "supplier_name": r["supplier_name"],
                    "order_reference": r["order_reference"],
                    "parts_status": r["parts_status"],
                    "expected_arrival_date": r["expected_arrival_date"],
                    "tracking_notes": r["tracking_notes"],
                    "updated_at": r["updated_at"],
                }
                for r in sup_cur.fetchall()
            ]

            comp_cur = conn.execute(
                "SELECT * FROM repair_completions WHERE job_id = ? ORDER BY completed_at DESC LIMIT 1",
                (job_id,),
            )
            comp_row = comp_cur.fetchone()
            completion = (
                {
                    "completion_id": comp_row["completion_id"],
                    "job_id": comp_row["job_id"],
                    "technician_name": comp_row["technician_name"],
                    "actions_taken": comp_row["actions_taken"],
                    "parts_replaced": json.loads(comp_row["parts_replaced"]),
                    "qc_tests_passed": json.loads(comp_row["qc_tests_passed"]),
                    "burn_in_duration_minutes": comp_row["burn_in_duration_minutes"],
                    "technician_signature_confirmed": bool(
                        comp_row["technician_signature_confirmed"]
                    ),
                    "completed_at": comp_row["completed_at"],
                }
                if comp_row
                else None
            )

            notif_cur = conn.execute(
                "SELECT * FROM pickup_notifications WHERE job_id = ? ORDER BY sent_at DESC",
                (job_id,),
            )
            notifications = [
                {
                    "notification_id": r["notification_id"],
                    "job_id": r["job_id"],
                    "channel": r["channel"],
                    "recipient_phone": r["recipient_phone"],
                    "message_text": r["message_text"],
                    "sent_by_technician": r["sent_by_technician"],
                    "sent_at": r["sent_at"],
                }
                for r in notif_cur.fetchall()
            ]

            fol_cur = conn.execute(
                "SELECT * FROM follow_ups WHERE job_id = ? ORDER BY recorded_at DESC LIMIT 1",
                (job_id,),
            )
            fol_row = fol_cur.fetchone()
            follow_up = (
                {
                    "followup_id": fol_row["followup_id"],
                    "job_id": fol_row["job_id"],
                    "picked_up_at": fol_row["picked_up_at"],
                    "amount_paid_inr": fol_row["amount_paid_inr"],
                    "payment_method": fol_row["payment_method"],
                    "payment_reference": fol_row["payment_reference"],
                    "warranty_days": fol_row["warranty_days"],
                    "customer_feedback": fol_row["customer_feedback"],
                    "feedback_rating": fol_row["feedback_rating"],
                    "recorded_by": fol_row["recorded_by"],
                    "recorded_at": fol_row["recorded_at"],
                }
                if fol_row
                else None
            )

            close_cur = conn.execute(
                "SELECT * FROM job_closes WHERE job_id = ? ORDER BY closed_at DESC LIMIT 1",
                (job_id,),
            )
            close_row = close_cur.fetchone()
            close_info = (
                {
                    "close_id": close_row["close_id"],
                    "job_id": close_row["job_id"],
                    "closed_by": close_row["closed_by"],
                    "resolution_summary": close_row["resolution_summary"],
                    "closed_at": close_row["closed_at"],
                }
                if close_row
                else None
            )

            audit_cur = conn.execute(
                "SELECT * FROM audit_events WHERE job_id = ? ORDER BY created_at ASC", (job_id,)
            )
            audit_events = [
                {
                    "event_id": r["event_id"],
                    "job_id": r["job_id"],
                    "from_state": r["from_state"],
                    "to_state": r["to_state"],
                    "action": r["action"],
                    "actor_type": r["actor_type"],
                    "actor_name": r["actor_name"],
                    "idempotency_key": r["idempotency_key"],
                    "version_before": r["version_before"],
                    "version_after": r["version_after"],
                    "payload": json.loads(r["payload"]),
                    "created_at": r["created_at"],
                }
                for r in audit_cur.fetchall()
            ]

            return {
                "job": job.model_dump(),
                "technician_notes": notes,
                "parts": parts,
                "estimate": estimate,
                "customer_approval": approval,
                "supplier_statuses": supplier_statuses,
                "repair_completion": completion,
                "pickup_notifications": notifications,
                "follow_up": follow_up,
                "job_close": close_info,
                "audit_events": audit_events,
            }

    def get_audit_events(self, job_id: str) -> list[AuditEvent]:
        with get_db_connection(self.db_path) as conn:
            cur = conn.execute(
                "SELECT * FROM audit_events WHERE job_id = ? ORDER BY created_at ASC", (job_id,)
            )
            return [
                AuditEvent(
                    event_id=r["event_id"],
                    job_id=r["job_id"],
                    from_state=r["from_state"],
                    to_state=r["to_state"],
                    action=r["action"],
                    actor_type=ActorType(r["actor_type"]),
                    actor_name=r["actor_name"],
                    idempotency_key=r["idempotency_key"],
                    version_before=r["version_before"],
                    version_after=r["version_after"],
                    payload=json.loads(r["payload"]),
                    created_at=r["created_at"],
                )
                for r in cur.fetchall()
            ]


SqlRepairJobStore = SqliteRepairJobStore


class PostgresRepairJobStore(SqliteRepairJobStore):
    """PostgreSQL store implementation conforming to SqlRepairJobStore."""

    pass
