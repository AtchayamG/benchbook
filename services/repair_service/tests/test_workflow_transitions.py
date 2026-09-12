"""Comprehensive integration test for Benchbook complete 11-stage workflow."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_complete_live_workflow_slice(client: TestClient) -> None:
    """Demonstrate the full persisted vertical slice:

    intake -> technician note -> parts lookup -> estimate -> customer approval ->
    supplier status -> repair queue -> completion -> pickup notification -> follow-up -> close
    """
    # 1. Intake: Create job
    intake_resp = client.post(
        "/api/jobs",
        json={
            "customer_name": "Senthil Nathan",
            "customer_phone": "+91 98401 23456",
            "customer_address": "Gandhipuram, Coimbatore",
            "device_kind": "BLDC Ceiling Fan",
            "brand_model": "Atomberg Renesa 1200mm",
            "serial_number": "ATMB-2024-88419",
            "intake_symptoms": "Motor humming loudly at speed 2, erratic speed transitions, LED blinks 3 times.",
            "physical_condition": "Canopy and downrod intact.",
            "accessories_received": ["Remote", "Shackle Kit"],
            "promised_date": "2026-09-16",
            "assigned_technician": "Murugan R.",
        },
    )
    assert intake_resp.status_code == 201
    job = intake_resp.json()["job"]
    job_id = job["job_id"]
    assert job["current_state"] == "intake"
    assert job["version"] == 1

    # 2. Technician Note: Diagnosis
    note_resp = client.post(
        f"/api/jobs/{job_id}/technician-note",
        json={
            "expected_version": 1,
            "technician_name": "Murugan R.",
            "diagnosis_findings": "Inspected motor driver PCB. Phase B gate driver FET damaged.",
            "root_cause": "Failed FD6288Q gate driver IC and dried 450V filter capacitor.",
            "recommended_action": "Replace gate driver IC and high-voltage filter capacitor.",
            "test_measurements": {"phase_a_ohms": 14.2, "phase_b_ohms": 0.8, "dc_bus_volts": 318.0},
        },
    )
    assert note_resp.status_code == 200
    data = note_resp.json()
    assert data["job"]["current_state"] == "diagnosis"
    assert data["job"]["version"] == 2
    assert (
        data["technician_note"]["root_cause"]
        == "Failed FD6288Q gate driver IC and dried 450V filter capacitor."
    )

    # 3. Parts Lookup: Record parts required
    parts_resp = client.post(
        f"/api/jobs/{job_id}/parts-lookup",
        json={
            "expected_version": 2,
            "parts": [
                {
                    "part_name": "BLDC Motor Driver Controller IC (FD6288Q)",
                    "part_number": "FD6288Q",
                    "supplier_name": "Supreme Electronics Spares, Cross Cut Road, Coimbatore",
                    "unit_cost_inr": 280.0,
                    "quantity": 1,
                    "availability_status": "in_stock",
                    "suggested_by": "technician",
                },
                {
                    "part_name": "SMPS High-Voltage Filter Capacitor (450V 22uF)",
                    "part_number": "Rubycon BXW 450V",
                    "supplier_name": "Kovai Micro Spares, Gandhipuram",
                    "unit_cost_inr": 45.0,
                    "quantity": 1,
                    "availability_status": "in_stock",
                    "suggested_by": "technician",
                },
            ],
            "actor_name": "Murugan R.",
        },
    )
    assert parts_resp.status_code == 200
    data = parts_resp.json()
    assert data["job"]["current_state"] == "parts_lookup"
    assert data["job"]["version"] == 3
    assert len(data["parts"]) == 2

    # 4. Estimate: Generate repair cost estimate
    est_resp = client.post(
        f"/api/jobs/{job_id}/estimate",
        json={
            "expected_version": 3,
            "labor_charge_inr": 450.0,
            "parts_total_inr": 325.0,
            "tax_inr": 139.50,
            "total_amount_inr": 914.50,
            "promised_delivery_date": "2026-09-15",
            "notes": "Includes PCB rework, SMD component soldering, and 2-hour burn-in test.",
            "created_by": "Murugan R.",
        },
    )
    assert est_resp.status_code == 200
    data = est_resp.json()
    assert data["job"]["current_state"] == "estimate_pending"
    assert data["job"]["version"] == 4
    assert data["estimate"]["total_amount_inr"] == 914.50

    # 5. Customer Approval: Explicit human authorization (technician on behalf of customer)
    appr_resp = client.post(
        f"/api/jobs/{job_id}/customer-approval",
        json={
            "expected_version": 4,
            "approved": True,
            "approved_by": "Senthil Nathan",
            "recorded_by_technician": "Murugan R.",
            "channel": "phone",
            "approval_notes": "Customer agreed to estimate of ₹914.50 over phone call at 11:30 AM.",
            "agreed_amount_inr": 914.50,
            "actor_type": "technician",
        },
    )
    assert appr_resp.status_code == 200
    data = appr_resp.json()
    assert data["job"]["current_state"] == "customer_approved"
    assert data["job"]["version"] == 5
    assert data["customer_approval"]["approved"] is True

    # 6. Supplier Status: Update procurement/stock allocation
    sup_resp = client.post(
        f"/api/jobs/{job_id}/supplier-status",
        json={
            "expected_version": 5,
            "supplier_name": "Supreme Electronics Spares, Cross Cut Road",
            "order_reference": "SES-CBE-2026-441",
            "parts_status": "in_stock",
            "expected_arrival_date": "2026-09-13",
            "tracking_notes": "Parts picked up from local counter stock.",
            "actor_name": "Murugan R.",
        },
    )
    assert sup_resp.status_code == 200
    data = sup_resp.json()
    assert data["job"]["current_state"] == "parts_ready"
    assert data["job"]["version"] == 6

    # 7. Repair Queue: Move to queue and begin work
    queue_resp = client.post(
        f"/api/jobs/{job_id}/repair-queue",
        json={
            "expected_version": 6,
            "target_state": "repair_queue",
            "actor_name": "Murugan R.",
        },
    )
    assert queue_resp.status_code == 200
    assert queue_resp.json()["job"]["current_state"] == "repair_queue"
    assert queue_resp.json()["job"]["version"] == 7

    start_resp = client.post(
        f"/api/jobs/{job_id}/repair-queue",
        json={
            "expected_version": 7,
            "target_state": "repair_in_progress",
            "actor_name": "Murugan R.",
        },
    )
    assert start_resp.status_code == 200
    assert start_resp.json()["job"]["current_state"] == "repair_in_progress"
    assert start_resp.json()["job"]["version"] == 8

    # 8. Repair Completion: Technician sign-off and QC testing (Human Gate)
    comp_resp = client.post(
        f"/api/jobs/{job_id}/repair-completion",
        json={
            "expected_version": 8,
            "technician_name": "Murugan R.",
            "actions_taken": "Desoldered defective FD6288Q IC. Installed new IC with heatsink compound. Replaced 450V capacitor.",
            "parts_replaced": ["FD6288Q Gate Driver IC", "Rubycon 450V 22uF Capacitor"],
            "qc_tests_passed": [
                "3-phase back-EMF balance verified",
                "Speed steps 1 to 5 verified without stutter",
                "Thermal scan: driver IC stable at 44 deg C",
            ],
            "burn_in_duration_minutes": 120,
            "technician_signature_confirmed": True,
            "actor_type": "technician",
        },
    )
    assert comp_resp.status_code == 200
    data = comp_resp.json()
    assert data["job"]["current_state"] == "repair_completed"
    assert data["job"]["version"] == 9
    assert len(data["repair_completion"]["qc_tests_passed"]) == 3

    # 9. Pickup Notification: Send message to customer
    notif_resp = client.post(
        f"/api/jobs/{job_id}/pickup-notification",
        json={
            "expected_version": 9,
            "channel": "whatsapp",
            "recipient_phone": "+91 98401 23456",
            "message_text": "Vanakkam Senthil Nathan, your Atomberg fan is repaired, QC passed, and ready for pickup.",
            "sent_by_technician": "Murugan R.",
        },
    )
    assert notif_resp.status_code == 200
    data = notif_resp.json()
    assert data["job"]["current_state"] == "ready_for_pickup"
    assert data["job"]["version"] == 10

    # 10. Follow-up / Handover: Customer collection & payment
    fol_resp = client.post(
        f"/api/jobs/{job_id}/follow-up",
        json={
            "expected_version": 10,
            "amount_paid_inr": 914.50,
            "payment_method": "upi",
            "payment_reference": "UPI/20260914/994821034",
            "warranty_days": 30,
            "customer_feedback": "Fan is spinning smoothly and quietly like brand new.",
            "feedback_rating": 5,
            "recorded_by": "Murugan R.",
        },
    )
    assert fol_resp.status_code == 200
    data = fol_resp.json()
    assert data["job"]["current_state"] == "follow_up"
    assert data["job"]["version"] == 11
    assert data["follow_up"]["payment_method"] == "upi"

    # 11. Close Job: Final closure (Human Gate)
    close_resp = client.post(
        f"/api/jobs/{job_id}/close",
        json={
            "expected_version": 11,
            "closed_by": "Murugan R.",
            "resolution_summary": "Job completed successfully, customer collected, payment received via UPI, 30-day warranty activated.",
            "actor_type": "technician",
        },
    )
    assert close_resp.status_code == 200
    data = close_resp.json()
    assert data["job"]["current_state"] == "closed"
    assert data["job"]["version"] == 12

    # Verify complete job details and full audit trail
    details_resp = client.get(f"/api/jobs/{job_id}")
    assert details_resp.status_code == 200
    details = details_resp.json()
    assert details["job"]["current_state"] == "closed"
    assert details["job"]["version"] == 12
    assert len(details["technician_notes"]) == 1
    assert len(details["parts"]) == 2
    assert details["estimate"] is not None
    assert details["customer_approval"] is not None
    assert len(details["supplier_statuses"]) == 1
    assert details["repair_completion"] is not None
    assert len(details["pickup_notifications"]) == 1
    assert details["follow_up"] is not None
    assert details["job_close"] is not None
    assert len(details["audit_events"]) == 12


def test_invalid_state_transition_fails(client: TestClient) -> None:
    """Verify that jumping over required steps is rejected with 400."""
    intake_resp = client.post(
        "/api/jobs",
        json={
            "customer_name": "Karthik Rajan",
            "customer_phone": "+91 98940 56789",
            "device_kind": "Mixer Grinder",
            "brand_model": "Preethi Zodiac",
            "intake_symptoms": "Armature sparking.",
        },
    )
    job_id = intake_resp.json()["job"]["job_id"]

    # Attempting to jump from intake straight to repair_completed
    jump_resp = client.post(
        f"/api/jobs/{job_id}/repair-completion",
        json={
            "expected_version": 1,
            "technician_name": "Murugan R.",
            "actions_taken": "Fixed",
            "qc_tests_passed": ["Done"],
            "technician_signature_confirmed": True,
            "actor_type": "technician",
        },
    )
    assert jump_resp.status_code == 400
    data = jump_resp.json()
    assert data["error"] == "INVALID_STATE_TRANSITION"
    assert "Workflow does not permit transition" in data["message"]


def test_rejected_estimate_leads_to_close(client: TestClient) -> None:
    """Verify flow when customer rejects repair estimate."""
    intake_resp = client.post(
        "/api/jobs",
        json={
            "customer_name": "Meenakshi Sundaram",
            "customer_phone": "+91 94432 34567",
            "device_kind": "Split AC Inverter PCB",
            "brand_model": "Voltas 185V",
            "intake_symptoms": "E6 error.",
        },
    )
    job_id = intake_resp.json()["job"]["job_id"]

    # Note
    client.post(
        f"/api/jobs/{job_id}/technician-note",
        json={
            "expected_version": 1,
            "technician_name": "Palanisamy K.",
            "diagnosis_findings": "Multiple burnt traces and fried microcontroller.",
            "root_cause": "Lightning surge.",
            "recommended_action": "Board replacement required.",
        },
    )

    # Estimate
    client.post(
        f"/api/jobs/{job_id}/estimate",
        json={
            "expected_version": 2,
            "labor_charge_inr": 800.0,
            "parts_total_inr": 4500.0,
            "tax_inr": 954.0,
            "total_amount_inr": 6254.0,
            "notes": "Cost of new OEM board.",
            "created_by": "Palanisamy K.",
        },
    )

    # Customer declines
    decl_resp = client.post(
        f"/api/jobs/{job_id}/customer-approval",
        json={
            "expected_version": 3,
            "approved": False,
            "approved_by": "Meenakshi Sundaram",
            "recorded_by_technician": "Palanisamy K.",
            "channel": "phone",
            "approval_notes": "Customer felt new AC board is too expensive, decided to buy new AC unit.",
            "agreed_amount_inr": 0.0,
            "actor_type": "technician",
        },
    )
    assert decl_resp.status_code == 200
    assert decl_resp.json()["job"]["current_state"] == "estimate_rejected"
    assert decl_resp.json()["job"]["version"] == 4

    # Close job directly from estimate_rejected
    close_resp = client.post(
        f"/api/jobs/{job_id}/close",
        json={
            "expected_version": 4,
            "closed_by": "Palanisamy K.",
            "resolution_summary": "Estimate declined. Board returned to customer without repair.",
            "actor_type": "technician",
        },
    )
    assert close_resp.status_code == 200
    assert close_resp.json()["job"]["current_state"] == "closed"
    assert close_resp.json()["job"]["version"] == 5
