"""Repair jobs management routes."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, Query, status

from benchbook.domain.models import Job, JobState
from benchbook.infrastructure.seed_data import SAMPLE_PRESETS, create_sample_job
from benchbook.infrastructure.sqlite_store import SqliteRepairJobStore
from benchbook.interfaces.http.dependencies import (
    get_current_workspace_id,
    get_store,
)
from benchbook.interfaces.http.schemas import CreateJobRequest, resolve_idempotency_key

router = APIRouter(prefix="/jobs", tags=["Jobs"])


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


@router.post("", status_code=status.HTTP_201_CREATED)
def create_job(
    payload: CreateJobRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    store: SqliteRepairJobStore = Depends(get_store),
    workspace_id: str = Depends(get_current_workspace_id),
) -> dict[str, Any]:
    """Create a new repair intake job scoped to the active workbench."""
    effective_idempotency = resolve_idempotency_key(idempotency_key, payload.idempotency_key)

    now = _now_iso()
    job_id = str(uuid4())
    # Generate sequential or timestamped job number
    random_suffix = job_id[:6].upper()
    job_number = f"BB-2026-{random_suffix}"

    job = Job(
        workspace_id=workspace_id,
        job_id=job_id,
        job_number=job_number,
        customer_name=payload.customer_name,
        customer_phone=payload.customer_phone,
        customer_address=payload.customer_address,
        device_kind=payload.device_kind,
        brand_model=payload.brand_model,
        serial_number=payload.serial_number,
        intake_symptoms=payload.intake_symptoms,
        physical_condition=payload.physical_condition,
        accessories_received=payload.accessories_received,
        promised_date=payload.promised_date,
        assigned_technician=payload.assigned_technician,
        current_state=JobState.INTAKE,
        version=1,
        created_at=now,
        updated_at=now,
    )

    created_job = store.create_job(
        job,
        idempotency_key=effective_idempotency,
        payload=payload,
        workspace_id=workspace_id,
    )
    return {"job": created_job.model_dump()}


@router.get("")
def list_jobs(
    state: str | None = Query(default=None, description="Filter by job state"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    store: SqliteRepairJobStore = Depends(get_store),
    workspace_id: str = Depends(get_current_workspace_id),
) -> dict[str, Any]:
    """List repair jobs with optional state filter for current workbench."""
    job_state = JobState(state) if state else None
    jobs = store.list_jobs(
        state=job_state,
        limit=limit,
        offset=offset,
        workspace_id=workspace_id,
    )
    return {"jobs": [j.model_dump() for j in jobs], "count": len(jobs)}


@router.get("/{job_id}")
def get_job_details(
    job_id: str,
    store: SqliteRepairJobStore = Depends(get_store),
    workspace_id: str = Depends(get_current_workspace_id),
) -> dict[str, Any]:
    """Retrieve full details, records, and history for a repair job."""
    return store.get_job_details(job_id, workspace_id=workspace_id)


@router.get("/{job_id}/audit")
def get_audit_trail(
    job_id: str,
    store: SqliteRepairJobStore = Depends(get_store),
    workspace_id: str = Depends(get_current_workspace_id),
) -> dict[str, Any]:
    """Retrieve immutable audit events for a repair job."""
    # Ensure job exists and belongs to workspace
    store.get_job_details(job_id, workspace_id=workspace_id)
    events = store.get_audit_events(job_id, workspace_id=workspace_id)
    return {"job_id": job_id, "audit_events": [e.model_dump() for e in events]}


@router.post("/seed", status_code=status.HTTP_201_CREATED)
def seed_sample_jobs(
    store: SqliteRepairJobStore = Depends(get_store),
    workspace_id: str = Depends(get_current_workspace_id),
) -> dict[str, Any]:
    """Seed realistic Tamil Nadu repair jobs for testing and demonstration in current workbench."""
    seeded: list[dict[str, Any]] = []
    for i in range(len(SAMPLE_PRESETS)):
        sample_job = create_sample_job(i).model_copy(update={"workspace_id": workspace_id})
        # Avoid duplicate job_number if re-seeded in this workspace
        existing = store.get_job_by_number(sample_job.job_number, workspace_id=workspace_id)
        if not existing:
            store.create_job(sample_job, workspace_id=workspace_id)
            seeded.append(sample_job.model_dump())
    return {"message": f"Seeded {len(seeded)} sample jobs.", "jobs": seeded}
