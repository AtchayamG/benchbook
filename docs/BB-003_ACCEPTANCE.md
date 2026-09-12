## Codex review complete — 2026-09-12

BB-003 ACCEPTED for local transactional correctness and configuration after Codex corrections. Independent: 66 backend tests (real PostgreSQL included), 9 frontend tests, build/lint/typing pass. Public hosting and real Strands remain pending. Read BB-003_CODEX_REVIEW.md for evidence and limits.

# BB-003 Acceptance Report: Transactional Correctness and Real PostgreSQL Release Evidence

- **Task ID**: `BB-003`
- **Worker**: AGY, senior backend/full-stack developer
- **Model / Effort**: Gemini 3.8 Flash High (Effort: `HIGH`)
- **Repository**: `D:\Work\Codex\Hackathon Projects\Agents For Humans\02_BENCHBOOK`
- **Base Commit**: `805d88f` on branch `worker/agy/BB-003`
- **Spend**: â‚¹0.00 / $0.00 (Zero paid infrastructure, zero cloud credentials, 100% offline local verification)

---

## 1. Executive Summary

Benchbook (Project 2) provides an intuitive, high-velocity workbench for small electrical and electronic repair shops (such as Kovai Tech Bench in Gandhipuram, Coimbatore), preventing technicians from being consumed by administrative coordination while strictly preserving human-authority boundaries.

Under **BB-003**, Benchbook has been hardened with:
1. **Strict Transactional Boundaries**: Full locking semantics (`SELECT ... FOR UPDATE` on PostgreSQL, `BEGIN IMMEDIATE` write locking on SQLite), conditional atomic updates (`WHERE job_id = ? AND version = ?` with `cur.rowcount == 1` assertion), and single-transaction atomicity across child entities, state/version bumps, audit events, and idempotency records with clean zero-orphan rollback on any failure.
2. **Robust, Non-Destructive Idempotency**: Canonical SHA-256 request payload hashing with sorted keys, atomic commit, cached replay for identical payloads, HTTP 409 `IDEMPOTENCY_CONFLICT` without state modification or data leakage for altered payloads, header-body key agreement enforcement (mismatch returns HTTP 422 `VALIDATION_ERROR`), and automatic schema migration for existing databases.
3. **Real Disposable PostgreSQL 16.10 Evidence**: Reusable local binaries from `00_PROGRAM_CONTROL/worktrees/BS-011-claude/.pgtest/pgsql/bin` spun up on dynamic ephemeral loopback ports, validating the complete 19-step lifecycle, concurrent two-connection optimistic contention, concurrent identical-key races with PostgreSQL advisory transaction locks (`pg_advisory_xact_lock`), altered-payload conflict guards, atomic rollback, and cross-restart durability on both SQLite and PostgreSQL.
4. **Production Deployment Discipline**: Container `$PORT` injection in `Dockerfile`, explicit production environment validators forbidding SQLite in production, honest engine reporting in `/api/health` and `/api/ready`, and strict CORS validation.
5. **Advisory Assistant Boundaries**: Maintained strict human authorization gates (Customer Approval, QC Completion Sign-Off, Job Close) with 403 Forbidden enforcement and zero live LLM provider calls.

---

## 2. Key Architecture & Implementation Details

### A. Transactional Locking & Conditional Updates
- **Lock Acquisition (`_get_and_lock_job`)**:
  - **PostgreSQL**: Executes `SELECT * FROM jobs WHERE job_id = ? FOR UPDATE` inside an explicit transaction context.
  - **SQLite**: Starts an exclusive transaction with `BEGIN IMMEDIATE;` to serialize database-level writes, with WAL journal mode enabled.
  - Verifies `current_job.version == expected_version`, immediately raising `StateConflictError` (HTTP 409 `STATE_CONFLICT`) if stale.
- **Conditional Update Execution**:
  - Updates `jobs` with `WHERE job_id = ? AND version = ?`.
  - Asserts `cur.rowcount == 1`. If another concurrent transaction committed in the interim, `StateConflictError` is raised.
