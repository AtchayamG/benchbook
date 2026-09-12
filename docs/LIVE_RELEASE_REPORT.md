# Benchbook live release report

Date: 2026-09-12

## Public endpoints

- App: https://web-eight-phi-69.vercel.app
- Readiness: https://web-eight-phi-69.vercel.app/api/ready
- Repository: https://github.com/AtchayamG/benchbook (main, commit `d0d112f`)

## Evidence

- Fresh browser session loaded the public app over HTTPS.
- `GET /api/ready` returned `{"status":"ready","database":{"engine":"postgres","status":"connected"}}`.
- A fresh session received an opaque workspace cookie and seeded four synthetic Tamil Nadu repair jobs.
- The UI showed the PostgreSQL badge, workspace isolation count, advisory-only label, and human approval locks.
- Local browser review exercised the Strands-shaped fake transport, grounded parts advisory, estimate persistence, and approval gate.
- A separate browser workspace saw no jobs from the first workspace during the local isolation review.
- Production regression check created two fresh cookie sessions and seeded both successfully (`201`/`201`); the second workspace received collision-safe numbers `BB-2026-101-5d50f1` through `BB-2026-104-5d50f1` instead of a duplicate-key `500`.
- Vercel production logs for the regression check contain four successful requests and no exception entries.

## Honest boundaries

The public deployment runs deterministic offline catalogue mode and sends no external model requests. The repository includes the real Strands/Groq adapter and zero-spend fake-transport tests, but this report does not claim live provider inference. Messages remain drafts; no external customer message is sent.

## Remaining submission work

Create and review the narrated five-minute demo, attach the architecture diagram and this repository, then submit the distinct Benchbook Devpost entry after the final audit.
