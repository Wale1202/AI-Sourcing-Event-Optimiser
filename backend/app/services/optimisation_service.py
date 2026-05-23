"""OR-Tools CP-SAT model for the supplier-award problem.

Plain-English statement of the model
------------------------------------
For one sourcing event we know:
  - a total demand ``D`` (units we need to buy)
  - a set of bids ``B``; each bid ``b`` belongs to one supplier and carries a
    unit price, a capacity, a quality score, and (via the supplier) a risk
    score
  - constraints set on the event: ``max_suppliers``, ``min_quality_score``,
    ``max_average_risk``

We want to decide, for every bid, how many units to award to that bid. Call
that quantity ``q_b``. Total cost is the sum of ``q_b * price_b`` and we want
to minimise it.

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
      This is exactly "weighted-by-quantity average risk ≤ threshold", because
      Σ_b q_b = D from (1).

Objective
  minimise Σ_b q_b * price_b

Why CP-SAT and not a linear MIP?
  Constraint (3) is an indicator constraint that couples an integer variable
  to a boolean — exactly what CP-SAT is good at. CP-SAT also handles all our
  variables natively in integers (we scale prices to cents and risk to ‰).

Infeasibility diagnosis
  Before invoking the solver we run cheap pre-checks (no eligible bids, total
  capacity below demand, top-K capacity below demand for max_suppliers,
  best-case risk above the threshold) so the API can return a *specific*
  warning instead of a bare "infeasible".
"""

from __future__ import annotations

from dataclasses import dataclass

from ortools.sat.python import cp_model
from sqlmodel import Session, select

from app.models import Bid, OptimisationResult, SourcingEvent, Supplier
from app.schemas import OptimisationResponse, SupplierAllocation

# Scaling factors used to convert float inputs into the integer arithmetic
# CP-SAT expects. Keep them as module constants so they are explicit.
PRICE_SCALE = 100   # unit_price → integer cents
RISK_SCALE = 1000   # risk_score (0..1) → integer per-mille (0..1000)

# Cap solve time so a misconfigured event never blocks the API thread.
SOLVER_TIME_LIMIT_SECONDS = 10.0


@dataclass(frozen=True)
class _BidView:
    """Read-only snapshot of a (bid, supplier) pair, easier to pass around
    than two SQLModel rows. Created once per call to ``optimise``."""

    bid_id: int
    supplier_id: int
    supplier_name: str
    unit_price: float
    capacity: int
    lead_time_days: int
    quality_score: float
    risk_score: float


# ---------- public entry point ----------


def optimise(session: Session, event_id: int) -> OptimisationResponse | None:
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

    bid_views = _load_bid_views(session, event_id)

    # Step 1: drop bids that fail the quality floor — they cannot win, so the
    # solver should never see them.
    eligible, excluded_quality = _filter_by_quality(bid_views, event.min_quality_score)

    # Step 2: cheap structural checks before invoking the solver. Each one
    # explains *why* the event is impossible, which beats a generic message.
    pre_check_warnings = _pre_check(event, eligible)
    if pre_check_warnings:
        return _infeasible_response(event, pre_check_warnings, excluded_quality)

    # Step 3: build the model and solve.
    model, q_vars, y_vars = _build_model(event, eligible)
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = SOLVER_TIME_LIMIT_SECONDS
    status = solver.Solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        # Pre-checks said it should be feasible, so the binding constraint is
        # most likely the average-risk ceiling (it depends on the mix, which
        # pre-checks only bound loosely).
        return _infeasible_response(
            event,
            [
                "Solver could not satisfy all constraints — the average-risk "
                "ceiling is the most likely cause given the eligible bids."
            ],
            excluded_quality,
        )

    # Step 4: read the solution and build the response.
    allocations = _extract_allocations(eligible, q_vars, solver)
    total_cost = sum(a.total_cost for a in allocations)
    average_quality = _weighted_average(
        allocations, eligible, attr="quality_score", demand=event.total_demand
    )
    average_risk = _weighted_average(
        allocations, eligible, attr="risk_score", demand=event.total_demand
    )
    explanation = _build_explanation(
        event, allocations, eligible, excluded_quality,
        total_cost, average_quality, average_risk,
    )

    # Persist the aggregate result so /events/{id}/runs can list history later.
    result_row = OptimisationResult(
        event_id=event.id,  # type: ignore[arg-type]
        total_cost=total_cost,
        average_quality=average_quality,
        average_risk=average_risk,
        explanation=explanation,
    )
    session.add(result_row)
    session.commit()
    session.refresh(result_row)

    return OptimisationResponse(
        status="optimal",
        event_id=event.id,  # type: ignore[arg-type]
        result_id=result_row.id,
        allocations=allocations,
        total_cost=round(total_cost, 2),
        average_quality=round(average_quality, 4),
        average_risk=round(average_risk, 4),
        explanation=explanation,
        warnings=[],
    )


