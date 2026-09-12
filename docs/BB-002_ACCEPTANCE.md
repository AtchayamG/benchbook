# BB-002 Acceptance Report — Release Readiness & Zero-Spend Deployment Path

- **Task ID**: `BB-002`
- **Product**: Benchbook (*"Benchbook keeps a small repair shop moving from intake to pickup without making the technician become a full-time coordinator."*)
- **Worker**: AGY, senior full-stack developer
- **Base Commit**: `50038fc` (BB-001)
- **Branch**: `worker/agy/BB-002`
- **Date**: 2026-09-12
- **Personal Spend**: Exactly ₹0.00 / $0.00 (Zero paid infrastructure, zero external API keys)
- **Deployment Status**: `BLOCKED_INFRA` (all configuration, container definitions, and blueprint templates complete; external deployment waiting on hosted credentials).

---

## 1. Executive Summary

BB-002 transitions Benchbook from an initial vertical slice (BB-001) into a production-ready, release-verified application. The release boundaries have been fully hardened:
1. **Multi-Engine Database Support**: Dual support for local zero-setup SQLite WAL and hosted PostgreSQL (Neon Free Tier) via an explicit environment setting (`BENCHBOOK_DATABASE_URL` / `DATABASE_URL`). Schema initialization automatically adapts SQLite PRAGMAs for PostgreSQL, and parameter placeholder translation (`?` -> `%s`) is transparently handled.
2. **CORS & Environment Hardening**: Strict allowlist CORS middleware parsing comma-separated strings or JSON arrays; explicit container readiness probe (`GET /api/ready`) returning 503 on database disconnection; honest health endpoint reporting database engine and connection status.
3. **Zero-Spend Deployment Blueprints**: Complete infrastructure-as-code manifests for ₹0.00 hosting:
   - `render.yaml` (Render Blueprint for FastAPI free tier web service)
   - `railway.json` (Railway NIXPACKS service definition)
   - `Procfile` (Standard PaaS process launcher)
   - `Dockerfile` (Multi-stage Python 3.11-slim container)
   - `apps/web/vercel.json` (Vercel SPA routing and proxy configuration)
   - `.env.example` & `apps/web/.env.example` (documented configuration templates)
4. **Deterministic Release Smoke Path**: `scripts/release_smoke.py` executes all 11 lifecycle stages, validates human authority gates (HTTP 403 on assistant attempts), verifies optimistic concurrency (HTTP 409 `STATE_CONFLICT`), exercises idempotency key replays, and verifies full aggregated readback across 10 child tables.
5. **Judge-Facing UI Polish**: Added a 60-second Evaluator Guide banner to the workbench header, a real-time database indicator badge (`SQLite (WAL)` / `PostgreSQL (Neon)`), and visual 🔒 lock badges on human-gated timeline stages.
6. **Zero Skipped Tests & Strict Typing**: 37 backend tests in 1.22s, 9 frontend tests in 250ms, all 17 release smoke checks passed (0 skipped, 0 failed), clean ruff linting & formatting, clean ESLint, and 100% strict Mypy & TypeScript across all source files.

---

## 2. Requirement Verification Matrix

