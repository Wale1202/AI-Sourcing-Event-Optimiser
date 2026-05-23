"""CRUD endpoints for SourcingEvent."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.database import get_session
from app.schemas import SourcingEventCreate, SourcingEventRead, SourcingEventUpdate
from app.services import event_service

router = APIRouter(prefix="/api/v1/events", tags=["events"])


@router.post("", response_model=SourcingEventRead, status_code=status.HTTP_201_CREATED)
def create_event(
    payload: SourcingEventCreate, session: Session = Depends(get_session)
) -> SourcingEventRead:
    return event_service.create(session, payload)  # type: ignore[return-value]


@router.get("", response_model=list[SourcingEventRead])
def list_events(session: Session = Depends(get_session)) -> list[SourcingEventRead]:
    return event_service.list_all(session)  # type: ignore[return-value]


@router.get("/{event_id}", response_model=SourcingEventRead)
def get_event(event_id: int, session: Session = Depends(get_session)) -> SourcingEventRead:
    event = event_service.get(session, event_id)
    if event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Event not found")
    return event  # type: ignore[return-value]


@router.patch("/{event_id}", response_model=SourcingEventRead)
def update_event(
    event_id: int,
    payload: SourcingEventUpdate,
    session: Session = Depends(get_session),
) -> SourcingEventRead:
    updated = event_service.update(session, event_id, payload)
    if updated is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Event not found")
    return updated  # type: ignore[return-value]


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_event(event_id: int, session: Session = Depends(get_session)):
    if not event_service.delete(session, event_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Event not found")
