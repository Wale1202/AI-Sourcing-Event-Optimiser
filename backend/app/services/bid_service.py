"""Persistence logic for Bid.

Bid creation is the one place the service layer enforces a domain rule:
the referenced event and supplier must exist, and (event, supplier) pairs
are unique. Routers translate the structured failures into HTTP responses.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from sqlmodel import Session, select

from app.models import Bid, SourcingEvent, Supplier
from app.schemas import BidCreate, BidUpdate


class BidCreateError(str, Enum):
    EVENT_NOT_FOUND = "event_not_found"
    SUPPLIER_NOT_FOUND = "supplier_not_found"
    DUPLICATE_BID = "duplicate_bid"


@dataclass
class BidCreateResult:
    bid: Bid | None
    error: BidCreateError | None


def create(session: Session, payload: BidCreate) -> BidCreateResult:
    if session.get(SourcingEvent, payload.event_id) is None:
        return BidCreateResult(None, BidCreateError.EVENT_NOT_FOUND)
    if session.get(Supplier, payload.supplier_id) is None:
        return BidCreateResult(None, BidCreateError.SUPPLIER_NOT_FOUND)

    existing = session.exec(
        select(Bid).where(
            Bid.event_id == payload.event_id,
            Bid.supplier_id == payload.supplier_id,
        )
    ).first()
    if existing is not None:
        return BidCreateResult(None, BidCreateError.DUPLICATE_BID)

    bid = Bid(**payload.model_dump())
    session.add(bid)
    session.commit()
    session.refresh(bid)
    return BidCreateResult(bid, None)


def list_all(session: Session, event_id: int | None = None) -> list[Bid]:
    statement = select(Bid).order_by(Bid.id)
    if event_id is not None:
        statement = statement.where(Bid.event_id == event_id)
    return list(session.exec(statement).all())


def get(session: Session, bid_id: int) -> Bid | None:
    return session.get(Bid, bid_id)


def update(session: Session, bid_id: int, payload: BidUpdate) -> Bid | None:
    bid = session.get(Bid, bid_id)
    if bid is None:
        return None
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(bid, key, value)
    session.add(bid)
    session.commit()
    session.refresh(bid)
    return bid


def delete(session: Session, bid_id: int) -> bool:
    bid = session.get(Bid, bid_id)
    if bid is None:
        return False
    session.delete(bid)
    session.commit()
    return True
