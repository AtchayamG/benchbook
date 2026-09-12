# Benchbook REST API Contract Specification

## 1. Overview

- **Base Path**: `/api`
- **Content-Type**: `application/json`
- **Supported Headers**:
  - `Idempotency-Key` (optional string): Used for safe retry and deduplication.
- **Error Response Envelope**:
  ```json
  {
    "error": "STRING_CODE",
    "message": "Human-readable description of error.",
    "details": {}
  }
  ```

### HTTP Status Code Semantics
- `200 OK`: Request succeeded.
- `201 Created`: Resource successfully registered.
- `400 Bad Request`: `INVALID_STATE_TRANSITION` — illegal transition on lifecycle graph.
- `403 Forbidden`: `HUMAN_APPROVAL_REQUIRED` — automated assistant or system actor attempted a human-only action.
- `404 Not Found`: `JOB_NOT_FOUND` — job ID does not exist.
- `409 Conflict`:
  - `STATE_CONFLICT` — optimistic lock failed; `expected_version` did not match database version.
  - `IDEMPOTENCY_CONFLICT` — `Idempotency-Key` was previously used with a different request payload or different operation scope.
- `422 Unprocessable Entity`: `VALIDATION_ERROR` — missing required payload fields, malformed body, or disagreement between `Idempotency-Key` HTTP header and payload `idempotency_key`.
- `429 Too Many Requests`: `ASSISTANT_BUSY` — assistant capacity limit reached.
- `502 Bad Gateway`: `ASSISTANT_INVALID_OUTPUT` — ungrounded or unparseable assistant response.
- `503 Service Unavailable`: `ASSISTANT_UNAVAILABLE` — assistant service offline or unreachable, or database disconnected on `/api/ready`.
- `504 Gateway Timeout`: `ASSISTANT_TIMEOUT` — assistant deadline exceeded.

### Idempotency Contract & Guarantees
- **Header & Body Agreement**: An idempotency key can be supplied via the `Idempotency-Key` HTTP header, in the JSON request body as `idempotency_key`, or both. If supplied in both places, their values MUST match exactly; disagreement returns HTTP 422 `VALIDATION_ERROR`.
- **Canonical Payload Hashing**: The request payload (excluding the idempotency key itself) is serialized canonically with sorted keys and hashed via SHA-256 (`payload_hash`).
- **Atomic Mutation & Replay**: The idempotency record, job version mutation, and immutable audit event are committed in a single atomic transaction.
- **Identical Key + Identical Payload**: Safely replays the committed response payload and HTTP status code without duplicate writes or version bumps.
- **Identical Key + Different Payload / Scope**: Immediately rejects the conflicting mutation with HTTP 409 `IDEMPOTENCY_CONFLICT` without modifying existing records or leaking prior response payloads.
- **Persistence**: Idempotency records are durably persisted in `idempotency_records` table across database reboots on both SQLite (WAL) and PostgreSQL 16.10.

---

## 2. Health Endpoint

### `GET /api/health`
Returns health status, shop details, and assistant operating mode.

**Response 200**:
```json
{
  "status": "ok",
  "app": "Benchbook",
  "version": "0.1.0",
  "milestone": "M1",
  "shop": {
    "name": "Kovai Tech Bench",
    "location": "Gandhipuram, Coimbatore, Tamil Nadu",
    "phone": "+91 98400 11223"
  },
  "assistant": {
    "mode": "deterministic",
    "role": "advisory_only",
    "human_approval_required": true
  }
}
```

---

## 3. Jobs Management Endpoints

### `POST /api/jobs`
Creates a new intake job.

**Request Body**:
```json
{
  "customer_name": "Senthil Nathan",
  "customer_phone": "+91 98401 23456",
  "customer_address": "Gandhipuram, Coimbatore",
  "device_kind": "BLDC Ceiling Fan",
  "brand_model": "Atomberg Renesa 1200mm",
  "serial_number": "ATMB-2024-88419",
  "intake_symptoms": "Motor humming loudly at speed 2, erratic speed transitions.",
  "physical_condition": "Good condition, remote included.",
  "accessories_received": ["Remote Control", "Shackle Kit"],
  "promised_date": "2026-09-15",
  "assigned_technician": "Murugan R."
}
```
**Response 201**: Returns `{"job": Job}`.

### `GET /api/jobs`
Lists jobs with optional state filtering (`?state=intake`, `?state=repair_in_progress`, etc.).

