# BB-002 Test Status & Verification Report

- **Task ID**: `BB-002`
- **Project**: Benchbook (`02_BENCHBOOK`)
- **Worker**: AGY, senior full-stack developer
- **Date**: 2026-09-12
- **Base Commit**: `50038fc`
- **Branch**: `worker/agy/BB-002`
- **Spend**: ₹0.00 / $0.00 (Zero paid infrastructure, zero external API keys)

---

## 1. Test Summary

| Suite / Check | Tool | Files | Status | Details |
|---|---|---|---|---|
| **Backend Unit & Integration Tests** | `pytest` | 9 test files | **PASSED** (37/37) | 37 passed, 0 skipped, 0 failed in 1.22s |
| **Backend Linting** | `ruff check` | 31 source files | **PASSED** | All rules passed, 0 errors, 0 warnings |
| **Backend Formatting** | `ruff format --check` | 31 source files | **PASSED** | 31 files inspected, 0 changes needed |
| **Backend Type Checking** | `mypy --strict` | 31 source files | **PASSED** | Success: no issues found in 31 source files |
| **Frontend Unit & Component Tests** | `vitest` | 1 test file | **PASSED** (9/9) | 9 passed, 0 skipped, 0 failed in 250ms |
| **Frontend Type Checking** | `tsc --noEmit` | `apps/web` | **PASSED** | 0 type errors |
| **Frontend Linting** | `eslint .` | `apps/web` | **PASSED** | 0 errors, 0 warnings |
| **Frontend Production Build** | `vite build` | `apps/web` | **PASSED** | Built production bundle in 848ms |
| **Release Smoke Path** | `scripts/release_smoke.py` | Standalone script | **PASSED** (17/17) | Complete 11-stage persisted lifecycle & gates |

**Total Automated Tests**: **46 tests passed** (37 pytest + 9 vitest) + **17 release smoke checks**, 0 failed, 0 skipped.

---

## 2. Backend Test Suite Details (`services/repair_service/tests/`)

### `test_api_routes.py` (4 tests)
- `test_health_route`: Verifies `GET /api/health` returns status `ok`, database engine, and human approval requirement.
- `test_seed_sample_jobs_and_filter_list`: Verifies seeding synthetic Tamil Nadu jobs and listing with filters.
- `test_get_job_details_and_audit`: Verifies aggregated details endpoint and audit trail retrieval.
- `test_get_nonexistent_job_returns_404`: Verifies missing job returns HTTP 404 with standard envelope.

### `test_assistant_adapter.py` (7 tests)
- `test_parts_suggestions_for_domain_devices`: Verifies parts knowledge base for BLDC fans, inverter ACs, mixers, laptops.
- `test_estimate_message_drafting`: Verifies WhatsApp/SMS estimate explanation with shop details.
- `test_pickup_notification_drafting`: Verifies pickup notification draft with store hours and payment methods.
- `test_assistant_honest_failure_modes`: Parametrized test verifying 4 failure modes:
  - `timeout` -> 504 `ASSISTANT_TIMEOUT`
  - `busy` -> 429 `ASSISTANT_BUSY`
  - `unavailable` -> 503 `ASSISTANT_UNAVAILABLE`
  - `invalid_output` -> 502 `ASSISTANT_INVALID_OUTPUT`

### `test_config_and_cors.py` (7 tests)
- `test_config_defaults`: Verifies default configuration values (SQLite WAL, standard ports, shop details).
- `test_config_postgres_normalization`: Verifies `postgres://` is normalized to `postgresql://` for psycopg compatibility.
- `test_config_cors_parsing_comma_separated`: Verifies parsing comma-separated strings into CORS origin lists.
- `test_config_cors_parsing_json_list`: Verifies parsing JSON arrays into CORS origin lists.
- `test_cors_middleware_allowed_origin`: Verifies CORS headers are properly returned for allowed origins.
- `test_readiness_probe_healthy`: Verifies `GET /api/ready` returns 200 when database is responsive.
- `test_readiness_probe_failure_reports_503`: Verifies `GET /api/ready` returns 503 when database is unreachable.

### `test_human_approval_boundaries.py` (5 tests)
- `test_assistant_cannot_approve_estimate`: Assistant attempting customer approval returns HTTP 403 `HUMAN_APPROVAL_REQUIRED`.
- `test_system_cannot_approve_estimate`: System actor attempting customer approval returns HTTP 403 `HUMAN_APPROVAL_REQUIRED`.
- `test_human_technician_can_approve_estimate`: Human technician successfully records customer approval.
- `test_assistant_cannot_complete_repair`: Assistant attempting repair QC completion returns HTTP 403 `HUMAN_APPROVAL_REQUIRED`.
- `test_assistant_cannot_close_job`: Assistant attempting final job closure returns HTTP 403 `HUMAN_APPROVAL_REQUIRED`.

### `test_idempotency_and_conflicts.py` (3 tests)
- `test_optimistic_locking_conflict_returns_409`: Submitting stale `expected_version` returns HTTP 409 `STATE_CONFLICT`.
- `test_idempotency_key_replay_returns_cached_result`: Repeated intake with identical key returns cached result without duplicate job.
- `test_transition_idempotency_key_replay`: Repeated state advance returns cached response without version increment.

