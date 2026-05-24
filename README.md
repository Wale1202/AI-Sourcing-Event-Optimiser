# AI Sourcing Event Optimiser

A full-stack procurement optimisation prototype that helps buyers structure
sourcing events, compare supplier bids, and generate award recommendations
based on cost, capacity, quality, risk and sustainability constraints.

It pairs an OR-Tools CP-SAT optimiser with a React dashboard, an explanation
layer that surfaces *why* each supplier was (or wasn't) selected, and a
deterministic Sourcing Brief Assistant that converts plain-English briefs
into draft event fields.

---

## Why I built it

I wanted to understand how optimisation and decision-support software can
support procurement teams. From outside, sourcing looks simple — "pick the
cheapest bid." In practice, buyers face real trade-offs: cost versus risk,
single-supplier discounts versus resilience, low unit price versus quality
and lead time. A small but honest implementation seemed like the best way to
learn both sides of that problem:

- the **optimisation side** — how do you model "max 3 suppliers" alongside
  "average risk ≤ 0.4" without the constraints fighting each other?
- the **product side** — how do you present a recommendation a buyer can
  actually defend to stakeholders?

This project is a portfolio piece, not production software. It deliberately
stops short of multi-tenant auth, real supplier integrations, and audit
logging. What it does try to do well is take a domain problem from a blank
repo to a working stack with tests, docs and CI.

## Key features

- **Sourcing event creation** — define demand, category, constraints
  (max suppliers, min quality score, max average risk).
- **Supplier and bid management** — CRUD with per-event bid uniqueness and
  cascade-delete safety.
- **Constraint-based optimisation** — Google OR-Tools CP-SAT minimises total
  cost subject to demand, capacity, supplier count, quality floor, and a
  quantity-weighted risk ceiling.
- **Scenario comparison** — every run is saved with the exact constraints it
  used; the UI shows total cost, supplier count, average quality, risk and
  sustainability side-by-side, with one-click switching between scenarios.
- **Explainable award recommendations** — each result returns structured
  reasons for selected and rejected suppliers, the binding constraints, and
  the trade-offs the buyer should be aware of (e.g. *"cheapest supplier
  capped by the risk ceiling — solver had to mix in lower-risk suppliers"*).
- **Sourcing Brief Assistant** — a rule-based parser that turns
  *"we need 1000 laptops, avoid high-risk suppliers, max 3, quality ≥ 75"*
  into draft event fields, with explicit confidence notes and a list of
  fields the buyer still has to confirm.
- **API-first backend** — clean REST surface, OpenAPI/Swagger at `/docs`,
  decoupled from any single frontend.
- **Automated tests and CI workflow** — 28 pytest tests covering API,
  optimiser, brief parser and scenario flow; ruff + pytest + frontend
  typecheck/build run on every push and pull request.

## Technical architecture

```
 ┌──────────────────────┐     HTTP /api/v1     ┌────────────────────────────┐
 │ React + TypeScript   │ ───────────────────▶ │ FastAPI backend             │
 │ Vite + Tailwind UI   │                      │ - SQLModel ORM               │
 │ (nginx in Docker,    │ ◀── JSON / CORS ──── │ - OR-Tools CP-SAT solver     │
 │  Vite in local dev)  │                      │ - Rule-based brief parser    │
 └──────────────────────┘                      │ - REST routers per resource  │
                                               └──────────────┬──────────────┘
                                                              │ SQL
                                                              ▼
                                                  ┌────────────────────────┐
                                                  │ Postgres 16   (compose)│
                                                  │ or SQLite     (local)  │
                                                  └────────────────────────┘
```

- **Backend** — Python 3.11, FastAPI, SQLModel (Pydantic v2 + SQLAlchemy 2),
  uvicorn. Routes are thin; services are pure Python with no FastAPI imports,
  so they can be called from tests, the solver, or future workers without
  pulling the HTTP layer.
- **Frontend** — React 18, TypeScript, Vite, Tailwind CSS, React Router,
  axios. One page per route, shared primitives in `components/`, a typed
  API client per resource.
- **Database** — SQLite for local dev (zero setup), Postgres 16 for
  `docker compose` (matches a production shape). The same SQLModel layer
  drives both; only `DATABASE_URL` changes.
- **Optimisation service** ([`backend/app/services/optimisation_service.py`](backend/app/services/optimisation_service.py))
  — wraps the CP-SAT model behind a typed input/output API. Accepts per-run
  constraint overrides so what-if scenarios don't mutate the event itself.
- **Brief parser** ([`backend/app/services/brief_parser.py`](backend/app/services/brief_parser.py))
  — sits behind a `BriefParser` Protocol so an LLM-backed adapter can be
  added later without changing the route, the response shape, or the tests.

Per-service detail is in [`backend/README.md`](backend/README.md) and
[`frontend/README.md`](frontend/README.md).

## Optimisation logic

For each sourcing event we know a total demand **D**, a set of bids (one per
supplier on that event, with unit price, capacity, quality score and lead
time), each supplier's risk and sustainability scores, and the event's
constraints: `max_suppliers`, `min_quality_score`, `max_average_risk`.

For every eligible bid *b* (i.e. one whose quality score clears the floor),
the model has two decision variables:

- **q_b** — the integer quantity awarded to that supplier, between 0 and
  the bid's capacity;
- **y_b** — a boolean: 1 if the bid is selected (any quantity awarded), 0
  otherwise.

It minimises total cost — **Σ q_b · price_b** — subject to:

1. **Demand met exactly.** `Σ q_b = D`.
2. **Capacity per bid.** `0 ≤ q_b ≤ capacity_b` (built into the variable
   domain).
3. **Link q ↔ y.** `q_b ≤ capacity_b · y_b`, so any positive award forces
   the bid to be marked "selected".
4. **Cap on supplier count.** `Σ y_b ≤ max_suppliers`.
5. **Quality floor.** Bids below the floor are pruned up-front and never
   reach the solver.
6. **Average risk ceiling.** `Σ q_b · risk_b ≤ max_average_risk · D`, which
   is exactly *"quantity-weighted average risk ≤ ceiling"*.

Prices are scaled to integer cents and risk scores to per-mille so the whole
model stays inside CP-SAT's integer arithmetic. Before invoking the solver,
cheap pre-checks (no eligible bids, total capacity below demand, top-K
capacity below demand for `max_suppliers`, lowest-possible average risk
above the ceiling) catch the common infeasible cases and return *specific*
warnings rather than a bare "infeasible".

After a solve the service builds a **structured explanation**:

- per-selected-supplier rationale with machine-readable reason codes
  (`lowest_price`, `at_capacity`, `lowest_risk_selected`, …);
- per-rejected-supplier reason (`quality_floor`, `cost_dominated`);
- binding constraints, with a priority-based "most active" pick;
- a heuristic list of trade-offs (e.g. *"cheaper bid X excluded by quality
  floor", "cheapest supplier capped by risk", "supplier at full capacity"*).

Every run — successful or infeasible — is persisted with the constraints it
used and a JSON snapshot of the allocations, so scenarios are reproducible
from a single row.

## AI usage

I built this project with the help of AI coding tools (primarily Claude). I
used them to scaffold boilerplate, work through specific bugs, and draft
documentation — but every piece of generated code was read, tested and
adapted before being committed. The optimisation model, the structured
explanation design, the test scenarios with hand-computed expected values,
the data model, and the product decisions (what to surface, what to skip,
what to call things) are mine.

I treated the AI the way I'd treat a fast pair-programming colleague:
useful for first drafts I can critique, not a substitute for understanding
the code I'm shipping. The bar I settled on was simple — if I couldn't
explain a file on a whiteboard, I rewrote it. That gave me the explanation
layer in particular: most of its design started as my dissatisfaction with
the AI's first draft, which read like a generated narrative rather than
something a buyer could act on.

## What I learned

- **API design has more taste than I expected.** When to use 404 vs. 409,
  how to keep request shapes optional without breaking the body parser, how
  to evolve responses (adding structured fields) without breaking existing
  clients — every one of those decisions is opinionated. Keeping the brief
  parser behind a Protocol was less about the LLM and more about refusing
  to let the route depend on the parser's internals.

- **Optimisation modelling is half maths, half failure-mode design.**
  Translating "average risk ≤ 0.4" into integer CP-SAT arithmetic is the
  easy part. The harder part is what to do when the solver says
  "infeasible". Cheap pre-checks that name the actual binding shortage
  ("eligible capacity 500 vs demand 1000") beat a bare error every time
  and make the model debuggable from the API surface alone.

- **Testing as specification.** Hand-computing expected outputs for the
  optimisation tests caught real regressions in a way "the solver returned
  *something*" never could. Each test reads as a small worked example, so
  the suite doubles as a spec for the model. That paid for itself when I
  refactored the explanation builder — the tests didn't care about
  internals, only the externally-observable contract.

- **Trade-offs.** A lot of the most interesting decisions weren't technical:
  whether `/optimise` should mutate the event (no — overrides are per-run),
  whether infeasible runs should be persisted (yes — "I tried that, it
  didn't work" is data), whether the brief parser should ever guess
  ungrounded values (no — `null` and `missing_fields` are safer). I kept
  choosing the option that let the buyer reverse the decision later.

- **Product thinking.** A cost number isn't an answer; a cost number
  alongside *"the risk ceiling forced 500 units to Globex instead of
  Umbrella"* is. Building the explanation panel taught me the value of an
  optimiser is its interpretability, not its objective value.

- **Responsible AI-assisted development.** Working with AI tools made me
  think harder about what "understanding my own code" means in practice.
  Speed without understanding is a liability; speed with understanding is
  leverage. The difference is whether you can defend the diff.

## Future improvements

- **Real supplier data import** — CSV / Excel upload (supplier master + bid
  sheets) with validation, dry-run preview and per-row error reporting.
- **Authentication and multi-tenant workspaces** — currently single-tenant
  by design; a real version needs auth on the API, per-buyer workspaces,
  and audit logging on every optimisation run.
- **Better natural language parsing** — an LLM-backed `BriefParser`
  (the Protocol is already in place), with the rule-based parser kept as a
  deterministic fallback and a way to compare both outputs side-by-side.
- **Advanced optimisation objectives** — true multi-objective: explicit
  Pareto fronts (cost vs. risk, cost vs. sustainability), lexicographic
  optimisation when objectives are ordered, sensitivity analysis on the
  binding constraints.
- **Role-based buyer/supplier views** — let suppliers submit bids against
  open events themselves; buyers see the consolidated picture and can run
  optimisations as they come in.
- **Deployment to cloud** — managed Postgres + container hosting (Fly.io
  or AWS Fargate) for the backend, Cloudflare Pages or Vercel for the
  frontend, secrets via the platform's secret store rather than env files.
  The Dockerfiles are already production-shaped; the missing pieces are
  CI/CD pipelines and secret management.

---

## Getting started

### With Docker Compose (recommended)

```bash
git clone <this-repo>
cd AI-Sourcing-Event-Optimiser
docker compose up --build
```

The first build takes 1–3 minutes (mostly pulling Postgres and installing
OR-Tools). After that:

| Service  | URL |
|----------|-----|
| Frontend | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| Swagger UI  | http://localhost:8000/docs |
| Postgres | `localhost:5432`, user / pass / db = `sourcing` |

Stop and wipe the database: `docker compose down -v`.

### Without Docker

You'll need Python 3.11+ and Node 18+.

```bash
# Terminal 1 — backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
uvicorn app.main:app --reload                  # http://127.0.0.1:8000/docs

# Terminal 2 — frontend
cd frontend
npm install
npm run dev                                    # http://127.0.0.1:5173
```

The first backend start creates `backend/sourcing.db` (SQLite) and seeds it
with one sample event ("Laptop Procurement Q3"), five suppliers and five
bids — so the dashboard isn't empty on a fresh clone.

## API examples (curl)

The seed event has `id=1`. Adjust ids for the examples below as you create
your own data.

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

**Add a supplier and a bid**
```bash
curl -X POST http://localhost:8000/api/v1/suppliers -H 'Content-Type: application/json' -d '{
    "name": "Acme Computers", "country": "Ireland",
    "risk_score": 0.2, "sustainability_score": 80
  }'

curl -X POST http://localhost:8000/api/v1/bids -H 'Content-Type: application/json' -d '{
    "event_id": 2, "supplier_id": 6,
    "unit_price": 350, "capacity": 300,
    "lead_time_days": 14, "quality_score": 85
  }'
```

**Run the optimiser (baseline + what-if)**
```bash
# Use the event's stored constraints
curl -X POST http://localhost:8000/api/v1/events/1/optimise \
  -H 'Content-Type: application/json' -d '{ "label": "Baseline" }'

# Override the average-risk ceiling for this run only
curl -X POST http://localhost:8000/api/v1/events/1/optimise \
  -H 'Content-Type: application/json' -d '{
    "label": "Tighter risk ceiling",
    "overrides": { "max_average_risk": 0.3 }
  }'
```

**List scenarios for comparison, and fetch a specific run**
```bash
curl http://localhost:8000/api/v1/events/1/runs
curl http://localhost:8000/api/v1/runs/1
```

**Parse a plain-English brief**
```bash
curl -X POST http://localhost:8000/api/v1/briefs/parse \
  -H 'Content-Type: application/json' \
  -d '{ "text": "We need 1000 laptops for Q3. Avoid high-risk suppliers. Max 3 suppliers, quality at least 75." }'
```

## Testing

```bash
# Backend
cd backend && source .venv/bin/activate
ruff check .            # 0 findings
pytest -q --cov=app     # 28 passed, ~95% coverage

# Frontend
cd frontend
npm run typecheck
npm run build
```

The same checks run on every push and pull request via
[`.github/workflows/ci.yml`](.github/workflows/ci.yml).

| Test file | What it asserts |
|-----------|-----------------|
| `test_health.py` | Liveness probe + DB ping |
| `test_events.py` | CRUD + 422 validation |
| `test_suppliers.py` | CRUD + 422 validation |
| `test_bids.py` | CRUD, 404 missing parent, 409 on duplicate, cascade delete |
| `test_optimisation.py` | Solver: cost-minimising baseline, capacity-infeasible, quality floor exclusion, max-suppliers binding |
| `test_briefs.py` | Brief parser: full brief, multi-word category + risk-tolerant, sparse brief with missing fields |
| `test_runs.py` | Per-run overrides don't mutate event, structured explanation shape, scenario history + detail + delete, sustainability math |

## Troubleshooting

**`docker compose up` complains about port 5173, 8000, or 5432.**
Something else is already using that port. Change the host-side port in
[`docker-compose.yml`](docker-compose.yml) (left side of `5173:80`, etc.)
or stop the other service.

**Browser shows a CORS or network error.**
The frontend was built pointing at a different backend URL. Either rebuild
with the right address (`VITE_API_URL=http://localhost:8000 docker compose
up --build`) or set `VITE_API_URL` in `.env`.

**`OptimisationResult` schema errors after pulling a new commit.**
SQLite's `create_all()` doesn't add columns to existing tables. For local
dev, delete `backend/sourcing.db`; for Docker,
`docker compose down -v && docker compose up --build`. The seeder will
rebuild from scratch.

**`pytest` says "ModuleNotFoundError: No module named 'app'".**
Run pytest from `backend/`, not from the repo root. The `pyproject.toml`
in `backend/` adds `backend/` to `pythonpath`.

**VS Code shows "Package … is not installed" hints on `requirements.txt`.**
The workspace interpreter is the system Python, not `backend/.venv/bin/python`.
Open the command palette → *Python: Select Interpreter* → choose the venv.
The code runs correctly regardless.

**`ortools` install is slow or fails.**
OR-Tools ships binary wheels for Python 3.11–3.13 on the major platforms.
On pre-release Python versions wheels may not yet exist — pin to 3.11
(matches the backend Dockerfile).

## Repository layout

```
.
├── backend/                 FastAPI + SQLModel + OR-Tools service
│   ├── app/
│   │   ├── main.py
│   │   ├── database.py
│   │   ├── models.py        SQLModel tables
│   │   ├── schemas.py       Pydantic DTOs
│   │   ├── routes/          one router per resource
│   │   ├── services/        pure logic — solver, brief parser, run history
│   │   └── tests/           28 pytest tests
│   ├── Dockerfile
│   └── requirements*.txt
├── frontend/                React + TypeScript + Tailwind UI
│   ├── src/
│   │   ├── api/             axios client per resource
│   │   ├── components/      Layout, Button, Card, Badge, …
│   │   ├── pages/           Dashboard, CreateEvent, EventDetail,
│   │   │                    OptimisationPage, BriefAssistant
│   │   └── types/
│   ├── Dockerfile           multi-stage Node build → nginx serve
│   └── nginx.conf
├── .github/workflows/ci.yml ruff + pytest + frontend typecheck + build
├── docker-compose.yml       db + backend + frontend
└── .env.example
```
