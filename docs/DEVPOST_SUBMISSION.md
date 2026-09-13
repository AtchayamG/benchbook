# Benchbook — Human-led repair shop workflow

## Track
Everyday Agents — Agents for Humans Hackathon

## What it solves
Small repair shops lose time chasing the state of every ticket across intake,
diagnosis, parts, estimates, repair, quality control, and pickup. Benchbook gives
the technician one persistent workbench for that sequence.

## How it works
The public Vercel application uses synthetic Tamil Nadu repair jobs and Neon
PostgreSQL. A technician records findings, requests bounded parts advice from a
real Strands agent, and reviews the suggestion with visible provenance. Human
workflow stages remain explicit: the assistant cannot approve estimates, sign off
quality control, close jobs, order parts, or send messages. Customer updates remain
drafts. Versioned writes, idempotency, and durable audit history protect the record.

## Links

- Live demo: https://web-eight-phi-69.vercel.app
- Public source: https://github.com/AtchayamG/benchbook
- Demo video: `video/Benchbook-demo-master.mp4` (3:52, under the five-minute cap)
- Thumbnail: `video/Benchbook-thumbnail-v1.png`

## Technical implementation

FastAPI + React/TypeScript/Vite, PostgreSQL/SQLite adapters, Strands Agents,
Groq free model adapter, bounded read context, human approval gates, and a
multi-stage Vercel deployment. All demonstration data is synthetic and personal
spend is ₹0.00.

## Limitations

The public catalogue is a demonstration catalogue and does not verify supplier
stock or market prices. The browser demo uses synthetic customer details; shop
identity and customer identity verification are future work.