- **Single-Transaction Atomicity**:
  - In `create_job` and all 10 transition endpoints (`add_technician_note`, `add_parts`, `create_estimate`, `record_customer_approval`, `update_supplier_status`, `advance_repair_queue`, `complete_repair`, `record_pickup_notification`, `record_follow_up`, `close_job`), child records, job status/version updates, audit trail entries, and idempotency records are committed within the **same** transaction.
  - On error or exception, the connection automatically rolls back. Zero orphan child records or audit events are left behind.

### B. Idempotency Contract & Canonical Hashing
- **Header vs. Body Key Agreement (`resolve_idempotency_key`)**:
  - Accepts idempotency key from either the `Idempotency-Key` HTTP header, the request body's `idempotency_key` field, or both.
  - If both are present, they must match identically; disagreement raises `ValidationError` (HTTP 422 `VALIDATION_ERROR`).
- **Canonical Payload Hashing (`canonical_payload_hash`)**:
  - Excludes the `idempotency_key` attribute itself.
  - Normalizes JSON serialization using `sort_keys=True, separators=(',', ':')` and calculates a SHA-256 hex digest (`payload_hash`).
- **Idempotency Table Schema & Migration**:
  - `idempotency_records` schema: `(idempotency_key PRIMARY KEY, job_id, action, payload_hash, scope, response_payload, response_status, created_at)`.
  - Non-destructive migration in `init_db`: inspects existing tables and executes `ALTER TABLE idempotency_records ADD COLUMN ...` before creating `idx_idempotency_scope` on legacy databases.
- **Replay & Conflict Handling**:
  - Same key + matching payload hash & scope: replays committed response payload and status code directly without re-executing business logic or incrementing version.
  - Same key + differing payload hash or scope: raises `IdempotencyConflictError` (HTTP 409 `IDEMPOTENCY_CONFLICT`) without modifying existing data or exposing previous payload data.
- **PostgreSQL Advisory Locking (`_lock_idempotency_key`)**:
  - In PostgreSQL mode, transactions execute `SELECT pg_advisory_xact_lock(hashtext(?))` on the idempotency key, cleanly serializing concurrent requests with the identical key before reading or inserting.

### C. Real Disposable PostgreSQL 16.10 Verification
- Implemented `tests/disposable_postgres.py`:
  - Locates local PostgreSQL 16.10 binaries at `00_PROGRAM_CONTROL/worktrees/BS-011-claude/.pgtest/pgsql/bin` (read-only).
  - Obtains dynamic loopback ports from the operating system (`socket.bind(('127.0.0.1', 0))`).
  - Initializes ephemeral data cluster with `initdb.exe` and starts server via `pg_ctl.exe`.
  - Supports isolated test databases via `create_isolated_db()` on the cluster.
  - Safely stops server with `pg_ctl.exe stop -m fast` and wipes data directories.

---

## 3. Test & Verification Evidence

### A. Full Automated Test Suite
- **Pytest**: **53 passed**, 0 failed, 0 skipped in 14.91s.
- **Ruff Linter**: Clean (all checks passed across 33 source files).
- **Ruff Formatter**: 33 files inspected, 100% formatted.
- **Mypy Typecheck**: Strict mode passed (33 source files checked).
- **Web Tests (`vitest`)**: 9 passed in 274ms.
- **Web Linter (`eslint`)**: Clean (0 errors, 0 warnings with `--max-warnings 0`).
- **Web Build (`vite build`)**: Clean production bundle built in 489ms.
- **Release Smoke Test (`scripts/release_smoke.py`)**: All 19 deterministic checks passed on SQLite and PostgreSQL.

### B. Matrix of Verified Concurrency & Transactional Behaviors