# ---------- helpers (private) ----------


def _load_bid_views(session: Session, event_id: int) -> list[_BidView]:
    """Pull bids + their supplier rows in one go and return read-only views."""
    bids = list(session.exec(select(Bid).where(Bid.event_id == event_id)).all())
    views: list[_BidView] = []
    for b in bids:
        supplier = session.get(Supplier, b.supplier_id)
        if supplier is None:  # defensive — FK should prevent this
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
            )
        )
    return views


def _filter_by_quality(
    bids: list[_BidView], min_quality: float
) -> tuple[list[_BidView], list[_BidView]]:
    eligible = [b for b in bids if b.quality_score >= min_quality]
    excluded = [b for b in bids if b.quality_score < min_quality]
    return eligible, excluded


def _pre_check(event: SourcingEvent, eligible: list[_BidView]) -> list[str]:
    """Catch the obvious "this event cannot succeed" cases up-front."""
    warnings: list[str] = []

    if not eligible:
        warnings.append(
            "No bids meet the quality floor "
            f"(min_quality_score={event.min_quality_score})."
        )
        return warnings

    total_capacity = sum(b.capacity for b in eligible)
    if total_capacity < event.total_demand:
        warnings.append(
            f"Total eligible supplier capacity ({total_capacity}) is less than "
            f"the event demand ({event.total_demand})."
        )

    # Best max_suppliers picks alone may still not cover demand.
    top_k_capacity = sum(
        b.capacity for b in sorted(eligible, key=lambda x: -x.capacity)[: event.max_suppliers]
    )
    if top_k_capacity < event.total_demand:
        warnings.append(
            f"With max_suppliers={event.max_suppliers}, the largest "
            f"{event.max_suppliers} eligible bid(s) only cover "
            f"{top_k_capacity} units — short of the {event.total_demand} required."
        )

    # Best-case (lowest-risk) average risk: greedily fill demand using
    # the lowest-risk eligible bids. If even this exceeds the ceiling, the
    # event is infeasible regardless of cost.
    best_risk = _best_case_average_risk(eligible, event.total_demand)
    if best_risk is not None and best_risk > event.max_average_risk + 1e-9:
        warnings.append(
            f"Even using the lowest-risk eligible suppliers, average risk would "
            f"be {best_risk:.3f} — above the ceiling of {event.max_average_risk}."
        )

    return warnings


def _best_case_average_risk(
    eligible: list[_BidView], demand: int
) -> float | None:
    """Greedy lower bound on average risk: fill demand starting from the
    lowest-risk supplier. Returns None if total capacity is below demand."""
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


def _build_model(
    event: SourcingEvent, eligible: list[_BidView]
) -> tuple[cp_model.CpModel, dict[int, cp_model.IntVar], dict[int, cp_model.IntVar]]:
    """Assemble the CP-SAT model. See the module docstring for the maths."""
    model = cp_model.CpModel()

    q_vars: dict[int, cp_model.IntVar] = {}
    y_vars: dict[int, cp_model.IntVar] = {}
    for b in eligible:
        q_vars[b.bid_id] = model.NewIntVar(0, b.capacity, f"q_{b.bid_id}")
        y_vars[b.bid_id] = model.NewBoolVar(f"y_{b.bid_id}")
        # Constraint (3): if y=0 then q must also be 0; if q>0 then y must be 1.
        model.Add(q_vars[b.bid_id] <= b.capacity * y_vars[b.bid_id])

    # Constraint (1): demand is met exactly.
    model.Add(sum(q_vars[b.bid_id] for b in eligible) == event.total_demand)

    # Constraint (4): supplier count cap.
    model.Add(sum(y_vars[b.bid_id] for b in eligible) <= event.max_suppliers)

    # Constraint (6): quantity-weighted average risk.
    risk_scaled = {b.bid_id: round(b.risk_score * RISK_SCALE) for b in eligible}
    max_risk_scaled = round(event.max_average_risk * RISK_SCALE)
    model.Add(
        sum(q_vars[b.bid_id] * risk_scaled[b.bid_id] for b in eligible)
        <= max_risk_scaled * event.total_demand
    )

    # Objective: minimise total cost, in integer cents to stay in CP-SAT's
    # integer world. We divide back out when reporting the answer.
    price_cents = {b.bid_id: round(b.unit_price * PRICE_SCALE) for b in eligible}
    model.Minimize(sum(q_vars[b.bid_id] * price_cents[b.bid_id] for b in eligible))

    return model, q_vars, y_vars


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
    # Sort by unit price ascending — reads naturally in the UI and in tests.
    allocations.sort(key=lambda a: a.unit_price)
    return allocations


