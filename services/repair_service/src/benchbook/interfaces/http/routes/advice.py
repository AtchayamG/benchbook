"""Canonical owned-job advisory endpoint with Strands Agent integration."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, Request

from benchbook.domain.errors import (
    IneligibleAdviceError,
    JobNotFoundError,
    StateConflictError,
)
from benchbook.domain.models import AdviceResponse, JobState
from benchbook.domain.ports import AdvisoryPort
from benchbook.infrastructure.sqlite_store import SqliteRepairJobStore
from benchbook.interfaces.http.dependencies import (
    get_current_workspace_id,
    get_store,
)
from benchbook.interfaces.http.schemas import AdviceRequest, resolve_idempotency_key

router = APIRouter(prefix="/jobs", tags=["Advisory"])


def _check_operation_eligibility(
    operation: str,
    job_state: JobState,
    bundle: dict[str, Any],
) -> None:
    """Validate that job state and recorded data satisfy prerequisites for requested advice."""
    if operation == "parts":
        if job_state == JobState.CLOSED:
            raise IneligibleAdviceError(
                f"Parts advice cannot be generated for a {job_state.value} job."
            )
        notes = bundle.get("technician_notes", [])
        if not notes:
            raise IneligibleAdviceError(
                "Parts advice requires recorded diagnostic findings from a technician note."
            )

    elif operation in ("estimate", "estimate_message"):
        if not bundle.get("estimate"):
            raise IneligibleAdviceError(
                "Estimate message drafting requires a saved repair estimate."
            )

    elif operation in ("pickup", "pickup_message"):
        if not bundle.get("repair_completion"):
            raise IneligibleAdviceError(
                "Pickup notification drafting requires recorded repair completion."
            )
        eligible_states = {
            JobState.REPAIR_COMPLETED,
            JobState.READY_FOR_PICKUP,
        }
        if job_state not in eligible_states:
            raise IneligibleAdviceError(
                f"Pickup notification drafting requires eligible repair completion state (currently '{job_state.value}')."
            )
    else:
        raise IneligibleAdviceError(f"Unsupported advisory operation '{operation}'.")


@router.post("/{job_id}/advice", response_model=AdviceResponse)
async def get_job_advice(
    job_id: str,
    payload: AdviceRequest,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    store: SqliteRepairJobStore = Depends(get_store),
    workspace_id: str = Depends(get_current_workspace_id),
) -> AdviceResponse:
    """Provide Strands AI advisory grounded in the authorized job snapshot."""
    effective_idempotency = resolve_idempotency_key(idempotency_key, payload.idempotency_key)

    # 1. Load job and verify workspace ownership
    job = store.get_job(job_id, workspace_id=workspace_id)
    if not job:
        raise JobNotFoundError(f"Job with id '{job_id}' not found.")

    if job.version != payload.expected_version:
        raise StateConflictError(
            expected_version=payload.expected_version,
            current_version=job.version,
            current_job=job.model_dump(),
            message="Expected version does not match current job version.",
        )

    # 2. Check operation eligibility against snapshot
    bundle = store.get_job_details(job_id, workspace_id=workspace_id)
    _check_operation_eligibility(payload.operation, job.current_state, bundle)

    # 3. Call advisory engine (handles SQL admission, Strands execution, grounding, and replay)
    engine: AdvisoryPort = request.app.state.advisory_engine
    advice = await engine.generate_advice(
        workspace_id=workspace_id,
        job=job,
        operation=payload.operation,
        expected_version=payload.expected_version,
        idempotency_key=effective_idempotency,
        job_details=bundle,
    )

    # 4. Recheck job version after inference to prevent stale advice
    recheck_job = store.get_job(job_id, workspace_id=workspace_id)
    if not recheck_job or recheck_job.version != payload.expected_version:
        raise StateConflictError(
            expected_version=payload.expected_version,
            current_version=recheck_job.version if recheck_job else -1,
            message="Job was concurrently modified during advisory inference. Advice discarded.",
        )

    return advice
