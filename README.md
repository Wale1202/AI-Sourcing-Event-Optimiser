# AI Sourcing Event Optimiser

A small full-stack portfolio project that simulates a procurement sourcing
event: a buyer creates an event, captures supplier bids, sets cost / quality /
risk / sustainability constraints, runs an OR-Tools CP-SAT optimiser, and gets
back a recommended award with a **structured explanation** of why each
supplier was (or wasn't) selected. Multiple runs of the same event can be
compared side-by-side as scenarios.

It also ships a deterministic **Sourcing Brief Assistant** that converts a
plain-English brief like *"We need 1000 laptops for Q3, avoid high-risk
suppliers, max 3 suppliers, quality at least 75"* into draft event fields —
no LLM API required.

## Architecture at a glance

```
 ┌──────────────────────┐     HTTP /api/v1     ┌────────────────────────┐
 │   React + Vite UI    │ ───────────────────▶ │   FastAPI backend       │
 │   (nginx in Docker)  │                      │   - SQLModel ORM         │
 │   localhost:5173     │ ◀── JSON / CORS ──── │   - OR-Tools CP-SAT      │
 └──────────────────────┘                      │   - Brief parser         │
                                               │   localhost:8000         │
                                               └──────────────┬──────────┘
                                                              │ SQL
                                                              ▼
                                                       ┌──────────────┐
                                                       │  Postgres 16 │
                                                       │  localhost:  │
                                                       │  5432        │
                                                       └──────────────┘
```

Local dev without Docker uses SQLite (single file, no setup). Compose swaps
that for Postgres so the stack mirrors how it would be deployed.

## Quick start with Docker Compose (recommended)

```bash
git clone <this-repo>
cd AI-Sourcing-Event-Optimiser
docker compose up --build
```

The first build takes 1-3 minutes (mostly pulling Postgres + installing
ortools). Subsequent starts are seconds.

When it's ready:

| Service  | URL |
|----------|-----|
| Frontend | http://localhost:5173 |
| Backend  | http://localhost:8000 |
| Swagger  | http://localhost:8000/docs |
| Postgres | `localhost:5432`, user/pass/db = `sourcing` |

To stop + remove the database volume: `docker compose down -v`.

## Run locally without Docker

You need Python 3.11+, Node 18+, and (optionally) a Postgres if you want
to skip the SQLite default.

```bash
# Terminal 1 — backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
uvicorn app.main:app --reload          # http://127.0.0.1:8000/docs

# Terminal 2 — frontend
cd frontend
npm install
npm run dev                            # http://127.0.0.1:5173
```

The first backend start creates `backend/sourcing.db` and seeds it with one
sample event ("Laptop Procurement Q3") and five suppliers/bids.

## Repository layout

```
.
├── backend/                 FastAPI + SQLModel + OR-Tools service
│   ├── app/
│   │   ├── main.py          App factory + lifespan
│   │   ├── database.py
│   │   ├── models.py        SQLModel tables
│   │   ├── schemas.py       Pydantic DTOs
│   │   ├── routes/          One router per resource
│   │   ├── services/        Pure logic — solver, brief parser, run history
│   │   └── tests/           28 pytest tests
│   ├── Dockerfile
│   └── requirements*.txt
├── frontend/                React + TypeScript + Tailwind + Vite UI
│   ├── src/
│   │   ├── api/             axios client per resource
│   │   ├── components/      Layout, Button, Card, Badge, …
│   │   ├── pages/           Dashboard, CreateEvent, EventDetail,
│   │   │                    OptimisationPage (with scenario comparison),
│   │   │                    BriefAssistant
│   │   └── types/
│   ├── Dockerfile           Multi-stage Node-build → nginx serve
│   └── nginx.conf
├── .github/workflows/ci.yml CI: ruff + pytest + frontend typecheck + build
├── docker-compose.yml       db + backend + frontend
└── .env.example
```

## Testing

```bash
# Backend
cd backend && source .venv/bin/activate
ruff check .            # 0 findings
pytest -q               # 28 passed

# Frontend
cd frontend
npm run typecheck       # tsc -b --noEmit
npm run build           # full TS + Vite build
```

The same checks run on every push and pull request via `.github/workflows/ci.yml`.

### What the test suite covers

| Test file | What it asserts |
|-----------|-----------------|
| `test_health.py` | Liveness probe + DB ping |
| `test_events.py` | CRUD + 422 validation |
| `test_suppliers.py` | CRUD + 422 validation |
| `test_bids.py` | CRUD, 404 missing parent, 409 on duplicate, cascade delete |
| `test_optimisation.py` | Solver: cost-minimising baseline, infeasible by capacity, quality floor exclusion, max-suppliers binding |
| `test_briefs.py` | Brief parser: full brief, multi-word category + risk-tolerant, sparse brief with missing fields |
| `test_runs.py` | Per-run overrides don't mutate event, structured-explanation shape (selected/rejected/binding/trade-offs), scenario history list + detail + delete, sustainability math |

## API examples (curl)

The seed event has `id=1`. Replace as needed.

**Create an event**
```bash
curl -X POST http://localhost:8000/api/v1/events \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "Q4 Monitors",
    "category": "IT Hardware",
    "total_demand": 500,
    "max_suppliers": 3,
    "min_quality_score": 75,
    "max_average_risk": 0.4
  }'
```

**Add a supplier**
```bash
curl -X POST http://localhost:8000/api/v1/suppliers \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "Acme Computers",
    "country": "Ireland",
    "risk_score": 0.2,
    "sustainability_score": 80
  }'
```

**Add a bid (event_id + supplier_id from the previous calls)**
```bash
curl -X POST http://localhost:8000/api/v1/bids \
  -H 'Content-Type: application/json' \
  -d '{
    "event_id": 2,
    "supplier_id": 6,
    "unit_price": 350,
    "capacity": 300,
    "lead_time_days": 14,
    "quality_score": 85
  }'
```

**Run the optimiser (baseline scenario)**
```bash
curl -X POST http://localhost:8000/api/v1/events/1/optimise \
  -H 'Content-Type: application/json' \
  -d '{ "label": "Baseline" }'
```

**Run a what-if scenario with tighter risk**
```bash
curl -X POST http://localhost:8000/api/v1/events/1/optimise \
  -H 'Content-Type: application/json' \
  -d '{
    "label": "Tighter risk ceiling",
    "overrides": { "max_average_risk": 0.3 }
  }'
```

**List scenario runs for an event (comparison table data)**
```bash
curl http://localhost:8000/api/v1/events/1/runs
```

**Fetch a single saved scenario in full**
```bash
curl http://localhost:8000/api/v1/runs/1
```

**Parse a plain-English sourcing brief**
```bash
curl -X POST http://localhost:8000/api/v1/briefs/parse \
  -H 'Content-Type: application/json' \
  -d '{ "text": "We need 1000 laptops for Q3. Avoid high-risk suppliers. Max 3 suppliers, quality at least 75." }'
```

## Troubleshooting

**`docker compose up` complains about port 5173, 8000, or 5432.**
Something else on your machine is already using that port. Stop it, or change
the host-side port in [`docker-compose.yml`](docker-compose.yml) (left side
of `5173:80`, etc.).

**Browser shows "Network error" / CORS error.**
The frontend was built pointing at a different backend URL.
Rebuild with the right address:
```bash
docker compose build --build-arg VITE_API_URL=http://localhost:8000 frontend
docker compose up
```
Or set `VITE_API_URL` in `.env` before `docker compose up`.

**`OptimisationResult` schema errors after pulling a new milestone.**
SQLite's `create_all()` doesn't add columns to existing tables. For local
dev (no Alembic yet):
```bash
rm backend/sourcing.db
# or, for Docker:
docker compose down -v && docker compose up --build
```
The seeder will rebuild from scratch.

**`pytest` fails with "ModuleNotFoundError: No module named 'app'".**
Run pytest from `backend/`, not from the repo root. `pyproject.toml` puts
`backend/` on the Python path via `pythonpath = ["."]`.

**VS Code shows "Package … is not installed" hints on `requirements.txt`.**
The workspace's selected Python interpreter is the system Python, not
`backend/.venv/bin/python`. Open the command palette → *Python: Select
Interpreter* → pick the venv. Code runs correctly regardless.

**`ortools` install is slow / fails.**
ortools ships binary wheels for `linux/amd64`, `linux/arm64`, `macos`, and
`windows` on Python 3.11–3.13. On other combinations (e.g. very new
pre-release Pythons), the wheel may not yet exist. Use Python 3.11 to be
safe.

**Frontend Docker build hangs on `npm ci`.**
Older Docker versions on macOS sometimes throttle network in the build
sandbox. Restart Docker Desktop, then `docker compose build --no-cache
frontend`.

## Milestones (for context)

The project was built in five phases, each demoable on its own:

1. **Foundations** — repo scaffolding, FastAPI/Vite hello-world, CI.
2. **Core domain** — SQLModel schema, CRUD for events/suppliers/bids, seed.
3. **Optimisation engine** — OR-Tools CP-SAT model, cost minimisation, basic explanation.
4. **Constraints + multi-objective explainability** — risk/quality/sustainability metrics,
   structured rejection/binding/trade-off explanation, scenario comparison.
5. **UI + docs + DevOps** — full React UI, brief assistant, Docker Compose,
   GitHub Actions, this README. **Currently here.**

Per-service detail lives in [`backend/README.md`](backend/README.md) and
[`frontend/README.md`](frontend/README.md).