| Test Name | Target Engine | Verified Behavior | Status |
|---|---|---|---|
| `test_postgres_full_19_stage_smoke_lifecycle` | PostgreSQL 16.10 | All 19 deterministic stages & gates on real PostgreSQL | **PASSED** |
| `test_two_connection_contention_sqlite` | SQLite (WAL) | Simultaneous diagnosis write on same v1: one 200, one 409 `STATE_CONFLICT`, 0 orphan child/audit rows | **PASSED** |
| `test_two_connection_contention_postgres` | PostgreSQL 16.10 | Simultaneous diagnosis write on same v1: one 200, one 409 `STATE_CONFLICT`, row-level lock isolation | **PASSED** |
| `test_identical_key_race_sqlite` | SQLite (WAL) | Simultaneous job intake with identical key: both 201, identical `job_id`, exactly 1 job/idempotency/audit row | **PASSED** |
| `test_identical_key_race_postgres` | PostgreSQL 16.10 | Simultaneous job intake with identical key: advisory lock serializes, both 201, exactly 1 job in DB | **PASSED** |
| `test_changed_payload_conflict_sqlite` | SQLite (WAL) | Same key + altered customer payload: rejected with 409 `IDEMPOTENCY_CONFLICT`, 0 database overwrite | **PASSED** |
| `test_changed_payload_conflict_postgres` | PostgreSQL 16.10 | Same key + altered customer payload: rejected with 409 `IDEMPOTENCY_CONFLICT`, 0 database overwrite | **PASSED** |
| `test_atomic_rollback_sqlite` | SQLite (WAL) | Mid-transaction audit failure: rolls back child note and job status, version stays 1, 0 orphan notes | **PASSED** |
| `test_atomic_rollback_postgres` | PostgreSQL 16.10 | Mid-transaction audit failure: rolls back child note and job status, version stays 1, 0 orphan notes | **PASSED** |
| `test_durability_reconnect_sqlite` | SQLite (WAL) | Disconnect and instantiate fresh store: job state, version, audit events, and idempotency replay intact | **PASSED** |
| `test_durability_reconnect_postgres` | PostgreSQL 16.10 | Disconnect and instantiate fresh store: job state, version, audit events, and idempotency replay intact | **PASSED** |

---

## 4. Deployment Configuration & Production Hardening

- **Dockerfile**:
  ```dockerfile
  CMD ["sh", "-c", "exec uvicorn benchbook.interfaces.http.app:app --host 0.0.0.0 --port ${PORT:-8001}"]
  ```
  Properly respects platform-injected `$PORT` variables (Render, Railway, Fly.io, Cloud Run).
- **Production Validation (`benchbook/config.py`)**:
  - In `production` environment (`BENCHBOOK_ENVIRONMENT=production`), `database_url` must explicitly use `postgresql://` or `postgres://`.
  - Rejects default SQLite configuration with `ValueError: Production environment requires a valid PostgreSQL database_url (cannot run on SQLite in production).`
  - Rejects localhost/wildcard CORS origins in production.
- **Observability**:
  - `/api/health` and `/api/ready` report `store.engine_name` directly from the injected store instance (`sqlite` or `postgres`).

---

## 5. Artifacts and File Map

- `services/repair_service/src/benchbook/infrastructure/sqlite_store.py`: Atomic transactional locking, advisory locks, canonical hashing, single-transaction mutations.
- `services/repair_service/src/benchbook/infrastructure/database.py`: Safe schema migration, SQLite write locking, PostgreSQL transaction wrapping, connection pooling.
- `services/repair_service/src/benchbook/interfaces/http/schemas.py`: `resolve_idempotency_key`, header vs. body validation.
- `services/repair_service/src/benchbook/domain/errors.py`: `IdempotencyConflictError`.
- `services/repair_service/src/benchbook/config.py`: Production configuration validator.
- `services/repair_service/tests/disposable_postgres.py`: Ephemeral PostgreSQL 16 runner and isolated database manager.
- `services/repair_service/tests/test_transactional_concurrency.py`: Comprehensive concurrency, race, contention, rollback, and durability test suite.
- `scripts/release_smoke.py`: Deterministic 19-point release smoke runner.
- `docs/API_CONTRACT.md`: Formally updated API contract with idempotency semantics.
