"""OR-Tools CP-SAT model for the supplier-award problem.

Plain-English statement of the model
------------------------------------
For one sourcing event we know:
  - a total demand ``D`` (units we need to buy)
  - a set of bids ``B``; each bid ``b`` belongs to one supplier and carries a
    unit price, a capacity, a quality score, and (via the supplier) a risk
    score and a sustainability score
  - constraints set on the event: ``max_suppliers``, ``min_quality_score``,
    ``max_average_risk`` — any of which may be overridden per run for what-if
    scenarios.

Decision variables (per eligible bid ``b``)
  q_b ∈ Z, 0 ≤ q_b ≤ capacity_b     — quantity awarded
  y_b ∈ {0,1}                       — 1 iff this bid is "selected" (q_b > 0)

Hard constraints
  (1) Demand:      Σ_b q_b = D
  (2) Capacity:    0 ≤ q_b ≤ capacity_b                (built into the domain)
  (3) Link q↔y:   q_b ≤ capacity_b * y_b               (q_b > 0  ⇒  y_b = 1)
  (4) Suppliers:   Σ_b y_b ≤ max_suppliers
  (5) Quality:     bids with quality_b < min_quality_score are dropped up-front
  (6) Average risk:
        Σ_b q_b * risk_b ≤ max_average_risk * D

Objective
  minimise Σ_b q_b * price_b

What's new in this milestone
----------------------------
- Per-run constraint **overrides** so buyers can run what-if scenarios without
  mutating the event.
- Full **structured explanation**: selected-rationale, rejected-rationale,
  binding-constraint detection, and trade-off observations — surfaced as
  typed objects so the UI can render them panel-by-panel.
- **Sustainability** as a first-class metric (quantity-weighted average).
- Every run, success or infeasible, is **persisted** so the scenario
  comparison view never re-solves.
"""

from __future__ import annotations

from dataclasses import dataclass

from ortools.sat.python import cp_model
from sqlmodel import Session, select

from app.models import Bid, OptimisationResult, SourcingEvent, Supplier
from app.schemas import (
    BindingConstraintReport,
    OptimisationResponse,
    OptimiseRequest,
    RejectedRationale,
    SelectedRationale,
    StructuredExplanation,
    SupplierAllocation,
    TradeOff,
)

PRICE_SCALE = 100   # unit_price → integer cents
RISK_SCALE = 1000   # risk_score (0..1) → integer per-mille
SOLVER_TIME_LIMIT_SECONDS = 10.0


@dataclass(frozen=True)
class _BidView:
    """Read-only snapshot of a (bid, supplier) pair."""

    bid_id: int
    supplier_id: int
    supplier_name: str
    unit_price: float
    capacity: int
    lead_time_days: int
    quality_score: float
    risk_score: float
    sustainability_score: float


@dataclass(frozen=True)
class _EffectiveConstraints:
    """Constraints actually applied to a run — event defaults with overrides."""

    total_demand: int
    max_suppliers: int
    min_quality_score: float
    max_average_risk: float

    def as_dict(self) -> dict[str, float | int]:
        return {
            "total_demand": self.total_demand,
            "max_suppliers": self.max_suppliers,
            "min_quality_score": self.min_quality_score,
            "max_average_risk": self.max_average_risk,
        }


# ---------- public entry point ----------


