"""Benchbook Domain Workflow Rules and Governance.

Defines allowable state transitions, optimistic concurrency validation,
and strict human approval boundaries.
"""

from __future__ import annotations

from benchbook.domain.errors import (
    HumanApprovalRequiredError,
    InvalidStateTransitionError,
    StateConflictError,
)
from benchbook.domain.models import ActorType, Job, JobState

# Map of allowable transitions: source state -> set of target states
ALLOWED_TRANSITIONS: dict[JobState, set[JobState]] = {
    JobState.INTAKE: {JobState.DIAGNOSIS},
    JobState.DIAGNOSIS: {JobState.PARTS_LOOKUP, JobState.ESTIMATE_PENDING},
    JobState.PARTS_LOOKUP: {JobState.ESTIMATE_PENDING},
    JobState.ESTIMATE_PENDING: {JobState.CUSTOMER_APPROVED, JobState.ESTIMATE_REJECTED},
    JobState.ESTIMATE_REJECTED: {JobState.CLOSED},
    JobState.CUSTOMER_APPROVED: {
        JobState.SUPPLIER_ORDERED,
        JobState.PARTS_READY,
        JobState.REPAIR_QUEUE,
    },
    JobState.SUPPLIER_ORDERED: {JobState.PARTS_READY},
    JobState.PARTS_READY: {JobState.REPAIR_QUEUE},
    JobState.REPAIR_QUEUE: {JobState.REPAIR_IN_PROGRESS},
    JobState.REPAIR_IN_PROGRESS: {JobState.REPAIR_COMPLETED},
    JobState.REPAIR_COMPLETED: {JobState.READY_FOR_PICKUP},
    JobState.READY_FOR_PICKUP: {JobState.FOLLOW_UP},
    JobState.FOLLOW_UP: {JobState.CLOSED},
    JobState.CLOSED: set(),
}

# Actions that strictly require human approval (Assistant or System cannot execute)
HUMAN_ONLY_ACTIONS: set[str] = {
    "approve_estimate",
    "reject_estimate",
    "complete_repair",
    "close_job",
}

# Target states that can only be reached through human authorization
HUMAN_ONLY_TARGET_STATES: set[JobState] = {
    JobState.CUSTOMER_APPROVED,
    JobState.ESTIMATE_REJECTED,
    JobState.REPAIR_COMPLETED,
    JobState.CLOSED,
}


def validate_optimistic_lock(job: Job, expected_version: int) -> None:
    """Ensure the client's expected version matches the current job version."""
    if job.version != expected_version:
        raise StateConflictError(
            expected_version=expected_version,
            current_version=job.version,
            current_job=job.model_dump(),
        )


def validate_transition(
    current_state: JobState,
    target_state: JobState,
    action: str,
    actor_type: ActorType,
) -> None:
    """Validate that a transition is allowed by the workflow and respects human gates."""
    # 1. Check human gate
    if (
        action in HUMAN_ONLY_ACTIONS or target_state in HUMAN_ONLY_TARGET_STATES
    ) and actor_type in (ActorType.ASSISTANT, ActorType.SYSTEM):
        raise HumanApprovalRequiredError(action=action, actor_type=actor_type.value)

    # 2. Check transition graph
    allowed = ALLOWED_TRANSITIONS.get(current_state, set())
    if target_state not in allowed:
        raise InvalidStateTransitionError(
            current_state=current_state.value,
            target_state=target_state.value,
            reason=f"Workflow does not permit transition from '{current_state.value}' to '{target_state.value}'.",
        )
