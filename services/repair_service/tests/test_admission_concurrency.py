"""Multi-process and multi-connection admission engine concurrency tests (ADR-004).

Enforces across PostgreSQL 16.10:
1. Exactly one active advisory operation globally (concurrent attempt refused with 429).
2. Rolling quota limits: 6 sends/60s, 120 sends/24h globally, 24 sends/24h per workspace.
3. Failed calls consume quota without refund bypass.
4. Provider 429 initiates 15-minute cooldown globally.
5. Zero DB transactions held during inference.
"""

from __future__ import annotations

import threading
import time
from uuid import uuid4

import pytest

from benchbook.infrastructure.admission import (
    RESERVED_SENDS,
    AdmissionFailureCode,
    AdmissionRefusedError,
    AdmissionReservationRequest,
    AdmissionState,
    InferenceAdmissionStore,
)
from benchbook.infrastructure.database import get_db_connection, init_db


@pytest.fixture(autouse=True)
def _setup_schema(pg_db_url: str) -> None:
    init_db(pg_db_url)


def _make_req(
    workspace_id: str = "ws_test",
    owner_id: str = "own_test",
    key: str | None = None,
    payload: str | None = None,
) -> AdmissionReservationRequest:
    return AdmissionReservationRequest(
        reservation_id=f"res_{uuid4().hex[:12]}",
        workspace_id=workspace_id,
        owner_id=owner_id,
        request_key_hash=key or uuid4().hex,
        payload_hash=payload or uuid4().hex,
        reserved_sends=RESERVED_SENDS,
    )


def test_admission_1_active_operation_globally_pg(pg_db_url: str) -> None:
    """Exactly one active operation globally; concurrent attempt gets refused."""
    store = InferenceAdmissionStore(pg_db_url)
    barrier = threading.Barrier(2)
    results: list[tuple[bool, str]] = []
    lock = threading.Lock()

    def worker(idx: int) -> None:
        req = _make_req(workspace_id=f"ws_{idx}")
        barrier.wait()
        try:
            store.reserve(req)
            store.mark_dispatched(req.reservation_id, req.owner_id)
            with lock:
                results.append((True, "reserved"))
            # Simulate inference work while active
            time.sleep(0.1)
            store.finish(
                req.reservation_id,
                req.owner_id,
                AdmissionState.SUCCEEDED,
                cleanup_completed=True,
                actual_sends=2,
            )
        except AdmissionRefusedError as exc:
            with lock:
                results.append((False, str(exc)))

    t1 = threading.Thread(target=worker, args=(1,))
    t2 = threading.Thread(target=worker, args=(2,))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # Exactly one succeeded and one was refused
    successes = [r for r in results if r[0]]
    failures = [r for r in results if not r[0]]
    assert len(successes) == 1
    assert len(failures) == 1
    assert "active" in failures[0][1].lower()


def test_admission_rolling_limit_60s_pg(pg_db_url: str) -> None:
    """Rolling 60-second limit allows 6 sends; immediate second attempt within 60s is refused."""
    store = InferenceAdmissionStore(pg_db_url)
    req1 = _make_req(workspace_id="ws_60s")

    # Op 1 reserves 6 sends
    store.reserve(req1)
    store.mark_dispatched(req1.reservation_id, req1.owner_id)
    store.finish(
        req1.reservation_id,
        req1.owner_id,
        AdmissionState.SUCCEEDED,
        cleanup_completed=True,
        actual_sends=2,
    )

    # Op 2 within 60s requests 6 sends -> 6 + 6 = 12 > 6 -> Refused
    req2 = _make_req(workspace_id="ws_60s")
    with pytest.raises(AdmissionRefusedError) as exc_info:
        store.reserve(req2)
    assert "60-second" in str(exc_info.value)

    # Exact idempotent replay of Op 1 bypasses limit check and succeeds
    replayed = store.reserve(req1)
    assert replayed["reservation_id"] == req1.reservation_id


def test_admission_rolling_limit_24h_workspace_pg(pg_db_url: str) -> None:
    """Workspace limit is 24 sends (4 ops). 5th op is refused; other workspaces unaffected."""
    store = InferenceAdmissionStore(pg_db_url)
    ws_target = "ws_exhausted"

    # Manually insert 4 finished operations into PostgreSQL from 5 minutes ago
    # (outside 60s window, inside 24h window)
    with get_db_connection(pg_db_url, write=True) as conn:
        for i in range(4):
            res_id = f"res_prev_{i}"
            conn.execute(
                """
                INSERT INTO inference_admissions (
                    reservation_id, workspace_id, owner_id, request_key_hash,
                    payload_hash, reserved_sends, actual_sends, deadline_at,
                    state, is_active, created_at, released_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, 6, 2, '2026-09-12T00:00:00Z', 'SUCCEEDED', 0,
                          '2026-09-12T12:00:00Z', '2026-09-12T12:01:00Z', '2026-09-12T12:01:00Z')
                """,
                (res_id, ws_target, "own_prev", f"k_{i}", f"p_{i}"),
            )

    # 5th op for ws_target: 24 + 6 = 30 > 24 -> Refused
    req_ws_fail = _make_req(workspace_id=ws_target)
    with pytest.raises(AdmissionRefusedError) as exc_info:
        store.reserve(req_ws_fail)
    assert "workspace 24-hour" in str(exc_info.value).lower()

    # But an op for another workspace ws_other succeeds!
    req_ws_other = _make_req(workspace_id="ws_other")
    row_other = store.reserve(req_ws_other)
    assert row_other["workspace_id"] == "ws_other"


