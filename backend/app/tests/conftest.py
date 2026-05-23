"""Pytest fixtures.

Every test gets a fresh in-memory SQLite database via a StaticPool so a single
connection is reused across the whole test (otherwise the `:memory:` DB would
vanish between checkouts). The on-disk `sourcing.db` is never touched.
"""

from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.database import get_session
from app.main import create_app


@pytest.fixture()
def session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture()
def client(session: Session) -> Generator[TestClient, None, None]:
    app = create_app(use_lifespan=False)

    def _override_get_session() -> Generator[Session, None, None]:
        yield session

    app.dependency_overrides[get_session] = _override_get_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
