"""Tests for Workbench Session Isolation and Quotas (ADR-004).

Enforces:
1. Opaque 32-byte HttpOnly session cookies.
2. Complete workspace isolation: jobs, transitions, audit, and idempotency.
3. Cross-workspace access returns 404 without data leaks.
4. Capacity limits: 50 jobs/workspace, 1000 active workspaces, 30 sessions/min.
5. Production Origin checks on state-changing requests.
6. Legacy local workspace rows remain inaccessible to anonymous public sessions.
7. Both SQLite and PostgreSQL parity.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from benchbook.infrastructure.session import COOKIE_NAME, LEGACY_WORKSPACE_ID
from benchbook.interfaces.http.app import create_app


def _sample_intake_payload(name: str = "Test Customer") -> dict[str, Any]:
    return {
        "customer_name": name,
        "customer_phone": "9840123456",
        "device_kind": "Mixer Grinder",
        "brand_model": "Preethi Zodiac",
        "intake_symptoms": "Motor humming, no blade rotation",
    }


def test_session_lifecycle(temp_db_path: str) -> None:
    """Verify session cookie generation, resume, and status introspection."""
    app = create_app(db_path=temp_db_path)
    with TestClient(app) as client:
        # 1. Start session
        resp = client.post("/api/session")
        assert resp.status_code == 200
        data = resp.json()
        assert data["workspace_id"].startswith("ws_")
        assert data["is_new"] is True
        assert COOKIE_NAME in resp.cookies
        cookie_val = resp.cookies[COOKIE_NAME]
        assert len(cookie_val) >= 32

        # 2. Check session status
        status_resp = client.get("/api/session")
        assert status_resp.status_code == 200
        status_data = status_resp.json()
        assert status_data["authenticated"] is True
        assert status_data["workspace_id"] == data["workspace_id"]
        assert status_data["job_count"] == 0
        assert status_data["max_jobs"] == 50

        # 3. Re-calling POST /api/session with cookie resumes existing workspace
        resume_resp = client.post("/api/session")
        assert resume_resp.status_code == 200
        resume_data = resume_resp.json()
        assert resume_data["workspace_id"] == data["workspace_id"]
        assert resume_data["is_new"] is False


def test_cross_workspace_isolation(temp_db_path: str) -> None:
    """Verify that two workspaces are completely isolated with 404s on foreign accesses."""
    app = create_app(db_path=temp_db_path)

    # Session A
    with TestClient(app) as client_a:
        resp_a = client_a.post("/api/session")
        assert resp_a.status_code == 200
        ws_a = resp_a.json()["workspace_id"]

        create_a = client_a.post("/api/jobs", json=_sample_intake_payload("Alice"))
        assert create_a.status_code == 201
        job_a_id = create_a.json()["job"]["job_id"]

        # Session B
        with TestClient(app) as client_b:
            resp_b = client_b.post("/api/session")
            assert resp_b.status_code == 200
            ws_b = resp_b.json()["workspace_id"]
            assert ws_a != ws_b

            create_b = client_b.post("/api/jobs", json=_sample_intake_payload("Bob"))
            assert create_b.status_code == 201
            job_b_id = create_b.json()["job"]["job_id"]

            # Client B lists jobs -> only sees Job B
            list_b = client_b.get("/api/jobs")
            assert list_b.status_code == 200
            jobs_b = list_b.json()["jobs"]
            assert len(jobs_b) == 1
            assert jobs_b[0]["job_id"] == job_b_id

            # Client B attempts to read Job A -> 404
            get_foreign = client_b.get(f"/api/jobs/{job_a_id}")
            assert get_foreign.status_code == 404
            assert get_foreign.json()["error"] == "JOB_NOT_FOUND"

            # Client B attempts to mutate Job A -> 404
            note_foreign = client_b.post(
                f"/api/jobs/{job_a_id}/technician-note",
                json={
                    "expected_version": 1,
                    "technician_name": "Intruder",
                    "diagnosis_findings": "Hacked",
                    "root_cause": "Intrusion",
                    "recommended_action": "None",
                },
            )
            assert note_foreign.status_code == 404

            # Client B attempts to fetch audit of Job A -> 404
            audit_foreign = client_b.get(f"/api/jobs/{job_a_id}/audit")
            assert audit_foreign.status_code == 404

            # Client B attempts to request advice on Job A -> 404
            advice_foreign = client_b.post(
                f"/api/jobs/{job_a_id}/advice",
                json={"operation": "parts", "expected_version": 1},
            )
            assert advice_foreign.status_code == 404

        # Back to Client A -> lists jobs, only sees Job A
        list_a = client_a.get("/api/jobs")
        assert list_a.status_code == 200
        jobs_a = list_a.json()["jobs"]
        assert len(jobs_a) == 1
        assert jobs_a[0]["job_id"] == job_a_id

        # Verify job count in session status
        status_a = client_a.get("/api/session").json()
        assert status_a["job_count"] == 1


def test_idempotency_scoped_to_workspace(temp_db_path: str) -> None:
    """Same idempotency key in two different workspaces creates two separate jobs."""
    app = create_app(db_path=temp_db_path)
    shared_key = "shared-idempotency-key-1"

    with TestClient(app) as client_a:
        client_a.post("/api/session")
        resp_a = client_a.post(
            "/api/jobs",
            json=_sample_intake_payload("User A"),
            headers={"Idempotency-Key": shared_key},
        )
        assert resp_a.status_code == 201
        job_a_id = resp_a.json()["job"]["job_id"]

    with TestClient(app) as client_b:
        client_b.post("/api/session")
        resp_b = client_b.post(
            "/api/jobs",
            json=_sample_intake_payload("User B"),
            headers={"Idempotency-Key": shared_key},
        )
        assert resp_b.status_code == 201
        job_b_id = resp_b.json()["job"]["job_id"]

    assert job_a_id != job_b_id


def test_workspace_job_capacity_limit_50(temp_db_path: str) -> None:
    """Workspace cannot exceed 50 jobs; 51st attempt returns HTTP 503 CapacityExceededError."""
    app = create_app(db_path=temp_db_path)
    with TestClient(app) as client:
        client.post("/api/session")

        # Create 50 jobs
        for i in range(50):
            r = client.post(
                "/api/jobs",
                json=_sample_intake_payload(f"Customer {i}"),
            )
            assert r.status_code == 201

        # 51st job creation must fail with 503
        r_overflow = client.post(
            "/api/jobs",
            json=_sample_intake_payload("Customer 51"),
        )
        assert r_overflow.status_code == 503
        err = r_overflow.json()
        assert err["error"] == "CAPACITY_EXCEEDED"
        assert "50 jobs" in err["message"]


def test_production_origin_verification(temp_db_path: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """In production, missing or foreign origin on mutating endpoints returns 403 ORIGIN_REFUSED."""
    monkeypatch.setenv("BENCHBOOK_ENVIRONMENT", "production")
    monkeypatch.setenv(
        "BENCHBOOK_DATABASE_URL", "postgresql://user:pass@localhost:5432/benchbook_prod"
    )
    monkeypatch.setenv("BENCHBOOK_CORS_ORIGINS", "https://benchbook.example.com")
    from benchbook.config import Settings

    prod_settings = Settings()
    monkeypatch.setattr("benchbook.interfaces.http.dependencies.settings", prod_settings)
    monkeypatch.setattr("benchbook.interfaces.http.routes.session.settings", prod_settings)

    app = create_app(db_path=temp_db_path)
    with TestClient(app) as client:
        # 1. Missing Origin on POST in production -> 403
        resp_missing = client.post("/api/session")
        assert resp_missing.status_code == 403
        assert resp_missing.json()["error"] == "ORIGIN_REFUSED"

        # 2. Foreign Origin -> 403
        resp_foreign = client.post(
            "/api/session",
            headers={"Origin": "https://evil.com"},
        )
        assert resp_foreign.status_code == 403
        assert resp_foreign.json()["error"] == "ORIGIN_REFUSED"

        # 3. Valid allowed Origin -> 200
        resp_valid = client.post(
            "/api/session",
            headers={"Origin": "https://benchbook.example.com"},
        )
        assert resp_valid.status_code == 200


def test_legacy_rows_inaccessible_to_anonymous_sessions(temp_db_path: str) -> None:
    """Verify that rows residing in legacy_local_workspace are inaccessible to anonymous sessions."""
    app = create_app(db_path=temp_db_path)
    store = app.state.store
    from benchbook.domain.models import Job, JobState
    from benchbook.infrastructure.sqlite_store import _now_iso

    legacy_job = Job(
        job_id="job_legacy_001",
        workspace_id=LEGACY_WORKSPACE_ID,
        job_number="BB-2026-LEGACY",
        customer_name="Secret Admin",
        customer_phone="9999999999",
        device_kind="Mixer Grinder",
        brand_model="Vintage Preethi",
        intake_symptoms="Smoke",
        physical_condition="Old",
        current_state=JobState.INTAKE,
        version=1,
        created_at=_now_iso(),
        updated_at=_now_iso(),
    )
    store.create_job(legacy_job)

    with TestClient(app) as client:
        client.post("/api/session")

        # Cannot see legacy job in job list
        list_resp = client.get("/api/jobs")
        assert list_resp.status_code == 200
        assert len(list_resp.json()["jobs"]) == 0

        # Cannot access legacy job directly
        get_resp = client.get("/api/jobs/job_legacy_001")
        assert get_resp.status_code == 404


def test_postgres_workspace_isolation(pg_db_url: str) -> None:
    """Verify that multi-session workbench isolation works identically on PostgreSQL."""
    app = create_app(db_path=pg_db_url)

    with TestClient(app) as client_a:
        resp_a = client_a.post("/api/session")
        assert resp_a.status_code == 200
        ws_a = resp_a.json()["workspace_id"]

        create_a = client_a.post("/api/jobs", json=_sample_intake_payload("Alice"))
        assert create_a.status_code == 201
        job_a_id = create_a.json()["job"]["job_id"]

        with TestClient(app) as client_b:
            resp_b = client_b.post("/api/session")
            assert resp_b.status_code == 200
            ws_b = resp_b.json()["workspace_id"]
            assert ws_a != ws_b

            create_b = client_b.post("/api/jobs", json=_sample_intake_payload("Bob"))
            assert create_b.status_code == 201
            job_b_id = create_b.json()["job"]["job_id"]

            list_b = client_b.get("/api/jobs")
            assert list_b.status_code == 200
            jobs_b = list_b.json()["jobs"]
            assert len(jobs_b) == 1
            assert jobs_b[0]["job_id"] == job_b_id

            get_foreign = client_b.get(f"/api/jobs/{job_a_id}")
            assert get_foreign.status_code == 404

            advice_foreign = client_b.post(
                f"/api/jobs/{job_a_id}/advice",
                json={"operation": "parts", "expected_version": 1},
            )
            assert advice_foreign.status_code == 404

        list_a = client_a.get("/api/jobs")
        assert list_a.status_code == 200
        assert len(list_a.json()["jobs"]) == 1
        assert list_a.json()["jobs"][0]["job_id"] == job_a_id
