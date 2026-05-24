"""Scenario comparison endpoints.

  GET    /api/v1/events/{event_id}/runs   — list runs for one event (summary)
  GET    /api/v1/runs/{run_id}            — full detail for one saved run
  DELETE /api/v1/runs/{run_id}            — drop a saved scenario
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.database import get_session
from app.schemas import OptimisationRunDetail, OptimisationRunSummary
from app.services import run_service

router = APIRouter(tags=["scenarios"])


@router.get(
    "/api/v1/events/{event_id}/runs", response_model=list[OptimisationRunSummary]
)
def list_runs_for_event(
    event_id: int, session: Session = Depends(get_session)
) -> list[OptimisationRunSummary]:
    if not run_service.event_exists(session, event_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Event not found")
    rows = run_service.list_for_event(session, event_id)
    return [run_service.to_summary(r) for r in rows]


@router.get("/api/v1/runs/{run_id}", response_model=OptimisationRunDetail)
def get_run(run_id: int, session: Session = Depends(get_session)) -> OptimisationRunDetail:
    row = run_service.get(session, run_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Run not found")
    return run_service.to_detail(row)


@router.delete(
    "/api/v1/runs/{run_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
def delete_run(run_id: int, session: Session = Depends(get_session)):
    if not run_service.delete(session, run_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Run not found")
