"""Tests for Real Strands Advisory Agent and Offline Transport (ADR-004).

Exercises the actual Strands agent loop, tool execution, structured extraction,
grounding against the synthetic parts catalogue, customer PII redaction,
send budget enforcement, idempotent replay, version conflict checks,
and honest error mapping using an instrumented offline HTTP transport.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from benchbook.domain.errors import (
    AssistantBusyError,
    AssistantInvalidOutputError,
    AssistantTimeoutError,
    AssistantUnavailableError,
)
from benchbook.infrastructure.admission import InferenceAdmissionStore
from benchbook.infrastructure.groq_model import GROQ_MODEL_ID
from benchbook.infrastructure.strands_advisory import StrandsAdvisoryEngine
from benchbook.interfaces.http.app import create_app

DUMMY_KEY = "gsk_test_mock_key_0123456789abcdef"


def _make_sse_tool_call(tool_name: str, arguments: dict[str, Any], call_id: str = "call_1") -> str:
    chunk1 = {
        "id": "chatcmpl-tool-1",
        "object": "chat.completion.chunk",
        "created": 1725880000,
        "model": GROQ_MODEL_ID,
        "choices": [
            {
                "index": 0,
                "delta": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "index": 0,
                            "id": call_id,
                            "type": "function",
                            "function": {
                                "name": tool_name,
                                "arguments": json.dumps(arguments),
                            },
                        }
                    ],
                },
                "finish_reason": None,
            }
        ],
    }
    chunk2 = {
        "id": "chatcmpl-tool-1",
        "object": "chat.completion.chunk",
        "created": 1725880000,
        "model": GROQ_MODEL_ID,
        "choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}],
    }
    return f"data: {json.dumps(chunk1)}\n\ndata: {json.dumps(chunk2)}\n\ndata: [DONE]\n\n"


def _make_sse_text_response(text: str) -> str:
    chunk = {
        "id": "chatcmpl-text-1",
        "object": "chat.completion.chunk",
        "created": 1725880000,
        "model": GROQ_MODEL_ID,
        "choices": [
            {
                "index": 0,
                "delta": {"role": "assistant", "content": text},
                "finish_reason": "stop",
            }
        ],
    }
    return f"data: {json.dumps(chunk)}\n\ndata: [DONE]\n\n"


def _make_parsed_response(content: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "id": "chatcmpl-parsed-1",
        "object": "chat.completion",
        "created": 1725880000,
        "model": GROQ_MODEL_ID,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": json.dumps(content) if content is not None else None,
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 120,
            "completion_tokens": 45,
            "total_tokens": 165,
        },
    }


def _make_mock_transport(
    tool_name: str = "read_repair_context",
    extracted_content: dict[str, Any] | None = None,
    captured_requests: list[dict[str, Any]] | None = None,
) -> httpx.MockTransport:
    tool_sse = _make_sse_tool_call(tool_name, {})
    text_sse = _make_sse_text_response(
        "Inspected repair context and identified candidate bearing wear."
    )
    parsed_json = _make_parsed_response(
        extracted_content
        or {
            "summary": "Identified bearing degradation in motor assembly.",
            "part_ids": ["FAN-BRG-608ZZ"],
            "part_reasons": ["Deep groove ball bearing matches hum symptoms."],
            "draft_notes": "Inspect bearing seats for excessive play.",
        }
    )

    turn = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal turn
        turn += 1
        body = json.loads(request.content.decode("utf-8"))
        if captured_requests is not None:
            captured_requests.append(body)

        if "response_format" in body:
            return httpx.Response(200, json=parsed_json)
        if turn == 1:
            return httpx.Response(200, headers={"content-type": "text/event-stream"}, text=tool_sse)
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, text=text_sse)

    return httpx.MockTransport(handler)


@pytest.mark.anyio
async def test_strands_advisory_two_stage_loop_success(temp_db_path: str) -> None:
    """Verify two-stage Strands loop with observed tool execution, grounding, and provenance."""
    admission_store = InferenceAdmissionStore(temp_db_path)
    mock_transport = _make_mock_transport()
    engine = StrandsAdvisoryEngine(
        admission_store=admission_store,
        api_key=DUMMY_KEY,
        transport=mock_transport,
    )

    app = create_app(db_path=temp_db_path)
    store = app.state.store
    from benchbook.domain.models import Job, JobState
    from benchbook.infrastructure.sqlite_store import _now_iso

    job = Job(
        job_id="job_adv_001",
        workspace_id="ws_adv_test",
        job_number="BB-2026-ADV01",
        customer_name="Senthil Nathan",
        customer_phone="9840122334",
        customer_address="Gandhipuram, Coimbatore",
        device_kind="BLDC Ceiling Fan",
        brand_model="Atomberg Renesa 1200mm",
        intake_symptoms="Motor bearing hum",
        physical_condition="Good",
        current_state=JobState.INTAKE,
        version=1,
        created_at=_now_iso(),
        updated_at=_now_iso(),
    )
    store.create_job(job)

    # Add diagnostic technician note
    from benchbook.domain.models import TechnicianNote

    store.add_technician_note(
        TechnicianNote(
            note_id="note_001",
            job_id="job_adv_001",
            technician_name="Murugan",
            diagnosis_findings="Bearing ball wear",
            root_cause="Bearing failure",
            recommended_action="Replace 608ZZ bearings",
            created_at=_now_iso(),
        ),
        expected_version=1,
        actor_name="Murugan",
    )

    job = store.get_job("job_adv_001", workspace_id="ws_adv_test")
    assert job is not None
    details = store.get_job_details("job_adv_001", workspace_id="ws_adv_test")

    # Generate advice
    advice = await engine.generate_advice(
        workspace_id="ws_adv_test",
        job=job,
        operation="parts",
        expected_version=job.version,
        job_details=details,
    )

    assert advice.job_id == "job_adv_001"
    assert advice.source_version == 2
    assert advice.operation == "parts"
    assert "bearing" in advice.summary.lower()
    assert len(advice.suggested_parts) == 1
    suggested = advice.suggested_parts[0]
    assert suggested.part_id == "FAN-BRG-608ZZ"
    assert suggested.part_name == "Deep Groove Ball Bearing 608ZZ"
    assert suggested.unit_cost_inr == 120.0
    assert suggested.availability == "Sample / Unverified"

    # Truthful provenance
    prov = advice.provenance
    assert prov.engine == "strands"
    assert prov.provider == "offline_transport_test"
    assert prov.model == GROQ_MODEL_ID
    assert prov.actual_tools == 1
    assert prov.actual_sends >= 2


@pytest.mark.anyio
async def test_strands_advisory_redacts_pii(temp_db_path: str) -> None:
    """Verify that customer phone, address, and identity are redacted before inference."""
    captured_requests: list[dict[str, Any]] = []
    mock_transport = _make_mock_transport(captured_requests=captured_requests)
    admission_store = InferenceAdmissionStore(temp_db_path)
    engine = StrandsAdvisoryEngine(
        admission_store=admission_store,
        api_key=DUMMY_KEY,
        transport=mock_transport,
    )

    app = create_app(db_path=temp_db_path)
    store = app.state.store
    from benchbook.domain.models import Job, JobState, TechnicianNote
    from benchbook.infrastructure.sqlite_store import _now_iso

    job = Job(
        job_id="job_pii_001",
        workspace_id="ws_pii",
        job_number="BB-2026-PII01",
        customer_name="Confidential VIP Customer",
        customer_phone="9876543210",
        customer_address="123 Secret Palace Road, Coimbatore",
        device_kind="Mixer Grinder",
        brand_model="Preethi Zodiac",
        intake_symptoms="Overload trip",
        physical_condition="Good",
        current_state=JobState.INTAKE,
        version=1,
        created_at=_now_iso(),
        updated_at=_now_iso(),
    )
    store.create_job(job)
    store.add_technician_note(
        TechnicianNote(
            note_id="note_pii_001",
            job_id="job_pii_001",
            technician_name="Murugan",
            diagnosis_findings="Coupler damaged",
            root_cause="Worn teeth",
            recommended_action="Replace coupler",
            created_at=_now_iso(),
        ),
        expected_version=1,
        actor_name="Murugan",
    )

    job = store.get_job("job_pii_001", workspace_id="ws_pii")
    assert job is not None
    details = store.get_job_details("job_pii_001", workspace_id="ws_pii")

    await engine.generate_advice(
        workspace_id="ws_pii",
        job=job,
        operation="parts",
        expected_version=job.version,
        job_details=details,
    )

    # Inspect all wire requests sent to the model transport
    all_wire_text = json.dumps(captured_requests)
    assert "9876543210" not in all_wire_text, "Customer phone leaked across wire!"
    assert "123 Secret Palace Road" not in all_wire_text, "Customer address leaked across wire!"
    assert "Confidential VIP Customer" not in all_wire_text, "Customer raw name leaked across wire!"


@pytest.mark.anyio
async def test_strands_advisory_rejects_ungrounded_parts(temp_db_path: str) -> None:
    """Verify model-invented part IDs not in PARTS_CATALOGUE are rejected."""
    invented_parts_content = {
        "summary": "Replace components.",
        "part_ids": ["FAN-BRG-608ZZ", "FABRICATED-PART-XYZ-999", "FANTASTIC-TURBO-CHARGER"],
        "part_reasons": ["Valid bearing", "Made up by model", "Fake"],
        "draft_notes": "Notes",
    }
    mock_transport = _make_mock_transport(extracted_content=invented_parts_content)
    admission_store = InferenceAdmissionStore(temp_db_path)
    engine = StrandsAdvisoryEngine(
        admission_store=admission_store,
        api_key=DUMMY_KEY,
        transport=mock_transport,
    )

    app = create_app(db_path=temp_db_path)
    store = app.state.store
    from benchbook.domain.models import Job, JobState, TechnicianNote
    from benchbook.infrastructure.sqlite_store import _now_iso

    job = Job(
        job_id="job_ground_001",
        workspace_id="ws_ground",
        job_number="BB-2026-GR01",
        customer_name="User",
        customer_phone="9840112233",
        device_kind="BLDC Ceiling Fan",
        brand_model="Atomberg",
        intake_symptoms="Noise",
        physical_condition="Good",
        current_state=JobState.INTAKE,
        version=1,
        created_at=_now_iso(),
        updated_at=_now_iso(),
    )
    store.create_job(job)
    store.add_technician_note(
        TechnicianNote(
            note_id="n_gr",
            job_id="job_ground_001",
            technician_name="Murugan",
            diagnosis_findings="Bearing dry",
            root_cause="Wear",
            recommended_action="Replace",
            created_at=_now_iso(),
        ),
        expected_version=1,
        actor_name="Murugan",
    )
    job = store.get_job("job_ground_001", workspace_id="ws_ground")
    assert job is not None
    details = store.get_job_details("job_ground_001", workspace_id="ws_ground")

    with pytest.raises(AssistantInvalidOutputError) as exc_info:
        await engine.generate_advice(
            workspace_id="ws_ground",
            job=job,
            operation="parts",
            expected_version=job.version,
            job_details=details,
        )
    assert (
        "ungrounded" in str(exc_info.value).lower()
        or "not in regional catalogue" in str(exc_info.value).lower()
    )


@pytest.mark.anyio
async def test_strands_advisory_rejects_mismatched_reasons(temp_db_path: str) -> None:
    """Verify model output with mismatched part IDs and reasons count is rejected."""
    mismatched_content = {
        "summary": "Mismatched reasons test.",
        "part_ids": ["FAN-BRG-608ZZ"],
        "part_reasons": ["Reason 1", "Extra unexpected reason 2"],
        "draft_notes": "Notes",
    }
    mock_transport = _make_mock_transport(extracted_content=mismatched_content)
    admission_store = InferenceAdmissionStore(temp_db_path)
    engine = StrandsAdvisoryEngine(
        admission_store=admission_store,
        api_key=DUMMY_KEY,
        transport=mock_transport,
    )

    app = create_app(db_path=temp_db_path)
    store = app.state.store
    from benchbook.domain.models import Job, JobState
    from benchbook.infrastructure.sqlite_store import _now_iso

    job = Job(
        job_id="job_mismatch_001",
        workspace_id="ws_mismatch",
        job_number="BB-2026-MM01",
        customer_name="Mismatch Tester",
        customer_phone="9840112233",
        device_kind="BLDC Ceiling Fan",
        brand_model="Atomberg",
        intake_symptoms="Noise",
        physical_condition="Good",
        current_state=JobState.INTAKE,
        version=1,
        created_at=_now_iso(),
        updated_at=_now_iso(),
    )
    store.create_job(job)

    with pytest.raises(AssistantInvalidOutputError) as exc_info:
        await engine.generate_advice(
            workspace_id="ws_mismatch",
            job=job,
            operation="parts",
            expected_version=job.version,
        )
    assert "mismatched" in str(exc_info.value).lower()


@pytest.mark.anyio
async def test_strands_advisory_idempotent_replay_no_extra_sends(temp_db_path: str) -> None:
    """Replay under same idempotency key returns exact cached response with 0 extra model sends."""
    send_counter = [0]

    async def counting_handler(request: httpx.Request) -> httpx.Response:
        send_counter[0] += 1
        body = json.loads(request.content.decode("utf-8"))
        if "response_format" in body:
            return httpx.Response(
                200,
                json=_make_parsed_response({"summary": "Ok", "part_ids": [], "part_reasons": []}),
            )
        if send_counter[0] == 1:
            return httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                text=_make_sse_tool_call("read_repair_context", {}),
            )
        return httpx.Response(
            200, headers={"content-type": "text/event-stream"}, text=_make_sse_text_response("Done")
        )

    mock_transport = httpx.MockTransport(counting_handler)
    admission_store = InferenceAdmissionStore(temp_db_path)
    engine = StrandsAdvisoryEngine(
        admission_store=admission_store,
        api_key=DUMMY_KEY,
        transport=mock_transport,
    )

    app = create_app(db_path=temp_db_path)
    store = app.state.store
    from benchbook.domain.models import Job, JobState, TechnicianNote
    from benchbook.infrastructure.sqlite_store import _now_iso

    job = Job(
        job_id="job_replay_001",
        workspace_id="ws_rep",
        job_number="BB-2026-REP",
        customer_name="User",
        customer_phone="9840112233",
        device_kind="Fan",
        brand_model="Atomberg",
        intake_symptoms="Hum",
        physical_condition="Good",
        current_state=JobState.INTAKE,
        version=1,
        created_at=_now_iso(),
        updated_at=_now_iso(),
    )
    store.create_job(job)
    store.add_technician_note(
        TechnicianNote(
            note_id="n_rep",
            job_id="job_replay_001",
            technician_name="Murugan",
            diagnosis_findings="Checked",
            root_cause="None",
            recommended_action="None",
            created_at=_now_iso(),
        ),
        expected_version=1,
        actor_name="Murugan",
    )
    job = store.get_job("job_replay_001", workspace_id="ws_rep")
    assert job is not None
    details = store.get_job_details("job_replay_001", workspace_id="ws_rep")

    # Call 1
    resp1 = await engine.generate_advice(
        workspace_id="ws_rep",
        job=job,
        operation="parts",
        expected_version=job.version,
        idempotency_key="exact-replay-key-001",
        job_details=details,
    )
    sends_after_first = send_counter[0]
    assert sends_after_first >= 2

    # Call 2 (exact replay with same key and payload)
    resp2 = await engine.generate_advice(
        workspace_id="ws_rep",
        job=job,
        operation="parts",
        expected_version=job.version,
        idempotency_key="exact-replay-key-001",
        job_details=details,
    )

    # Sends must NOT have increased
    assert send_counter[0] == sends_after_first
    assert resp1.summary == resp2.summary
    assert resp1.suggested_parts == resp2.suggested_parts


def test_stale_job_version_after_inference_409(temp_db_path: str) -> None:
    """If job version was modified during inference, returns 409 STATE_CONFLICT."""
    app = create_app(db_path=temp_db_path)
    with TestClient(app) as client:
        client.post("/api/session")
        c_resp = client.post(
            "/api/jobs",
            json={
                "customer_name": "Test User",
                "customer_phone": "9840123456",
                "device_kind": "Mixer Grinder",
                "brand_model": "Preethi",
                "intake_symptoms": "Trip",
            },
        )
        assert c_resp.status_code == 201
        job_id = c_resp.json()["job"]["job_id"]

        # Add diagnosis note (bumps version to 2)
        client.post(
            f"/api/jobs/{job_id}/technician-note",
            json={
                "expected_version": 1,
                "technician_name": "Murugan",
                "diagnosis_findings": "Worn carbon",
                "root_cause": "Carbon brush wear",
                "recommended_action": "Replace carbon brush",
            },
        )

        # Attempt advice with stale expected_version=1 -> 409
        resp = client.post(
            f"/api/jobs/{job_id}/advice",
            json={"operation": "parts", "expected_version": 1},
        )
        assert resp.status_code == 409
        err = resp.json()
        assert err["error"] == "STATE_CONFLICT"
        assert err["details"]["expected_version"] == 1
        assert err["details"]["current_version"] == 2


@pytest.mark.anyio
async def test_strands_advisory_send_budget_exhaustion(temp_db_path: str) -> None:
    """When sends exceed the strict max sends limit (6), raises AssistantBusyError."""
    # Always return a tool call so the agent loops and exhausts send budget
    infinite_tool_sse = _make_sse_tool_call("read_repair_context", {})

    async def infinite_tool_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, headers={"content-type": "text/event-stream"}, text=infinite_tool_sse
        )

    mock_transport = httpx.MockTransport(infinite_tool_handler)
    admission_store = InferenceAdmissionStore(temp_db_path)
    engine = StrandsAdvisoryEngine(
        admission_store=admission_store,
        api_key=DUMMY_KEY,
        transport=mock_transport,
    )

    app = create_app(db_path=temp_db_path)
    store = app.state.store
    from benchbook.domain.models import Job, JobState
    from benchbook.infrastructure.sqlite_store import _now_iso

    job = Job(
        job_id="job_budget_001",
        workspace_id="ws_budget",
        job_number="BB-2026-BDG01",
        customer_name="Budget Tester",
        customer_phone="9840123456",
        customer_address="Coimbatore",
        device_kind="Mixer Grinder",
        brand_model="Preethi",
        intake_symptoms="Smoke",
        physical_condition="Fair",
        current_state=JobState.INTAKE,
        version=1,
        created_at=_now_iso(),
        updated_at=_now_iso(),
    )
    store.create_job(job)

    with pytest.raises(AssistantBusyError) as exc_info:
        await engine.generate_advice(
            workspace_id="ws_budget",
            job=job,
            operation="parts",
            expected_version=1,
        )
    assert (
        "budget" in str(exc_info.value).lower()
        or "limit" in str(exc_info.value).lower()
        or "busy" in str(exc_info.value).lower()
    )


@pytest.mark.anyio
async def test_strands_advisory_provider_429_busy(temp_db_path: str) -> None:
    """When provider returns HTTP 429 rate limit, maps to AssistantBusyError."""

    async def rate_limit_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            headers={"retry-after": "10"},
            json={"error": {"message": "Rate limit reached", "type": "tokens"}},
        )

    mock_transport = httpx.MockTransport(rate_limit_handler)
    admission_store = InferenceAdmissionStore(temp_db_path)
    engine = StrandsAdvisoryEngine(
        admission_store=admission_store,
        api_key=DUMMY_KEY,
        transport=mock_transport,
    )

    app = create_app(db_path=temp_db_path)
    store = app.state.store
    from benchbook.domain.models import Job, JobState
    from benchbook.infrastructure.sqlite_store import _now_iso

    job = Job(
        job_id="job_429_001",
        workspace_id="ws_429",
        job_number="BB-2026-42901",
        customer_name="Rate Limit Tester",
        customer_phone="9840123456",
        customer_address="Coimbatore",
        device_kind="Mixer Grinder",
        brand_model="Preethi",
        intake_symptoms="Overheat",
        physical_condition="Fair",
        current_state=JobState.INTAKE,
        version=1,
        created_at=_now_iso(),
        updated_at=_now_iso(),
    )
    store.create_job(job)

    with pytest.raises(AssistantBusyError) as exc_info:
        await engine.generate_advice(
            workspace_id="ws_429",
            job=job,
            operation="parts",
            expected_version=1,
        )
    assert "429" in str(exc_info.value) or "rate limit" in str(exc_info.value).lower()


@pytest.mark.anyio
async def test_strands_advisory_connection_failure_unavailable(temp_db_path: str) -> None:
    """When transport fails to connect to provider, maps to AssistantUnavailableError (503)."""

    async def connect_fail_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection refused by provider host")

    mock_transport = httpx.MockTransport(connect_fail_handler)
    admission_store = InferenceAdmissionStore(temp_db_path)
    engine = StrandsAdvisoryEngine(
        admission_store=admission_store,
        api_key=DUMMY_KEY,
        transport=mock_transport,
    )

    app = create_app(db_path=temp_db_path)
    store = app.state.store
    from benchbook.domain.models import Job, JobState
    from benchbook.infrastructure.sqlite_store import _now_iso

    job = Job(
        job_id="job_conn_001",
        workspace_id="ws_conn",
        job_number="BB-2026-CON01",
        customer_name="Conn Tester",
        customer_phone="9840123456",
        customer_address="Coimbatore",
        device_kind="Mixer Grinder",
        brand_model="Preethi",
        intake_symptoms="Trip",
        physical_condition="Fair",
        current_state=JobState.INTAKE,
        version=1,
        created_at=_now_iso(),
        updated_at=_now_iso(),
    )
    store.create_job(job)

    with pytest.raises(AssistantUnavailableError) as exc_info:
        await engine.generate_advice(
            workspace_id="ws_conn",
            job=job,
            operation="parts",
            expected_version=1,
        )
    assert "connection" in str(exc_info.value).lower() or "failed" in str(exc_info.value).lower()


@pytest.mark.anyio
async def test_strands_advisory_no_tool_execution_invalid_output(temp_db_path: str) -> None:
    """When agent hallucinates without calling read_repair_context, maps to AssistantInvalidOutputError."""
    # Return direct text without calling tool
    text_sse = _make_sse_text_response("I know what is wrong without reading the database context.")

    async def no_tool_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, text=text_sse)

    mock_transport = httpx.MockTransport(no_tool_handler)
    admission_store = InferenceAdmissionStore(temp_db_path)
    engine = StrandsAdvisoryEngine(
        admission_store=admission_store,
        api_key=DUMMY_KEY,
        transport=mock_transport,
    )

    app = create_app(db_path=temp_db_path)
    store = app.state.store
    from benchbook.domain.models import Job, JobState
    from benchbook.infrastructure.sqlite_store import _now_iso

    job = Job(
        job_id="job_notool_001",
        workspace_id="ws_notool",
        job_number="BB-2026-NT01",
        customer_name="NoTool Tester",
        customer_phone="9840123456",
        customer_address="Coimbatore",
        device_kind="Mixer Grinder",
        brand_model="Preethi",
        intake_symptoms="Hum",
        physical_condition="Fair",
        current_state=JobState.INTAKE,
        version=1,
        created_at=_now_iso(),
        updated_at=_now_iso(),
    )
    store.create_job(job)

    with pytest.raises(AssistantInvalidOutputError) as exc_info:
        await engine.generate_advice(
            workspace_id="ws_notool",
            job=job,
            operation="parts",
            expected_version=1,
        )
    assert "read_repair_context" in str(exc_info.value) or "invalid" in str(exc_info.value).lower()


@pytest.mark.anyio
async def test_strands_advisory_live_mode_missing_api_key(temp_db_path: str) -> None:
    """When mode is live and GROQ_API_KEY is missing, raises AssistantUnavailableError."""
    admission_store = InferenceAdmissionStore(temp_db_path)
    engine = StrandsAdvisoryEngine(
        admission_store=admission_store,
        api_key="",  # Missing API key
        transport=None,  # No offline transport
        mode="live",
    )

    app = create_app(db_path=temp_db_path)
    store = app.state.store
    from benchbook.domain.models import Job, JobState
    from benchbook.infrastructure.sqlite_store import _now_iso

    job = Job(
        job_id="job_nokey_001",
        workspace_id="ws_nokey",
        job_number="BB-2026-NK01",
        customer_name="NoKey Tester",
        customer_phone="9840123456",
        customer_address="Coimbatore",
        device_kind="Mixer Grinder",
        brand_model="Preethi",
        intake_symptoms="Hum",
        physical_condition="Fair",
        current_state=JobState.INTAKE,
        version=1,
        created_at=_now_iso(),
        updated_at=_now_iso(),
    )
    store.create_job(job)

    with pytest.raises(AssistantUnavailableError) as exc_info:
        await engine.generate_advice(
            workspace_id="ws_nokey",
            job=job,
            operation="parts",
            expected_version=1,
        )
    assert "GROQ_API_KEY" in str(exc_info.value)


@pytest.mark.anyio
async def test_strands_advisory_deadline_timeout(temp_db_path: str) -> None:
    """When transport exceeds deadline, maps to AssistantTimeoutError."""

    async def slow_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("Request timed out waiting for provider response")

    mock_transport = httpx.MockTransport(slow_handler)
    admission_store = InferenceAdmissionStore(temp_db_path)
    engine = StrandsAdvisoryEngine(
        admission_store=admission_store,
        api_key=DUMMY_KEY,
        transport=mock_transport,
    )

    app = create_app(db_path=temp_db_path)
    store = app.state.store
    from benchbook.domain.models import Job, JobState
    from benchbook.infrastructure.sqlite_store import _now_iso

    job = Job(
        job_id="job_slow_001",
        workspace_id="ws_slow",
        job_number="BB-2026-SLW01",
        customer_name="Slow Tester",
        customer_phone="9840123456",
        customer_address="Coimbatore",
        device_kind="Mixer Grinder",
        brand_model="Preethi",
        intake_symptoms="Smoke",
        physical_condition="Fair",
        current_state=JobState.INTAKE,
        version=1,
        created_at=_now_iso(),
        updated_at=_now_iso(),
    )
    store.create_job(job)

    with pytest.raises(AssistantTimeoutError) as exc_info:
        await engine.generate_advice(
            workspace_id="ws_slow",
            job=job,
            operation="parts",
            expected_version=1,
        )
    assert (
        "deadline" in str(exc_info.value).lower()
        or "timeout" in str(exc_info.value).lower()
        or "expired" in str(exc_info.value).lower()
    )
