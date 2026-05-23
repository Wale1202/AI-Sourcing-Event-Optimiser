"""POST /events/{event_id}/optimise — runs the CP-SAT solver."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.database import get_session
from app.schemas import OptimisationResponse
from app.services import optimisation_service

router = APIRouter(prefix="/api/v1/events", tags=["optimisation"])


@router.post("/{event_id}/optimise", response_model=OptimisationResponse)
def optimise_event(
    event_id: int, session: Session = Depends(get_session)
) -> OptimisationResponse:
    response = optimisation_service.optimise(session, event_id)
    if response is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Event not found")
    return response
