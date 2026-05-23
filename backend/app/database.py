"""Database engine, session factory, and FastAPI dependency."""

from __future__ import annotations

import os
from collections.abc import Generator

from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./sourcing.db")

# SQLite needs check_same_thread=False so a session can be used across the
# FastAPI request worker threads.
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, echo=False, connect_args=_connect_args)


# SQLite does not enforce foreign keys by default — turn it on so ORM-level
# cascades behave the same way they will on Postgres later.
@event.listens_for(engine, "connect")
def _enable_sqlite_fks(dbapi_connection, _):  # type: ignore[no-untyped-def]
    if DATABASE_URL.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def init_db() -> None:
    """Create all tables. Safe to call repeatedly."""
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a transactional session."""
    with Session(engine) as session:
        yield session
