"""Concurrency, transactional mutation locking, and PostgreSQL 16 release evidence."""

from __future__ import annotations

import sys
import threading
from pathlib import Path
from typing import Any
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

repo_root = Path(__file__).resolve().parents[3]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from scripts.release_smoke import SmokeClient, run_smoke_verification  # noqa: E402

from benchbook.infrastructure.database import get_db_connection  # noqa: E402
from benchbook.interfaces.http.app import create_app  # noqa: E402


# ---------------------------------------------------------------------------
# 1. Real PostgreSQL 16.10 Full Lifecycle & Smoke Test
# ---------------------------------------------------------------------------
def test_postgres_full_19_stage_smoke_lifecycle(pg_db_url: str) -> None:
    """Execute all 19 deterministic smoke verification checks against real PostgreSQL 16.10."""
    client = SmokeClient(db_url=pg_db_url)
    try:
        run_smoke_verification(client)
    finally:
        client.close()


# ---------------------------------------------------------------------------
# 2. Two-Connection Contention (Optimistic Concurrency & Row Locks)
# ---------------------------------------------------------------------------
def _run_contention_test(store_target: str) -> None:
    """Verify that concurrent writes to the same job at the same version cleanly isolate."""
    app = create_app(db_path=store_target)
    with TestClient(app) as init_client:
        intake_resp = init_client.post(
            "/api/jobs",
            json={
                "customer_name": "Ramesh K.",
                "customer_phone": "+91 94431 11223",
                "customer_address": "R.S. Puram, Coimbatore",
                "device_kind": "Mixer Grinder",
                "brand_model": "Preethi Zodiac 750W",
                "intake_symptoms": "Jar coupler stripped; motor sparking at high speed",
            },
        )
        assert intake_resp.status_code == 201
        job_id = intake_resp.json()["job"]["job_id"]

    barrier = threading.Barrier(2)
    results: list[tuple[int, dict[str, Any]]] = []

    def worker(worker_id: int) -> None:
        with TestClient(app) as client:
            barrier.wait(timeout=10)
            resp = client.post(
                f"/api/jobs/{job_id}/technician-note",
                json={
                    "expected_version": 1,
                    "technician_name": f"Tech-{worker_id}",
                    "diagnosis_findings": f"Coupler teeth rounded off by worker {worker_id}",
                    "root_cause": "Fatigue and high load wear",
                    "recommended_action": "Replace nylon coupler",
                },
            )
            results.append((resp.status_code, resp.json()))

    t1 = threading.Thread(target=worker, args=(1,))
    t2 = threading.Thread(target=worker, args=(2,))
    t1.start()
    t2.start()
    t1.join(timeout=30)
    t2.join(timeout=30)
    assert not t1.is_alive() and not t2.is_alive(), "Contention test exceeded deadline"

    # Exactly one thread succeeds (200), and exactly one gets 409 Conflict
    status_codes = sorted([r[0] for r in results])
    assert status_codes == [200, 409], f"Unexpected status codes: {results}"

    conflict_res = next(r[1] for r in results if r[0] == 409)
    assert conflict_res.get("error") == "STATE_CONFLICT"

    # Verify database state in an independent connection
    with get_db_connection(store_target, write=False) as conn:
        row = conn.execute(
            "SELECT version, current_state FROM jobs WHERE job_id = ?", (job_id,)
        ).fetchone()
        assert row is not None
        assert row["version"] == 2
        assert row["current_state"] == "diagnosis"

        # Exactly 1 technician note row (from winning thread)
        note_count = conn.execute(
            "SELECT COUNT(*) as cnt FROM technician_notes WHERE job_id = ?", (job_id,)
        ).fetchone()["cnt"]
        assert note_count == 1

        # Exactly 2 audit events: creation (v0->v1) and winning diagnosis (v1->v2)
        audit_count = conn.execute(
            "SELECT COUNT(*) as cnt FROM audit_events WHERE job_id = ?", (job_id,)
        ).fetchone()["cnt"]
        assert audit_count == 2


