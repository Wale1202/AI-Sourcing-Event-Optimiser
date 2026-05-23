"""End-to-end tests for POST /events/{id}/optimise.

Each test builds a small, hand-solvable scenario so the expected output is
checkable by eye — that way the suite doubles as a spec for the model.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


# ---------- scenario helpers ----------


def _make_event(client: TestClient, **overrides) -> int:
    """Create an event with permissive defaults and return its id."""
    payload = {
        "name": "Test Event",
        "category": "IT Hardware",
        "total_demand": 100,
        "max_suppliers": 10,
        "min_quality_score": 0.0,
        "max_average_risk": 1.0,
        **overrides,
    }
    response = client.post("/api/v1/events", json=payload)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _make_supplier(client: TestClient, name: str, **overrides) -> int:
    payload = {
        "name": name,
        "country": "Ireland",
        "risk_score": 0.2,
        "sustainability_score": 80.0,
        **overrides,
    }
    response = client.post("/api/v1/suppliers", json=payload)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _make_bid(
    client: TestClient, event_id: int, supplier_id: int,
    unit_price: float, capacity: int,
    quality_score: float = 80.0, lead_time_days: int = 14,
) -> None:
    response = client.post(
        "/api/v1/bids",
        json={
            "event_id": event_id,
            "supplier_id": supplier_id,
            "unit_price": unit_price,
            "capacity": capacity,
            "lead_time_days": lead_time_days,
            "quality_score": quality_score,
        },
    )
    assert response.status_code == 201, response.text


# ---------- 1. normal successful optimisation ----------


def test_optimise_basic_minimises_cost(client: TestClient) -> None:
    """Three suppliers, no binding side-constraints. Optimal allocation is:
    60 units from A (€10) + 40 units from B (€20) = €1400. Supplier C (€30)
    is more expensive and should not appear."""
    event_id = _make_event(client, total_demand=100)
    a = _make_supplier(client, "Acme")
    b = _make_supplier(client, "Globex")
    c = _make_supplier(client, "Initech")
    _make_bid(client, event_id, a, unit_price=10.0, capacity=60)
    _make_bid(client, event_id, b, unit_price=20.0, capacity=80)
    _make_bid(client, event_id, c, unit_price=30.0, capacity=50)

    response = client.post(f"/api/v1/events/{event_id}/optimise")
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["status"] == "optimal"
    assert body["warnings"] == []
    assert body["total_cost"] == 1400.0

    by_name = {alloc["supplier_name"]: alloc for alloc in body["allocations"]}
    assert set(by_name) == {"Acme", "Globex"}
    assert by_name["Acme"]["awarded_quantity"] == 60
    assert by_name["Acme"]["total_cost"] == 600.0
    assert by_name["Globex"]["awarded_quantity"] == 40
    assert by_name["Globex"]["total_cost"] == 800.0
    assert body["result_id"] is not None


# ---------- 2. impossible: total capacity is below demand ----------


def test_optimise_infeasible_when_capacity_too_low(client: TestClient) -> None:
    """Demand 1000, total supplier capacity 500 → infeasible, with a warning
    that names the shortfall."""
    event_id = _make_event(client, total_demand=1000)
    a = _make_supplier(client, "Acme")
    b = _make_supplier(client, "Globex")
    _make_bid(client, event_id, a, unit_price=10.0, capacity=300)
    _make_bid(client, event_id, b, unit_price=20.0, capacity=200)

    response = client.post(f"/api/v1/events/{event_id}/optimise")
    assert response.status_code == 200
    body = response.json()

    assert body["status"] == "infeasible"
    assert body["allocations"] == []
    assert body["total_cost"] == 0.0
    assert any("capacity" in w.lower() for w in body["warnings"])
    assert "1000" in " ".join(body["warnings"])  # references the demand


# ---------- 3. quality constraint excludes some suppliers ----------


def test_optimise_quality_floor_excludes_supplier(client: TestClient) -> None:
    """A is cheap but below the quality floor; B is more expensive but eligible.
    The result must use B for all 100 units even though A is cheaper."""
    event_id = _make_event(client, total_demand=100, min_quality_score=80.0)
    a = _make_supplier(client, "CheapButLowQuality")
    b = _make_supplier(client, "PricierButPasses")
    _make_bid(client, event_id, a, unit_price=5.0, capacity=200, quality_score=70.0)
    _make_bid(client, event_id, b, unit_price=10.0, capacity=200, quality_score=85.0)

    response = client.post(f"/api/v1/events/{event_id}/optimise")
    assert response.status_code == 200
    body = response.json()

    assert body["status"] == "optimal"
    assert len(body["allocations"]) == 1
    assert body["allocations"][0]["supplier_name"] == "PricierButPasses"
    assert body["allocations"][0]["awarded_quantity"] == 100
    assert body["total_cost"] == 1000.0
    # The explanation should mention the excluded supplier by name.
    assert "CheapButLowQuality" in body["explanation"]


# ---------- 4. max_suppliers changes the result ----------


def test_optimise_max_suppliers_binds_and_costs_more(client: TestClient) -> None:
    """Same bid table, two runs differing only in max_suppliers:
       - max_suppliers=3 lets the solver mix A (cheapest, cap 80) + C (€15, cap 50)
         for total cost  80*10 + 20*15 = 1100.
       - max_suppliers=1 forces a single supplier with capacity ≥ demand.
         Only B (€50, cap 100) fits, costing 5000.
    The single-supplier run must be strictly more expensive."""
    # Suppliers shared across both events.
    a = _make_supplier(client, "Acme")
    b = _make_supplier(client, "Globex")
    c = _make_supplier(client, "Initech")

    def _build_event(max_suppliers: int) -> int:
        event_id = _make_event(
            client, total_demand=100, max_suppliers=max_suppliers,
            name=f"event-max-{max_suppliers}",
        )
        _make_bid(client, event_id, a, unit_price=10.0, capacity=80)
        _make_bid(client, event_id, b, unit_price=50.0, capacity=100)
        _make_bid(client, event_id, c, unit_price=15.0, capacity=50)
        return event_id

    open_event = _build_event(max_suppliers=3)
    locked_event = _build_event(max_suppliers=1)

    open_body = client.post(f"/api/v1/events/{open_event}/optimise").json()
    locked_body = client.post(f"/api/v1/events/{locked_event}/optimise").json()

    assert open_body["status"] == "optimal"
    assert locked_body["status"] == "optimal"
    assert open_body["total_cost"] == 1100.0
    assert locked_body["total_cost"] == 5000.0
    # The tight run is strictly more expensive and uses exactly one supplier.
    assert locked_body["total_cost"] > open_body["total_cost"]
    assert len(locked_body["allocations"]) == 1
    assert locked_body["allocations"][0]["supplier_name"] == "Globex"
