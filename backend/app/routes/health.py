"""Liveness endpoint. Also pings the DB so a broken DATABASE_URL fails loudly."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlmodel import Session

from app.database import get_session

router = APIRouter(prefix="/api/v1", tags=["health"])


@router.get("/health")
def health(session: Session = Depends(get_session)) -> dict[str, str]:
    session.exec(text("SELECT 1"))  # type: ignore[arg-type]
    return {"status": "ok"}
