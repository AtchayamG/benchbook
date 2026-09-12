# Benchbook — Professional Agents for Repair Shops

> **Benchbook keeps a repair shop moving from intake to pickup without making the technician become a full-time coordinator.**

Benchbook is **Project 2** of the **Agents for Humans** program. It is an independent, production-grade system designed for small electronics and appliance repair shops in Tamil Nadu (e.g. *Kovai Tech Bench, Gandhipuram, Coimbatore*). It automates customer communication, parts lookup, supplier tracking, and estimate drafts while enforcing strict human authority over diagnostic and financial decisions.

---

## 1. Key Invariants & Design Principles

1. **Complete 11-Stage Workflow**:
   `intake -> technician note -> parts lookup -> estimate -> customer approval -> supplier status -> repair queue -> repair in progress -> completion -> pickup notification -> follow-up -> close`
2. **Strict Human Approval Boundaries**:
   The technician owns the diagnosis, the repair method, and the final quality sign-off. The customer owns the financial approval. The assistant can suggest, draft, and summarize, but **MUST NEVER** approve work, spend money, mark a repair complete, or close a ticket without human action. Attempts by assistant/system actors trigger `403 HUMAN_APPROVAL_REQUIRED`.
3. **Optimistic Concurrency & Idempotency**:
   Every state mutation requires `expected_version`. Stale mutations return `409 STATE_CONFLICT` with current state snapshot. Requests carrying `Idempotency-Key` return identical responses without duplicate mutations or version bumps.
4. **Immutable Audit Event Stream**:
   Every state transition appends an append-only audit event recording `from_state`, `to_state`, `actor_type`, `actor_name`, `action`, payload, and version delta.
5. **Advisory Assistant with Provenance**:
   Zero live cloud dependencies or API keys required (₹0.00 spend). Ships with a deterministic offline rules engine rooted in authentic Tamil Nadu spare parts sourcing (Cross-Cut Road, 100 Feet Road, Ritchie Street) and simulated honest failure modes (429 Busy, 502 Bad Output, 503 Unavailable, 504 Timeout).
6. **Refresh-Proof Frontend**:
   React 18 + Vite SPA loads all state from the backend on initial load and browser refresh.

---

## 2. Project Architecture

```
02_BENCHBOOK/
├── apps/
│   └── web/                           # React 18 + Vite + TypeScript Frontend
│       ├── src/
│       │   ├── api/client.ts          # Typed REST API client
│       │   ├── components/            # UI components (Timeline, Detail, Cards)
│       │   ├── types/benchbook.ts     # TypeScript domain models & enums
│       │   ├── App.tsx                # Workbench main screen with Evaluator Guide
│       │   └── index.css              # Accessible, clean styling
│       ├── vercel.json                # Vercel SPA routing and proxy config
│       └── package.json
├── architecture/
│   └── benchbook_architecture.mmd     # Mermaid system architecture diagram
├── docs/
│   ├── API_CONTRACT.md                # Complete REST API specification
│   ├── ARCHITECTURE.md                # System architecture & invariants
│   ├── BB-001_ACCEPTANCE.md           # Formal BB-001 acceptance criteria report
│   ├── BB-002_ACCEPTANCE.md           # Formal BB-002 release readiness report
│   ├── BB-003_ACCEPTANCE.md           # Formal BB-003 transactional & PostgreSQL evidence
│   ├── HANDOVER.md                    # Operational handover instructions
│   ├── REVIEW_QUEUE.md                # Review checkpoint queue
│   ├── TASKSTATUS.md                  # Milestone status tracking
│   └── TEST_STATUS.md                 # Verification test results & commands
├── scripts/
│   └── release_smoke.py               # Deterministic 19-point release smoke script
├── services/
│   └── repair_service/                # Python / FastAPI Backend
│       ├── src/benchbook/
│       │   ├── domain/                # Models, enums, errors, workflow engine
│       │   ├── infrastructure/        # SQLite WAL / PostgreSQL store, adapter, seeds
│       │   └── interfaces/http/       # FastAPI app & route handlers
│       ├── tests/                     # 11 pytest test suites (53 tests)
│       └── pyproject.toml             # Ruff, mypy, pytest configs
├── Dockerfile                         # Production multi-stage Python container
├── Procfile                           # PaaS process launcher
├── railway.json                       # Railway NIXPACKS deployment config
├── render.yaml                        # Render Blueprint for zero-spend web service
├── .env.example                       # Documented environment template
└── README.md
```

---

## 3. Quickstart & Local Setup

### Prerequisites
- **Python**: 3.11+ (tested on Python 3.14)
- **Node.js**: 18+ (tested on Node 22.22 / npm 10.9)

### Backend Setup (`services/repair_service`)
```bash
cd services/repair_service

# Create virtual environment and install dependencies
python -m venv .venv
.venv\Scripts\activate            # On Windows (or source .venv/bin/activate on Linux/macOS)
pip install -e .

# Run the FastAPI server
uvicorn src.benchbook.interfaces.http.app:app --reload --port 8001
```
The API documentation is available at:
- Swagger UI: `http://localhost:8001/docs`
- Health check: `http://localhost:8001/api/health`
- Container readiness: `http://localhost:8001/api/ready`