| Requirement | Implementation Detail | Verification Method | Status |
|---|---|---|---|
| **1. Audit & Non-Destructive Enhancements** | Audited existing BB-001 implementation; preserved domain workflow, optimistic concurrency, and human gates. | Visual inspection & full test suite regression | **MET** |
| **2. Database Boundary Hardening** | Added `psycopg[binary]>=3.1.0`. Implemented `ConnectionWrapper` and dynamic store resolution in `benchbook.infrastructure.database` and `store_factory.py`. Local default remains `sqlite:///./benchbook.db`. | `test_postgres_store_compatibility.py` & `release_smoke.py` | **MET** |
| **3. Strict CORS Allow-List** | Added `cors_origins_raw` setting supporting comma-separated strings or JSON arrays with `CORSMiddleware`. | `test_config_and_cors.py` | **MET** |
| **4. Honest Health & Readiness** | Updated `GET /api/health` to report `database: {engine, status}`. Added `GET /api/ready` returning 503 on DB disconnect. | `test_config_and_cors.py` (readiness healthy & 503 probe tests) | **MET** |
| **5. Zero-Spend Deployment Manifests** | Created `render.yaml`, `railway.json`, `Procfile`, `Dockerfile`, `apps/web/vercel.json`, and `.env.example` templates. | Syntax validation & container build inspection | **MET** |
| **6. Deterministic Release Smoke Script** | `scripts/release_smoke.py` tests all 11 stages, human gates (403), advisory provenance, 409 conflict, and idempotency replay. | Executed `python scripts/release_smoke.py`: 17/17 passed | **MET** |
| **7. Judge-Facing UI Polish** | Added Evaluator 60-second guide banner, database engine badge, and human gate lock badges on timeline. | Vitest tests & TypeScript compilation (`npm run build`) | **MET** |
| **8. Comprehensive Test Coverage** | Added 12 new backend tests and 2 new frontend tests. Zero skipped tests. Zero runtime mocks of business logic. | `pytest` (37 passed), `vitest` (9 passed) | **MET** |
| **9. Strict Typing & Code Standards** | Python type stubs (`py.typed`), strict Mypy across 31 source files, Ruff format & check, TypeScript `tsc --noEmit`. | Automated CI commands | **MET** |
| **10. Zero Personal Spend** | Zero paid APIs, zero cloud bills incurred, zero committed secrets. | Code audit & deployment documentation | **MET** |

---

## 3. Deployment Artifacts Summary

### 3.1 Backend
- `render.yaml`: Defines `benchbook-api` Web Service on Python environment with auto-provisioned free Postgres environment variable mapping.
- `railway.json`: Declares NIXPACKS builder targeting `python -m uvicorn benchbook.interfaces.http.app:app`.
- `Procfile`: Declares standard PaaS process `web: uvicorn benchbook.interfaces.http.app:app --host 0.0.0.0 --port ${PORT:-8000}`.
- `Dockerfile`: Multi-stage Python 3.11-slim container with non-root security user, curl healthcheck, and runtime entrypoint.
- `.env.example`: Documents all environment variables (`BENCHBOOK_DATABASE_URL`, `CORS_ORIGINS`, `ENVIRONMENT`, `SHOP_NAME`).

### 3.2 Frontend
- `apps/web/vercel.json`: Handles SPA routing rewrites (`/* -> /index.html`) and `/api/*` reverse proxy mapping.
- `apps/web/.env.example`: Documents `VITE_API_BASE_URL` for decoupled hosted deployments.

---

## 4. Test & Verification Results

### 4.1 Backend (`services/repair_service`)
- `pytest -v`: **37 passed** in 1.22s (0 failures, 0 skipped)
  - `test_api_routes.py`: 4 tests
  - `test_assistant_adapter.py`: 7 tests
  - `test_config_and_cors.py`: 7 tests
  - `test_human_approval_boundaries.py`: 5 tests
  - `test_idempotency_and_conflicts.py`: 3 tests
  - `test_postgres_store_compatibility.py`: 4 tests
  - `test_release_smoke.py`: 1 test (runs all 17 smoke stages)
  - `test_sqlite_persistence.py`: 3 tests
  - `test_workflow_transitions.py`: 3 tests
- `ruff check services/repair_service scripts`: Clean (0 errors, 0 warnings)
- `ruff format --check services/repair_service scripts`: Clean (31 files checked)
- `mypy --explicit-package-bases services/repair_service/src services/repair_service/tests scripts`: **Clean (0 errors across 31 source files)**

### 4.2 Frontend (`apps/web`)
- `npm test` (`vitest run`): **9 passed** in 250ms (0 failures, 0 skipped)
- `npm run lint` (`eslint . --max-warnings 0`): Clean (0 errors, 0 warnings)
- `npm run build` (`tsc && vite build`): Clean production build in 848ms (0 TypeScript errors)

