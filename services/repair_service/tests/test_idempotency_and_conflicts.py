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


def test_header_vs_body_idempotency_key_mismatch_returns_422(client: TestClient) -> None:
    """Header and body idempotency keys must agree or return HTTP 422 VALIDATION_ERROR."""
    resp = client.post(
        "/api/jobs",
        headers={"Idempotency-Key": "key-from-header"},
        json={
            "customer_name": "Karthik Raja",
            "customer_phone": "+91 98401 11223",
            "device_kind": "Mixer Grinder",
            "brand_model": "Preethi Zodiac",
            "intake_symptoms": "Motor humming",
            "idempotency_key": "key-from-body-different",
        },
    )
    assert resp.status_code == 422
    data = resp.json()
    assert data["error"] == "VALIDATION_ERROR"
    assert "Idempotency-Key header and request body idempotency_key must match" in data["message"]


def test_header_vs_body_idempotency_key_agreement_succeeds(client: TestClient) -> None:
    """When both header and body keys are provided and agree, request succeeds."""
    key = "agreed-key-991122"
    resp = client.post(
        "/api/jobs",
        headers={"Idempotency-Key": key},
        json={
            "customer_name": "Karthik Raja",
            "customer_phone": "+91 98401 11223",
            "device_kind": "Mixer Grinder",
            "brand_model": "Preethi Zodiac",
            "intake_symptoms": "Motor humming",
            "idempotency_key": key,
        },
    )
    assert resp.status_code == 201
    assert resp.json()["job"]["customer_name"] == "Karthik Raja"


def test_idempotency_key_with_different_payload_returns_409(client: TestClient) -> None:
    """Reusing an idempotency key with a changed payload must return HTTP 409 IDEMPOTENCY_CONFLICT."""
    key = "conflict-key-556677"
    # First request: customer A
    resp1 = client.post(
        "/api/jobs",
        headers={"Idempotency-Key": key},
        json={
            "customer_name": "Original Customer",
            "customer_phone": "+91 98401 99999",
            "device_kind": "Induction Stove",
            "brand_model": "Prestige PIC 20",
            "intake_symptoms": "E0 Error code",
        },
    )
    assert resp1.status_code == 201
    _job_id = resp1.json()["job"]["job_id"]
    assert _job_id is not None

    # Second request: same key, but different payload (customer name changed)
    resp2 = client.post(
        "/api/jobs",
        headers={"Idempotency-Key": key},
        json={
            "customer_name": "Attacker / Different Customer",
            "customer_phone": "+91 98401 99999",
            "device_kind": "Induction Stove",
            "brand_model": "Prestige PIC 20",
            "intake_symptoms": "E0 Error code",
        },
    )
    assert resp2.status_code == 409
    data = resp2.json()
    assert data["error"] == "IDEMPOTENCY_CONFLICT"
    assert "previously used with a different request" in data["message"]
    assert data["details"]["idempotency_key"] == key
    # Ensure no data leak of the original payload
    assert "Original Customer" not in str(data)

    # Verify no second job was created
    list_resp = client.get("/api/jobs")
    attacker_jobs = [
        j for j in list_resp.json()["jobs"] if j["customer_name"] == "Attacker / Different Customer"
    ]
    assert len(attacker_jobs) == 0


def test_idempotency_key_across_different_scopes_returns_409(client: TestClient) -> None:
    """Reusing an idempotency key for a different transition operation must return 409 IDEMPOTENCY_CONFLICT."""
    key = "cross-scope-key-3344"
    resp1 = client.post(
        "/api/jobs",
        headers={"Idempotency-Key": key},
        json={
            "customer_name": "Nandhini G.",
            "customer_phone": "+91 98402 33445",
            "device_kind": "Iron Box",
            "brand_model": "Philips GC181",
            "intake_symptoms": "No heating",
        },
    )
    assert resp1.status_code == 201
    job_id = resp1.json()["job"]["job_id"]

    # Try to reuse the exact same idempotency key for adding a technician note on that job
    resp2 = client.post(
        f"/api/jobs/{job_id}/technician-note",
        headers={"Idempotency-Key": key},
        json={
            "expected_version": 1,
            "technician_name": "Murugan R.",
            "diagnosis_findings": "Thermal fuse blown",
            "root_cause": "Overheat",
            "recommended_action": "Replace thermal fuse",
        },
    )
    assert resp2.status_code == 409
    assert resp2.json()["error"] == "IDEMPOTENCY_CONFLICT"


def test_idempotency_durable_across_restart(tmp_path: object) -> None:
    """Idempotency records must persist across store restarts / client reconnections."""
    from benchbook.interfaces.http.app import create_app

    db_path = str(tmp_path) + "/durable_idemp.db"
    key = "durable-restart-key-7788"

    # Process 1 / Connection 1 creates job
    app1 = create_app(db_path=db_path)
    client1 = TestClient(app1)

    r1 = client1.post(
        "/api/jobs",
        headers={"Idempotency-Key": key},
        json={
            "customer_name": "Durable Customer",
            "customer_phone": "+91 98403 77889",
            "device_kind": "Table Fan",
            "brand_model": "Usha Mist Air",
            "intake_symptoms": "Oscillation broken",
        },
    )
    assert r1.status_code == 201
    created_job = r1.json()["job"]

    # Process 2 / Connection 2 (simulating service restart on same DB)
    app2 = create_app(db_path=db_path)
    client2 = TestClient(app2)

    # Replay with same key + same payload: returns identical cached result
    r2 = client2.post(
        "/api/jobs",
        headers={"Idempotency-Key": key},
        json={
            "customer_name": "Durable Customer",
            "customer_phone": "+91 98403 77889",
            "device_kind": "Table Fan",
            "brand_model": "Usha Mist Air",
            "intake_symptoms": "Oscillation broken",
        },
    )
    assert r2.status_code == 201
    replayed_job = r2.json()["job"]
    assert replayed_job["job_id"] == created_job["job_id"]
    assert replayed_job["job_number"] == created_job["job_number"]

    # Conflict with same key + changed payload after restart: returns 409
    r3 = client2.post(
        "/api/jobs",
        headers={"Idempotency-Key": key},
        json={
            "customer_name": "Changed Name After Restart",
            "customer_phone": "+91 98403 77889",
            "device_kind": "Table Fan",
            "brand_model": "Usha Mist Air",
            "intake_symptoms": "Oscillation broken",
        },
    )
    assert r3.status_code == 409
    assert r3.json()["error"] == "IDEMPOTENCY_CONFLICT"