def _weighted_average(
    allocations: list[SupplierAllocation],
    eligible: list[_BidView],
    *,
    attr: str,
    demand: int,
) -> float:
    """Quantity-weighted average of ``attr`` across the awarded allocations."""
    if demand <= 0:
        return 0.0
    by_supplier = {b.supplier_id: getattr(b, attr) for b in eligible}
    total = sum(a.awarded_quantity * by_supplier[a.supplier_id] for a in allocations)
    return total / demand


def _build_explanation(
    event: SourcingEvent,
    allocations: list[SupplierAllocation],
    eligible: list[_BidView],
    excluded_quality: list[_BidView],
    total_cost: float,
    average_quality: float,
    average_risk: float,
) -> str:
    """Plain-English summary of why the solver picked this allocation.

    Deliberately rule-based (not LLM-generated): deterministic, free to run,
    and easy to defend in an interview.
    """
    lines: list[str] = []
    lines.append(
        f"Selected {len(allocations)} supplier(s) to cover "
        f"{event.total_demand} units of '{event.name}', minimising total cost "
        f"subject to: max_suppliers={event.max_suppliers}, "
        f"min_quality_score={event.min_quality_score}, "
        f"max_average_risk={event.max_average_risk}."
    )

    cheapest_price = min((b.unit_price for b in eligible), default=None)
    lines.append("")
    lines.append("Allocations (cheapest first):")
    for a in allocations:
        bid = next(b for b in eligible if b.supplier_id == a.supplier_id)
        reason = _allocation_reason(a, bid, cheapest_price)
        lines.append(
            f"  - {a.supplier_name}: {a.awarded_quantity} units @ "
            f"{a.unit_price:.2f} = {a.total_cost:.2f}  ({reason})"
        )

    if excluded_quality:
        names = ", ".join(
            f"{b.supplier_name} (quality {b.quality_score:g})"
            for b in excluded_quality
        )
        lines.append("")
        lines.append(
            f"Excluded by quality floor (min {event.min_quality_score:g}): {names}."
        )

    lines.append("")
    lines.append(
        f"Totals: cost {total_cost:.2f}, "
        f"weighted quality {average_quality:.2f}, "
        f"weighted risk {average_risk:.3f}."
    )
    return "\n".join(lines)


def _allocation_reason(
    allocation: SupplierAllocation,
    bid: _BidView,
    cheapest_price: float | None,
) -> str:
    if cheapest_price is not None and bid.unit_price == cheapest_price:
        if allocation.awarded_quantity == bid.capacity:
            return "lowest unit price, awarded at full capacity"
        return "lowest unit price"
    if allocation.awarded_quantity == bid.capacity:
        return "next-cheapest, capped by capacity"
    return "next-cheapest, fills remaining demand"


def _infeasible_response(
    event: SourcingEvent,
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
            f"{b.supplier_name} (quality {b.quality_score:g})"
            for b in excluded_quality
        )
        explanation_lines.append("")
        explanation_lines.append(
            f"Excluded by quality floor (min {event.min_quality_score:g}): {names}."
        )
    return OptimisationResponse(
        status="infeasible",
        event_id=event.id,  # type: ignore[arg-type]
        result_id=None,
        allocations=[],
        total_cost=0.0,
        average_quality=0.0,
        average_risk=0.0,
        explanation="\n".join(explanation_lines),
        warnings=warnings,
    )
