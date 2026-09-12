"""Workflow transition routes with optimistic concurrency and human gates."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, Header

from benchbook.domain.models import (
    ActorType,
    CustomerApproval,
    Estimate,
    FollowUpRecord,
    JobClose,
    JobState,
    PartItem,
    PickupNotification,
    RepairCompletion,
    SupplierStatus,
    TechnicianNote,
)
from benchbook.infrastructure.sqlite_store import SqliteRepairJobStore
from benchbook.interfaces.http.dependencies import (
    get_current_workspace_id,
    get_store,
)
from benchbook.interfaces.http.schemas import (
    AddPartsLookupRequest,
    AddTechnicianNoteRequest,
    CreateEstimateRequest,
    CustomerApprovalRequest,
    FollowUpRequest,
    JobCloseRequest,
    PickupNotificationRequest,
    RepairCompletionRequest,
    RepairQueueTransitionRequest,
    SupplierStatusRequest,
    resolve_idempotency_key,
)

router = APIRouter(prefix="/jobs/{job_id}", tags=["Workflow Transitions"])


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


@router.post("/technician-note")
def add_technician_note(
    job_id: str,
    payload: AddTechnicianNoteRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    store: SqliteRepairJobStore = Depends(get_store),
    workspace_id: str = Depends(get_current_workspace_id),
) -> dict[str, Any]:
    """Record technician diagnosis and findings (advances state to diagnosis)."""
    effective_idempotency = resolve_idempotency_key(idempotency_key, payload.idempotency_key)

    note = TechnicianNote(
        note_id=str(uuid4()),
        job_id=job_id,
        technician_name=payload.technician_name,
        diagnosis_findings=payload.diagnosis_findings,
        root_cause=payload.root_cause,
        recommended_action=payload.recommended_action,
        test_measurements=payload.test_measurements,
        created_at=_now_iso(),
    )

    created_note, updated_job = store.add_technician_note(
        note=note,
        expected_version=payload.expected_version,
        actor_name=payload.technician_name,
        idempotency_key=effective_idempotency,
        payload=payload,
        workspace_id=workspace_id,
    )

    return {
        "technician_note": created_note.model_dump(),
        "job": updated_job.model_dump(),
    }


@router.post("/parts-lookup")
def add_parts_lookup(
    job_id: str,
    payload: AddPartsLookupRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    store: SqliteRepairJobStore = Depends(get_store),
    workspace_id: str = Depends(get_current_workspace_id),
) -> dict[str, Any]:
    """Record parts required or suggested for the repair."""
    effective_idempotency = resolve_idempotency_key(idempotency_key, payload.idempotency_key)

    now = _now_iso()
    parts = [
        PartItem(
            part_id=str(uuid4()),
            job_id=job_id,
            part_name=p.part_name,
            part_number=p.part_number,
            supplier_name=p.supplier_name,
            unit_cost_inr=p.unit_cost_inr,
            quantity=p.quantity,
            availability_status=p.availability_status,
            suggested_by=p.suggested_by,
            created_at=now,
        )
        for p in payload.parts
    ]

    actor_type = ActorType(payload.actor_type.lower())
    saved_parts, updated_job = store.add_parts_lookup(
        job_id=job_id,
        parts=parts,
        expected_version=payload.expected_version,
        actor_type=actor_type,
        actor_name=payload.actor_name,
        idempotency_key=effective_idempotency,
        payload=payload,
        workspace_id=workspace_id,
    )

    return {
        "parts": [p.model_dump() for p in saved_parts],
        "job": updated_job.model_dump(),
    }


@router.post("/estimate")
def create_estimate(
    job_id: str,
    payload: CreateEstimateRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    store: SqliteRepairJobStore = Depends(get_store),
    workspace_id: str = Depends(get_current_workspace_id),
) -> dict[str, Any]:
    """Generate repair cost estimate (advances state to estimate_pending)."""
    effective_idempotency = resolve_idempotency_key(idempotency_key, payload.idempotency_key)

    estimate = Estimate(
        estimate_id=str(uuid4()),
        job_id=job_id,
        labor_charge_inr=payload.labor_charge_inr,
        parts_total_inr=payload.parts_total_inr,
        tax_inr=payload.tax_inr,
        total_amount_inr=payload.total_amount_inr,
        promised_delivery_date=payload.promised_delivery_date,
        notes=payload.notes,
        created_by=payload.created_by,
        created_at=_now_iso(),
    )

    created_est, updated_job = store.create_estimate(
        estimate=estimate,
        expected_version=payload.expected_version,
        actor_name=payload.created_by,
        idempotency_key=effective_idempotency,
        payload=payload,
        workspace_id=workspace_id,
    )

    return {
        "estimate": created_est.model_dump(),
        "job": updated_job.model_dump(),
    }


@router.post("/customer-approval")
def record_customer_approval(
    job_id: str,
    payload: CustomerApprovalRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    store: SqliteRepairJobStore = Depends(get_store),
    workspace_id: str = Depends(get_current_workspace_id),
) -> dict[str, Any]:
    """Record customer approval or decline. STRICT HUMAN GATE: Assistant cannot execute."""
    effective_idempotency = resolve_idempotency_key(idempotency_key, payload.idempotency_key)

    actor_type = ActorType(payload.actor_type.lower())

    approval = CustomerApproval(
        approval_id=str(uuid4()),
        job_id=job_id,
        approved=payload.approved,
        approved_by=payload.approved_by,
        recorded_by_technician=payload.recorded_by_technician,
        channel=payload.channel,
        approval_notes=payload.approval_notes,
        agreed_amount_inr=payload.agreed_amount_inr,
        approved_at=_now_iso(),
    )

    created_appr, updated_job = store.record_customer_approval(
        approval=approval,
        expected_version=payload.expected_version,
        actor_type=actor_type,
        actor_name=payload.recorded_by_technician,
        idempotency_key=effective_idempotency,
        payload=payload,
        workspace_id=workspace_id,
    )

    return {
        "customer_approval": created_appr.model_dump(),
        "job": updated_job.model_dump(),
    }


@router.post("/supplier-status")
def update_supplier_status(
    job_id: str,
    payload: SupplierStatusRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    store: SqliteRepairJobStore = Depends(get_store),
    workspace_id: str = Depends(get_current_workspace_id),
) -> dict[str, Any]:
    """Update supplier order status for required repair parts."""
    effective_idempotency = resolve_idempotency_key(idempotency_key, payload.idempotency_key)

    status_obj = SupplierStatus(
        status_id=str(uuid4()),
        job_id=job_id,
        supplier_name=payload.supplier_name,
        order_reference=payload.order_reference,
        parts_status=payload.parts_status,
        expected_arrival_date=payload.expected_arrival_date,
        tracking_notes=payload.tracking_notes,
        updated_at=_now_iso(),
    )

    created_stat, updated_job = store.update_supplier_status(
        status=status_obj,
        expected_version=payload.expected_version,
        actor_name=payload.actor_name,
        idempotency_key=effective_idempotency,
        payload=payload,
        workspace_id=workspace_id,
    )

    return {
        "supplier_status": created_stat.model_dump(),
        "job": updated_job.model_dump(),
    }


@router.post("/repair-queue")
def transition_repair_queue(
    job_id: str,
    payload: RepairQueueTransitionRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    store: SqliteRepairJobStore = Depends(get_store),
    workspace_id: str = Depends(get_current_workspace_id),
) -> dict[str, Any]:
    """Transition job to repair_queue or start repair_in_progress."""
    effective_idempotency = resolve_idempotency_key(idempotency_key, payload.idempotency_key)

    target = JobState(payload.target_state)
    updated_job = store.transition_repair_queue(
        job_id=job_id,
        target_state=target,
        expected_version=payload.expected_version,
        actor_name=payload.actor_name,
        idempotency_key=effective_idempotency,
        payload=payload,
        workspace_id=workspace_id,
    )

    return {"job": updated_job.model_dump()}


@router.post("/repair-completion")
def record_repair_completion(
    job_id: str,
    payload: RepairCompletionRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    store: SqliteRepairJobStore = Depends(get_store),
    workspace_id: str = Depends(get_current_workspace_id),
) -> dict[str, Any]:
    """Sign off repair completion and QC tests. STRICT HUMAN GATE: Assistant cannot execute."""
    effective_idempotency = resolve_idempotency_key(idempotency_key, payload.idempotency_key)

    actor_type = ActorType(payload.actor_type.lower())

    completion = RepairCompletion(
        completion_id=str(uuid4()),
        job_id=job_id,
        technician_name=payload.technician_name,
        actions_taken=payload.actions_taken,
        parts_replaced=payload.parts_replaced,
        qc_tests_passed=payload.qc_tests_passed,
        burn_in_duration_minutes=payload.burn_in_duration_minutes,
        technician_signature_confirmed=payload.technician_signature_confirmed,
        completed_at=_now_iso(),
    )

    created_comp, updated_job = store.record_repair_completion(
        completion=completion,
        expected_version=payload.expected_version,
        actor_type=actor_type,
        actor_name=payload.technician_name,
        idempotency_key=effective_idempotency,
        payload=payload,
        workspace_id=workspace_id,
    )

    return {
        "repair_completion": created_comp.model_dump(),
        "job": updated_job.model_dump(),
    }


@router.post("/pickup-notification")
def record_pickup_notification(
    job_id: str,
    payload: PickupNotificationRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    store: SqliteRepairJobStore = Depends(get_store),
    workspace_id: str = Depends(get_current_workspace_id),
) -> dict[str, Any]:
    """Log pickup notification sent to customer (advances state to ready_for_pickup)."""
    effective_idempotency = resolve_idempotency_key(idempotency_key, payload.idempotency_key)

    notification = PickupNotification(
        notification_id=str(uuid4()),
        job_id=job_id,
        channel=payload.channel,
        recipient_phone=payload.recipient_phone,
        message_text=payload.message_text,
        sent_by_technician=payload.sent_by_technician,
        sent_at=_now_iso(),
    )

    created_notif, updated_job = store.record_pickup_notification(
        notification=notification,
        expected_version=payload.expected_version,
        actor_name=payload.sent_by_technician,
        idempotency_key=effective_idempotency,
        payload=payload,
        workspace_id=workspace_id,
    )

    return {
        "pickup_notification": created_notif.model_dump(),
        "job": updated_job.model_dump(),
    }


@router.post("/follow-up")
def record_follow_up(
    job_id: str,
    payload: FollowUpRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    store: SqliteRepairJobStore = Depends(get_store),
    workspace_id: str = Depends(get_current_workspace_id),
) -> dict[str, Any]:
    """Record customer device handover, payment receipt, and warranty terms."""
    effective_idempotency = resolve_idempotency_key(idempotency_key, payload.idempotency_key)

    followup = FollowUpRecord(
        followup_id=str(uuid4()),
        job_id=job_id,
        picked_up_at=_now_iso(),
        amount_paid_inr=payload.amount_paid_inr,
        payment_method=payload.payment_method,
        payment_reference=payload.payment_reference,
        warranty_days=payload.warranty_days,
        customer_feedback=payload.customer_feedback,
        feedback_rating=payload.feedback_rating,
        recorded_by=payload.recorded_by,
        recorded_at=_now_iso(),
    )

    created_fol, updated_job = store.record_follow_up(
        followup=followup,
        expected_version=payload.expected_version,
        actor_name=payload.recorded_by,
        idempotency_key=effective_idempotency,
        payload=payload,
        workspace_id=workspace_id,
    )

    return {
        "follow_up": created_fol.model_dump(),
        "job": updated_job.model_dump(),
    }


@router.post("/close")
def record_job_close(
    job_id: str,
    payload: JobCloseRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    store: SqliteRepairJobStore = Depends(get_store),
    workspace_id: str = Depends(get_current_workspace_id),
) -> dict[str, Any]:
    """Final closure of the repair job. STRICT HUMAN GATE: Assistant cannot execute."""
    effective_idempotency = resolve_idempotency_key(idempotency_key, payload.idempotency_key)

    actor_type = ActorType(payload.actor_type.lower())

    close_obj = JobClose(
        close_id=str(uuid4()),
        job_id=job_id,
        closed_by=payload.closed_by,
        resolution_summary=payload.resolution_summary,
        closed_at=_now_iso(),
    )

    created_close, updated_job = store.record_job_close(
        close=close_obj,
        expected_version=payload.expected_version,
        actor_type=actor_type,
        actor_name=payload.closed_by,
        idempotency_key=effective_idempotency,
        payload=payload,
        workspace_id=workspace_id,
    )

    return {
        "job_close": created_close.model_dump(),
        "job": updated_job.model_dump(),
    }