def test_two_connection_contention_sqlite(temp_db_path: str) -> None:
    """Verify two-connection optimistic concurrency conflict on SQLite."""
    _run_contention_test(temp_db_path)


def test_two_connection_contention_postgres(pg_db_url: str) -> None:
    """Verify two-connection optimistic concurrency conflict on real PostgreSQL 16.10."""
    _run_contention_test(pg_db_url)


# ---------------------------------------------------------------------------
# 3. Identical-Key Concurrent Race (Advisory Locking / Serialization)
# ---------------------------------------------------------------------------
def _run_identical_key_race_test(store_target: str) -> None:
    """Verify that concurrent requests with the identical idempotency key return identical responses."""
    idemp_key = "concurrent-race-key-001"
    payload = {
        "customer_name": "Kavitha S.",
        "customer_phone": "+91 98422 99887",
        "customer_address": "Saibaba Colony, Coimbatore",
        "device_kind": "Wet Grinder",
        "brand_model": "Ultra Perfect+",
        "intake_symptoms": "Drum wobbling and belt squeak",
    }
    headers = {"Idempotency-Key": idemp_key}

    app = create_app(db_path=store_target)
    barrier = threading.Barrier(2)
    results: list[tuple[int, dict[str, Any]]] = []

    def worker() -> None:
        with TestClient(app) as client:
            barrier.wait(timeout=10)
            resp = client.post("/api/jobs", json=payload, headers=headers)
            results.append((resp.status_code, resp.json()))

    t1 = threading.Thread(target=worker)
    t2 = threading.Thread(target=worker)
    t1.start()
    t2.start()
    t1.join(timeout=30)
    t2.join(timeout=30)
    assert not t1.is_alive() and not t2.is_alive(), "Idempotency test exceeded deadline"

    # Both threads must succeed with 201 Created
    assert len(results) == 2
    assert results[0][0] == 201, f"Result 0 failed: {results[0]}"
    assert results[1][0] == 201, f"Result 1 failed: {results[1]}"

    # Both must return the identical job ID
    job_id_1 = results[0][1]["job"]["job_id"]
    job_id_2 = results[1][1]["job"]["job_id"]
    assert job_id_1 == job_id_2

    # Assert exactly ONE job and ONE idempotency record in DB
    with get_db_connection(store_target, write=False) as conn:
        assert conn.execute("SELECT COUNT(*) as cnt FROM jobs").fetchone()["cnt"] == 1
        assert (
            conn.execute(
                "SELECT COUNT(*) as cnt FROM audit_events WHERE job_id = ?", (job_id_1,)
            ).fetchone()["cnt"]
            == 1
        )
        assert (
            conn.execute(
                "SELECT COUNT(*) as cnt FROM idempotency_records WHERE idempotency_key = ?",
                (idemp_key,),
            ).fetchone()["cnt"]
            == 1
        )


def test_identical_key_race_sqlite(temp_db_path: str) -> None:
    """Verify concurrent race with identical idempotency key on SQLite."""
    _run_identical_key_race_test(temp_db_path)


def test_identical_key_race_postgres(pg_db_url: str) -> None:
    """Verify concurrent race with identical idempotency key on PostgreSQL 16.10."""
    _run_identical_key_race_test(pg_db_url)