### `GET /api/jobs/{job_id}`
Returns full aggregated job details, notes, parts, estimates, approvals, completions, and audit trail.

### `GET /api/jobs/{job_id}/audit`
Returns immutable audit events for this job.

### `POST /api/jobs/seed`
Populates the database with 4 realistic Tamil Nadu electronics/appliance repair preset jobs.

---

## 4. Workflow Transition Endpoints

All transition endpoints require:
- Path parameter: `job_id: string`
- Body parameter: `expected_version: int`
- Optional Header: `Idempotency-Key: string`

### `POST /api/jobs/{job_id}/technician-note`
Transitions state to `diagnosis`.
```json
{
  "expected_version": 1,
  "technician_name": "Murugan R.",
  "diagnosis_findings": "Phase B gate driver FET damaged.",
  "root_cause": "Failed FD6288Q gate driver IC.",
  "recommended_action": "Replace IC.",
  "test_measurements": {"dc_bus_volts": 318.0}
}
```

### `POST /api/jobs/{job_id}/parts-lookup`
Transitions state to `parts_lookup`.
```json
{
  "expected_version": 2,
  "parts": [
    {
      "part_name": "BLDC Motor Driver Controller IC",
      "part_number": "FD6288Q",
      "supplier_name": "Supreme Electronics Spares",
      "unit_cost_inr": 280.0,
      "quantity": 1,
      "availability_status": "in_stock",
      "suggested_by": "technician"
    }
  ],
  "actor_name": "Murugan R."
}
```

### `POST /api/jobs/{job_id}/estimate`
Transitions state to `estimate_pending`.
```json
{
  "expected_version": 3,
  "labor_charge_inr": 450.0,
  "parts_total_inr": 280.0,
  "tax_inr": 131.40,
  "total_amount_inr": 861.40,
  "promised_delivery_date": "2026-09-15",
  "notes": "Includes 2-hour burn-in",
  "created_by": "Murugan R."
}
```

### `POST /api/jobs/{job_id}/customer-approval` (HUMAN GATE)
Transitions state to `customer_approved` or `estimate_rejected`.
- **Constraint**: `actor_type` must NOT be `"assistant"` or `"system"`.
```json
{
  "expected_version": 4,
  "approved": true,
  "approved_by": "Senthil Nathan",
  "recorded_by_technician": "Murugan R.",
  "channel": "phone",
  "approval_notes": "Customer confirmed estimate on phone.",
  "agreed_amount_inr": 861.40,
  "actor_type": "technician"
}
```

### `POST /api/jobs/{job_id}/supplier-status`
Transitions state to `parts_ready` (if delivered/in_stock) or `supplier_ordered`.
```json
{
  "expected_version": 5,
  "supplier_name": "Supreme Electronics Spares",
  "order_reference": "SES-041",
  "parts_status": "in_stock",
  "expected_arrival_date": "2026-09-14",
  "tracking_notes": "Counter pickup",
  "actor_name": "Murugan R."
}
```

### `POST /api/jobs/{job_id}/repair-queue`
Transitions state to `repair_queue` or `repair_in_progress`.
```json
{
  "expected_version": 6,
  "target_state": "repair_queue",
  "actor_name": "Murugan R."
}
```

### `POST /api/jobs/{job_id}/repair-completion` (HUMAN GATE)
Transitions state to `repair_completed`.
- **Constraint**: `actor_type` must NOT be `"assistant"` or `"system"`.
- **Constraint**: `technician_signature_confirmed` must be `true`.
```json
{
  "expected_version": 8,
  "technician_name": "Murugan R.",
  "actions_taken": "Replaced IC and cleaned PCB.",
  "parts_replaced": ["FD6288Q IC"],
  "qc_tests_passed": ["Phase balance pass", "Speed step 1-5 pass"],
  "burn_in_duration_minutes": 120,
  "technician_signature_confirmed": true,
  "actor_type": "technician"
}
```

### `POST /api/jobs/{job_id}/pickup-notification`
Transitions state to `ready_for_pickup`.
```json
{
  "expected_version": 9,
  "channel": "whatsapp",
  "recipient_phone": "+91 98401 23456",
  "message_text": "Your device is ready for pickup!",
  "sent_by_technician": "Murugan R."
}
```

