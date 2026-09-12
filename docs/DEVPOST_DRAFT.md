# Benchbook — Devpost draft

## What it does

Small repair shops lose time coordinating intake, diagnosis notes, parts, supplier status, customer estimates, pickup, and closure across messages and paper notes. Benchbook gives the technician one persistent workbench from intake to pickup while keeping financial approval, repair completion, quality sign-off, and closure under human control.

## Who it is for

Independent repair shops and technicians who need a clear queue and an auditable customer handoff without giving an assistant authority to approve work or spend money.

## How it works

Each public visitor receives an isolated PostgreSQL-backed workbench. Jobs move through a version-guarded, idempotent workflow. The advisory layer can suggest grounded local parts and draft customer/supplier messages; all suggestions show provenance and remain drafts. Human approval gates are visible on the timeline and enforced by the API. The public deployment uses the deterministic offline catalogue mode at ₹0 provider spend; the repository also contains the bounded Strands/Groq adapter and its instrumented tests.

## Live demo and source

- Live app: https://web-eight-phi-69.vercel.app
- API readiness: https://web-eight-phi-69.vercel.app/api/ready
- Source: https://github.com/AtchayamG/benchbook

## Verification

107 backend tests passed, including disposable PostgreSQL concurrency and migration coverage. 12 frontend tests, strict mypy, Ruff, frontend lint, production build, and browser E2E also passed. The public canary created an isolated workspace, seeded four synthetic jobs, and persisted them in Neon PostgreSQL.

## Video checklist

Use a narrated video under five minutes showing the problem, intended technician, live intake-to-pickup workflow, advisory provenance, human approval locks, persistence after refresh, architecture, and the honest offline-provider label.
