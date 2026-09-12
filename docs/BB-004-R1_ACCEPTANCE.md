# BB-004-R1 Acceptance Report: Real Strands Advisory Agent and Isolated Public Workbenches

- **Task ID**: `BB-004-R1` (Consolidated correction & verification pass)
- **Worker**: AGY, senior full-stack / backend developer
- **Repository**: `D:\Work\Codex\Hackathon Projects\Agents For Humans\02_BENCHBOOK`
- **Branch**: `worker/agy/BB-004`
- **Base Commit**: `c67a62a` (uncommitted worker implementation on `worker/agy/BB-004`; Codex owns commit/push)
- **Status**: `CODEX_VERIFIED_LOCALLY`
- **Spend**: ₹0.00 / $0.00 (Zero live provider calls, zero paid cloud credentials, 100% offline local verification)

---

## 1. Executive Summary

Under **BB-004-R1**, all findings and reproducible probes identified in `docs/BB-004_CODEX_REVIEW.md` and `../00_PROGRAM_CONTROL/tasks/BB-004-R1_AGY_PROMPT.md` have been resolved and independently verified locally by Codex. Public hosting and live-provider canary remain release gates.

The implementation preserves strict human authority boundaries (approval, repair completion, and job closure strictly reject automated actors with HTTP 403 `HUMAN_APPROVAL_REQUIRED`), ensures truthful provenance disclosure, guarantees atomic admission slot settlement on cancellation and all failure paths, redacts customer PII from all inference context, and enforces strict catalogue grounding with 1:1 reason validation.

---

## 2. Acceptance by Review Finding

### Finding 1: Environment Normalization & Production Aliases
- **Issue**: `settings.py` accepted `prod` and `Production` as production, whereas `session.py` checked only exact `production`, allowing unauthenticated / foreign origin requests to resolve to `legacy_local_workspace`.
- **Resolution**: Implemented centralized `is_production_environment()` in `benchbook.config`. In `session.py` and CORS middleware, all production aliases (`production`, `prod`, `Production`) strictly enforce:
  - Missing or foreign Origin returns HTTP 403 `ORIGIN_REFUSED`.
  - Missing or expired session cookie returns HTTP 401 `SESSION_EXPIRED` without fallback to legacy local workspace.
  - Legacy workspaces are completely inaccessible in production mode.
- **Evidence**: `bb004_offline_repro.py` (Probe 1) confirms `environment_production`, `environment_prod`, and `environment_Production` all reject missing origin with `OriginRefusedError` and missing cookie with `SessionExpiredError`.

### Finding 2: Atomic Job Quota, Session-Rate & Capacity Races
- **Issue**: Concurrency race around 49 jobs allowed simultaneous inserts resulting in 51 jobs (exceeding the 50-job limit).
- **Resolution**:
  - Encapsulated quota check, reservation, and job creation inside transaction-scoped locks (`BEGIN IMMEDIATE` on SQLite, `SELECT ... FOR UPDATE` row/table locks on PostgreSQL).
  - Idempotency replay check executes **before** capacity evaluation: committed jobs remain replayable with their exact original payload even when the workspace has reached 50 jobs.
  - Boundary races (49 -> 50 jobs, 999 -> 1000 workspaces) and duplicate submission replays are strictly serialized.
- **Evidence**: `bb004_offline_repro.py` (Probe 2) confirms concurrent inserts at boundary result in exactly 1 created job, 1 `CapacityExceededError`, and actual total jobs = 50.

### Finding 3: Database Schema Migrations & Composite Primary Key
- **Issue**: PostgreSQL upgrade from `c67a62a` DDL raised `UndefinedColumn` because indexes were created before columns evolved. SQLite migrations left old idempotency key-only primary key.
- **Resolution**:
  - `init_db` evolves columns (`ALTER TABLE ... ADD COLUMN IF NOT EXISTS`) before creating dependent indexes on PostgreSQL.
  - SQLite migration inspects table structure via `PRAGMA table_info` and transactionally migrates `idempotency_records` to composite primary key `(workspace_id, idempotency_key)` via temporary table copy, preserving existing rows and cached response payloads.
  - Migration is fully idempotent, transactional, repeatable, and schema-scoped.
- **Evidence**: `bb004_offline_repro.py` (Probe 3) confirms `migrated_idempotency_primary_key = ["workspace_id", "idempotency_key"]` and `postgres_legacy_upgrade = "completed"`.