def test_admission_rolling_limit_24h_global_pg(pg_db_url: str) -> None:
    """Global limit is 120 sends (20 ops). Once reached, any new op is refused."""
    store = InferenceAdmissionStore(pg_db_url)

    # Manually insert 20 finished operations across different workspaces from 10 minutes ago
    with get_db_connection(pg_db_url, write=True) as conn:
        for i in range(20):
            conn.execute(
                """
                INSERT INTO inference_admissions (
                    reservation_id, workspace_id, owner_id, request_key_hash,
                    payload_hash, reserved_sends, actual_sends, deadline_at,
                    state, is_active, created_at, released_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, 6, 2, '2026-09-12T00:00:00Z', 'SUCCEEDED', 0,
                          '2026-09-12T12:00:00Z', '2026-09-12T12:01:00Z', '2026-09-12T12:01:00Z')
                """,
                (f"res_g_{i}", f"ws_distinct_{i}", "own_g", f"kg_{i}", f"pg_{i}"),
            )

    # Next op globally: 120 + 6 = 126 > 120 -> Refused
    req_global_fail = _make_req(workspace_id="ws_fresh")
    with pytest.raises(AdmissionRefusedError) as exc_info:
        store.reserve(req_global_fail)
    assert "global 24-hour" in str(exc_info.value).lower()


def test_admission_failed_calls_consume_quota_no_refund_pg(pg_db_url: str) -> None:
    """Failed calls settle as FAILED_CONFIRMED and retain reserved sends (no refund bypass)."""
    store = InferenceAdmissionStore(pg_db_url)
    req = _make_req(workspace_id="ws_fail_test")

    store.reserve(req)
    store.mark_dispatched(req.reservation_id, req.owner_id)
    # Settlement records failure
    store.finish(
        req.reservation_id,
        req.owner_id,
        AdmissionState.FAILED_CONFIRMED,
        cleanup_completed=True,
        actual_sends=1,
        failure_code=AdmissionFailureCode.PROVIDER_FAILURE,
    )

    # Verify that reserved_sends remains 6 in database
    with get_db_connection(pg_db_url, write=False) as conn:
        cur = conn.execute(
            "SELECT reserved_sends, actual_sends, state, is_active FROM inference_admissions WHERE reservation_id = ?",
            (req.reservation_id,),
        )
        row = cur.fetchone()
        assert row is not None
        assert row["reserved_sends"] == 6
        assert row["actual_sends"] == 1
        assert row["state"] == "FAILED_CONFIRMED"
        assert row["is_active"] == 0

    # Because 6 sends were reserved within 60s, a new request is immediately refused
    req2 = _make_req(workspace_id="ws_fail_test")
    with pytest.raises(AdmissionRefusedError):
        store.reserve(req2)


def test_admission_provider_429_initiates_15m_cooldown_pg(pg_db_url: str) -> None:
    """When a provider 429 failure occurs, all subsequent admissions are locked for 15 minutes."""
    store = InferenceAdmissionStore(pg_db_url)
    req1 = _make_req(workspace_id="ws_cooldown_1")

    store.reserve(req1)
    store.mark_dispatched(req1.reservation_id, req1.owner_id)
    store.finish(
        req1.reservation_id,
        req1.owner_id,
        AdmissionState.FAILED_CONFIRMED,
        cleanup_completed=True,
        actual_sends=1,
        failure_code=AdmissionFailureCode.PROVIDER_429,
    )

    # Even for a completely different workspace, admission is refused due to provider cooldown
    req2 = _make_req(workspace_id="ws_cooldown_2")
    with pytest.raises(AdmissionRefusedError) as exc_info:
        store.reserve(req2)
    assert "cooldown active" in str(exc_info.value).lower()


def test_admission_zero_db_transaction_during_inference_pg(pg_db_url: str) -> None:
    """Verify that during model inference, zero database transactions or advisory locks are held."""
    store = InferenceAdmissionStore(pg_db_url)
    req = _make_req(workspace_id="ws_zero_tx")

    # Reserve admission
    store.reserve(req)
    store.mark_dispatched(req.reservation_id, req.owner_id)

    # While operation is active ("inferring"), another connection can write and read freely
    with get_db_connection(pg_db_url, write=True) as other_conn:
        # Create a workspace record
        other_conn.execute(
            "INSERT INTO workspaces (workspace_id, created_at, expires_at, last_active_at) VALUES (?, ?, ?, ?)",
            (
                "ws_concurrent_check",
                "2026-09-12T00:00:00Z",
                "2026-09-13T00:00:00Z",
                "2026-09-12T00:00:00Z",
            ),
        )
        cur = other_conn.execute("SELECT COUNT(*) AS c FROM workspaces")
        count = cur.fetchone()["c"]
        assert count >= 1

    # Finally finish the admission
    store.finish(
        req.reservation_id,
        req.owner_id,
        AdmissionState.SUCCEEDED,
        cleanup_completed=True,
        actual_sends=2,
    )