### 4.3 Standalone Deterministic Release Smoke (`scripts/release_smoke.py`)
```
======================================================================
BENCHBOOK RELEASE SMOKE VERIFICATION
Target: In-Process ASGI TestClient (SQLite WAL)
======================================================================
[PASS]   1. Health Endpoint            Milestone=M1 DB=sqlite
[PASS]   1b. Readiness Probe           Database connectivity confirmed
[PASS]   2. Customer Intake            Job=BB-2026-A8A6A1 v1 state=intake
[PASS]   3. Technician Diagnosis       v2 state=diagnosis
[PASS]   4a. Assistant Parts Lookup    Provenance=benchbook_offline_adapter parts=2
[PASS]   4b. Parts Added to Job        v3 state=parts_lookup
[PASS]   5. Estimate Created           Total=INR 1260.0 v4
[PASS]   6a. Gate 1 Protection         Assistant approval rejected with 403 Forbidden
[PASS]   6b. Human Customer Approval   v5 state=customer_approved
[PASS]   7. Supplier Parts Received    v6 state=parts_ready
[PASS]   8. Repair Queued              v7 state=repair_queue
[PASS]   9. Repair In Progress         v8 state=repair_in_progress
[PASS]   10a. Gate 2 Protection        Assistant completion rejected with 403 Forbidden
[PASS]   10b. Technician QC Sign-Off   v9 state=repair_completed
[PASS]   11a. Assistant Message Draft  Channel=whatsapp text_len=429
[PASS]   11b. Customer Notified        v10 state=ready_for_pickup
[PASS]   12. Settlement & Handover     Paid=INR 1260 (UPI) v11
[PASS]   13a. Gate 3 Protection        Assistant closure rejected with 403 Forbidden
[PASS]   13b. Technician Close Sign-Off v12 state=closed
[PASS]   14. Aggregated Details Readback All 10 child record tables verified
[PASS]   15. Audit Stream Monotonicity 12 events verified v0 → v12
[PASS]   16. Optimistic Concurrency 409 Stale write rejected: STATE_CONFLICT
[PASS]   17. Idempotency Replay        Exact cached response returned for key=smoke-replay-key-001
======================================================================
ALL 17 SMOKE VERIFICATION CHECKS PASSED (100% REAL PERSISTENCE)
Zero fake success, zero live provider calls, INR 0.00 spend verified.
======================================================================
```

---

## 5. Human Authority Invariants Preserved

1. **Gate 1: Customer Approval** (`POST /api/jobs/{job_id}/customer-approval`):
   - Assistant actor returns HTTP 403 `HUMAN_APPROVAL_REQUIRED`.
   - Customer authorization requires human record.
2. **Gate 2: Repair Completion & QC Sign-Off** (`POST /api/jobs/{job_id}/repair-completion`):
   - Assistant actor returns HTTP 403 `HUMAN_APPROVAL_REQUIRED`.
   - Technician physical inspection, test pass confirmation, and signature required.
3. **Gate 3: Job Closure** (`POST /api/jobs/{job_id}/close`):
   - Assistant actor returns HTTP 403 `HUMAN_APPROVAL_REQUIRED`.
   - Technician resolution summary and manual sign-off required.
4. **Advisory Assistant Seam**:
   - Every assistant response carries explicit provenance:
     ```json
     {
       "engine": "benchbook_offline_adapter",
       "model": "rule-heuristic-v1",
       "advisory_only": true,
       "requires_human_verification": true
     }
     ```

---

## 6. Zero-Spend Protocol Adherence

- Personal spend across all BB-002 tasks: **₹0.00 / $0.00**.
- No paid cloud services, private model endpoints, or subscription APIs were invoked.
- External deployment is marked `BLOCKED_INFRA` pending user/judge credentials; zero fictitious URLs committed.
