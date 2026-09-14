# Final submission verification

Authenticated Devpost API readback on 2026-09-14 confirms submission to Agents for Humans.

- Public page: https://devpost.com/software/benchbook-human-approved-repair-shop-workflow
- Submitted at: 2026-09-14T01:04:01.790-04:00
- Video: https://youtu.be/WhYPSrmjgzc
- Status: submitted (non-null hackathon submitted_at).
- The API supplies the timestamp even though the participant browser UI does not.
- Corrected architecture PNG and PDF are included in this release commit.
- No application code was changed in this reconciliation.

## Submitted description

Inspiration

A small repair shop's work extends beyond the repair bench: diagnostic notes, estimates, customer approvals, parts and pickup all compete for the technician's attention. Benchbook keeps that coordination in one persistent record.

What it does

A technician starts a workspace, seeds synthetic Tamil Nadu repair jobs or creates an intake, records diagnostic findings, and moves a job through its repair lifecycle. Strands provides bounded parts advice and customer-message drafts grounded in the owned job's context. The technician reviews the advice before taking action.

Estimate approval, quality-control sign-off and closure remain explicit human actions. Messages remain drafts; the application does not order parts or send customer communications.

How we built it

React and TypeScript call a FastAPI backend through the public Vercel application. Neon PostgreSQL persists job records, audit history and idempotency records; SQLite supports local development. The Strands advisory engine uses a Groq model adapter, read-only context, admission limits and visible provenance. Version checks reject stale updates and stale advice.

Why it matters

The goal is to make a repair's next step and accountable decision visible without replacing the technician's judgment. This is a Professional Agents project for independent repair businesses.

Challenges and lessons

Production review exposed session-start ordering, database initialization and model-client cleanup issues. We corrected those paths and checked the hosted database and advisory workflow. A useful agent needs reliable state and clear authority boundaries as much as a fluent response.

Try it

Open https://web-eight-phi-69.vercel.app and seed the synthetic sample jobs. Select a job, add diagnostic findings, request advice, and inspect its timeline and audit history. Use synthetic details only.

Source and setup: https://github.com/AtchayamG/benchbook

Current limits

The public demo has synthetic roles, not verified customer or technician identities. Catalogue suggestions do not establish current supplier stock or prices. Provider and hosting free-tier limits can temporarily restrict availability. No AgentCore deployment is claimed.

Next

Evaluate the workflow with repair technicians, improve the catalogue with verified sources, and add production identity management before real customer use.
