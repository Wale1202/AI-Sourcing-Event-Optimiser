"""SQLModel tables for the sourcing domain.

Relationships use ORM-level ``delete-orphan`` cascade so deleting an event
also removes its bids and results, and deleting a supplier removes its bids.

Note: this module deliberately does NOT use ``from __future__ import annotations``
because SQLModel/SQLAlchemy needs to introspect the relationship annotations
at runtime to wire up the mapping.
"""

from datetime import datetime, timezone
from typing import List, Optional


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel


class SourcingEvent(SQLModel, table=True):
    __tablename__ = "sourcing_events"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    category: str
    total_demand: int
    max_suppliers: int
    min_quality_score: float
    max_average_risk: float
    created_at: datetime = Field(default_factory=_utcnow)

    bids: List["Bid"] = Relationship(
        back_populates="event",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    results: List["OptimisationResult"] = Relationship(
        back_populates="event",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class Supplier(SQLModel, table=True):
    __tablename__ = "suppliers"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    country: str
    risk_score: float
    sustainability_score: float

    bids: List["Bid"] = Relationship(
        back_populates="supplier",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class Bid(SQLModel, table=True):
    __tablename__ = "bids"
    # One bid per (event, supplier) pair — suppliers re-submit by updating.
    __table_args__ = (
        UniqueConstraint("event_id", "supplier_id", name="uq_bid_event_supplier"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    event_id: int = Field(foreign_key="sourcing_events.id")
    supplier_id: int = Field(foreign_key="suppliers.id")
    unit_price: float
    capacity: int
    lead_time_days: int
    quality_score: float

    event: Optional["SourcingEvent"] = Relationship(back_populates="bids")
    supplier: Optional["Supplier"] = Relationship(back_populates="bids")


class OptimisationResult(SQLModel, table=True):
    __tablename__ = "optimisation_results"

    id: Optional[int] = Field(default=None, primary_key=True)
    event_id: int = Field(foreign_key="sourcing_events.id")
    total_cost: float
    average_quality: float
    average_risk: float
    explanation: str
    created_at: datetime = Field(default_factory=_utcnow)

    event: Optional["SourcingEvent"] = Relationship(back_populates="results")