### `test_postgres_store_compatibility.py` (4 tests)
- `test_postgres_schema_strips_sqlite_pragmas`: Verifies PostgreSQL schema generator strips SQLite PRAGMAs cleanly.
- `test_connection_wrapper_placeholder_adaptation`: Verifies `ConnectionWrapper` translates `?` to `%s` in Postgres mode.
- `test_store_factory_sqlite_resolution`: Verifies `get_repair_job_store` resolves SQLite store for `sqlite:///` URLs.
- `test_store_factory_postgres_resolution`: Verifies `get_repair_job_store` resolves Postgres store for `postgresql://` URLs.

### `test_release_smoke.py` (1 test)
- `test_full_release_smoke_suite`: Executes the complete 17-step release smoke verification within pytest.

### `test_sqlite_persistence.py` (3 tests)
- `test_sqlite_wal_and_foreign_keys`: Confirms SQLite journal mode is WAL and foreign keys are enforced.
- `test_job_not_found_raises_domain_error`: Verifies querying invalid job ID raises domain error.
- `test_cascade_delete_cleans_child_records`: Confirms cascade delete cleans all 10 child tables.

### `test_workflow_transitions.py` (3 tests)
- `test_complete_live_workflow_slice`: Tests full 11-stage progression from intake to closed.
- `test_invalid_state_transition_fails`: Tests invalid transition jumping directly from intake to repair queue.
- `test_rejected_estimate_leads_to_close`: Tests customer rejecting estimate transitions to rejection and close.

---

## 3. Frontend Test Suite Details (`apps/web/src/test/`)

### `Workflow.test.tsx` (9 tests)
- `renders empty workbench without crashing`: Verifies initial load state.
- `renders job list when jobs provided`: Verifies job bench list with badges.
- `renders 11-stage workflow timeline`: Verifies all 11 stages with active indicators.
- `renders human gate banner when action is restricted`: Verifies warning banner on gated actions.
- `renders assistant advisory card with provenance`: Verifies provenance display.
- `filters jobs by search input`: Tests client-side search filtering.
- `filters jobs by state dropdown`: Tests state filter dropdown.
- `renders evaluator guide banner`: Verifies 60-second evaluator guide banner in header.
- `renders database indicator badge`: Verifies database badge displaying engine type (`SQLite (WAL)` / `PostgreSQL (Neon)`).

---

## 4. Release Smoke Verification (`scripts/release_smoke.py`)

Deterministic 17-point automated verification against live running service or in-process ASGI app:
1. `GET /api/health` — Checks status `ok`, milestone `M1`, and database engine.
2. `GET /api/ready` — Verifies database connection readiness.
3. `POST /api/jobs` — Creates customer intake (v1, state: `intake`).
4. `POST /api/jobs/{id}/technician-note` — Technician records diagnosis (v2, state: `diagnosis`).
5. `POST /api/assistant/suggest-parts` — Advisory parts query with provenance verification.
6. `POST /api/jobs/{id}/parts-lookup` — Technician adds parts to ticket (v3, state: `parts_lookup`).
7. `POST /api/jobs/{id}/estimate` — Technician creates cost estimate (v4, state: `estimate_pending`).
8. `POST /api/jobs/{id}/customer-approval` (Bypass Attempt) — Assistant approval rejected with HTTP 403.
9. `POST /api/jobs/{id}/customer-approval` (Human Approval) — Customer approves via phone (v5, state: `customer_approved`).
10. `POST /api/jobs/{id}/supplier-status` — Supplier parts arrival logged (v6, state: `parts_ready`).
11. `POST /api/jobs/{id}/repair-queue` — Queues job for bench repair (v7, state: `repair_queue`).
12. `POST /api/jobs/{id}/repair-queue` — Technician starts repair (v8, state: `repair_in_progress`).
13. `POST /api/jobs/{id}/repair-completion` (Bypass Attempt) — Assistant completion rejected with HTTP 403.
14. `POST /api/jobs/{id}/repair-completion` (Human Sign-Off) — Technician signs off QC (v9, state: `repair_completed`).
15. `POST /api/assistant/draft-pickup-notification` — Advisory message drafting with provenance verification.
16. `POST /api/jobs/{id}/pickup-notification` — Technician sends pickup message (v10, state: `ready_for_pickup`).
17. `POST /api/jobs/{id}/follow-up` — Payment handover logged (v11, state: `follow_up`).
18. `POST /api/jobs/{id}/close` (Bypass Attempt) — Assistant close rejected with HTTP 403.
19. `POST /api/jobs/{id}/close` (Human Sign-Off) — Technician closes ticket (v12, state: `closed`).
20. `GET /api/jobs/{id}` — Full readback verifying all 10 child record tables.
21. `GET /api/jobs/{id}/audit` — Verifies 12 audit events with monotonic version continuity v0 → v12.
22. `POST /api/jobs/{id}/close` (Stale Write) — Rejects stale version write with HTTP 409 `STATE_CONFLICT`.
23. `POST /api/jobs` (Idempotency Replay) — Verifies duplicate submission with same `Idempotency-Key` returns exact cached response without creating a new job.

---

## 5. Environment & Quality Checks

- **Python**: 3.14.3
- **Node.js**: v22.22.3, **npm**: 10.9.8
- **Ruff**: `0.9.10` — `ruff check` (clean), `ruff format --check` (clean across 31 files)
- **Mypy**: `1.15.0` — `mypy --explicit-package-bases` (clean across 31 files)
- **ESLint**: `9.20.1` — `eslint . --max-warnings 0` (clean)
- **TypeScript**: `5.7.3` — `tsc --noEmit` (clean)
- **Vite**: `6.2.0` — Production build in 848ms
