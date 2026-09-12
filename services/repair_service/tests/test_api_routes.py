"""Tests for API routes (health, list, details, audit, seed)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_route(client: TestClient) -> None:
    """Verify health endpoint reports correct app identity and M1 milestone."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["app"] == "Benchbook"
    assert data["milestone"] == "M1"
    assert "Kovai Tech Bench" in data["shop"]["name"]
    assert data["assistant"]["human_approval_required"] is True


def test_seed_sample_jobs_and_filter_list(client: TestClient) -> None:
    """Verify seeding realistic Tamil Nadu jobs and listing with filters."""
    seed_resp = client.post("/api/jobs/seed")
    assert seed_resp.status_code == 201
    seeded = seed_resp.json()["jobs"]
    assert len(seeded) == 4

    # List all jobs
    list_resp = client.get("/api/jobs")
    assert list_resp.status_code == 200
    all_jobs = list_resp.json()["jobs"]
    assert len(all_jobs) >= 4

    # Filter by intake state
    intake_list = client.get("/api/jobs?state=intake")
    assert intake_list.status_code == 200
    assert len(intake_list.json()["jobs"]) >= 4

    # Filter by closed state (empty initially)
    closed_list = client.get("/api/jobs?state=closed")
    assert closed_list.status_code == 200
    assert len(closed_list.json()["jobs"]) == 0


def test_get_job_details_and_audit(client: TestClient) -> None:
    """Verify fetching job details and audit trail."""
    intake_resp = client.post(
        "/api/jobs",
        json={
            "customer_name": "Senthil Nathan",
            "customer_phone": "+91 98401 23456",
            "device_kind": "BLDC Ceiling Fan",
            "brand_model": "Atomberg",
            "intake_symptoms": "Motor humming",
        },
    )
    job_id = intake_resp.json()["job"]["job_id"]

    details_resp = client.get(f"/api/jobs/{job_id}")
    assert details_resp.status_code == 200
    details = details_resp.json()
    assert details["job"]["job_id"] == job_id
    assert details["job"]["customer_name"] == "Senthil Nathan"
    assert len(details["audit_events"]) == 1

    audit_resp = client.get(f"/api/jobs/{job_id}/audit")
    assert audit_resp.status_code == 200
    events = audit_resp.json()["audit_events"]
    assert len(events) == 1
    assert events[0]["action"] == "create_job"


def test_get_nonexistent_job_returns_404(client: TestClient) -> None:
    """Verify 404 response for invalid job UUID."""
    resp = client.get("/api/jobs/invalid-uuid-12345")
    assert resp.status_code == 404
    assert resp.json()["error"] == "JOB_NOT_FOUND"
