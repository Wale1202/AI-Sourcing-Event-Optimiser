"""SQLModel tables for the sourcing domain.

Relationships use ORM-level ``delete-orphan`` cascade so deleting an event
also removes its bids and results, and deleting a supplier removes its bids.

Note: this module deliberately does NOT use ``from __future__ import annotations``
because SQLModel/SQLAlchemy needs to introspect the relationship annotations
at runtime to wire up the mapping.
"""

from datetime import UTC, datetime
from typing import Any, Optional

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel


def _utcnow() -> datetime:
    return datetime.now(UTC)


class SourcingEvent(SQLModel, table=True):
    __tablename__ = "sourcing_events"

    id: int | None = Field(default=None, primary_key=True)
    name: str
    category: str
    total_demand: int
    max_suppliers: int
    min_quality_score: float
    max_average_risk: float
    created_at: datetime = Field(default_factory=_utcnow)

    bids: list["Bid"] = Relationship(
        back_populates="event",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    results: list["OptimisationResult"] = Relationship(
        back_populates="event",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class Supplier(SQLModel, table=True):
    __tablename__ = "suppliers"

    id: int | None = Field(default=None, primary_key=True)
    name: str
    country: str
    risk_score: float
    sustainability_score: float

    bids: list["Bid"] = Relationship(
        back_populates="supplier",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class Bid(SQLModel, table=True):
    __tablename__ = "bids"
    # One bid per (event, supplier) pair — suppliers re-submit by updating.
    __table_args__ = (
        UniqueConstraint("event_id", "supplier_id", name="uq_bid_event_supplier"),
    )

    id: int | None = Field(default=None, primary_key=True)
    event_id: int = Field(foreign_key="sourcing_events.id")
    supplier_id: int = Field(foreign_key="suppliers.id")
    unit_price: float
    capacity: int
    lead_time_days: int
    quality_score: float

    event: Optional["SourcingEvent"] = Relationship(back_populates="bids")
    supplier: Optional["Supplier"] = Relationship(back_populates="bids")


class OptimisationResult(SQLModel, table=True):
    """One persisted optimisation *scenario* run.

    Stores both the aggregate metrics and a JSON snapshot of the allocations,
    the constraints used (possibly overridden from the event defaults), and
    the structured explanation — so scenarios are independently reproducible
    and the comparison table never needs to re-solve.
    """

    __tablename__ = "optimisation_results"

    id: int | None = Field(default=None, primary_key=True)
    event_id: int = Field(foreign_key="sourcing_events.id")
    label: str | None = Field(default=None, max_length=120)
    status: str = "optimal"  # "optimal" | "infeasible"

    total_cost: float = 0.0
    average_quality: float = 0.0
    average_risk: float = 0.0
    average_sustainability: float = 0.0
    suppliers_selected: int = 0

    explanation: str = ""  # human-readable fallback text

    # JSON snapshots so each run is fully reproducible from its row alone.
    constraints_used: dict[str, Any] | None = Field(
        default=None, sa_column=Column(JSON)
    )
    allocations_snapshot: list[dict[str, Any]] | None = Field(
        default=None, sa_column=Column(JSON)
    )
    structured_explanation: dict[str, Any] | None = Field(
        default=None, sa_column=Column(JSON)
    )
    warnings_snapshot: list[str] | None = Field(
        default=None, sa_column=Column(JSON)
    )

    created_at: datetime = Field(default_factory=_utcnow)

    event: Optional["SourcingEvent"] = Relationship(back_populates="results")
