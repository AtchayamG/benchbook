"""Adversarial regressions from independent BB-004 review; no provider traffic."""

from __future__ import annotations

import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from test_strands_advisory import _make_mock_transport

from benchbook.config import settings
from benchbook.domain.errors import (
    AssistantTimeoutError,
    AssistantUnavailableError,
    CapacityExceededError,
)
from benchbook.domain.models import Job, Workspace
from benchbook.infrastructure.admission import InferenceAdmissionStore
from benchbook.infrastructure.database import get_db_connection
from benchbook.infrastructure.sqlite_store import SqliteRepairJobStore, _now_iso
from benchbook.infrastructure.strands_advisory import StrandsAdvisoryEngine
from benchbook.interfaces.http.app import create_app


def sample_job() -> Job:
    return Job(
        job_id="review-job",
        job_number="REVIEW",
        workspace_id="review-workspace",
        customer_name="Synthetic Customer",
        customer_phone="9000000000",
        customer_address="Example Street",
        serial_number="SYNTHETIC-SERIAL",
        brand_model="Synthetic Customer fan",
        device_kind="fan 9000000000",
        intake_symptoms="Bearing hum",
        physical_condition="synthetic",
        created_at=_now_iso(),
        updated_at=_now_iso(),
    )


def test_static_path_cannot_escape_bundle(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    static = tmp_path / "public"
    static.mkdir()
    (static / "index.html").write_text("<h1>Public</h1>")
    (tmp_path / "private.txt").write_text("private fixture")
    monkeypatch.setenv("BENCHBOOK_STATIC_DIR", str(static))
    with TestClient(create_app(str(tmp_path / "data.sqlite"))) as client:
        response = client.get("/%2e%2e/private.txt")
        assert response.status_code == 404
        assert "private fixture" not in response.text


class ObservedTransport(httpx.AsyncBaseTransport):
    def __init__(self, fail_close: bool = False, hang: bool = False) -> None:
        self.requests: list[dict[str, Any]] = []
        self.inner = _make_mock_transport(captured_requests=self.requests)
        self.closed = False
        self.fail_close = fail_close
        self.hang = hang

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if self.hang:
            await asyncio.sleep(60)
        return await self.inner.handle_async_request(request)

    async def aclose(self) -> None:
        if self.fail_close:
            raise RuntimeError("synthetic private error must not escape")
        await self.inner.aclose()
        self.closed = True


def admission_row(store: SqliteRepairJobStore) -> dict[str, Any]:
    with get_db_connection(store.db_path) as conn:
        return dict(conn.execute("SELECT * FROM inference_admissions").fetchone())


@pytest.mark.asyncio
async def test_success_closes_transport_before_releasing_and_scrubs_both_stages(
    store: SqliteRepairJobStore,
) -> None:
    transport = ObservedTransport()
    engine = StrandsAdvisoryEngine(
        InferenceAdmissionStore(store.db_path), "synthetic-key", transport, "live"
    )
    result = await engine.generate_advice("review-workspace", sample_job(), "parts", 1)
    assert result.provenance.actual_sends == 3
    assert transport.closed
    assert admission_row(store)["is_active"] == 0
    wire = json.dumps(transport.requests)
    assert "Synthetic Customer" not in wire
    assert "9000000000" not in wire
    assert "SYNTHETIC-SERIAL" not in wire


@pytest.mark.asyncio
async def test_close_failure_fences_slot_and_does_not_claim_success(
    store: SqliteRepairJobStore,
) -> None:
    transport = ObservedTransport(fail_close=True)
    engine = StrandsAdvisoryEngine(
        InferenceAdmissionStore(store.db_path), "synthetic-key", transport, "live"
    )
    with pytest.raises(AssistantUnavailableError):
        await engine.generate_advice("review-workspace", sample_job(), "parts", 1)
    row = admission_row(store)
    assert row["state"] == "UNCERTAIN"
    assert row["is_active"] == 1
    assert row["cleanup_completed"] == 0
    assert row["response_body"] is None
    assert row["reserved_sends"] == 6


@pytest.mark.asyncio
async def test_outer_deadline_cancels_owned_work_and_closes_transport(
    store: SqliteRepairJobStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    import benchbook.infrastructure.strands_advisory as module

    monkeypatch.setattr(module, "DEFAULT_OPERATION_DEADLINE_SECONDS", 0.05)
    transport = ObservedTransport(hang=True)
    engine = StrandsAdvisoryEngine(
        InferenceAdmissionStore(store.db_path), "synthetic-key", transport, "live"
    )
    with pytest.raises(AssistantTimeoutError):
        await asyncio.wait_for(
            engine.generate_advice("review-workspace", sample_job(), "parts", 1), 2
        )
    assert transport.closed
    row = admission_row(store)
    assert row["is_active"] == 0 and row["cleanup_completed"] == 1


def test_live_readiness_fails_without_key_and_app_modes_are_independent(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "groq_api_key", None)
    first = create_app(str(tmp_path / "first.sqlite"), "live")
    second = create_app(str(tmp_path / "second.sqlite"), "deterministic")
    with TestClient(first) as live, TestClient(second) as local:
        assert live.get("/api/ready").status_code == 503
        assert local.get("/api/ready").status_code == 200
        assert live.get("/api/health").json()["assistant"]["mode"] == "live"
        assert local.get("/api/health").json()["assistant"]["mode"] == "deterministic"


@pytest.mark.parametrize("store_fixture", ["store", "pg_store"])
@pytest.mark.parametrize("boundary", ["sessions", "workspaces", "jobs"])
def test_real_quota_boundaries_are_atomic(
    request: pytest.FixtureRequest, store_fixture: str, boundary: str
) -> None:
    store = request.getfixturevalue(store_fixture)
    now = datetime.now(UTC)
    old = (now - timedelta(days=1)).isoformat()
    future = (now + timedelta(days=30)).isoformat()
    with get_db_connection(store.db_path, write=True) as conn:
        if boundary != "jobs":
            for number in range(29 if boundary == "sessions" else 999):
                identifier = f"seed-{number}"
                created = now.isoformat() if boundary == "sessions" else old
                conn.execute(
                    "INSERT INTO workspaces VALUES (?, ?, ?, ?)",
                    (identifier, created, future, created),
                )
                conn.execute(
                    "INSERT INTO session_tokens VALUES (?, ?, ?, ?)",
                    (identifier, identifier, created, future),
                )
    if boundary == "jobs":
        for number in range(49):
            store.create_job(
                sample_job().model_copy(
                    update={"job_id": f"job-{number}", "job_number": f"J-{number}"}
                )
            )
    barrier = Barrier(2, timeout=5)

    def attempt(number: int) -> str:
        barrier.wait()
        try:
            if boundary == "jobs":
                store.create_job(
                    sample_job().model_copy(
                        update={"job_id": f"new-{number}", "job_number": f"N-{number}"}
                    )
                )
            else:
                identifier = f"new-{number}"
                store.create_workspace_and_token(
                    Workspace(
                        workspace_id=identifier,
                        created_at=now.isoformat(),
                        expires_at=future,
                        last_active_at=now.isoformat(),
                    ),
                    identifier,
                    future,
                )
            return "created"
        except CapacityExceededError:
            return "refused"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(attempt, [0, 1], timeout=15))
    assert sorted(outcomes) == ["created", "refused"]