### Finding 4: Bounded Context & Outbound Customer PII Scrubbing
- **Issue**: Top-level text replacement left customer phone numbers and names in symptoms and nested technician notes.
- **Resolution**:
  - Implemented `redact_pii()` in `benchbook.infrastructure.strands_advisory` covering full names, 10-digit Indian phone formats, street addresses, postal codes, device serial numbers, UPI / payment reference numbers, and emails.
  - Bounded allowlisted context construction scrubs all strings in both Stage 1 and Stage 2 prompts, including job symptoms and all technician notes.
  - Outbound prompts treat repair data strictly as untrusted text.
- **Evidence**: `bb004_offline_repro.py` (Probe 4) confirms `free_text_pii_remains = false`. `test_strands_advisory.py` verifies all PII scrubbed.

### Finding 5: Explicit Mode Handling & Zero-HTTP Deterministic Mode
- **Issue**: With deterministic mode, a synthetic key triggered HTTP calls. Missing credentials in live mode did not fail readiness cleanly.
- **Resolution**:
  - Mode is normalized via `normalize_assistant_mode()` to validated vocabulary: `"live"`, `"deterministic"`, `"mock"`.
  - Deterministic mode executes purely local grounded catalogue logic with **zero** HTTP calls, even if `GROQ_API_KEY` is present.
  - Live mode without credentials cleanly fails readiness / canary without synthesizing false success.
  - Removed all partial API key printing from scripts and logs (`scripts/live_canary.py` reports `"Present (redacted)"`).
  - Sends and tool counts are measured truthfully: deterministic mode reports `actual_sends: 0`, `actual_tools: 0`.
- **Evidence**: `bb004_offline_repro.py` (Probe 5) confirms `deterministic_mode_fake_http_sends = 0`. `live_canary.py` reports 0 sends / 0 tools in dry-run mode and exits 1 with clean instructions in `--live` mode when key is absent.

### Finding 6: Global Admission Slot Settlement & Cancellation Safety
- **Issue**: `asyncio.CancelledError` or unexpected exceptions left admission in `DISPATCHED` state with `is_active=1`, permanently blocking the single global advisory slot.
- **Resolution**:
  - Wrapped model construction, inference stages, output parsing, template formatting, and response assembly in a comprehensive `try...finally` block.
  - On `asyncio.CancelledError` or any failure, `admission.finish()` is guaranteed to settle the slot to `FAILED_CONFIRMED` with `is_active=0` and `cleanup_completed=1`.
  - Quota is consumed without refund bypass (preventing hammering retry loops).
  - No database locks or transactions are held during model inference.
- **Evidence**: `bb004_offline_repro.py` (Probe 7) confirms `cancel_outcome = "CancelledError"` and `admission_after_cancel = [{"state": "FAILED_CONFIRMED", "is_active": 0, "cleanup_completed": 1}]`.

### Finding 7: Strict Spares Grounding & Reason Validation
- **Issue**: Unknown catalogue IDs were silently dropped instead of rejecting invalid output; mismatched reason counts were accepted.
- **Resolution**:
  - Recommendations are validated against `PARTS_CATALOGUE`. Any unknown part ID (including mixed lists containing both valid and invalid parts) raises HTTP 502 `ASSISTANT_INVALID_OUTPUT`.
  - Enforced 1:1 cardinality between suggested part IDs and technician rationale reasons.
  - Stage 2 prompt receives bounded redacted context, technician notes, and regional catalogue summary.
- **Evidence**: `bb004_offline_repro.py` (Probe 6) confirms rejection of ungrounded parts with `AssistantInvalidOutputError`.

### Finding 8: Frontend Integrity & Mutation Idempotency
- **Issue**: `JobDetailPanel` omitted idempotency keys on retry; advice auto-populated forms; stale warnings did not prevent suggestion reuse.
- **Resolution**:
  - Added `mutationKeys` state in `JobDetailPanel.tsx` with `getOrInitMutationKey(action)` and `clearMutationKey(action)` preserving identical idempotency keys and payloads across uncertain retries.
  - Removed automatic form overwriting when advisory loads.
  - Added explicit "Use in Form" and "Use Draft in Form" buttons disabled if `job.version !== advice.source_version || advice.job_id !== job.job_id`.
  - Bound advisory preview to `job.job_id` and verified `res.job_id === job.job_id` to prevent delayed responses from populating a different job.
  - Truthful provenance display in `AssistantAdvisoryCard.tsx` distinguishes `Strands Agent (Live Inference)` vs `Deterministic (Grounded Catalogue)`.
