"""Persistence logic for SourcingEvent. No FastAPI imports here."""

from __future__ import annotations

from sqlmodel import Session, select

from app.models import SourcingEvent
from app.schemas import SourcingEventCreate, SourcingEventUpdate


def create(session: Session, payload: SourcingEventCreate) -> SourcingEvent:
    event = SourcingEvent(**payload.model_dump())
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


def list_all(session: Session) -> list[SourcingEvent]:
    return list(session.exec(select(SourcingEvent).order_by(SourcingEvent.id)).all())


def get(session: Session, event_id: int) -> SourcingEvent | None:
    return session.get(SourcingEvent, event_id)


def update(
    session: Session, event_id: int, payload: SourcingEventUpdate
) -> SourcingEvent | None:
    event = session.get(SourcingEvent, event_id)
    if event is None:
        return None
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(event, key, value)
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


def delete(session: Session, event_id: int) -> bool:
    event = session.get(SourcingEvent, event_id)
    if event is None:
        return False
    session.delete(event)
    session.commit()
    return True
