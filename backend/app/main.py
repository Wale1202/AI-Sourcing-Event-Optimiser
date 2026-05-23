"""FastAPI application entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import init_db
from app.routes import bids, events, health, optimisation, suppliers
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
    app.include_router(health.router)
    app.include_router(events.router)
    app.include_router(suppliers.router)
    app.include_router(bids.router)
    app.include_router(optimisation.router)
    return app


app = create_app()
