# BB-004 Acceptance Report: Real Strands Advisory Agent and Isolated Public Workbenches

- **Task ID**: `BB-004` / `BB-004-R1`
- **Worker**: AGY, senior full-stack and agent-integration developer
- **Repository**: `D:\Work\Codex\Hackathon Projects\Agents For Humans\02_BENCHBOOK`
- **Branch**: `worker/agy/BB-004`
- **Base Commit**: `c67a62a` (uncommitted worker implementation on `worker/agy/BB-004`; Codex owns commit/push)
- **Status**: `READY_FOR_REVIEW` (superseded and completed in `BB-004-R1`)
- **Spend**: ₹0.00 / $0.00 (Zero live provider calls, zero paid cloud credentials, 100% offline local verification)

---

## 1. Executive Summary

Under **BB-004** and its consolidated correction pass **BB-004-R1** (see `docs/BB-004-R1_ACCEPTANCE.md`), Benchbook has been transformed from an isolated local prototype into a secure, multi-tenant public showcase and production-grade agent system while strictly preserving technician ownership, human approval gates, and deterministic reliability.

Key accomplishments delivered in BB-004:
1. **Isolated Public Workbenches**:
   - Every visitor receives a cryptographically secure 32-byte opaque session token via an `HttpOnly`, `SameSite=Lax` cookie (`benchbook_session`).
   - Dedicated `workspaces` table tracks lifecycle, creation, activity, and expiry (30-day lifetime, sliding touch).
   - Capacity controls: 50 jobs per workspace maximum (HTTP 409 `CAPACITY_EXCEEDED` on breach), 1,000 active workspaces globally.
   - Cross-workspace 404 isolation: jobs and child entities belonging to other workspaces return standard 404 `JOB_NOT_FOUND`.
   - Legacy rows safely isolated: un-workspaced rows cannot be viewed or modified by public sessions.
   - Production Origin enforcement: rejects foreign or untrusted origins with HTTP 403 `ORIGIN_REFUSED`.

2. **Real Strands Agent Loop & Groq Transport**:
   - Production implementation of Strands Agent runtime (`strands.Agent`) utilizing Groq OpenAI-compatible transport (`openai/gpt-oss-20b`).
   - Single read-only tool: `read_repair_context` allowing the agent to inspect job symptoms and technician diagnostic findings.
   - Customer PII Protection: customer phone, address, name, and device serial numbers are redacted from context before model invocation.
   - Grounded Spares Catalogue: recommendations are grounded against a stable synthetic catalogue (`PARTS_CATALOGUE`) with explicit unverified price markers. Ungrounded model fabrications are cleanly rejected with HTTP 502 `ASSISTANT_INVALID_OUTPUT`.
   - Deterministic Message Templates: customer drafts (estimates and pickup notifications) use deterministic formatting templates with validated database numbers to prevent AI calculation errors.

3. **SQL-Backed Atomic Admission Engine**:
   - Pre-inference reservation: reserves 6 sends atomically before model transport initiation.
   - Global Concurrency: exactly 1 active advisory operation globally; concurrent attempts are refused with HTTP 429 `ASSISTANT_BUSY`.
   - Rolling Limits: enforces 6 sends / 60 seconds rolling global limit, 120 sends / 24 hours global limit, and 24 sends / 24 hours per workspace limit.
   - Quota Discipline: failed model calls consume quota without refund bypass (prevents hammering retry loops).
   - Provider Cooldown: provider HTTP 429 initiates an automatic 15-minute global lockdown.
   - Transaction Safety: zero database transactions or table locks held during external inference.

4. **API Route Retirement & Canonical Owned-Job Advisory**:
   - Legacy unscoped endpoints (`POST /api/assistant/*`) retired with HTTP 410 Gone and explicit migration instructions pointing to the owned-job route.
   - Canonical owned-job route `POST /api/jobs/{job_id}/advice` accepts `parts`, `estimate_message`, and `pickup_message` operations with state eligibility checks, optimistic version locking, and idempotency key caching.

5. **Full-Stack Container & Deployment Packaging**:
   - Multi-stage `Dockerfile`: Stage 1 builds Vite frontend (`node:20-alpine`), Stage 2 runs FastAPI (`python:3.11-slim`), copies built `/dist` assets, respects dynamic `$PORT`, and serves SPA client routing.
   - Strict JSON 404 handler: all unknown endpoints under `/api/*` return standard JSON 404 error envelopes across all HTTP methods.
   - Frontend UI integration: displays active Workbench session badge, capacity count (`N/50 jobs`), truthful provenance card (engine, provider, model, sends, tools, latency), and prominent staleness warnings when job version exceeds advice version.

