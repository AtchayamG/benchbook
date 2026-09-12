"""Assistant advisory endpoints for parts suggestions and communication drafting."""

from __future__ import annotations

from typing import Any, cast

from fastapi import APIRouter, Depends, Request

from benchbook.config import settings
from benchbook.infrastructure.assistant_adapter import DeterministicAssistantAdapter
from benchbook.interfaces.http.schemas import (
    AssistantDraftEstimateMessageRequest,
    AssistantDraftPickupRequest,
    AssistantSuggestPartsRequest,
)

router = APIRouter(prefix="/assistant", tags=["Assistant Advisory"])


def get_assistant(request: Request) -> DeterministicAssistantAdapter:
    return cast(DeterministicAssistantAdapter, request.app.state.assistant)


@router.post("/suggest-parts")
def suggest_parts(
    payload: AssistantSuggestPartsRequest,
    assistant: DeterministicAssistantAdapter = Depends(get_assistant),
) -> dict[str, Any]:
    """Provide advisory spare parts suggestions based on device kind and symptoms."""
    return assistant.suggest_parts(
        device_kind=payload.device_kind,
        symptoms=payload.symptoms,
        findings=payload.findings,
    )


@router.post("/draft-estimate-message")
def draft_estimate_message(
    payload: AssistantDraftEstimateMessageRequest,
    assistant: DeterministicAssistantAdapter = Depends(get_assistant),
) -> dict[str, Any]:
    """Draft WhatsApp/SMS estimate explanation for customer approval."""
    return assistant.draft_estimate_message(
        customer_name=payload.customer_name,
        device_kind=payload.device_kind,
        brand_model=payload.brand_model,
        labor_charge_inr=payload.labor_charge_inr,
        parts_total_inr=payload.parts_total_inr,
        tax_inr=payload.tax_inr,
        total_amount_inr=payload.total_amount_inr,
        promised_date=payload.promised_date,
        shop_name=settings.shop_name,
    )


@router.post("/draft-pickup-notification")
def draft_pickup_notification(
    payload: AssistantDraftPickupRequest,
    assistant: DeterministicAssistantAdapter = Depends(get_assistant),
) -> dict[str, Any]:
    """Draft WhatsApp/SMS pickup notification with shop hours and payment modes."""
    return assistant.draft_pickup_notification(
        customer_name=payload.customer_name,
        device_kind=payload.device_kind,
        brand_model=payload.brand_model,
        total_amount_inr=payload.total_amount_inr,
        warranty_days=payload.warranty_days,
        shop_name=settings.shop_name,
        shop_address=settings.shop_location,
    )