def optimise(
    session: Session,
    event_id: int,
    request: OptimiseRequest | None = None,
) -> OptimisationResponse | None:
    """Run the CP-SAT model for one event.

    Returns:
      - ``None`` if no event with ``event_id`` exists (route turns this into 404)
      - an ``OptimisationResponse`` with ``status="optimal"`` on success
      - an ``OptimisationResponse`` with ``status="infeasible"`` plus warnings
        otherwise
    """
    event = session.get(SourcingEvent, event_id)
    if event is None:
        return None

    effective = _resolve_constraints(event, request)
    bid_views = _load_bid_views(session, event_id)
    eligible, excluded_quality = _filter_by_quality(bid_views, effective.min_quality_score)

    pre_check_warnings = _pre_check(effective, eligible)
    if pre_check_warnings:
        return _persist_infeasible(
            session, event, effective, request, pre_check_warnings, excluded_quality
        )

    model, q_vars, _ = _build_model(effective, eligible)
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = SOLVER_TIME_LIMIT_SECONDS
    status = solver.Solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return _persist_infeasible(
            session, event, effective, request,
            [
                "Solver could not satisfy all constraints — the average-risk "
                "ceiling is the most likely cause given the eligible bids.",
            ],
            excluded_quality,
        )

    allocations = _extract_allocations(eligible, q_vars, solver)
    total_cost = sum(a.total_cost for a in allocations)
    average_quality = _weighted_average(
        allocations, eligible, attr="quality_score", demand=effective.total_demand
    )
    average_risk = _weighted_average(
        allocations, eligible, attr="risk_score", demand=effective.total_demand
    )
    average_sustainability = _weighted_average(
        allocations, eligible, attr="sustainability_score", demand=effective.total_demand
    )

    structured = _build_structured_explanation(
        effective=effective,
        eligible=eligible,
        excluded_quality=excluded_quality,
        allocations=allocations,
        average_risk=average_risk,
    )
    legacy_text = _render_legacy_explanation(
        structured, total_cost, average_quality, average_risk, average_sustainability
    )

    result_row = OptimisationResult(
        event_id=event.id,  # type: ignore[arg-type]
        label=(request.label if request else None) or None,
        status="optimal",
        total_cost=round(total_cost, 2),
        average_quality=round(average_quality, 4),
        average_risk=round(average_risk, 4),
        average_sustainability=round(average_sustainability, 4),
        suppliers_selected=len(allocations),
        explanation=legacy_text,
        constraints_used=effective.as_dict(),
        allocations_snapshot=[a.model_dump() for a in allocations],
        structured_explanation=structured.model_dump(),
        warnings_snapshot=[],
    )
    session.add(result_row)
    session.commit()
    session.refresh(result_row)

    return OptimisationResponse(
        status="optimal",
        event_id=event.id,  # type: ignore[arg-type]
        result_id=result_row.id,
        label=result_row.label,
        constraints_used=effective.as_dict(),
        allocations=allocations,
        total_cost=round(total_cost, 2),
        average_quality=round(average_quality, 4),
        average_risk=round(average_risk, 4),
        average_sustainability=round(average_sustainability, 4),
        suppliers_selected=len(allocations),
        explanation=legacy_text,
        structured_explanation=structured,
        warnings=[],
    )


# ---------- constraint resolution + data load ----------


def _resolve_constraints(
    event: SourcingEvent, request: OptimiseRequest | None
) -> _EffectiveConstraints:
    """Apply any per-run overrides on top of the event defaults."""
    overrides = request.overrides if request and request.overrides else None
    return _EffectiveConstraints(
        total_demand=event.total_demand,
        max_suppliers=(
            overrides.max_suppliers
            if overrides and overrides.max_suppliers is not None
            else event.max_suppliers
        ),
        min_quality_score=(
            overrides.min_quality_score
            if overrides and overrides.min_quality_score is not None
            else event.min_quality_score
        ),
        max_average_risk=(
            overrides.max_average_risk
            if overrides and overrides.max_average_risk is not None
            else event.max_average_risk
        ),
    )


def _load_bid_views(session: Session, event_id: int) -> list[_BidView]:
    bids = list(session.exec(select(Bid).where(Bid.event_id == event_id)).all())
    views: list[_BidView] = []
    for b in bids:
        supplier = session.get(Supplier, b.supplier_id)
        if supplier is None:
            continue
        views.append(
            _BidView(
                bid_id=b.id,  # type: ignore[arg-type]
                supplier_id=supplier.id,  # type: ignore[arg-type]
                supplier_name=supplier.name,
                unit_price=b.unit_price,
                capacity=b.capacity,
                lead_time_days=b.lead_time_days,
                quality_score=b.quality_score,
                risk_score=supplier.risk_score,
                sustainability_score=supplier.sustainability_score,
            )
        )
    return views


def _filter_by_quality(
    bids: list[_BidView], min_quality: float
) -> tuple[list[_BidView], list[_BidView]]:
    eligible = [b for b in bids if b.quality_score >= min_quality]
    excluded = [b for b in bids if b.quality_score < min_quality]
    return eligible, excluded


# ---------- pre-checks ----------


