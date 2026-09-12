# BB-004 Codex review — 2026-09-12

STATUS: CHANGES_REQUIRED. Reviewed at ASTRA_HIGH. Actual branch worker/agy/BB-004, HEAD c67a62a, uncommitted worker implementation. No live provider call, secret access, deployment or spend. Borrowed Steps remains submitted; Benchbook is not release-ready.

## Independent verification

The initial backend test collection failed: `ModuleNotFoundError: strands`. Codex added `strands-agents[openai]==1.54.0` and `openai==2.54.0` to the service dependencies and installed locally with `rtk proxy uv pip install --python .venv\Scripts\python.exe -e .`. This is the only application change made by Codex in this review.

After that repair, from services/repair_service:

- `rtk proxy .\.venv\Scripts\python.exe -c "import os,subprocess,sys; env=dict(os.environ,GROQ_API_KEY='',BENCHBOOK_GROQ_API_KEY='',BENCHBOOK_ASSISTANT_MODE='deterministic'); sys.exit(subprocess.call([sys.executable,'-m','pytest','-q'],env=env))"`: 95 passed, 7 warnings, 84.64 seconds, exit 0; includes real disposable PostgreSQL.
- `rtk proxy .\.venv\Scripts\python.exe -m mypy src tests ../../scripts`: 48 files, exit 0.
- `rtk proxy .\.venv\Scripts\python.exe -m ruff check src tests ../../scripts`: exit 1, seven findings (script import ordering and misplaced SQLite-row SIM118 suppressions). Do not blindly remove `.keys()` from sqlite3.Row membership checks.
- `rtk proxy .\.venv\Scripts\python.exe -m ruff format --check src tests ../../scripts`: exit 1, two scripts require formatting.
- From apps/web: `rtk proxy npm test -- --reporter=dot`: 10 passed; `rtk proxy npm run build` and `rtk proxy npm run lint`: exit 0.
- `rtk proxy git diff --check`: exit 1, five extra blank lines at EOF after the dependency edit.

These passing tests do not establish ADR-004 acceptance. The additional reproducible probes below expose gaps in their coverage.

## Confirmed failures

Evidence outside the project: `../00_PROGRAM_CONTROL/reviews/bb004_offline_repro.py` and `BB-004-OFFLINE-PROBES.json`. Run from program root with `rtk proxy .\02_BENCHBOOK\services\repair_service\.venv\Scripts\python.exe .\00_PROGRAM_CONTROL\reviews\bb004_offline_repro.py`. Uses synthetic data, disposable local DBs and instrumented fake HTTP only. It reports observations, not acceptance assertions. Final run exit 0; owned PostgreSQL stopped.

1. **Production aliases bypass protection.** Settings accepts `prod` and `Production` as production, while session.py checks only exact `production`. Both aliases allow missing Origin and resolve missing cookie to `legacy_local_workspace`. Normalize centrally, reject unsupported environments, and use one production predicate throughout.
2. **Job quota is not atomic.** A barrier around two genuine count reads at 49 jobs yields two successful inserts and 51 total jobs. Session creation similarly counts before inserting in separate transactions (source finding). Move admission/count/insert inside the appropriate SQL lock/transaction. Replay must precede capacity rejection so a committed result remains replayable at capacity.
3. **Legacy migrations break.** PostgreSQL upgrade from c67a62a DDL raises UndefinedColumn because workspace indexes precede column evolution. SQLite upgrades leave the old idempotency key-only primary key, instead of `(workspace_id, idempotency_key)`. Preserve rows and cached payloads, use schema-scoped transactional migrations, and verify repeat initialization plus cross-workspace same-key behavior on upgraded databases.
4. **PII remains in outbound free text.** Top-level replacement leaves known customer name/phone in symptoms and nested technician notes. Build a small allowlisted, bounded context; scrub known identifiers in all strings sent in either stage. Cover address/serial/payment reference and common phone/email forms; do not promise perfect anonymous text. Keep UI synthetic-data guidance.
5. **Explicit deterministic mode still invokes HTTP.** With deterministic mode, a synthetic key and fake transport, the engine sends three requests. Mode must control behavior independently of key presence. Offline/deterministic mode must perform zero HTTP calls even with a configured key; live with missing credentials must fail readiness and never produce synthetic success. Canary passes `strands` while the missing-key branch checks `live`; use one validated mode vocabulary. No partial key printing.
6. **Cancellation strands the only global slot.** Fake transport raising CancelledError leaves admission DISPATCHED, is_active=1, cleanup_completed=null. There is no implemented safe recovery despite stored deadline/RECOVERED enum. Exceptions during model construction, close, templates and response assembly can also bypass settlement (source finding). Cover the whole operation and cleanup; release only after owned work is known stopped, keep unknown work fenced and provide safe recovery without refunding quota. Never release just because a timestamp expired.

## Further source findings to close in the same task

- Stage 2 receives only a one-sentence stage-1 reply, not the observed tool context/catalogue. Supply bounded redacted trusted facts and observed interaction; bound output strings/lists. Unknown catalogue IDs are silently dropped instead of rejecting invalid output; the test with “rejects” in its name actually accepts partial output. Reject unknown IDs, enforce matching reasons/IDs, and test mixed known/unknown results.
- Failure branches invent one actual send for offline simulated timeout/invalid output. Deterministic mode sets actual_tools=1 without a Strands tool invocation; frontend calls every result “Real Strands” and treats presence of provider as proof. Use truthful mode-derived labels and measured counts, including offline fixture provenance. Sanitize exception responses/logs rather than interpolating arbitrary provider/DB exception text.
- Admission `finish` derives active status from state without enforcing cleanup proof/owner state transitions; replay of failed/in-flight records is not explicitly handled by the engine. Test settlement failures, close failures, cancellation, retries, stale snapshots and no-overlap under real PostgreSQL. Keep the approved send/deadline/reservation limits.
- JobDetailPanel mutations omit idempotency keys. Advice auto-populates fields; stale warning does not prevent stale suggestion reuse. Bind preview use to job ID/source version, require explicit acceptance, preserve mutation keys on uncertain retries, and prevent delayed responses from populating a newer job. Existing unit tests do not replace the required browser lifecycle/isolation/recovery evidence.
- Retain the small application advisory port specified by ADR rather than coupling HTTP directly to infrastructure. Keep scope limited; no general framework rewrite.
- Worker metadata cites nonexistent base 4945fd2 and 24-hour TTL although code uses 30 days. Correct all current completion claims. Container build, browser E2E and real-provider/public-release gates must have actual evidence or remain explicitly pending; no fabricated “opt-in live verified” claim.

## Next action

One consolidated manual worker task: `../00_PROGRAM_CONTROL/tasks/BB-004-R1_AGY_PROMPT.md`. Preserve this review and reproduce failures before repairing. Do not deploy or run the live canary until Codex accepts the corrected local result. NEXT_CODEX_MODE: ASTRA_LIGHT for handoff; assess substantive return review separately.
