"""Tests for optimistic concurrency (version conflicts) and idempotency replay."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_optimistic_locking_conflict_returns_409(client: TestClient) -> None:
    """Ensure that submitting a stale expected_version returns HTTP 409 STATE_CONFLICT."""
    intake_resp = client.post(
        "/api/jobs",
        json={
            "customer_name": "Anitha Selvaraj",
            "customer_phone": "+91 97890 45678",
            "device_kind": "Mixer Grinder",
            "brand_model": "Preethi Zodiac",
            "intake_symptoms": "Sparking",
        },
    )
    job = intake_resp.json()["job"]
    job_id = job["job_id"]
    assert job["version"] == 1

    # First update: increments version to 2
    note_resp = client.post(
        f"/api/jobs/{job_id}/technician-note",
        json={
            "expected_version": 1,
            "technician_name": "Murugan R.",
            "diagnosis_findings": "Burnt armature.",
            "root_cause": "Carbon brush wear.",
            "recommended_action": "Replace armature and brushes.",
        },
    )
    assert note_resp.status_code == 200
    assert note_resp.json()["job"]["version"] == 2

    # Second update from another stale tab/client expecting version 1: MUST fail with 409
    stale_resp = client.post(
        f"/api/jobs/{job_id}/technician-note",
        json={
            "expected_version": 1,
            "technician_name": "Murugan R.",
            "diagnosis_findings": "Stale findings.",
            "root_cause": "Stale cause.",
            "recommended_action": "Stale action.",
        },
    )
    assert stale_resp.status_code == 409
    data = stale_resp.json()
    assert data["error"] == "STATE_CONFLICT"
    assert "expected version 1, but current version is 2" in data["message"]
    assert data["details"]["current_version"] == 2
    assert data["details"]["current_job"]["version"] == 2


def test_idempotency_key_replay_returns_cached_result(client: TestClient) -> None:
    """Ensure that repeating a request with the same Idempotency-Key returns the identical

    response without duplicate writes or extra version increments.
    """
    idempotency_key = "idemp-create-job-998811"

    # 1. First call creates job
    resp1 = client.post(
        "/api/jobs",
        headers={"Idempotency-Key": idempotency_key},
        json={
            "customer_name": "Dr. R. Balaji",
            "customer_phone": "+91 94860 67890",
            "device_kind": "Laptop",
            "brand_model": "Lenovo ThinkPad E14",
            "intake_symptoms": "Broken charging port",
        },
    )
    assert resp1.status_code == 201
    job1 = resp1.json()["job"]

    # 2. Replay with identical key returns cached response
    resp2 = client.post(
        "/api/jobs",
        headers={"Idempotency-Key": idempotency_key},
        json={
            "customer_name": "Dr. R. Balaji",
            "customer_phone": "+91 94860 67890",
            "device_kind": "Laptop",
            "brand_model": "Lenovo ThinkPad E14",
            "intake_symptoms": "Broken charging port",
        },
    )
    assert resp2.status_code == 201
    job2 = resp2.json()["job"]
    assert job1["job_id"] == job2["job_id"]
    assert job1["version"] == job2["version"]

    # Verify no duplicate job was created
    list_resp = client.get("/api/jobs")
    jobs = list_resp.json()["jobs"]
    matching = [j for j in jobs if j["customer_name"] == "Dr. R. Balaji"]
    assert len(matching) == 1


def test_transition_idempotency_key_replay(client: TestClient) -> None:
    """Ensure transition endpoints replay cached result on duplicate submit."""
    intake = client.post(
        "/api/jobs",
        json={
            "customer_name": "Senthil Nathan",
            "customer_phone": "+91 98401 23456",
            "device_kind": "Fan",
            "brand_model": "Atomberg",
            "intake_symptoms": "No power",
        },
    ).json()["job"]

    transition_key = "idemp-note-step-2233"

    # First attempt
    res1 = client.post(
        f"/api/jobs/{intake['job_id']}/technician-note",
        headers={"Idempotency-Key": transition_key},
        json={
            "expected_version": 1,
            "technician_name": "Murugan",
            "diagnosis_findings": "Power surge",
            "root_cause": "Blown fuse",
            "recommended_action": "Replace fuse",
        },
    )
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["job"]["version"] == 2

    # Duplicate attempt with same idempotency key
    res2 = client.post(
        f"/api/jobs/{intake['job_id']}/technician-note",
        headers={"Idempotency-Key": transition_key},
        json={
            "expected_version": 1,
            "technician_name": "Murugan",
            "diagnosis_findings": "Power surge",
            "root_cause": "Blown fuse",
            "recommended_action": "Replace fuse",
        },
    )
    assert res2.status_code == 200
    data2 = res2.json()
    assert data1["technician_note"]["note_id"] == data2["technician_note"]["note_id"]
    assert data2["job"]["version"] == 2

    # Check audit trail only has 2 events (create + 1 note, not 2 notes)
    audit_resp = client.get(f"/api/jobs/{intake['job_id']}/audit")
    events = audit_resp.json()["audit_events"]
    assert len(events) == 2
