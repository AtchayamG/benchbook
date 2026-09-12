"""Benchbook HTTP Request and Response Pydantic Schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CreateJobRequest(BaseModel):
    """Payload for registering a new intake job."""

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
    idempotency_key: str | None = None


class AddTechnicianNoteRequest(BaseModel):
    """Payload for submitting diagnostic findings."""

    expected_version: int
    technician_name: str
    diagnosis_findings: str
    root_cause: str
    recommended_action: str
    test_measurements: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = None


class PartItemInput(BaseModel):
    """Single part item input."""

    part_name: str
    part_number: str | None = None
    supplier_name: str | None = None
    unit_cost_inr: float
    quantity: int = 1
    availability_status: str = "in_stock"
    suggested_by: str = "technician"


class AddPartsLookupRequest(BaseModel):
    """Payload for recording parts needed."""

    expected_version: int
    parts: list[PartItemInput]
    actor_name: str
    actor_type: str = "technician"
    idempotency_key: str | None = None


class CreateEstimateRequest(BaseModel):
    """Payload for submitting repair cost estimate."""

    expected_version: int
    labor_charge_inr: float
    parts_total_inr: float
    tax_inr: float = 0.0
    total_amount_inr: float
    promised_delivery_date: str | None = None
    notes: str | None = None
    created_by: str
    idempotency_key: str | None = None


class CustomerApprovalRequest(BaseModel):
    """Payload for customer authorization (Human Gate)."""

    expected_version: int
    approved: bool
    approved_by: str
    recorded_by_technician: str
    channel: str = "phone"
    approval_notes: str | None = None
    agreed_amount_inr: float
    actor_type: str = "technician"  # Must NOT be "assistant" or "system"
    idempotency_key: str | None = None


class SupplierStatusRequest(BaseModel):
    """Payload for updating parts procurement status."""

    expected_version: int
    supplier_name: str
    order_reference: str | None = None
    parts_status: str = "ordered"
    expected_arrival_date: str | None = None
    tracking_notes: str | None = None
    actor_name: str
    idempotency_key: str | None = None


class RepairQueueTransitionRequest(BaseModel):
    """Payload for advancing queue state."""

    expected_version: int
    target_state: str  # "repair_queue" or "repair_in_progress"
    actor_name: str
    idempotency_key: str | None = None


class RepairCompletionRequest(BaseModel):
    """Payload for technician repair sign-off (Human Gate)."""

    expected_version: int
    technician_name: str
    actions_taken: str
    parts_replaced: list[str] = Field(default_factory=list)
    qc_tests_passed: list[str] = Field(default_factory=list)
    burn_in_duration_minutes: int = 0
    technician_signature_confirmed: bool = True
    actor_type: str = "technician"  # Must NOT be "assistant" or "system"
    idempotency_key: str | None = None


class PickupNotificationRequest(BaseModel):
    """Payload for logging pickup message sent to customer."""

    expected_version: int
    channel: str = "whatsapp"
    recipient_phone: str
    message_text: str
    sent_by_technician: str
    idempotency_key: str | None = None


class FollowUpRequest(BaseModel):
    """Payload for logging handover, payment, and warranty."""

    expected_version: int
    amount_paid_inr: float
    payment_method: str = "upi"
    payment_reference: str | None = None
    warranty_days: int = 30
    customer_feedback: str | None = None
    feedback_rating: int | None = None
    recorded_by: str
    idempotency_key: str | None = None


class JobCloseRequest(BaseModel):
    """Payload for final job close (Human Gate)."""

    expected_version: int
    closed_by: str
    resolution_summary: str
    actor_type: str = "technician"  # Must NOT be "assistant" or "system"
    idempotency_key: str | None = None


class AssistantSuggestPartsRequest(BaseModel):
    """Payload for assistant parts query."""

    device_kind: str
    symptoms: str
    findings: str | None = None


class AssistantDraftEstimateMessageRequest(BaseModel):
    """Payload for drafting customer estimate message."""

    customer_name: str
    device_kind: str
    brand_model: str
    labor_charge_inr: float
    parts_total_inr: float
    tax_inr: float
    total_amount_inr: float
    promised_date: str | None = None


class AssistantDraftPickupRequest(BaseModel):
    """Payload for drafting customer pickup notification."""

    customer_name: str
    device_kind: str
    brand_model: str
    total_amount_inr: float
    warranty_days: int = 30


class ErrorResponse(BaseModel):
    """Standardized error envelope."""

    error: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
