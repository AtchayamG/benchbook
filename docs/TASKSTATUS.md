## Codex review complete — 2026-09-12

BB-003 ACCEPTED for local transactional correctness and configuration after Codex corrections. Independent: 66 backend tests (real PostgreSQL included), 9 frontend tests, build/lint/typing pass. Public hosting and real Strands remain pending. Read BB-003_CODEX_REVIEW.md for evidence and limits.

## Latest: BB-003 Transactional Correctness and Real PostgreSQL Release Evidence

TASK_ID: BB-003
STATUS: READY_FOR_REVIEW
WORKER: AGY, senior backend/full-stack developer
MODEL: Gemini 3.8 Flash High
EFFORT: HIGH
BRANCH: worker/agy/BB-003
BASE_COMMIT: 805d88f
PROPOSED_COMMIT_MSG: feat(benchbook): transactional mutation locking and real postgresql release evidence (BB-003)

Hardened transactional boundaries and completed real PostgreSQL 16.10 test evidence for Project 2 (Benchbook) at:
`D:\Work\Codex\Hackathon Projects\Agents For Humans\02_BENCHBOOK`

Key achievements & verifications:
- Strict Transactional Mutation Boundaries:
  - Row-level lock acquisition in `_get_and_lock_job`: `SELECT ... FOR UPDATE` on PostgreSQL, `BEGIN IMMEDIATE` write-locking on SQLite.
  - Conditional atomic updates `WHERE job_id = ? AND version = ?` asserting `cur.rowcount == 1`.
  - Single-transaction atomic commit: child records, state/version update, audit trail, and idempotency records commit together in one transaction with automatic complete rollback on failure.
- Robust Idempotency & Canonical Payload Hashing:
  - Canonical request hashing (`canonical_payload_hash`) via SHA-256 over sorted keys excluding idempotency key.
  - Same key + matching payload replays committed response; same key + altered payload raises `IdempotencyConflictError` (HTTP 409 `IDEMPOTENCY_CONFLICT`) without modifying state or leaking previous data.
  - Header vs. body key resolution (`resolve_idempotency_key`) enforces agreement; mismatch returns HTTP 422 `VALIDATION_ERROR`.
  - PostgreSQL advisory transaction locking (`pg_advisory_xact_lock`) cleanly serializes concurrent requests with identical keys.
  - Safe, non-destructive schema evolution in `init_db` for pre-existing SQLite and PostgreSQL databases.
- Real Disposable PostgreSQL 16.10 Test Evidence:
  - Reused local read-only binaries from `00_PROGRAM_CONTROL/worktrees/BS-011-claude/.pgtest/pgsql/bin` on dynamic loopback ports.
  - Verified full 19-stage deterministic smoke lifecycle on real PostgreSQL.
  - Verified two-connection contention, identical-key races, changed-payload conflicts, mid-transaction rollback, and restart durability on both engines.
- Deployment Configuration Hardening:
  - `Dockerfile` honors platform-injected `$PORT`.
  - Strict production environment validation forbidding SQLite when `BENCHBOOK_ENVIRONMENT=production`.
  - Health (`/api/health`) and readiness (`/api/ready`) accurately report injected store engine.
- Automated Verification:
  - Pytest: 53 passed, 0 skipped, 0 failed in 14.9s.
  - Ruff check & format: 100% clean (33 files).
  - Strict Mypy: 100% clean (33 source files).
  - Web tests: 9 passed in 274ms; lint clean; build clean.
  - Smoke script: 19/19 checks passed on SQLite and PostgreSQL.
  - Personal spend: Exactly â‚¹0.00 / $0.00.
  - Advisory assistant status strictly maintained.

Documentation:
- `docs/BB-003_ACCEPTANCE.md`
- `docs/TASKSTATUS.md`
- `docs/HANDOVER.md`
- `docs/TEST_STATUS.md`
- `docs/REVIEW_QUEUE.md`
- `docs/API_CONTRACT.md`
- `README.md`

NEXT_CODEX_MODE: ASTRA_HIGH
REASON: BB-003 is fully implemented, hardened, and verified with real PostgreSQL 16.10 evidence; ready for Codex review.

---

## BB-002 Benchbook Release Readiness and Zero-Spend Deployment Path

TASK_ID: BB-002
STATUS: CHANGES_REQUIRED (BB-002 review; superseded by BB-003)
WORKER: AGY, senior full-stack developer
MODEL: Gemini 3.8 Flash High
EFFORT: HIGH
BRANCH: worker/agy/BB-002
BASE_COMMIT: 50038fc
PROPOSED_COMMIT_MSG: feat(benchbook): complete release readiness and deployment path (BB-002)

Hardened and release-verified Project 2 (Benchbook) at:
`D:\Work\Codex\Hackathon Projects\Agents For Humans\02_BENCHBOOK`

Key achievements & verifications:
- Database Boundary Hardening:
  - Added PostgreSQL (`psycopg[binary]>=3.1.0`) support with zero-breaking changes to local SQLite default.
  - Safe schema initialization (`init_db`) strips SQLite PRAGMAs for PostgreSQL.
  - Dynamic store factory (`get_repair_job_store`) resolves store implementation based on DB URL scheme.
  - `ConnectionWrapper` adapts parameter placeholders (`?` -> `%s`) transparently on PostgreSQL.
- Security & Environment Hardening:
  - Strict CORS allow-list middleware parsing comma-separated strings or JSON arrays.
  - Container readiness probe `GET /api/ready` returning 503 on database disconnection.
  - Honest health check `GET /api/health` reporting database engine (`sqlite` / `postgres`) and connection status.