### Frontend Setup (`apps/web`)
```bash
cd apps/web

# Install dependencies
npm install

# Start Vite development server (proxies /api to localhost:8001)
npm run dev
```
Open `http://localhost:5173` to access the Benchbook technician workbench.

---

## 4. Deterministic Release Smoke Path

Benchbook includes a standalone deterministic smoke script that exercises the full 11-stage persisted lifecycle against any running API service or in-process ASGI app:

```bash
# Run against in-process ASGI app (zero setup, isolated SQLite WAL database)
python scripts/release_smoke.py

# Or run against live running service
python scripts/release_smoke.py --base-url http://localhost:8001
```

The script rigorously checks:
1. Health & readiness probes (honest database engine check).
2. Complete 11-stage happy path from Customer Intake to Ticket Close.
3. Human Authority Gates: HTTP 403 Forbidden on assistant bypass attempts for Customer Approval, Technician QC Sign-off, and Ticket Close.
4. Advisory assistant provenance (`advisory_only: true`, `benchbook_offline_adapter`).
5. Monotonic version progression and complete 12-event audit stream readback.
6. Optimistic concurrency conflict rejection (HTTP 409 `STATE_CONFLICT` on stale version).
7. `Idempotency-Key` replay verification (exact cached response returned without creating duplicate jobs).

---

## 5. Zero-Spend Deployment Guide (₹0.00 / $0.00)

Benchbook is engineered for production deployment across free-tier providers without incurring any cost:

### Option A: Render (Backend) + Neon (Postgres) + Vercel (Frontend)
1. **Database (Neon Free Tier)**:
   - Create a free Postgres instance at [neon.tech](https://neon.tech).
   - Copy connection string (`postgres://...`).
2. **Backend (Render Free Web Service)**:
   - Connect repository to Render.
   - Use `render.yaml` blueprint or configure a Web Service:
     - Build: `pip install -e services/repair_service`
     - Start: `python -m uvicorn benchbook.interfaces.http.app:app --host 0.0.0.0 --port $PORT`
     - Environment Variables:
       - `BENCHBOOK_DATABASE_URL`: Your Neon Postgres URL.
       - `CORS_ORIGINS`: Your Vercel frontend domain (`https://benchbook-web.vercel.app`).
       - `ENVIRONMENT`: `production`.
3. **Frontend (Vercel Hobby Tier)**:
   - Deploy `apps/web` root.
   - Set environment variable `VITE_API_BASE_URL` to your Render backend URL (`https://benchbook-api.onrender.com`).
   - `apps/web/vercel.json` automatically configures SPA routing and clean headers.

### Option B: Container / PaaS (Railway / Fly.io / Docker)
- **Dockerfile**: Multi-stage container definition ready for build:
  ```bash
  docker build -t benchbook-api .
  docker run -p 8000:8000 -e BENCHBOOK_DATABASE_URL=sqlite:///./benchbook.db benchbook-api
  ```
- **Railway**: Connect repo; `railway.json` automatically detects configuration via NIXPACKS.
- **PaaS (Heroku/Dokku)**: `Procfile` declares `web: uvicorn benchbook.interfaces.http.app:app --host 0.0.0.0 --port ${PORT:-8000}`.

---

## 6. Automated Testing & Verification

### Backend Verification
From `services/repair_service`:
```bash
# Run pytest test suite (53 tests across 11 files, including real PostgreSQL 16.10 tests)
pytest -v

# Run Ruff linter & format checker
ruff check . ../../scripts
ruff format --check . ../../scripts

# Run strict type checking with Mypy
mypy --explicit-package-bases src tests ../../scripts
```
*Result: 53/53 passed (14.9s), 0 lint errors, 0 format issues, 0 type errors across 33 source files.*

### Frontend Verification
From `apps/web`:
```bash
# Run Vitest test suite (9 tests)
npm test

# Run ESLint
npm run lint

# Run TypeScript type check
npm run typecheck

# Run production build
npm run build
```
*Result: 9/9 passed (250ms), 0 lint errors, 0 type errors, production build succeeds in ~850ms.*

---

## 7. Tamil Nadu Synthetic Presets

Benchbook includes contact-safe synthetic presets reflecting common repair shop workloads in Coimbatore:
1. **Atomberg Renesa 1200mm Smart BLDC Fan**: Motor bearing hum and BLDC driver PCB sensor fault.
2. **Voltas 1.5T Inverter AC Outdoor PCB**: Error code E6 communication fault, burned IGBT module.
3. **Preethi Zodiac 750W Mixer Grinder**: Worn brass coupler, carbon brush sparking, jar bushing play.
4. **Lenovo ThinkPad E14 Laptop**: Liquid spill corrosion on 3.3V/5V power rail, keyboard replacement.

---

## 8. License

MIT License — see [LICENSE](LICENSE) for details.
