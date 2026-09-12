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
│       │   ├── App.tsx                # Workbench main screen
│       │   └── index.css              # Accessible, clean styling
│       └── package.json
├── architecture/
│   └── benchbook_architecture.mmd     # Mermaid system architecture diagram
├── docs/
│   ├── API_CONTRACT.md                # Complete REST API specification
│   ├── ARCHITECTURE.md                # System architecture & invariants
│   ├── BB-001_ACCEPTANCE.md           # Formal BB-001 acceptance criteria report
│   ├── HANDOVER.md                    # Operational handover instructions
│   ├── REVIEW_QUEUE.md                # Review checkpoint queue
│   ├── TASKSTATUS.md                  # Milestone status tracking
│   └── TEST_STATUS.md                 # Verification test results & commands
├── services/
│   └── repair_service/                # Python / FastAPI Backend
│       ├── src/benchbook/
│       │   ├── domain/                # Models, enums, errors, workflow engine
│       │   ├── infrastructure/        # SQLite WAL store, assistant adapter, seeds
│       │   └── interfaces/http/       # FastAPI app & route handlers
│       ├── tests/                     # 6 pytest test suites (25 tests)
│       └── pyproject.toml             # Ruff, mypy, pytest configs
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

### Frontend Setup (`apps/web`)
```bash
cd apps/web

# Install dependencies
npm install

# Start Vite development server
npm run dev
```
Open `http://localhost:5173` to access the Benchbook technician workbench.

---

## 4. Automated Testing & Verification

### Backend Verification
From `services/repair_service`:
```bash
# Run pytest test suite (25 tests)
pytest -v

# Run Ruff linter & format checker
ruff check .
ruff format --check .

# Run strict type checking with Mypy
mypy src tests
```
*Current result: 25/25 passed (0.94s), 0 lint errors, 0 format issues, 0 type errors across 26 source files.*

### Frontend Verification
From `apps/web`:
```bash
# Run Vitest test suite (7 tests)
npm test -- --run

# Run ESLint
npm run lint

# Run TypeScript type check
npx tsc --noEmit

# Run production build
npm run build
```
*Current result: 7/7 passed (204ms), 0 lint errors, 0 type errors, production build succeeds in ~550ms.*

---

## 5. Tamil Nadu Synthetic Presets

Benchbook includes contact-safe synthetic presets reflecting common repair shop workloads in Coimbatore:
1. **Atomberg Renesa 1200mm Smart BLDC Fan**: Motor bearing hum and BLDC driver PCB sensor fault.
2. **Voltas 1.5T Inverter AC Outdoor PCB**: Error code E6 communication fault, burned IGBT module.
3. **Preethi Zodiac 750W Mixer Grinder**: Worn brass coupler, carbon brush sparking, jar bushing play.
4. **Lenovo ThinkPad E14 Laptop**: Liquid spill corrosion on 3.3V/5V power rail, keyboard replacement.

---

## 6. License

MIT License — see [LICENSE](LICENSE) for details.
