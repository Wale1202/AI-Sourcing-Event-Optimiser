# AI Sourcing Event Optimiser — Backend

FastAPI + SQLModel + SQLite backend for the AI Sourcing Event Optimiser. Provides CRUD for
sourcing events, suppliers, and bids, plus storage for optimisation results (the solver
itself is added in a later milestone).

## Requirements
- Python 3.11+
- pip (or `uv` / `pipx`, optional)

## Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
```

Optional: copy `.env.example` to `.env` to override the database location.

## Run the server

```bash
uvicorn app.main:app --reload
```

The API is then available at:
- Swagger UI: http://127.0.0.1:8000/docs
- ReDoc:      http://127.0.0.1:8000/redoc
- Health:     http://127.0.0.1:8000/api/v1/health

On first start, the app creates `sourcing.db` (SQLite) and seeds one sample event
("Laptop Procurement Q3") with five suppliers and five bids. Subsequent starts skip
seeding if data already exists. Delete `sourcing.db` to reset.

## Run the tests

```bash
pytest
```

Tests use an in-memory SQLite database — they never touch `sourcing.db`.

## Project layout

```
backend/
├── app/
│   ├── main.py            FastAPI app + lifespan (init DB, seed sample data)
│   ├── database.py        SQLModel engine + session dependency
│   ├── models.py          SQLModel tables (SourcingEvent, Supplier, Bid, OptimisationResult)
│   ├── schemas.py         Pydantic request/response DTOs
│   ├── seed.py            Sample-data seeder, idempotent
│   ├── routes/            FastAPI routers, one per resource
│   ├── services/          Pure DB logic (no FastAPI imports)
│   └── tests/             Pytest suite (in-memory DB)
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml         Tool config only (pytest, ruff)
└── .env.example
```

## API surface (v1)

All endpoints are under `/api/v1`.

| Method | Path | Purpose |
| ------ | ---- | ------- |
| GET    | /health | Liveness probe |
| POST   | /events | Create event |
| GET    | /events | List events |
| GET    | /events/{id} | Get event |
| PATCH  | /events/{id} | Update event |
| DELETE | /events/{id} | Delete event (cascades to bids + results) |
| POST   | /suppliers | Create supplier |
| GET    | /suppliers | List suppliers |
| GET    | /suppliers/{id} | Get supplier |
| PATCH  | /suppliers/{id} | Update supplier |
| DELETE | /suppliers/{id} | Delete supplier (cascades to bids) |
| POST   | /bids | Create bid (validates event + supplier exist) |
| GET    | /bids | List bids (optional `?event_id=` filter) |
| GET    | /bids/{id} | Get bid |
| PATCH  | /bids/{id} | Update bid (price/capacity/lead time/quality) |
| DELETE | /bids/{id} | Delete bid |
| POST   | /events/{id}/optimise | Run OR-Tools CP-SAT solver, persist + return the recommended award |

The full schema lives at `/openapi.json` and renders in Swagger at `/docs`.

## Optimisation engine

`app/services/optimisation_service.py` builds an OR-Tools **CP-SAT** model that
chooses how many units to award to each bid so that total cost is minimised
subject to:

1. Σ awarded quantity = event total demand
2. 0 ≤ awarded quantity ≤ bid capacity
3. The number of selected suppliers is ≤ `max_suppliers`
4. Bids whose quality score is below `min_quality_score` are dropped up-front
5. Quantity-weighted average risk ≤ `max_average_risk`

Prices are scaled to integer cents and risk scores to per-mille so the whole
model stays inside CP-SAT's integer domain. Before invoking the solver, the
service runs cheap pre-checks (no bids, capacity shortfall, top-K capacity
shortfall, lowest-possible average risk above the ceiling) so the API can
return a *specific* warning rather than a bare "infeasible".