def _pre_check(
    effective: _EffectiveConstraints, eligible: list[_BidView]
) -> list[str]:
    warnings: list[str] = []

    if not eligible:
        warnings.append(
            "No bids meet the quality floor "
            f"(min_quality_score={effective.min_quality_score})."
        )
        return warnings

    total_capacity = sum(b.capacity for b in eligible)
    if total_capacity < effective.total_demand:
        warnings.append(
            f"Total eligible supplier capacity ({total_capacity}) is less than "
            f"the event demand ({effective.total_demand})."
        )

    top_k = sorted(eligible, key=lambda x: -x.capacity)[: effective.max_suppliers]
    top_k_capacity = sum(b.capacity for b in top_k)
    if top_k_capacity < effective.total_demand:
        warnings.append(
            f"With max_suppliers={effective.max_suppliers}, the largest "
            f"{effective.max_suppliers} eligible bid(s) only cover "
            f"{top_k_capacity} units — short of the {effective.total_demand} required."
        )

    best_risk = _best_case_average_risk(eligible, effective.total_demand)
    if best_risk is not None and best_risk > effective.max_average_risk + 1e-9:
        warnings.append(
            f"Even using the lowest-risk eligible suppliers, average risk would "
            f"be {best_risk:.3f} — above the ceiling of {effective.max_average_risk}."
        )

    return warnings


def _best_case_average_risk(eligible: list[_BidView], demand: int) -> float | None:
    remaining = demand
    weighted = 0.0
    for b in sorted(eligible, key=lambda x: x.risk_score):
        if remaining <= 0:
            break
        take = min(b.capacity, remaining)
        weighted += take * b.risk_score
        remaining -= take
    if remaining > 0:
        return None
    return weighted / demand


# ---------- CP-SAT model ----------


def _build_model(
    effective: _EffectiveConstraints, eligible: list[_BidView]
) -> tuple[cp_model.CpModel, dict[int, cp_model.IntVar], dict[int, cp_model.IntVar]]:
    model = cp_model.CpModel()

    q_vars: dict[int, cp_model.IntVar] = {}
    y_vars: dict[int, cp_model.IntVar] = {}
    for b in eligible:
        q_vars[b.bid_id] = model.NewIntVar(0, b.capacity, f"q_{b.bid_id}")
        y_vars[b.bid_id] = model.NewBoolVar(f"y_{b.bid_id}")
        model.Add(q_vars[b.bid_id] <= b.capacity * y_vars[b.bid_id])

    model.Add(sum(q_vars[b.bid_id] for b in eligible) == effective.total_demand)
    model.Add(sum(y_vars[b.bid_id] for b in eligible) <= effective.max_suppliers)

    risk_scaled = {b.bid_id: round(b.risk_score * RISK_SCALE) for b in eligible}
    max_risk_scaled = round(effective.max_average_risk * RISK_SCALE)
    model.Add(
        sum(q_vars[b.bid_id] * risk_scaled[b.bid_id] for b in eligible)
        <= max_risk_scaled * effective.total_demand
    )

    price_cents = {b.bid_id: round(b.unit_price * PRICE_SCALE) for b in eligible}
    model.Minimize(sum(q_vars[b.bid_id] * price_cents[b.bid_id] for b in eligible))

    return model, q_vars, y_vars


# ---------- solution extraction ----------


def _extract_allocations(
    eligible: list[_BidView],
    q_vars: dict[int, cp_model.IntVar],
    solver: cp_model.CpSolver,
) -> list[SupplierAllocation]:
    allocations: list[SupplierAllocation] = []
    for b in eligible:
        qty = int(solver.Value(q_vars[b.bid_id]))
        if qty <= 0:
            continue
        allocations.append(
            SupplierAllocation(
                supplier_id=b.supplier_id,
                supplier_name=b.supplier_name,
                awarded_quantity=qty,
                unit_price=b.unit_price,
                total_cost=round(qty * b.unit_price, 2),
            )
        )
    allocations.sort(key=lambda a: a.unit_price)
    return allocations


def _weighted_average(
    allocations: list[SupplierAllocation],
    eligible: list[_BidView],
    *,
    attr: str,
    demand: int,
) -> float:
    if demand <= 0:
        return 0.0
    by_supplier = {b.supplier_id: getattr(b, attr) for b in eligible}
    total = sum(
        a.awarded_quantity * by_supplier[a.supplier_id] for a in allocations
    )
    return total / demand


# ---------- structured explanation ----------


def _build_structured_explanation(
    *,
    effective: _EffectiveConstraints,
    eligible: list[_BidView],
    excluded_quality: list[_BidView],
    allocations: list[SupplierAllocation],
    average_risk: float,
) -> StructuredExplanation:
    selected = _build_selected_rationale(eligible, allocations)
    rejected = _build_rejected_rationale(eligible, excluded_quality, allocations, effective)
    binding = _detect_binding_constraints(
        eligible, allocations, effective, average_risk, excluded_quality
    )
    primary = _pick_primary_constraint(binding)
    trade_offs = _detect_trade_offs(
        eligible, excluded_quality, allocations, effective, average_risk
    )
    headline = _build_headline(allocations, effective)
    return StructuredExplanation(
        headline=headline,
        selected=selected,
        rejected=rejected,
        binding_constraints=binding,
        primary_constraint=primary,
        trade_offs=trade_offs,
    )


