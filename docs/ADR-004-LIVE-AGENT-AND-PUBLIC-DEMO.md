# ADR-004: real advisory agent and isolated public workbenches

Decision by Codex at ASTRA_HIGH, 2026-09-12. Implementation baseline:756cc0d. Status: APPROVED FOR IMPLEMENTATION; no live release claim.

## Product and authority

Keep Benchbook's existing repair lifecycle. The agent reduces coordination work using persisted job context; the technician retains diagnosis, repair method, spending/approval, QC and closure. Anonymous demo clicks are explicit user decisions, not authenticated proof of professional identity or customer consent. Public visitors must use synthetic data.

Official rules rechecked: Strands required, AgentCore optional, distinct submissions allowed, public MIT/Apache repository/diagram/public video at most5 minutes required; testing access through October8 PDT. Deadline September14,2026,17:00 PDT (September15,05:30 IST). No new material rule conflict found for this direction.

Sources:
- https://agentsforhumans.devpost.com/rules
- https://agentsforhumans.devpost.com/resources
- https://strandsagents.com/docs/user-guide/concepts/model-providers/openai/
- https://console.groq.com/docs/structured-outputs
- https://render.com/docs/free

## Smallest deployment shape

One same-origin full-stack container: FastAPI serves built Vite assets and `/api`; managed PostgreSQL stores all durable state. Preferred deployment candidate: Render Free web service with Neon Free database, conditional on account/terms/capacity verification by Codex. Render sleeps after15 minutes of inactivity and has ephemeral local storage; describe cold-start waiting honestly. No PC hosting, paid disk, auto-converting trial, uptime-pinging workaround, or paid upgrade. Keep Vercel optional, not a second required hop. AgentCore is not implemented or claimed.

## Public workbench isolation

Add opaque random32-byte session cookie, HttpOnly, Secure in production, SameSite=Lax, Path=/, no Domain attribute,30-day lifetime. Store only token hash with workspace id and expiry in SQL; never return token in JSON or log it. `POST /api/session` explicitly starts/reuses a workbench; `GET /api/session` reports status. Use exact configured production Origin checks on every state-changing request including session/seed/advice; missing/foreign/null Origin fails closed in production. Local tests/development use an explicit local setting. CORS alone is not authorization.

All job/list/detail/audit/seed/transition/advice access is server-scoped to that workspace. Cross-workspace or unknown ids return404 without details. Ownership is checked in the same transaction as mutations. Bind idempotency to workspace+operation+job+validated payload. Client actor labels, job IDs, workspace IDs or headers never grant ownership. Migrate existing rows to a reserved local/legacy workspace unavailable to public sessions. No public global reset; sample seed is idempotent per workspace. Cap jobs at50 per workspace and active workspaces at1000 globally, with clear capacity errors; session creation bound to30 per minute globally. Session and quota enforcement must work across processes in PostgreSQL. No login system or external messaging integration in this task.

## Advisory application boundary

One canonical `POST /api/jobs/{job_id}/advice` accepting `operation` (parts/estimate/pickup), `expected_version` and idempotency key. Resolve the owned job snapshot on the server; do not accept client-supplied prices, approval status or identity as authoritative agent context. Update frontend and remove old public unscoped assistant routes (or return a documented retirement error; no bypass). Parts requires recorded diagnosis; estimate draft requires stored estimate; pickup requires recorded completion/QC and an eligible current state. Fail unsupported state before inference.

Keep a small application port for advisory generation and ports for snapshot reading/admission. Domain remains independent of FastAPI, SQL and Strands. Deterministic mode remains explicit local/offline behavior; live mode with missing credentials fails startup/readiness and never silently substitutes fixtures.

## Actual Strands execution

Use Strands Agent with Groq OpenAI-compatible transport and model `openai/gpt-oss-20b`. Borrow only the provider transport safeguards from the accepted Borrowed Steps implementation; keep Benchbook independently installable, preserve license/source attribution, and disclose reused code. Pinned working reference: Strands1.54.0 and OpenAI2.54.0; verify compatibility in Benchbook rather than upgrading gratuitously.

Give the agent one read-only `read_repair_context` tool bound by the server to the authorized snapshot; no job-id argument, SQL, arbitrary URL, shell, credential, write or messaging tool. Return redacted job facts, technician findings and a small sample catalogue with stable part IDs. Require observed successful tool execution before accepting a generated result. Use a bounded tool loop then separate schema extraction, following the provider's tool/structured-output limitations. A dependency/badge or fake-model test is not proof of live inference.

Typed result: short coordination summary, catalogue part IDs/reasons where relevant, and source job/version. Resolve part names/prices from the catalogue, never model-invented stock/supplier facts. Label catalogue and quoted prices explicitly synthetic/unverified, remove fabricated confidence percentages and unsupported in-stock claims. Derive customer message amounts, dates, warranty, readiness and approval wording from validated stored facts in deterministic templates; model prose must not supply those authoritative values. Do not send customer names, phone, address, serial or payment reference to inference; substitute display names only after generation. All messages are drafts, never sent externally by this app.

On successful live result show engine/provider/model, source version, actual tool count, actual send count and generated time. Do not expose chain-of-thought, raw provider messages, prompts or secrets. Recheck version before returning; a concurrent update makes the draft stale and returns409 with no application mutation. Acceptance of suggestions is a separate explicit human mutation using existing version/idempotency rules.

## Bounds and honest failure

Keep reference transport's fixed HTTPS endpoint, request/body/output limits, max6 actual sends total across stages/retries,1024 completion tokens per send, low reasoning,110-second operation deadline and per-send timeout<=60 seconds bounded by remaining deadline. No automatic SDK retry outside that counter, no redirects or environment proxy inheritance. Close clients/cancel work; do not free capacity while old inference is still running.

Before inference reserve6 sends atomically in SQL, one active operation globally, max6 reserved sends/60 seconds,120/24h globally and24/24h/workspace as initial conservative defaults. All attempts, including failures/abandonment, consume reservations; no refund-based bypass. Store request fingerprint and completed response for same-key replay with no extra inference; changed payload conflicts. No DB transaction remains open across provider I/O. Fail closed if admission DB unavailable. A timed-out lease must not admit overlapping local work; follow the proven admission/cleanup ownership pattern. Codex will check aggregate account allowance across projects before enabling live traffic and may adjust limits only against verified free quota.

Return meaningful429/502/503/504 states, no fabricated success. Manual repair workflow remains usable during provider failures. No credentials or provider calls are delegated to AGY. Codex performs a bounded live canary and anonymous deployed verification after code acceptance.

## Acceptance boundary

BB-004 must deliver implementation, migrations, offline tests with actual Strands loop plus instrumented fake transport, real PostgreSQL isolation/admission tests, browser verification, container build/config and an opt-in live verification script that defaults to no network. Record fixture-vs-live provenance. Public release, final privacy/security audit, real provider canary, video and submission remain Codex gates.
