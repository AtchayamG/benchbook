"""Tests verifying strict human approval boundaries (assistant and system cannot approve work)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _setup_job_at_estimate(client: TestClient) -> tuple[str, int]:
    """Helper to advance a job to estimate_pending state."""
    job = client.post(
        "/api/jobs",
        json={
            "customer_name": "Senthil Nathan",
            "customer_phone": "+91 98401 23456",
            "device_kind": "BLDC Ceiling Fan",
            "brand_model": "Atomberg Renesa",
            "intake_symptoms": "Motor humming",
        },
    ).json()["job"]

    client.post(
        f"/api/jobs/{job['job_id']}/technician-note",
        json={
            "expected_version": 1,
            "technician_name": "Murugan",
            "diagnosis_findings": "Driver fault",
            "root_cause": "Driver IC",
            "recommended_action": "Replace IC",
        },
    )

    client.post(
        f"/api/jobs/{job['job_id']}/estimate",
        json={
            "expected_version": 2,
            "labor_charge_inr": 400.0,
            "parts_total_inr": 300.0,
            "tax_inr": 126.0,
            "total_amount_inr": 826.0,
            "created_by": "Murugan",
        },
    )

    return job["job_id"], 3


def test_assistant_cannot_approve_estimate(client: TestClient) -> None:
    """Assistant actor attempting to approve an estimate must be rejected with 403."""
    job_id, version = _setup_job_at_estimate(client)

    resp = client.post(
        f"/api/jobs/{job_id}/customer-approval",
        json={
            "expected_version": version,
            "approved": True,
            "approved_by": "AI Assistant Agent",
            "recorded_by_technician": "Auto-agent",
            "channel": "automated_agent",
            "agreed_amount_inr": 826.0,
            "actor_type": "assistant",  # DISALLOWED
        },
    )
    assert resp.status_code == 403
    data = resp.json()
    assert data["error"] == "HUMAN_APPROVAL_REQUIRED"
    assert "Actor 'assistant' cannot perform this action" in data["message"]


def test_system_cannot_approve_estimate(client: TestClient) -> None:
    """System actor attempting to approve an estimate must be rejected with 403."""
    job_id, version = _setup_job_at_estimate(client)

    resp = client.post(
        f"/api/jobs/{job_id}/customer-approval",
        json={
            "expected_version": version,
            "approved": True,
            "approved_by": "System Cron",
            "recorded_by_technician": "Daemon",
            "channel": "cron",
            "agreed_amount_inr": 826.0,
            "actor_type": "system",  # DISALLOWED
        },
    )
    assert resp.status_code == 403
    data = resp.json()
    assert data["error"] == "HUMAN_APPROVAL_REQUIRED"
    assert "Actor 'system' cannot perform this action" in data["message"]


def test_human_technician_can_approve_estimate(client: TestClient) -> None:
    """Human technician recording customer authorization succeeds."""
    job_id, version = _setup_job_at_estimate(client)

    resp = client.post(
        f"/api/jobs/{job_id}/customer-approval",
        json={
            "expected_version": version,
            "approved": True,
            "approved_by": "Senthil Nathan",
            "recorded_by_technician": "Murugan R.",
            "channel": "phone",
            "approval_notes": "Customer confirmed estimate on phone.",
            "agreed_amount_inr": 826.0,
            "actor_type": "technician",  # ALLOWED
        },
    )
    assert resp.status_code == 200
    assert resp.json()["job"]["current_state"] == "customer_approved"


def test_assistant_cannot_complete_repair(client: TestClient) -> None:
    """Assistant actor attempting to mark repair completed must be rejected with 403."""
    job_id, version = _setup_job_at_estimate(client)

    # Approve as human technician
    client.post(
        f"/api/jobs/{job_id}/customer-approval",
        json={
            "expected_version": version,
            "approved": True,
            "approved_by": "Senthil",
            "recorded_by_technician": "Murugan",
            "channel": "phone",
            "agreed_amount_inr": 826.0,
            "actor_type": "technician",
        },
    )

    # Move to queue and in_progress
    client.post(
        f"/api/jobs/{job_id}/repair-queue",
        json={"expected_version": 4, "target_state": "repair_queue", "actor_name": "Murugan"},
    )
    client.post(
        f"/api/jobs/{job_id}/repair-queue",
        json={"expected_version": 5, "target_state": "repair_in_progress", "actor_name": "Murugan"},
    )

    # Assistant attempts repair completion
    resp = client.post(
        f"/api/jobs/{job_id}/repair-completion",
        json={
            "expected_version": 6,
            "technician_name": "Auto Agent",
            "actions_taken": "Automated solder attempt",
            "qc_tests_passed": ["simulated_pass"],
            "technician_signature_confirmed": True,
            "actor_type": "assistant",  # DISALLOWED
        },
    )
    assert resp.status_code == 403
    data = resp.json()
    assert data["error"] == "HUMAN_APPROVAL_REQUIRED"
    assert "Actor 'assistant' cannot perform this action" in data["message"]


def test_assistant_cannot_close_job(client: TestClient) -> None:
    """Assistant actor attempting to close a job must be rejected with 403."""
    job_id, version = _setup_job_at_estimate(client)

    # Progress through legitimate steps to follow_up
    client.post(
        f"/api/jobs/{job_id}/customer-approval",
        json={
            "expected_version": version,
            "approved": True,
            "approved_by": "Senthil",
            "recorded_by_technician": "Murugan",
            "channel": "phone",
            "agreed_amount_inr": 826.0,
            "actor_type": "technician",
        },
    )
    client.post(
        f"/api/jobs/{job_id}/repair-queue",
        json={"expected_version": 4, "target_state": "repair_queue", "actor_name": "Murugan"},
    )
    client.post(
        f"/api/jobs/{job_id}/repair-queue",
        json={"expected_version": 5, "target_state": "repair_in_progress", "actor_name": "Murugan"},
    )
    client.post(
        f"/api/jobs/{job_id}/repair-completion",
        json={
            "expected_version": 6,
            "technician_name": "Murugan",
            "actions_taken": "Repaired driver",
            "qc_tests_passed": ["Speed check pass"],
            "technician_signature_confirmed": True,
            "actor_type": "technician",
        },
    )
    client.post(
        f"/api/jobs/{job_id}/pickup-notification",
        json={
            "expected_version": 7,
            "channel": "whatsapp",
            "recipient_phone": "+91 98401 23456",
            "message_text": "Ready for pickup",
            "sent_by_technician": "Murugan",
        },
    )
    client.post(
        f"/api/jobs/{job_id}/follow-up",
        json={
            "expected_version": 8,
            "amount_paid_inr": 826.0,
            "payment_method": "upi",
            "recorded_by": "Murugan",
        },
    )

    # Assistant attempts to close
    close_resp = client.post(
        f"/api/jobs/{job_id}/close",
        json={
            "expected_version": 9,
            "closed_by": "Automated Agent",
            "resolution_summary": "Auto close",
            "actor_type": "assistant",  # DISALLOWED
        },
    )
    assert close_resp.status_code == 403
    data = close_resp.json()
    assert data["error"] == "HUMAN_APPROVAL_REQUIRED"
    assert "Actor 'assistant' cannot perform this action" in data["message"]