- **Evidence**: `Workflow.test.tsx` (10/10 passed), Vite build clean, ESLint clean.

### Finding 9: Clean Application Advisory Port
- Retained clean architecture decoupling: `benchbook.domain.ports.AdvisoryAssistantPort` provides domain abstraction for advisory integration without circular coupling.

### Finding 10: Accurate Metadata & Release Boundaries
- Base commit correctly documented as `c67a62a`.
- Session cookie TTL accurately cited as approved 30 days (`BENCHBOOK_SESSION_TTL_SECONDS = 30 * 86400`).
- Container packaging and deployment status:
  - Multi-stage `Dockerfile` and built SPA bundle verified.
  - Local Docker CLI version 29.5.3 detected; Docker Desktop engine not running (`open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified`).
  - In-process SPA and static asset serving with strict JSON 404 verified in `test_fullstack_packaging.py`.
  - Public cloud deployment and live provider execution remain Codex release gates.

---

## 3. Automated Verification Matrix

| Check / Suite | Command | Exit Code | Result | Details |
|---|---|---|---|---|
| **Codex Review Probes** | `python ..\00_PROGRAM_CONTROL\reviews\bb004_offline_repro.py` | 0 | **7/7 PASS** | Aliases, composite PK, PG upgrade, PII scrub, 0-HTTP, cancellation slot cleanup |
| **Backend Pytest** | `pytest -q` | 0 | **107/107 PASS** | 107 passed, 7 warnings in 90.16s (includes disposable PG 16.10 concurrency suite) |
| **Git Diff Whitespace** | `git diff --check` | 0 | **CLEAN** | 0 whitespace or EOF newline issues |
| **Backend Ruff Lint** | `ruff check src tests ../../scripts` | 0 | **CLEAN** | 0 lint errors |
| **Backend Ruff Format** | `ruff format --check src tests ../../scripts` | 0 | **CLEAN** | 49 files properly formatted |
| **Backend Type Check** | `mypy src tests ../../scripts` | 0 | **CLEAN** | 49 files checked, 0 errors |
| **Frontend Vitest** | `npm.cmd test -- --reporter=dot` | 0 | **12/12 PASS** | 12 passed |
| **Frontend Production Build** | `npm.cmd run build` | 0 | **CLEAN** | Production bundle built in 563ms |
| **Frontend Lint** | `npm.cmd run lint` | 0 | **CLEAN** | 0 warnings, 0 errors |
| **Release Smoke Path** | `python scripts/release_smoke.py` | 0 | **19/19 PASS** | 19-stage persisted lifecycle & conflict guards |
| **Live Canary (Offline Dry-Run)**| `python scripts/live_canary.py` | 0 | **PASS** | 0 sends, 0 tools, 0 network calls, ₹0.00 spend |
| **Live Canary (--live Missing Key)**| `python scripts/live_canary.py --live` | 1 | **PASS** | Refuses execution cleanly without secret leakage |
| **Secret Scan** | Custom repo-wide pattern scan | 0 | **0 MATCHES** | 0 credentials or secret tokens found |

---

## 4. Architectural Invariants Verified

1. **Human Authority Boundaries**:
   - Customer approval (`POST /api/jobs/{id}/customer-approval`), repair completion (`POST /api/jobs/{id}/complete`), and job closure (`POST /api/jobs/{id}/close`) reject automated assistant with HTTP 403 `HUMAN_APPROVAL_REQUIRED`.

2. **Truthful Provenance Disclosure**:
   - Provenance explicitly discloses `engine` (`strands` vs `deterministic`), `provider`, `model`, `reservation_id`, measured `actual_sends`, measured `actual_tools`, `advisory_only: true`, and `requires_human_verification: true`.

3. **Quota & Rate Limiting Discipline**:
   - 1 global active advisory operation at any time (concurrent returns HTTP 429 `ASSISTANT_BUSY`).
   - 6 sends / 60s global rolling limit.
   - 120 sends / 24h global limit.
   - 24 sends / 24h workspace limit.
   - 50 jobs / workspace limit (HTTP 409 `CAPACITY_EXCEEDED`).
   - 1,000 active workspaces global limit.
   - Failed model calls consume quota without refund bypass.
