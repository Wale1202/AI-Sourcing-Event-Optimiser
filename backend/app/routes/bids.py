"""CRUD endpoints for Bid."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session

from app.database import get_session
from app.schemas import BidCreate, BidRead, BidUpdate
from app.services import bid_service
from app.services.bid_service import BidCreateError

router = APIRouter(prefix="/api/v1/bids", tags=["bids"])


_ERROR_TO_HTTP: dict[BidCreateError, tuple[int, str]] = {
    BidCreateError.EVENT_NOT_FOUND: (status.HTTP_404_NOT_FOUND, "Event not found"),
    BidCreateError.SUPPLIER_NOT_FOUND: (status.HTTP_404_NOT_FOUND, "Supplier not found"),
    BidCreateError.DUPLICATE_BID: (
        status.HTTP_409_CONFLICT,
        "A bid already exists for this (event, supplier) pair — update it instead.",
    ),
}


@router.post("", response_model=BidRead, status_code=status.HTTP_201_CREATED)
def create_bid(payload: BidCreate, session: Session = Depends(get_session)) -> BidRead:
    result = bid_service.create(session, payload)
    if result.error is not None:
        http_status, detail = _ERROR_TO_HTTP[result.error]
        raise HTTPException(http_status, detail)
    assert result.bid is not None
    return result.bid  # type: ignore[return-value]


@router.get("", response_model=list[BidRead])
def list_bids(
    event_id: int | None = Query(default=None, description="Filter bids by event"),
    session: Session = Depends(get_session),
) -> list[BidRead]:
    return bid_service.list_all(session, event_id=event_id)  # type: ignore[return-value]


@router.get("/{bid_id}", response_model=BidRead)
def get_bid(bid_id: int, session: Session = Depends(get_session)) -> BidRead:
    bid = bid_service.get(session, bid_id)
    if bid is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bid not found")
    return bid  # type: ignore[return-value]


@router.patch("/{bid_id}", response_model=BidRead)
def update_bid(
    bid_id: int,
    payload: BidUpdate,
    session: Session = Depends(get_session),
) -> BidRead:
    updated = bid_service.update(session, bid_id, payload)
    if updated is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bid not found")
    return updated  # type: ignore[return-value]


@router.delete("/{bid_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_bid(bid_id: int, session: Session = Depends(get_session)):
    if not bid_service.delete(session, bid_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bid not found")
