"""Pydantic DTOs for request validation and response serialisation.

These are kept distinct from the SQLModel tables so we can evolve API shapes
independently of storage (e.g. omit ``created_at`` from create requests, add
computed fields on read).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# ---------- SourcingEvent ----------


class SourcingEventCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=100)
    total_demand: int = Field(gt=0)
    max_suppliers: int = Field(gt=0)
    min_quality_score: float = Field(ge=0, le=100)
    max_average_risk: float = Field(ge=0, le=1)


class SourcingEventUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    category: str | None = Field(default=None, min_length=1, max_length=100)
    total_demand: int | None = Field(default=None, gt=0)
    max_suppliers: int | None = Field(default=None, gt=0)
    min_quality_score: float | None = Field(default=None, ge=0, le=100)
    max_average_risk: float | None = Field(default=None, ge=0, le=1)


class SourcingEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    category: str
    total_demand: int
    max_suppliers: int
    min_quality_score: float
    max_average_risk: float
    created_at: datetime


# ---------- Supplier ----------


class SupplierCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    country: str = Field(min_length=1, max_length=100)
    risk_score: float = Field(ge=0, le=1)
    sustainability_score: float = Field(ge=0, le=100)


class SupplierUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    country: str | None = Field(default=None, min_length=1, max_length=100)
    risk_score: float | None = Field(default=None, ge=0, le=1)
    sustainability_score: float | None = Field(default=None, ge=0, le=100)


class SupplierRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    country: str
    risk_score: float
    sustainability_score: float


# ---------- Bid ----------


class BidCreate(BaseModel):
    event_id: int
    supplier_id: int
    unit_price: float = Field(gt=0)
    capacity: int = Field(gt=0)
    lead_time_days: int = Field(ge=0)
    quality_score: float = Field(ge=0, le=100)


class BidUpdate(BaseModel):
    # event_id/supplier_id are immutable once a bid exists — re-create instead.
    unit_price: float | None = Field(default=None, gt=0)
    capacity: int | None = Field(default=None, gt=0)
    lead_time_days: int | None = Field(default=None, ge=0)
    quality_score: float | None = Field(default=None, ge=0, le=100)


class BidRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_id: int
    supplier_id: int
    unit_price: float
    capacity: int
    lead_time_days: int
    quality_score: float


# ---------- OptimisationResult (read-only for now) ----------


class OptimisationResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_id: int
    total_cost: float
    average_quality: float
    average_risk: float
    explanation: str
    created_at: datetime


# ---------- Optimisation run (POST /events/{id}/optimise) ----------


class SupplierAllocation(BaseModel):
    """One line of the recommended award."""

    supplier_id: int
    supplier_name: str
    awarded_quantity: int
    unit_price: float
    total_cost: float  # awarded_quantity * unit_price


# --- Structured explanation pieces (Phase: explainability) ---


class SelectedRationale(BaseModel):
    """Why a supplier ended up in the award."""

    supplier_id: int
    supplier_name: str
    awarded_quantity: int
    rationale: str  # human-readable
    reason_codes: list[str] = Field(default_factory=list)  # machine-readable tags


class RejectedRationale(BaseModel):
    """Why an eligible-by-existence bid was *not* in the award."""

    supplier_id: int
    supplier_name: str
    unit_price: float | None = None
    quality_score: float | None = None
    capacity: int | None = None
    reason: str
    reason_code: str  # "quality_floor" | "cost_dominated" | "risk_dominated" | "max_suppliers_cap"


class BindingConstraintReport(BaseModel):
    """A constraint that ended up active in the optimal solution."""

    name: str  # "demand" | "average_risk" | "max_suppliers" | "bid_capacity" | "quality_floor"
    description: str


class TradeOff(BaseModel):
    """A noteworthy comparison the buyer should be aware of."""

    summary: str
    impact: str  # "high" | "medium" | "low"


class StructuredExplanation(BaseModel):
    """The decomposed explanation rendered by the UI panel-by-panel."""

    headline: str
    selected: list[SelectedRationale] = Field(default_factory=list)
    rejected: list[RejectedRationale] = Field(default_factory=list)
    binding_constraints: list[BindingConstraintReport] = Field(default_factory=list)
    primary_constraint: BindingConstraintReport | None = None
    trade_offs: list[TradeOff] = Field(default_factory=list)


# --- Request shape ---


class ConstraintOverrides(BaseModel):
    """Per-run overrides for what-if scenarios. ``None`` = use event defaults."""

    max_suppliers: int | None = Field(default=None, gt=0)
    min_quality_score: float | None = Field(default=None, ge=0, le=100)
    max_average_risk: float | None = Field(default=None, ge=0, le=1)


class OptimiseRequest(BaseModel):
    """Optional body for ``POST /events/{id}/optimise``.

    Buyers iterate by tweaking constraints — overrides apply only to this
    run, never to the event's persisted defaults.
    """

    label: str | None = Field(default=None, max_length=120)
    overrides: ConstraintOverrides | None = None


class OptimisationResponse(BaseModel):
    """Full response payload for an optimisation run."""

    status: str
    event_id: int
    result_id: int | None = None
    label: str | None = None
    constraints_used: dict[str, float | int] = Field(default_factory=dict)

    allocations: list[SupplierAllocation] = Field(default_factory=list)
    total_cost: float = 0.0
    average_quality: float = 0.0
    average_risk: float = 0.0
    average_sustainability: float = 0.0
    suppliers_selected: int = 0

    explanation: str = ""
    structured_explanation: StructuredExplanation | None = None
    warnings: list[str] = Field(default_factory=list)


# --- Scenario comparison ---


class OptimisationRunSummary(BaseModel):
    """Compact shape used by the scenario comparison table."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    event_id: int
    label: str | None
    status: str
    total_cost: float
    average_quality: float
    average_risk: float
    average_sustainability: float
    suppliers_selected: int
    constraints_used: dict[str, float | int] = Field(default_factory=dict)
    created_at: datetime


class OptimisationRunDetail(OptimisationRunSummary):
    """Single-run detail view: summary + reproduction-ready snapshot."""

    allocations: list[SupplierAllocation] = Field(default_factory=list)
    structured_explanation: StructuredExplanation | None = None
    explanation: str = ""
    warnings: list[str] = Field(default_factory=list)


# ---------- Sourcing Brief Assistant (POST /briefs/parse) ----------


class BriefParseRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5000)


class ExtractedField(BaseModel):
    """One field extracted from a free-text brief, with a brief audit trail."""

    value: int | float | str
    confidence: str  # "high" | "medium" | "low"
    matched_text: str  # the snippet from the original brief that triggered the match


class BriefParseResponse(BaseModel):
    """Result of parsing a free-text sourcing brief.

    Each extracted field is optional — the buyer's brief may simply not mention
    it. ``missing_fields`` lists fields the buyer still has to confirm before
    creating a sourcing event.
    """

    original_text: str
    category: ExtractedField | None = None
    total_demand: ExtractedField | None = None
    max_suppliers: ExtractedField | None = None
    min_quality_score: ExtractedField | None = None
    risk_preference: ExtractedField | None = None
    cost_priority: ExtractedField | None = None
    confidence_notes: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