def _build_selected_rationale(
    eligible: list[_BidView], allocations: list[SupplierAllocation]
) -> list[SelectedRationale]:
    if not allocations:
        return []
    bid_by_supplier = {b.supplier_id: b for b in eligible}
    min_eligible_price = min(b.unit_price for b in eligible)
    max_quality_selected = max(
        bid_by_supplier[a.supplier_id].quality_score for a in allocations
    )
    min_risk_selected = min(
        bid_by_supplier[a.supplier_id].risk_score for a in allocations
    )

    out: list[SelectedRationale] = []
    for a in allocations:
        bid = bid_by_supplier[a.supplier_id]
        reasons: list[str] = []
        codes: list[str] = []

        if bid.unit_price == min_eligible_price:
            reasons.append(f"lowest unit price ({bid.unit_price:.2f})")
            codes.append("lowest_price")
        if len(allocations) > 1 and bid.quality_score == max_quality_selected:
            reasons.append(
                f"highest quality among awarded ({bid.quality_score:g})"
            )
            codes.append("highest_quality_selected")
        if len(allocations) > 1 and bid.risk_score == min_risk_selected:
            reasons.append(
                f"lowest risk among awarded ({bid.risk_score:.2f})"
            )
            codes.append("lowest_risk_selected")
        if a.awarded_quantity == bid.capacity:
            reasons.append("awarded at full capacity")
            codes.append("at_capacity")
        if not reasons:
            reasons.append("fills remaining demand within constraints")
            codes.append("fills_remaining")

        rationale = "; ".join(reasons)
        rationale = rationale[0].upper() + rationale[1:] + "."
        out.append(
            SelectedRationale(
                supplier_id=a.supplier_id,
                supplier_name=a.supplier_name,
                awarded_quantity=a.awarded_quantity,
                rationale=rationale,
                reason_codes=codes,
            )
        )
    return out


def _build_rejected_rationale(
    eligible: list[_BidView],
    excluded_quality: list[_BidView],
    allocations: list[SupplierAllocation],
    effective: _EffectiveConstraints,
) -> list[RejectedRationale]:
    awarded_ids = {a.supplier_id for a in allocations}
    out: list[RejectedRationale] = []

    for bid in excluded_quality:
        out.append(
            RejectedRationale(
                supplier_id=bid.supplier_id,
                supplier_name=bid.supplier_name,
                unit_price=bid.unit_price,
                quality_score=bid.quality_score,
                capacity=bid.capacity,
                reason=(
                    f"Quality score {bid.quality_score:g} is below the floor of "
                    f"{effective.min_quality_score:g}."
                ),
                reason_code="quality_floor",
            )
        )

    for bid in eligible:
        if bid.supplier_id in awarded_ids:
            continue
        out.append(
            RejectedRationale(
                supplier_id=bid.supplier_id,
                supplier_name=bid.supplier_name,
                unit_price=bid.unit_price,
                quality_score=bid.quality_score,
                capacity=bid.capacity,
                reason=(
                    "Cheaper allocations covered demand within the risk and "
                    "supplier-count constraints."
                ),
                reason_code="cost_dominated",
            )
        )
    return out


def _detect_binding_constraints(
    eligible: list[_BidView],
    allocations: list[SupplierAllocation],
    effective: _EffectiveConstraints,
    average_risk: float,
    excluded_quality: list[_BidView],
) -> list[BindingConstraintReport]:
    binding: list[BindingConstraintReport] = []
    bid_by_supplier = {b.supplier_id: b for b in eligible}

    binding.append(
        BindingConstraintReport(
            name="demand",
            description=(
                f"Total demand of {effective.total_demand} units must be met exactly."
            ),
        )
    )

    if allocations and abs(average_risk - effective.max_average_risk) < 1e-3:
        binding.append(
            BindingConstraintReport(
                name="average_risk",
                description=(
                    f"Quantity-weighted average risk is at the ceiling "
                    f"({effective.max_average_risk:g}) — shaped the supplier mix."
                ),
            )
        )

    if (
        allocations
        and len(allocations) == effective.max_suppliers
        and effective.max_suppliers > 0
    ):
        binding.append(
            BindingConstraintReport(
                name="max_suppliers",
                description=(
                    f"Used {effective.max_suppliers} supplier(s) — the cap allowed by max_suppliers."
                ),
            )
        )

    capacity_capped = [
        a
        for a in allocations
        if a.supplier_id in bid_by_supplier
        and a.awarded_quantity == bid_by_supplier[a.supplier_id].capacity
    ]
    if capacity_capped:
        names = ", ".join(a.supplier_name for a in capacity_capped)
        binding.append(
            BindingConstraintReport(
                name="bid_capacity",
                description=f"Awarded at full capacity: {names}.",
            )
        )

    if excluded_quality:
        binding.append(
            BindingConstraintReport(
                name="quality_floor",
                description=(
                    f"Excluded {len(excluded_quality)} bid(s) under the quality floor "
                    f"of {effective.min_quality_score:g}."
                ),
            )
        )

    return binding


