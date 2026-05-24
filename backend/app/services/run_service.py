"""Persistence helpers for OptimisationResult — i.e. saved scenarios.

These do not call the solver; they only read/write rows. The solver itself
lives in :mod:`app.services.optimisation_service` and is the only thing that
*creates* rows.
"""

from __future__ import annotations

from sqlmodel import Session, select

from app.models import OptimisationResult, SourcingEvent
from app.schemas import (
    OptimisationRunDetail,
    OptimisationRunSummary,
    StructuredExplanation,
    SupplierAllocation,
)


def list_for_event(session: Session, event_id: int) -> list[OptimisationResult]:
    statement = (
        select(OptimisationResult)
        .where(OptimisationResult.event_id == event_id)
        .order_by(OptimisationResult.created_at.desc())  # type: ignore[union-attr]
    )
    return list(session.exec(statement).all())


def get(session: Session, run_id: int) -> OptimisationResult | None:
    return session.get(OptimisationResult, run_id)


def event_exists(session: Session, event_id: int) -> bool:
    return session.get(SourcingEvent, event_id) is not None


def delete(session: Session, run_id: int) -> bool:
    row = session.get(OptimisationResult, run_id)
    if row is None:
        return False
    session.delete(row)
    session.commit()
    return True


# ---------- DB row → API schema ----------


def to_summary(row: OptimisationResult) -> OptimisationRunSummary:
    return OptimisationRunSummary(
        id=row.id,  # type: ignore[arg-type]
        event_id=row.event_id,
        label=row.label,
        status=row.status,
        total_cost=row.total_cost,
        average_quality=row.average_quality,
        average_risk=row.average_risk,
        average_sustainability=row.average_sustainability,
        suppliers_selected=row.suppliers_selected,
        constraints_used=row.constraints_used or {},
        created_at=row.created_at,
    )


def to_detail(row: OptimisationResult) -> OptimisationRunDetail:
    allocations = [
        SupplierAllocation(**a) for a in (row.allocations_snapshot or [])
    ]
    structured = (
        StructuredExplanation(**row.structured_explanation)
        if row.structured_explanation
        else None
    )
    return OptimisationRunDetail(
        id=row.id,  # type: ignore[arg-type]
        event_id=row.event_id,
        label=row.label,
        status=row.status,
        total_cost=row.total_cost,
        average_quality=row.average_quality,
        average_risk=row.average_risk,
        average_sustainability=row.average_sustainability,
        suppliers_selected=row.suppliers_selected,
        constraints_used=row.constraints_used or {},
        created_at=row.created_at,
        allocations=allocations,
        structured_explanation=structured,
        explanation=row.explanation,
        warnings=row.warnings_snapshot or [],
    )
