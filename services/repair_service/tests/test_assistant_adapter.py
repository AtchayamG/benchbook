"""Tests for deterministic assistant adapter and honest failure modes."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from benchbook.infrastructure.assistant_adapter import (
    DeterministicAssistantAdapter,
)
from benchbook.interfaces.http.app import create_app


def test_parts_suggestions_for_domain_devices() -> None:
    """Verify pre-computed parts suggestions for realistic Tamil Nadu repair devices."""
    adapter = DeterministicAssistantAdapter()

    # 1. BLDC Fan
    fan_res = adapter.suggest_parts(
        device_kind="BLDC Ceiling Fan", symptoms="Motor humming, speed drops"
    )
    assert len(fan_res["suggestions"]) >= 2
    assert "FD6288Q" in str(fan_res["suggestions"])
    assert fan_res["confidence_score"] > 0.8
    assert fan_res["provenance"]["advisory_only"] is True

    # 2. Split AC Inverter PCB
    ac_res = adapter.suggest_parts(
        device_kind="Split AC Inverter PCB", symptoms="E6 error compressor not starting"
    )
    assert any("IPM" in p["part_name"] for p in ac_res["suggestions"])

    # 3. Mixer Grinder
    mg_res = adapter.suggest_parts(device_kind="Mixer Grinder", symptoms="Sparking and smell")
    assert any("Armature" in p["part_name"] for p in mg_res["suggestions"])

    # 4. Unknown device falls back gracefully with provenance
    unk_res = adapter.suggest_parts(
        device_kind="Industrial Laser Welder", symptoms="Beam focus failure"
    )
    assert len(unk_res["suggestions"]) >= 1
    assert unk_res["provenance"]["requires_human_verification"] is True


def test_estimate_message_drafting() -> None:
    """Verify WhatsApp/SMS estimate explanation drafting."""
    adapter = DeterministicAssistantAdapter()
    draft = adapter.draft_estimate_message(
        customer_name="Senthil Nathan",
        device_kind="BLDC Ceiling Fan",
        brand_model="Atomberg Renesa",
        labor_charge_inr=450.0,
        parts_total_inr=325.0,
        tax_inr=139.50,
        total_amount_inr=914.50,
        promised_date="2026-09-15",
        shop_name="Kovai Tech Bench",
    )
    assert "Vanakkam Senthil Nathan" in draft["message_text"]
    assert "₹914.50" in draft["message_text"]
    assert "Kovai Tech Bench" in draft["message_text"]
    assert "Please reply 'APPROVE' to authorize" in draft["message_text"]
    assert draft["provenance"]["advisory_only"] is True


def test_pickup_notification_drafting() -> None:
    """Verify pickup notification drafting."""
    adapter = DeterministicAssistantAdapter()
    draft = adapter.draft_pickup_notification(
        customer_name="Meenakshi Sundaram",
        device_kind="Split AC Inverter PCB",
        brand_model="Voltas 185V",
        total_amount_inr=2450.0,
        warranty_days=45,
        shop_name="Kovai Tech Bench",
        shop_address="Gandhipuram, Coimbatore",
    )
    assert "Vanakkam Meenakshi Sundaram" in draft["message_text"]
    assert "45 days included" in draft["message_text"]
    assert "UPI (GPay/PhonePe)" in draft["message_text"]


@pytest.mark.parametrize(
    ("failure_mode", "expected_status", "expected_error"),
    [
        ("timeout", 504, "ASSISTANT_TIMEOUT"),
        ("busy", 429, "ASSISTANT_BUSY"),
        ("unavailable", 503, "ASSISTANT_UNAVAILABLE"),
        ("invalid_output", 502, "ASSISTANT_INVALID_OUTPUT"),
    ],
)
def test_assistant_honest_failure_modes(
    temp_db_path: str, failure_mode: str, expected_status: int, expected_error: str
) -> None:
    """Verify that assistant failure modes map to truthful HTTP statuses."""
    app = create_app(db_path=temp_db_path, assistant_mode=failure_mode)
    with TestClient(app) as test_client:
        resp = test_client.post(
            "/api/assistant/suggest-parts",
            json={"device_kind": "Mixer Grinder", "symptoms": "Overload trip"},
        )
        assert resp.status_code == expected_status
        data = resp.json()
        assert data["error"] == expected_error
        assert "Assistant" in data["message"]
