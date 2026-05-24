"""POST /events/{event_id}/optimise — runs the CP-SAT solver.

Accepts an optional body with a ``label`` (for tagging scenarios) and
``overrides`` (for what-if scenarios). Both are optional — calling with no
body uses the event's stored constraints.
"""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlmodel import Session

from app.database import get_session
from app.schemas import OptimisationResponse, OptimiseRequest
from app.services import optimisation_service

router = APIRouter(prefix="/api/v1/events", tags=["optimisation"])


@router.post("/{event_id}/optimise", response_model=OptimisationResponse)
def optimise_event(
    event_id: int,
    request: OptimiseRequest | None = Body(default=None),
    session: Session = Depends(get_session),
) -> OptimisationResponse:
    response = optimisation_service.optimise(session, event_id, request)
    if response is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Event not found")
    return response
