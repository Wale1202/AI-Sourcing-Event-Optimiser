"""FastAPI application entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.routes import bids, briefs, events, health, optimisation, runs, suppliers
from app.seed import seed_if_empty


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    seed_if_empty()
    yield


def create_app(*, use_lifespan: bool = True) -> FastAPI:
    """Build the FastAPI app.

    ``use_lifespan=False`` is used by tests to avoid touching the on-disk DB
    or running the seeder.
    """
    app = FastAPI(
        title="AI Sourcing Event Optimiser",
        description="Backend API for creating sourcing events, capturing bids, "
                    "and (in a later milestone) running OR-Tools optimisations.",
        version="0.1.0",
        lifespan=lifespan if use_lifespan else None,
    )
    # CORS for the Vite dev server. Tighten this list before deploying.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(events.router)
    app.include_router(suppliers.router)
    app.include_router(bids.router)
    app.include_router(optimisation.router)
    app.include_router(briefs.router)
    app.include_router(runs.router)
    return app


app = create_app()