def _pick_primary_constraint(
    binding: list[BindingConstraintReport],
) -> BindingConstraintReport | None:
    """The constraint that most shaped the allocation, by domain priority."""
    priority = ["average_risk", "max_suppliers", "bid_capacity", "quality_floor", "demand"]
    by_name = {b.name: b for b in binding}
    for name in priority:
        if name in by_name:
            return by_name[name]
    return None


def _detect_trade_offs(
    eligible: list[_BidView],
    excluded_quality: list[_BidView],
    allocations: list[SupplierAllocation],
    effective: _EffectiveConstraints,
    average_risk: float,
) -> list[TradeOff]:
    """Heuristic observations a buyer should be aware of."""
    out: list[TradeOff] = []
    if not allocations:
        return out

    bid_by_supplier = {b.supplier_id: b for b in eligible}
    awarded_ids = {a.supplier_id for a in allocations}
    max_allocation_price = max(a.unit_price for a in allocations)
    cheapest_bid = min(eligible, key=lambda b: b.unit_price) if eligible else None

    # 1. A quality-excluded bid would have been cheaper than the priciest selection.
    for bid in excluded_quality:
        if bid.unit_price < max_allocation_price:
            out.append(
                TradeOff(
                    summary=(
                        f"{bid.supplier_name} at {bid.unit_price:.2f}/unit would have been "
                        f"cheaper than the most expensive selected supplier "
                        f"({max_allocation_price:.2f}), but is excluded by the quality "
                        f"floor ({bid.quality_score:g} < {effective.min_quality_score:g})."
                    ),
                    impact="medium",
                )
            )

    # 2. Risk ceiling capped the cheapest supplier.
    if cheapest_bid and abs(average_risk - effective.max_average_risk) < 1e-3:
        cheapest_alloc = next(
            (a for a in allocations if a.supplier_id == cheapest_bid.supplier_id),
            None,
        )
        if cheapest_alloc and cheapest_alloc.awarded_quantity < cheapest_bid.capacity:
            out.append(
                TradeOff(
                    summary=(
                        f"Cheapest supplier {cheapest_bid.supplier_name} at "
                        f"{cheapest_bid.unit_price:.2f}/unit could not be fully utilised — "
                        f"its risk score ({cheapest_bid.risk_score:.2f}) is above the "
                        f"average-risk ceiling ({effective.max_average_risk:g}), so the "
                        f"solver mixed in lower-risk suppliers."
                    ),
                    impact="high",
                )
            )

    # 3. Awarded at full capacity — informational.
    for a in allocations:
        bid = bid_by_supplier.get(a.supplier_id)
        if bid and a.awarded_quantity == bid.capacity:
            out.append(
                TradeOff(
                    summary=(
                        f"{a.supplier_name} was awarded its full capacity of "
                        f"{bid.capacity} units — raising this cap could lower total cost."
                    ),
                    impact="low",
                )
            )

    # 4. max_suppliers cap forced consolidation.
    if len(allocations) == effective.max_suppliers:
        cheaper_unselected = [
            b for b in eligible
            if b.supplier_id not in awarded_ids and b.unit_price < max_allocation_price
        ]
        if cheaper_unselected:
            cheapest_unselected = min(cheaper_unselected, key=lambda b: b.unit_price)
            out.append(
                TradeOff(
                    summary=(
                        f"Supplier-count cap of {effective.max_suppliers} forced "
                        f"consolidation — {cheapest_unselected.supplier_name} at "
                        f"{cheapest_unselected.unit_price:.2f}/unit could have lowered cost "
                        f"if the cap were higher."
                    ),
                    impact="medium",
                )
            )

    return out