- Zero-Spend Deployment Blueprints:
  - Render Blueprint (`render.yaml`), Railway NIXPACKS (`railway.json`), PaaS `Procfile`, multi-stage `Dockerfile`, Vercel SPA config (`apps/web/vercel.json`), and comprehensive `.env.example` templates.
- Deterministic Release Smoke Path (`scripts/release_smoke.py`):
  - Standalone script exercising full 11-stage persisted lifecycle, human gates (403), advisory provenance, 409 optimistic conflict, idempotency replay, and 10 child tables readback. 17/17 checks passed.
  - Integrated into backend pytest suite via `tests/test_release_smoke.py`.
- Judge-Facing UI Polish:
  - 60-second dismissible Evaluator Guide banner in header.
  - Database engine badge (`SQLite (WAL)` / `PostgreSQL (Neon)`).
  - Visual ðŸ”’ lock badges on human-gated stages in `WorkflowTimeline`.
- Automated Verification:
  - Backend pytest: 37 passed, 0 skipped, 0 failed in 1.22s.
  - Frontend vitest: 9 passed, 0 skipped, 0 failed in 250ms.
  - Ruff check & format: clean (31 source files).
  - Strict Mypy: clean across 31 source files.
  - Frontend tsc typecheck & eslint: clean (0 errors, 0 warnings).
  - Frontend production build: clean bundle built in 848ms.
  - Standalone smoke test: 17/17 checks passed.
  - Personal spend: Exactly â‚¹0.00.
  - Deployment status: BLOCKED_INFRA (zero secrets committed, ready for credentials).

Documentation:
- `docs/BB-002_ACCEPTANCE.md`
- `docs/TASKSTATUS.md`
- `docs/HANDOVER.md`
- `docs/TEST_STATUS.md`
- `docs/REVIEW_QUEUE.md`
- `README.md`

NEXT_CODEX_MODE: ASTRA_HIGH
REASON: BB-002 is fully implemented and verified across backend, frontend, and deployment artifacts; ready for Codex review.

---

## BB-001 Benchbook Initial Repository and Full Workflow Slice

TASK_ID: BB-001
STATUS: READY_FOR_REVIEW
WORKER: AGY, senior full-stack developer
MODEL: Gemini 3.8 Flash High
EFFORT: HIGH
BRANCH: worker/agy/BB-001
BASE_COMMIT: 78830b8
PROPOSED_COMMIT_MSG: feat(benchbook): complete initial repository and live workflow slice (BB-001)

Created and verified the complete independent repository for Project 2 (Benchbook) at:
D:\Work\Codex\Hackathon Projects\Agents For Humans\02_BENCHBOOK

Key achievements & verifications:
- Product & Context:
  - Benchbook keeps a repair shop moving from intake to pickup without making the technician become a full-time coordinator.
  - Realistic Tamil Nadu repair shop context (Kovai Tech Bench, Gandhipuram, Coimbatore) with contact-safe synthetic presets (Atomberg BLDC Fan, Voltas AC Inverter PCB, Preethi Mixer Grinder, ThinkPad Laptop).
- Complete Live 11-Stage Workflow Slice (Persisted in SQLite with WAL & FK constraints):
  intake -> technician note -> parts lookup -> estimate -> customer approval -> supplier status -> repair queue -> repair in progress -> completion -> pickup notification -> follow-up -> close
- Strict Human Approval Gates:
  - Customer approval of estimate, technician QC completion sign-off, and job close strictly require human authorization.
  - Assistant or system calls return HTTP 403 HUMAN_APPROVAL_REQUIRED.
- Optimistic Concurrency & Idempotency:
  - Version increment on every mutation; stale writes return HTTP 409 STATE_CONFLICT.
  - Idempotency-Key caching returns identical payload without duplicate mutation or version increment.
  - Immutable audit event trail recorded for every transition.
- Advisory Assistant Adapter:
  - Deterministic offline rules with explicit provenance (engine, model, timestamp, advisory_only: true).
  - Testable honest failure modes: timeout (504), busy (429), unavailable (503), invalid_output (502).
  - Bounded Strands integration seam (zero live network calls, â‚¹0.00 spend).
- Frontend Workbench (apps/web):
  - React 18 + Vite SPA with English-first accessible UI.
  - Visual 11-stage WorkflowTimeline, left bench job list, active step action form, and real-time audit stream.
  - 100% refresh-proof: loads state from API on load and refresh.
- Automated Verification:
  - Backend pytest: 25 passed, 0 skipped, 0 failed in 0.94s.
  - Frontend vitest: 7 passed, 0 skipped, 0 failed in 204ms.
  - Ruff check & format: clean (26 source files).
  - Mypy: clean (strict mode, 26 source files).
  - Frontend tsc typecheck & eslint: clean (0 errors, 0 warnings).
  - Frontend build: clean production bundle generated in 550ms.
- Personal spend: Exactly â‚¹0.00.

Documentation:
- docs/BB-001_ACCEPTANCE.md
- docs/API_CONTRACT.md
- docs/ARCHITECTURE.md
- docs/TASKSTATUS.md
- docs/HANDOVER.md
- docs/TEST_STATUS.md
- docs/REVIEW_QUEUE.md
- README.md
- architecture/benchbook_architecture.mmd

NEXT_CODEX_MODE: ASTRA_HIGH
REASON: BB-001 complete, verified across backend and frontend, ready for Codex review.