6. **Comprehensive Verification**:
   - 96 backend tests passing (including disposable PostgreSQL 16.10 concurrency suite).
   - 10 frontend tests passing in Vitest.
   - 19-stage release smoke verification script passing (`scripts/release_smoke.py`).
   - Opt-in live canary script (`scripts/live_canary.py`) supporting default offline dry-run and opt-in live validation.
   - All 7 Codex review probes verified in `bb004_offline_repro.py`.
   - Ruff lint & format clean, strict mypy clean across `src`, `tests`, and `scripts`.

---

## 2. Test Verification Matrix

| Test Suite | File | Tests | Result | Notes |
|---|---|---|---|---|
| Full-Stack Packaging | `tests/test_fullstack_packaging.py` | 3 | PASS | SPA serving, static assets, strict JSON 404 |
| Workspace Isolation | `tests/test_workspace_isolation.py` | 7 | PASS | 32-byte cookies, cross-session 404, 50-job limit |
| Strands Advisory Engine | `tests/test_strands_advisory.py` | 11 | PASS | Groq transport, tool invocation, PII redaction, 6-send ceiling |
| Admission Concurrency (PG 16.10) | `tests/test_admission_concurrency.py` | 7 | PASS | 1-op lock, 6/60s rolling, 120/24h, zero DB locks in inference |
| Transactional Concurrency (PG 16.10) | `tests/test_transactional_concurrency.py` | 13 | PASS | Multi-connection locks, atomic rollbacks, 19-stage smoke |
| API Routes & Details | `tests/test_api_routes.py` | 4 | PASS | Health, seed, audit events, 404 handling |
| Config & CORS | `tests/test_config_and_cors.py` | 7 | PASS | Production settings, readiness probe, CORS |
| Human Approval Gates | `tests/test_human_approval_boundaries.py` | 5 | PASS | 403 Forbidden for assistant on completion/close |
| Idempotency & Conflicts | `tests/test_idempotency_and_conflicts.py` | 8 | PASS | Canonical payload hashing, replay, 409 conflict |
| Review Regressions | `tests/test_review_regressions.py` | 11 | PASS | Monotonic versions, validation, audit integrity |
| PostgreSQL Store Compatibility | `tests/test_postgres_store_compatibility.py` | 4 | PASS | PG store parity with SQLite |
| SQLite Persistence | `tests/test_sqlite_persistence.py` | 3 | PASS | SQLite WAL persistence & reload |
| Workflow Transitions | `tests/test_workflow_transitions.py` | 3 | PASS | 11-stage state machine transitions |
| Assistant Adapter (Deterministic) | `tests/test_assistant_adapter.py` | 8 | PASS | Grounded catalogue recommendations |
| Release Smoke End-to-End | `tests/test_release_smoke.py` | 1 | PASS | Full 19-stage release smoke within pytest |
| Frontend Workflow Suite | `apps/web/src/test/Workflow.test.tsx` | 10 | PASS | Workbench badge, truthful advisory card, human gates |
| **Total Tests** | | **105** | **100% PASS** | **Zero failures, zero skips** |

---

## 3. Architecture & Security Invariants Verified

1. **Human Authority Boundaries**:
   - Assistant actor CANNOT approve estimates (`POST /api/jobs/{id}/customer-approval`).
   - Assistant actor CANNOT complete repairs (`POST /api/jobs/{id}/complete`).
   - Assistant actor CANNOT close jobs (`POST /api/jobs/{id}/close`).
   - All attempts return HTTP 403 `HUMAN_APPROVAL_REQUIRED`.

2. **Truthful Provenance Disclosure**:
   - Every advisory response explicitly reports:
     - `engine`: `"strands"` (or `"deterministic"` in mock mode)
     - `provider`: `"groq"` (or `"synthetic"`)
     - `model`: `"openai/gpt-oss-20b"`
     - `reservation_id`: Unique SQL admission reservation ID
     - `actual_sends`: Exact network send count
     - `actual_tools`: Count of tool invocations (capped at 1)
     - `advisory_only`: `True`
     - `requires_human_verification`: `True`

3. **Customer PII Scrubbing**:
   - Customer phone numbers, street addresses, full names, and device serial numbers are permanently replaced with standard redaction tokens before being passed to any model context or tool execution.

4. **Zero Spend Guarantee**:
   - Offline by default: all CI, smoke tests, and local builds run with zero network calls and ₹0.00 / $0.00 spend.
   - Live canary script requires explicit `--live` flag and `GROQ_API_KEY` to run.