### `POST /api/jobs/{job_id}/follow-up`
Transitions state to `follow_up`.
```json
{
  "expected_version": 10,
  "amount_paid_inr": 861.40,
  "payment_method": "upi",
  "payment_reference": "UPI/20260914/991823",
  "warranty_days": 30,
  "customer_feedback": "Excellent repair",
  "feedback_rating": 5,
  "recorded_by": "Murugan R."
}
```

### `POST /api/jobs/{job_id}/close` (HUMAN GATE)
Transitions state to `closed`.
- **Constraint**: `actor_type` must NOT be `"assistant"` or `"system"`.
```json
{
  "expected_version": 11,
  "closed_by": "Murugan R.",
  "resolution_summary": "Handed over, paid via UPI, 30 days warranty.",
  "actor_type": "technician"
}
```

---

## 5. Canonical Owned-Job Advisory Endpoint (BB-004)

All AI advisory capabilities are accessed strictly via the owned-job route:
`POST /api/jobs/{job_id}/advice`

The advisory engine operates as an untrusted advisory sub-worker within an atomic SQL admission engine. The assistant **CANNOT** modify job state, approve estimates, sign off completion, or close jobs.

### `POST /api/jobs/{job_id}/advice`
- **Request Headers**:
  - `Cookie: benchbook_session=<32-byte-token>`
  - `Idempotency-Key` (optional string): Used for idempotent replaying of advice.
- **Request Body**:
  ```json
  {
    "operation": "parts",
    "expected_version": 2,
    "idempotency_key": "optional-key"
  }
  ```
- **Supported Operations**:
  - `"parts"`: Recommends grounded replacement spare parts from the verified catalogue based on technician diagnostic findings.
  - `"estimate"` or `"estimate_message"`: Generates customer WhatsApp/SMS estimate draft using deterministic calculation templates and verified DB facts (requires saved estimate).
  - `"pickup"` or `"pickup_message"`: Generates customer pickup ready notification message (requires recorded repair completion).

- **Response 200**:
  ```json
  {
    "job_id": "3e366d25-9817-4a9b-9895-2f3d67671f5c",
    "source_version": 2,
    "operation": "parts",
    "summary": "Motor bearing wear observed. Recommend 608ZZ replacement.",
    "suggested_parts": [
      {
        "part_id": "FAN-BRG-608ZZ",
        "part_name": "Deep Groove Ball Bearing 608ZZ",
        "unit_cost_inr": 120.0,
        "availability": "Sample / Unverified",
        "reason": "Matches vibration and humming symptoms on speed 2."
      }
    ],
    "draft_notes": null,
    "draft_message": null,
    "provenance": {
      "engine": "strands",
      "provider": "groq",
      "model": "openai/gpt-oss-20b",
      "reservation_id": "res_98a72b104c9e",
      "generated_at": "2026-09-12T16:20:00.000Z",
      "actual_sends": 2,
      "actual_tools": 1,
      "latency_ms": 340,
      "advisory_only": true,
      "requires_human_verification": true
    }
  }
  ```

---

## 6. Public Workbench Sessions (BB-004)

Public visitors operate within isolated temporary workspaces (24-hour TTL, 50 jobs max).

### `POST /api/session`
Initializes or resumes a workbench session. Sets `benchbook_session` 32-byte HttpOnly cookie.
- **Response 200**:
  ```json
  {
    "workspace_id": "ws_df49ba1b434787c14c08e3cc",
    "status": "active",
    "created_at": "2026-09-12T16:00:00Z",
    "expires_at": "2026-09-13T16:00:00Z",
    "job_count": 1,
    "max_jobs": 50,
    "active_workspaces": 12,
    "max_workspaces": 1000,
    "is_new": true,
    "authenticated": true
  }
  ```

### `GET /api/session`
Returns current session status, remaining job capacity, and active workspace count.

---

## 7. Retired Endpoints (HTTP 410 Gone)

The following unscoped assistant endpoints were retired in BB-004 and return `HTTP 410 Gone`:
- `POST /api/assistant/suggest-parts`
- `POST /api/assistant/draft-estimate-message`
- `POST /api/assistant/draft-pickup-notification`

**Response 410**:
```json
{
  "error": "ENDPOINT_RETIRED",
  "message": "This assistant endpoint has been retired. Use canonical owned-job advisory route POST /api/jobs/{job_id}/advice.",
  "details": {
    "migration": "POST /api/jobs/{job_id}/advice with payload {'operation': 'parts'|'estimate_message'|'pickup_message', 'expected_version': N}"
  }
}
```