# ---------------------------------------------------------------------------
# 4. Changed-Payload Conflict & Zero Overwrite
# ---------------------------------------------------------------------------
def _run_changed_payload_conflict_test(store_target: str) -> None:
    """Verify same key with changed payload raises 409 IDEMPOTENCY_CONFLICT without modifying DB."""
    key = "unique-reuse-key-77"
    payload_a = {
        "customer_name": "Original Customer",
        "customer_phone": "+91 99999 11111",
        "device_kind": "Inverter",
        "brand_model": "Luminous Zelio",
        "intake_symptoms": "Overload LED glowing",
    }
    headers = {"Idempotency-Key": key}

    app = create_app(db_path=store_target)
    with TestClient(app) as client:
        resp_a = client.post("/api/jobs", json=payload_a, headers=headers)
        assert resp_a.status_code == 201
        job_id = resp_a.json()["job"]["job_id"]

        # Replay with modified payload
        payload_b = dict(payload_a)
        payload_b["customer_name"] = "Attacker Customer"

        resp_b = client.post("/api/jobs", json=payload_b, headers=headers)
        assert resp_b.status_code == 409
        err_data = resp_b.json()
        assert err_data.get("error") == "IDEMPOTENCY_CONFLICT"

    # Verify database still has exactly 1 job with original customer
    with get_db_connection(store_target, write=False) as conn:
        row = conn.execute("SELECT customer_name FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        assert row is not None
        assert row["customer_name"] == "Original Customer"
        assert conn.execute("SELECT COUNT(*) as cnt FROM jobs").fetchone()["cnt"] == 1


def test_changed_payload_conflict_sqlite(temp_db_path: str) -> None:
    """Verify changed payload conflict guard on SQLite."""
    _run_changed_payload_conflict_test(temp_db_path)


def test_changed_payload_conflict_postgres(pg_db_url: str) -> None:
    """Verify changed payload conflict guard on PostgreSQL 16.10."""
    _run_changed_payload_conflict_test(pg_db_url)


# ---------------------------------------------------------------------------
# 5. Atomic Rollback On Mid-Transaction Failure (Zero Orphan Rows)
# ---------------------------------------------------------------------------
def _run_rollback_test(store_target: str) -> None:
    """Verify mid-transaction exception rolls back child rows and audit rows completely."""
    app = create_app(db_path=store_target)
    with TestClient(app, raise_server_exceptions=False) as client:
        intake_resp = client.post(
            "/api/jobs",
            json={
                "customer_name": "Senthil N.",
                "customer_phone": "+91 98401 22334",
                "device_kind": "Induction Cooktop",
                "brand_model": "Prestige PIC 20.0",
                "intake_symptoms": "E0 error code; IGBT shorted",
            },
        )
        assert intake_resp.status_code == 201
        job_id = intake_resp.json()["job"]["job_id"]

        # Monkeypatch uuid4 in sqlite_store to raise an exception during audit record creation
        with patch(
            "benchbook.infrastructure.sqlite_store.uuid4",
            side_effect=RuntimeError("Simulated failure before transaction commit"),
        ):
            resp = client.post(
                f"/api/jobs/{job_id}/technician-note",
                json={
                    "expected_version": 1,
                    "technician_name": "Murugan R.",
                    "diagnosis_findings": "IGBT shorted; bridge rectifier open",
                    "root_cause": "Overcurrent stress",
                    "recommended_action": "Replace 25N120 IGBT",
                },
            )
            # Must return 500 due to unhandled simulated failure
            assert resp.status_code == 500

    # Verify rollback in database:
    # 1. Job version must still be 1, current_state still intake
    # 2. 0 technician notes
    # 3. Exactly 1 audit row (from create_job)
    with get_db_connection(store_target, write=False) as conn:
        row = conn.execute(
            "SELECT version, current_state FROM jobs WHERE job_id = ?", (job_id,)
        ).fetchone()
        assert row is not None
        assert row["version"] == 1
        assert row["current_state"] == "intake"

        assert (
            conn.execute(
                "SELECT COUNT(*) as cnt FROM technician_notes WHERE job_id = ?", (job_id,)
            ).fetchone()["cnt"]
            == 0
        )
        assert (
            conn.execute(
                "SELECT COUNT(*) as cnt FROM audit_events WHERE job_id = ?", (job_id,)
            ).fetchone()["cnt"]
            == 1
        )


def test_atomic_rollback_sqlite(temp_db_path: str) -> None:
    """Verify atomic rollback on mid-transaction failure in SQLite."""
    _run_rollback_test(temp_db_path)


def test_atomic_rollback_postgres(pg_db_url: str) -> None:
    """Verify atomic rollback on mid-transaction failure in PostgreSQL 16.10."""
    _run_rollback_test(pg_db_url)


# ---------------------------------------------------------------------------
# 6. Durability Across Restart & Reconnection
# ---------------------------------------------------------------------------
def _run_durability_test(store_target: str) -> None:
    """Verify data persistence and idempotency replay across store reconnections."""
    idemp_key = "durability-restart-key-888"
    intake_payload = {
        "customer_name": "Durability User",
        "customer_phone": "+91 94444 33333",
        "device_kind": "Microwave Oven",
        "brand_model": "LG NeoChef 28L",
        "intake_symptoms": "High voltage fuse blown",
    }
    headers = {"Idempotency-Key": idemp_key}

    # Session 1: Create job with idempotency key and advance version
    app1 = create_app(db_path=store_target)
    with TestClient(app1) as client1:
        resp = client1.post("/api/jobs", json=intake_payload, headers=headers)
        assert resp.status_code == 201
        job_id = resp.json()["job"]["job_id"]

        resp_diag = client1.post(
            f"/api/jobs/{job_id}/technician-note",
            json={
                "expected_version": 1,
                "technician_name": "Murugan R.",
                "diagnosis_findings": "HV capacitor short; diode leaky",
                "root_cause": "HV dielectric failure",
                "recommended_action": "Replace HV cap and diode",
            },
        )
        assert resp_diag.status_code == 200

    # Session 2: Fresh app/client instance to simulate restart
    app2 = create_app(db_path=store_target)
    with TestClient(app2) as client2:
        # Verify job is at diagnosis and version 2
        resp_job = client2.get(f"/api/jobs/{job_id}")
        assert resp_job.status_code == 200
        job_data = resp_job.json()["job"]
        assert job_data["version"] == 2
        assert job_data["current_state"] == "diagnosis"

        # Verify idempotency record persisted and replays exact original response
        replayed = client2.post("/api/jobs", json=intake_payload, headers=headers)
        assert replayed.status_code == 201
        assert replayed.json()["job"]["job_id"] == job_id
        assert replayed.json()["job"]["version"] == 1  # Original snapshot

        # Verify audit trail
        resp_audit = client2.get(f"/api/jobs/{job_id}/audit")
        assert resp_audit.status_code == 200
        events = resp_audit.json()["audit_events"]
        assert len(events) == 2
        assert events[0]["version_before"] == 0 and events[0]["version_after"] == 1
        assert events[1]["version_before"] == 1 and events[1]["version_after"] == 2


def test_durability_reconnect_sqlite(temp_db_path: str) -> None:
    """Verify restart durability and idempotency replay on SQLite."""
    _run_durability_test(temp_db_path)


def test_durability_reconnect_postgres(pg_db_url: str) -> None:
    """Verify restart durability and idempotency replay on PostgreSQL 16.10."""
    _run_durability_test(pg_db_url)


class ReplaySmokeClient(SmokeClient):
    """Exercise every successful workflow POST twice, requiring an exact replay."""

    def post(self, path: str, json: Any = None, headers: dict[str, str] | None = None) -> Any:
        supplied = dict(headers or {})
        if not supplied and not (isinstance(json, dict) and json.get("idempotency_key")):
            supplied["Idempotency-Key"] = str(uuid4())
        response = super().post(path, json=json, headers=supplied)
        if response.status_code in (200, 201) and path.startswith("/api/jobs"):
            replay = super().post(path, json=json, headers=supplied)
            assert replay.status_code == response.status_code
            assert replay.json() == response.json(), f"Replay changed response for {path}"
        return response


def test_full_workflow_replays_sqlite(temp_db_path: str) -> None:
    client = ReplaySmokeClient(db_url=temp_db_path)
    try:
        run_smoke_verification(client)
    finally:
        client.close()


def test_full_workflow_replays_postgres(pg_db_url: str) -> None:
    client = ReplaySmokeClient(db_url=pg_db_url)
    try:
        run_smoke_verification(client)
    finally:
        client.close()
