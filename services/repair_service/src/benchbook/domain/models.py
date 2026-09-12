"""Benchbook Domain Models.

Core entities, value objects, and audit events representing the professional
repair shop workflow.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class JobState(StrEnum):
    """The lifecycle states of a Benchbook repair job."""

    INTAKE = "intake"
    DIAGNOSIS = "diagnosis"
    PARTS_LOOKUP = "parts_lookup"
    ESTIMATE_PENDING = "estimate_pending"
    CUSTOMER_APPROVED = "customer_approved"
    ESTIMATE_REJECTED = "estimate_rejected"
    SUPPLIER_ORDERED = "supplier_ordered"
    PARTS_READY = "parts_ready"
    REPAIR_QUEUE = "repair_queue"
    REPAIR_IN_PROGRESS = "repair_in_progress"
    REPAIR_COMPLETED = "repair_completed"
    READY_FOR_PICKUP = "ready_for_pickup"
    FOLLOW_UP = "follow_up"
    CLOSED = "closed"


class ActorType(StrEnum):
    """The kind of actor initiating an action."""

    TECHNICIAN = "technician"
    CUSTOMER = "customer"
    SYSTEM = "system"
    ASSISTANT = "assistant"


class Job(BaseModel):
    """Represents a repair job on the bench."""

    model_config = ConfigDict(frozen=True)

    job_id: str
    workspace_id: str = "legacy_local_workspace"
    job_number: str
    customer_name: str
    customer_phone: str
    customer_address: str | None = None
    device_kind: str
    brand_model: str
    serial_number: str | None = None
    intake_symptoms: str
    physical_condition: str | None = None
    accessories_received: list[str] = Field(default_factory=list)
    promised_date: str | None = None
    assigned_technician: str | None = None
    current_state: JobState = JobState.INTAKE
    version: int = 1
    created_at: str
    updated_at: str


class TechnicianNote(BaseModel):
    """Diagnostic findings and repair method documented by a technician."""

    model_config = ConfigDict(frozen=True)

    note_id: str
    job_id: str
    technician_name: str
    diagnosis_findings: str
    root_cause: str
    recommended_action: str
    test_measurements: dict[str, Any] = Field(default_factory=dict)
    created_at: str


class PartItem(BaseModel):
    """A part required or suggested for the repair."""

    model_config = ConfigDict(frozen=True)

    part_id: str
    job_id: str
    part_name: str
    part_number: str | None = None
    supplier_name: str | None = None
    unit_cost_inr: float
    quantity: int = 1
    availability_status: str = "in_stock"  # in_stock, ordered, local_market, unavailable
    suggested_by: str = "technician"  # technician, assistant
    created_at: str


class Estimate(BaseModel):
    """Cost estimate provided to the customer before repair authorization."""

    model_config = ConfigDict(frozen=True)

    estimate_id: str
    job_id: str
    labor_charge_inr: float
    parts_total_inr: float
    tax_inr: float
    total_amount_inr: float
    promised_delivery_date: str | None = None
    notes: str | None = None
    created_by: str
    created_at: str


class CustomerApproval(BaseModel):
    """Explicit human approval from the customer."""

    model_config = ConfigDict(frozen=True)

    approval_id: str
    job_id: str
    approved: bool
    approved_by: str
    recorded_by_technician: str
    channel: str = "phone"  # in_person, phone, whatsapp, sms
    approval_notes: str | None = None
    agreed_amount_inr: float
    approved_at: str


class SupplierStatus(BaseModel):
    """Status of parts procurement from local suppliers."""

    model_config = ConfigDict(frozen=True)

    status_id: str
    job_id: str
    supplier_name: str
    order_reference: str | None = None
    parts_status: str = "ordered"  # in_stock, ordered, in_transit, delivered
    expected_arrival_date: str | None = None
    tracking_notes: str | None = None
    updated_at: str


class RepairCompletion(BaseModel):
    """Technician sign-off confirming repair and quality tests passed."""

    model_config = ConfigDict(frozen=True)

    completion_id: str
    job_id: str
    technician_name: str
    actions_taken: str
    parts_replaced: list[str] = Field(default_factory=list)
    qc_tests_passed: list[str] = Field(default_factory=list)
    burn_in_duration_minutes: int = 0
    technician_signature_confirmed: bool = True
    completed_at: str


class PickupNotification(BaseModel):
    """Notification drafted or sent to customer for pickup."""

    model_config = ConfigDict(frozen=True)

    notification_id: str
    job_id: str
    channel: str = "whatsapp"  # whatsapp, sms, phone
    recipient_phone: str
    message_text: str
    sent_by_technician: str
    sent_at: str


class FollowUpRecord(BaseModel):
    """Device handover, payment settlement, and post-service warranty record."""

    model_config = ConfigDict(frozen=True)

    followup_id: str
    job_id: str
    picked_up_at: str
    amount_paid_inr: float
    payment_method: str = "upi"  # upi, cash, card, neft
    payment_reference: str | None = None
    warranty_days: int = 30
    customer_feedback: str | None = None
    feedback_rating: int | None = None  # 1 to 5
    recorded_by: str
    recorded_at: str


class JobClose(BaseModel):
    """Final closure of a completed repair job."""

    model_config = ConfigDict(frozen=True)

    close_id: str
    job_id: str
    closed_by: str
    resolution_summary: str
    closed_at: str


class AuditEvent(BaseModel):
    """Immutable audit trail for every state transition and record creation."""

    model_config = ConfigDict(frozen=True)

    event_id: str
    workspace_id: str = "legacy_local_workspace"
    job_id: str
    from_state: str
    to_state: str
    action: str
    actor_type: ActorType
    actor_name: str
    idempotency_key: str | None = None
    version_before: int
    version_after: int
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: str


class Workspace(BaseModel):
    """Represents an isolated public or local repair shop workbench."""

    model_config = ConfigDict(frozen=True)

    workspace_id: str
    created_at: str
    expires_at: str
    last_active_at: str


class SessionToken(BaseModel):
    """Hashed session token authenticating a workbench session."""

    model_config = ConfigDict(frozen=True)

    token_hash: str
    workspace_id: str
    created_at: str
    expires_at: str


class SessionStatus(BaseModel):
    """Public session status response."""

    model_config = ConfigDict(frozen=True)

    authenticated: bool
    workspace_id: str | None = None
    created_at: str | None = None
    expires_at: str | None = None
    job_count: int = 0
    job_capacity: int = 50


class AdviceProvenance(BaseModel):
    """Truthful runtime provenance of advisory generation."""

    model_config = ConfigDict(frozen=True)

    engine: str = "strands"
    provider: str = "groq"
    model: str = "openai/gpt-oss-20b"
    actual_sends: int
    actual_tools: int
    generated_at: str
    latency_ms: int


class PartSuggestion(BaseModel):
    """Grounding part suggestion matching the stable synthetic parts catalogue."""

    model_config = ConfigDict(frozen=True)

    part_id: str
    part_name: str
    unit_cost_inr: float
    availability: str = "Sample / Unverified"
    supplier: str = "Synthetic Regional Supplier"
    rationale: str


class AdviceResponse(BaseModel):
    """Structured advisory result for parts, estimate, or pickup."""

    model_config = ConfigDict(frozen=True)

    job_id: str
    source_version: int
    operation: str  # parts, estimate, pickup
    summary: str
    suggested_parts: list[PartSuggestion] = Field(default_factory=list)
    draft_message: str | None = None
    provenance: AdviceProvenance