def _build_headline(
    allocations: list[SupplierAllocation], effective: _EffectiveConstraints
) -> str:
    if not allocations:
        return "No award produced under the current constraints."
    n = len(allocations)
    return (
        f"Awarded {n} supplier{'s' if n != 1 else ''} for {effective.total_demand} units "
        f"under: max suppliers ≤ {effective.max_suppliers}, "
        f"quality ≥ {effective.min_quality_score:g}, "
        f"average risk ≤ {effective.max_average_risk:g}."
    )


def _render_legacy_explanation(
    structured: StructuredExplanation,
    total_cost: float,
    average_quality: float,
    average_risk: float,
    average_sustainability: float,
) -> str:
    """Flatten the structured explanation into a single text block for the
    backwards-compatible ``explanation`` field."""
    lines = [structured.headline, ""]
    if structured.selected:
        lines.append("Selected suppliers:")
        for s in structured.selected:
            lines.append(
                f"  - {s.supplier_name}: {s.awarded_quantity} units — {s.rationale}"
            )
        lines.append("")
    quality_excluded = [r for r in structured.rejected if r.reason_code == "quality_floor"]
    if quality_excluded:
        names = ", ".join(
            f"{r.supplier_name} (quality {r.quality_score:g})" for r in quality_excluded
        )
        lines.append(f"Excluded by quality floor: {names}.")
        lines.append("")
    if structured.primary_constraint:
        lines.append(
            f"Most-active constraint: {structured.primary_constraint.description}"
        )
        lines.append("")
    if structured.trade_offs:
        lines.append("Trade-offs:")
        for t in structured.trade_offs:
            lines.append(f"  - [{t.impact}] {t.summary}")
        lines.append("")
    lines.append(
        f"Totals: cost {total_cost:.2f}, weighted quality {average_quality:.2f}, "
        f"weighted risk {average_risk:.3f}, "
        f"weighted sustainability {average_sustainability:.2f}."
    )
    return "\n".join(lines)


# ---------- infeasible path (persisted) ----------


def _persist_infeasible(
    session: Session,
    event: SourcingEvent,
    effective: _EffectiveConstraints,
    request: OptimiseRequest | None,
    warnings: list[str],
    excluded_quality: list[_BidView],
) -> OptimisationResponse:
    explanation_lines = [
        "Optimisation could not produce an allocation for this event.",
        "",
        "Reasons:",
        *[f"  - {w}" for w in warnings],
    ]
    if excluded_quality:
        names = ", ".join(
            f"{b.supplier_name} (quality {b.quality_score:g})" for b in excluded_quality
        )
        explanation_lines.append("")
        explanation_lines.append(
            f"Excluded by quality floor (min {effective.min_quality_score:g}): {names}."
        )
    explanation = "\n".join(explanation_lines)

    structured = StructuredExplanation(
        headline="Infeasible under the current constraints.",
        selected=[],
        rejected=[
            RejectedRationale(
                supplier_id=b.supplier_id,
                supplier_name=b.supplier_name,
                unit_price=b.unit_price,
                quality_score=b.quality_score,
                capacity=b.capacity,
                reason=(
                    f"Quality score {b.quality_score:g} is below the floor of "
                    f"{effective.min_quality_score:g}."
                ),
                reason_code="quality_floor",
            )
            for b in excluded_quality
        ],
        binding_constraints=[],
        primary_constraint=None,
        trade_offs=[],
    )

    result_row = OptimisationResult(
        event_id=event.id,  # type: ignore[arg-type]
        label=(request.label if request else None) or None,
        status="infeasible",
        total_cost=0.0,
        average_quality=0.0,
        average_risk=0.0,
        average_sustainability=0.0,
        suppliers_selected=0,
        explanation=explanation,
        constraints_used=effective.as_dict(),
        allocations_snapshot=[],
        structured_explanation=structured.model_dump(),
        warnings_snapshot=warnings,
    )
    session.add(result_row)
    session.commit()
    session.refresh(result_row)

    return OptimisationResponse(
        status="infeasible",
        event_id=event.id,  # type: ignore[arg-type]
        result_id=result_row.id,
        label=result_row.label,
        constraints_used=effective.as_dict(),
        allocations=[],
        total_cost=0.0,
        average_quality=0.0,
        average_risk=0.0,
        average_sustainability=0.0,
        suppliers_selected=0,
        explanation=explanation,
        structured_explanation=structured,
        warnings=warnings,
    )
